"""Deterministic synthetic AP dataset: vendors, purchase orders, goods receipts, invoices.

Each vendor has a *quirk* — a recurring exception pattern a real AP desk
eventually learns. The `truth` field on each invoice is what an experienced
AP lead decides; the UI's "AP lead" panel and the replay script use it to
play the human reviewer. The agent never reads `truth`.

Run:  python -m ledgerwise.data_gen   (writes data/*.json)
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
START = date(2026, 8, 3)  # a Monday
WEEKS = 8

VENDORS = [
    {"id": "V-101", "name": "Tata Steel Distributors Pvt Ltd", "gstin": "27AABCT1332L1ZQ",
     "category": "Raw material", "terms": "Net 45", "bank": "HDFC ••4471",
     "quirk": "Steel-index clause: unit price drifts 1.5–4.5% above PO each month."},
    {"id": "V-102", "name": "Sharma Logistics LLP", "gstin": "07AAKFS8812M1Z2",
     "category": "Freight", "terms": "Net 15", "bank": "ICICI ••0921",
     "quirk": "Adds an unbudgeted fuel surcharge line; small ones are accepted, big ones are not."},
    {"id": "V-103", "name": "Nilgiri Packaging Industries", "gstin": "33AAHFN4410P1Z8",
     "category": "Packaging", "terms": "Net 30", "bank": "Axis ••7713",
     "quirk": "Bills the full PO quantity even when the truck arrives short."},
    {"id": "V-104", "name": "Kaveri Specialty Chemicals", "gstin": "29AAGCK9021Q1Z5",
     "category": "Chemicals", "terms": "Net 30", "bank": "SBI ••3380",
     "quirk": "Invoices at 18% GST on an HSN line contracted at 12%."},
    {"id": "V-105", "name": "Apex Office Supplies", "gstin": "36AAPFA2231C1Z1",
     "category": "Office", "terms": "Net 30", "bank": "Kotak ••5562",
     "quirk": "Re-sends unpaid invoices with an '-R' suffix after ~3 weeks."},
    {"id": "V-106", "name": "Meridian Electricals", "gstin": "36AAMFM7710D1Z9",
     "category": "Electrical", "terms": "Net 30", "bank": "HDFC ••2290",
     "quirk": "Clean vendor — until a 'new bank account' letter arrives."},
]

ITEMS = {
    "V-101": [("HR Coil 2.0mm IS2062", "7208", 61500.0, "MT", 12, 18)],
    "V-102": [("FTL Hyderabad→Pune 32ft", "9965", 48000.0, "Trip", 1, 12)],
    "V-103": [("5-ply corrugated box 18x12x10", "4819", 38.5, "Nos", 4000, 18)],
    "V-104": [("Sodium silicate (liquid) 50kg", "2839", 2150.0, "Drum", 40, 12)],
    "V-105": [("A4 copier paper 75gsm", "4802", 245.0, "Ream", 200, 12)],
    "V-106": [("LED panel 2x2 36W", "9405", 1180.0, "Nos", 60, 18)],
}


def _d(week: int, day: int) -> str:
    return (START + timedelta(weeks=week, days=day)).isoformat()


def generate(seed: int = 7) -> dict:
    rng = random.Random(seed)
    pos, grns, invoices = [], [], []
    seq = 1000

    def add(vendor_id, week, day, *, price_mult=1.0, qty_recv=None, gst_inv=None,
            surcharge=0.0, inv_no=None, bank=None, truth=None, note="", po_override=None):
        nonlocal seq
        seq += 1
        desc, hsn, price, unit, qty, gst = ITEMS[vendor_id][0]
        qty = qty if vendor_id != "V-101" else rng.choice([10, 12, 15])
        po_id = po_override or f"PO-26-{seq}"
        if not po_override:
            pos.append({"id": po_id, "vendor_id": vendor_id, "date": _d(week, 0) if week else _d(0, 0),
                        "lines": [{"desc": desc, "hsn": hsn, "qty": qty, "unit": unit,
                                   "price": price, "gst_pct": gst}]})
            grns.append({"id": f"GRN-{seq}", "po_id": po_id, "date": _d(week, day),
                         "qty_received": qty if qty_recv is None else qty_recv})
        lines = [{"desc": desc, "hsn": hsn, "qty": qty, "unit": unit,
                  "price": round(price * price_mult, 2),
                  "gst_pct": gst if gst_inv is None else gst_inv}]
        if surcharge:
            lines.append({"desc": "Fuel surcharge", "hsn": "9965", "qty": 1, "unit": "Lot",
                          "price": surcharge, "gst_pct": 12})
        invoices.append({
            "id": inv_no or f"{vendor_id[-3:]}/{seq}",
            "vendor_id": vendor_id, "po_id": po_id, "date": _d(week, day),
            "week": week + 1, "lines": lines,
            "bank": bank or next(v["bank"] for v in VENDORS if v["id"] == vendor_id),
            "note": note, "truth": truth,
        })
        return invoices[-1]

    for w in range(WEEKS):
        # V-101 steel index drift: always approved (clause 7.2) while <= 5%
        pct = rng.choice([1.6, 2.2, 2.8, 3.1, 3.7, 4.2])
        add("V-101", w, 1, price_mult=1 + pct / 100,
            truth={"decision": "APPROVE", "reason": "Contract clause 7.2 allows monthly steel-index price adjustment up to 5%; index sheet attached."})
        # V-102 surcharge: <= 2500 approve, above reject
        sur = rng.choice([1200, 1650, 2100, 2400]) if w != 5 else 6800
        add("V-102", w, 2, surcharge=sur,
            truth={"decision": "APPROVE" if sur <= 2500 else "REJECT",
                   "reason": ("Fuel surcharge up to ₹2,500/trip is pre-agreed with Sharma Logistics (email from Ops, Jun-26)."
                              if sur <= 2500 else "Surcharge above the ₹2,500 cap agreed with Ops — reject, ask vendor to reissue.")})
        # V-103 short shipment every other week
        if w % 2 == 0:
            add("V-103", w, 3, qty_recv=rng.choice([3600, 3750, 3820]),
                truth={"decision": "PARTIAL", "reason": "Pay only the GRN quantity; Nilgiri always bills full PO qty on short trucks. Debit note for the balance."})
        else:
            add("V-103", w, 3, truth={"decision": "APPROVE", "reason": "Clean 3-way match."})
        # V-104 GST mismatch every week
        add("V-104", w, 2, gst_inv=18,
            truth={"decision": "REJECT", "reason": "HSN 2839 is contracted at 12% GST; ask Kaveri for a credit note / revised invoice. Never pay the 18% version."})
        # V-105 normal invoice; resend with -R three weeks later
        if w < 5:
            inv = add("V-105", w, 4, truth={"decision": "APPROVE", "reason": "Clean 3-way match."})
            if w in (0, 1, 2):
                add("V-105", w + 3, 0, inv_no=inv["id"] + "-R", po_override=inv["po_id"],
                    truth={"decision": "HOLD_DUPLICATE", "reason": "Apex re-sends unpaid invoices with '-R'; original already in the payment run."})
        # V-106 clean, bank change in week 6
        if w == 5:
            add("V-106", w, 1, bank="Yes Bank ••8812",
                note="Cover letter: 'We have moved our banking to Yes Bank, please update.'",
                truth={"decision": "ESCALATE", "reason": "Bank change verified by call-back to known number before any payment."})
        else:
            add("V-106", w, 1, truth={"decision": "APPROVE", "reason": "Clean 3-way match."})

    invoices.sort(key=lambda i: (i["date"], i["id"]))
    return {"vendors": VENDORS, "pos": pos, "grns": grns, "invoices": invoices}


def write(out: Path = DATA_DIR) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    data = generate()
    for key, rows in data.items():
        (out / f"{key}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


if __name__ == "__main__":
    d = write()
    print(f"wrote {len(d['invoices'])} invoices, {len(d['pos'])} POs to {DATA_DIR}")
