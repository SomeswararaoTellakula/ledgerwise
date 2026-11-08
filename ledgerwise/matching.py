"""Deterministic 3-way match: invoice vs purchase order vs goods receipt.

This layer has no memory and no LLM. It only *detects* exceptions and measures
them. Deciding what to do about an exception is the agent's job (agent.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

PRICE_TOLERANCE_PCT = 0.5  # rounding noise allowed without raising an exception


@dataclass
class Exception_:
    type: str            # PRICE_VARIANCE | UNPO_CHARGE | QTY_SHORT | TAX_MISMATCH | DUPLICATE | BANK_CHANGE | NO_PO
    summary: str
    magnitude: float     # % for price, ₹ for charges, units for qty, pct-points for tax
    amount_at_risk: float
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def invoice_total(inv: dict) -> float:
    return round(sum(l["qty"] * l["price"] * (1 + l["gst_pct"] / 100) for l in inv["lines"]), 2)


def three_way_match(inv: dict, po: dict | None, grn: dict | None, vendor: dict,
                    seen_invoices: list[dict]) -> list[Exception_]:
    out: list[Exception_] = []

    if po is None:
        return [Exception_("NO_PO", "Invoice references an unknown PO", 0, invoice_total(inv))]

    po_line = po["lines"][0]
    inv_line = inv["lines"][0]

    # Duplicate: same vendor, same PO, invoice number differs only by suffix
    base = inv["id"].split("-R")[0]
    for prev in seen_invoices:
        if prev["vendor_id"] == inv["vendor_id"] and prev["id"] != inv["id"] and (
            prev["id"] == base or prev["po_id"] == inv["po_id"]
        ):
            out.append(Exception_(
                "DUPLICATE", f"Looks like a re-send of {prev['id']} (same PO {inv['po_id']})",
                0, invoice_total(inv), {"original": prev["id"], "suffix": inv["id"][len(base):] or None}))
            break

    # Bank account differs from vendor master
    if inv.get("bank") and inv["bank"] != vendor["bank"]:
        out.append(Exception_(
            "BANK_CHANGE", f"Remit-to account changed: {vendor['bank']} → {inv['bank']}",
            0, invoice_total(inv), {"master": vendor["bank"], "invoice": inv["bank"]}))

    # Unit price variance
    pct = (inv_line["price"] - po_line["price"]) / po_line["price"] * 100
    if abs(pct) > PRICE_TOLERANCE_PCT:
        delta = (inv_line["price"] - po_line["price"]) * inv_line["qty"]
        out.append(Exception_(
            "PRICE_VARIANCE", f"Unit price ₹{inv_line['price']:,} vs PO ₹{po_line['price']:,} ({pct:+.1f}%)",
            round(pct, 2), round(delta, 2), {"po_price": po_line["price"], "inv_price": inv_line["price"]}))

    # Quantity billed vs received
    if grn and inv_line["qty"] > grn["qty_received"]:
        short = inv_line["qty"] - grn["qty_received"]
        out.append(Exception_(
            "QTY_SHORT", f"Billed {inv_line['qty']:,} {inv_line['unit']} but GRN shows {grn['qty_received']:,}",
            short, round(short * inv_line["price"] * (1 + inv_line["gst_pct"] / 100), 2),
            {"billed": inv_line["qty"], "received": grn["qty_received"]}))

    # GST rate vs PO
    if inv_line["gst_pct"] != po_line["gst_pct"]:
        diff = inv_line["gst_pct"] - po_line["gst_pct"]
        out.append(Exception_(
            "TAX_MISMATCH", f"GST {inv_line['gst_pct']}% on HSN {inv_line['hsn']} vs PO {po_line['gst_pct']}%",
            diff, round(inv_line["qty"] * inv_line["price"] * diff / 100, 2),
            {"hsn": inv_line["hsn"], "po_gst": po_line["gst_pct"], "inv_gst": inv_line["gst_pct"]}))

    # Extra lines not on the PO
    for extra in inv["lines"][1:]:
        amt = extra["qty"] * extra["price"]
        out.append(Exception_(
            "UNPO_CHARGE", f"Line not on PO: {extra['desc']} ₹{amt:,.0f}", round(amt, 2),
            round(amt * (1 + extra["gst_pct"] / 100), 2), {"desc": extra["desc"]}))

    return out
