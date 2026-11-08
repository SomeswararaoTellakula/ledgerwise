"""The AP exception agent.

For every exception the matcher finds, the agent:
  1. RECALLS how this vendor's similar exceptions were resolved before (Hindsight),
  2. applies a conservative precedent policy to propose a decision,
  3. auto-resolves only when human precedent is consistent, otherwise escalates
     with the precedents attached,
and every human decision is RETAINED so the next invoice is easier.

Guardrails that memory can never override:
  * a bank-account change is always escalated for a call-back check;
  * only human decisions count as precedent — the agent never learns from itself;
  * a magnitude above anything a human has approved is escalated, not extrapolated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import llm
from .matching import Exception_, three_way_match, invoice_total
from .memory import MemoryBase, Precedent, parse_precedents, precedent_text

MAGNITUDE_TYPES = {"PRICE_VARIANCE", "UNPO_CHARGE"}
NEVER_AUTO = {"BANK_CHANGE", "NO_PO"}
MIN_PRECEDENTS = 2
MAGNITUDE_HEADROOM = 1.10  # allow 10% above the largest human-approved magnitude
SEVERITY = ["APPROVE", "PARTIAL", "HOLD_DUPLICATE", "REJECT", "ESCALATE"]


def _seq(invoice_id: str) -> int:
    nums = re.findall(r"\d+", invoice_id)
    return int(nums[-1]) if nums else 0


@dataclass
class ExceptionDecision:
    exception: dict
    decision: str          # proposed outcome
    auto: bool
    rule: str              # one-line reason the policy fired
    precedents: list = field(default_factory=list)


class APAgent:
    def __init__(self, memory: MemoryBase, data: dict, memory_enabled: bool = True,
                 reviewer: str = "Priya Nair (AP lead)"):
        self.memory = memory
        self.memory_enabled = memory_enabled
        self.reviewer = reviewer
        self.vendors = {v["id"]: v for v in data["vendors"]}
        self.pos = {p["id"]: p for p in data["pos"]}
        self.grns = {g["po_id"]: g for g in data["grns"]}
        self.seen: list[dict] = []
        self.recall_log: list[dict] = []

    # ---------- memory ----------
    def recall_precedents(self, vendor: dict, exc: Exception_) -> list[Precedent]:
        if not self.memory_enabled:
            return []
        query = (f"How were {exc.type.replace('_', ' ').lower()} exceptions on invoices from "
                 f"{vendor['name']} resolved, and why?")
        texts = self.memory.recall(query)
        precs = [p for p in parse_precedents(texts)
                 if p.vendor_id == vendor["id"] and p.type == exc.type]
        precs.sort(key=lambda p: _seq(p.invoice))
        self.recall_log.append({"query": query, "hits": len(texts), "precedents": len(precs)})
        return precs

    def retain_decision(self, invoice: dict, exc: dict, decision: str, reason: str, decided_by: str):
        vendor = self.vendors[invoice["vendor_id"]]
        self.memory.retain(
            precedent_text(vendor, exc["type"], exc["magnitude"], decision, invoice["id"], decided_by, reason),
            context=f"accounts payable exception resolution — {vendor['category'].lower()} vendor",
            document_id=f"{invoice['id']}:{exc['type']}",
            metadata={"vendor_id": vendor["id"], "exception": exc["type"], "decision": decision,
                      "decided_by": decided_by},
            timestamp=invoice["date"],
        )

    def vendor_brief(self, vendor_id: str) -> str:
        v = self.vendors[vendor_id]
        return self.memory.reflect(
            f"What should an AP clerk know about {v['name']} before approving their next invoice? "
            f"List recurring exceptions, how they were resolved, limits that were enforced, and red flags.",
            context="vendor brief before payment run")

    # ---------- policy ----------
    def _decide_exception(self, vendor: dict, exc: Exception_) -> ExceptionDecision:
        if exc.type in NEVER_AUTO:
            precs = self.recall_precedents(vendor, exc)
            return ExceptionDecision(exc.to_dict(), "ESCALATE", False,
                                     "Guardrail: bank/PO changes always need a human call-back check.",
                                     [p.to_dict() for p in precs])

        precs = [p for p in self.recall_precedents(vendor, exc) if p.is_human]
        cited = [p.to_dict() for p in precs[-5:]]
        if len(precs) < MIN_PRECEDENTS:
            return ExceptionDecision(exc.to_dict(), "ESCALATE", False,
                                     f"Only {len(precs)} human precedent(s) for this vendor + exception.", cited)

        if exc.type in MAGNITUDE_TYPES:
            approved = [p.magnitude for p in precs if p.decision == "APPROVE"]
            rejected = [p.magnitude for p in precs if p.decision == "REJECT"]
            cap = max(approved) * MAGNITUDE_HEADROOM if approved else None
            floor = min(rejected) if rejected else None
            if len(approved) >= MIN_PRECEDENTS and exc.magnitude <= cap and (floor is None or exc.magnitude < floor):
                return ExceptionDecision(exc.to_dict(), "APPROVE", True,
                                         f"{len(approved)} human approvals up to {max(approved):g}; this is {exc.magnitude:g}.", cited)
            if len(rejected) >= MIN_PRECEDENTS and exc.magnitude >= floor and (cap is None or exc.magnitude > cap):
                return ExceptionDecision(exc.to_dict(), "REJECT", True,
                                         f"{len(rejected)} human rejections at or below {floor:g}; this is {exc.magnitude:g}.", cited)
            if approved and exc.magnitude <= max(approved) * 1.5 and (floor is None or exc.magnitude < floor):
                suggestion = "APPROVE (close to past approvals)"
            elif approved or rejected:
                suggestion = "REJECT (far from anything approved)"
            else:
                suggestion = "no view"
            limit = f"largest approved {max(approved):g}" if approved else "no approvals yet"
            return ExceptionDecision(exc.to_dict(), "ESCALATE", False,
                                     f"Outside learned range ({limit}); this is {exc.magnitude:g}. Leaning {suggestion}.", cited)

        recent = precs[-3:]
        outcomes = {p.decision for p in recent}
        if len(outcomes) == 1:
            outcome = outcomes.pop()
            return ExceptionDecision(exc.to_dict(), outcome, True,
                                     f"Last {len(recent)} human decisions on this were all {outcome}.", cited)
        return ExceptionDecision(exc.to_dict(), "ESCALATE", False,
                                 f"Humans disagreed recently ({', '.join(sorted(outcomes))}).", cited)

    def process(self, invoice: dict) -> dict:
        vendor = self.vendors[invoice["vendor_id"]]
        po = self.pos.get(invoice["po_id"])
        grn = self.grns.get(invoice["po_id"])
        excs = three_way_match(invoice, po, grn, vendor, self.seen)
        self.seen.append(invoice)

        if not excs:
            return {"invoice_id": invoice["id"], "vendor": vendor["name"], "vendor_id": vendor["id"],
                    "total": invoice_total(invoice), "exceptions": [], "decision": "APPROVE",
                    "auto": True, "straight_through": True,
                    "explanation": "Clean 3-way match — PO, GRN and invoice agree."}

        # A duplicate is decided on its own: no point price-checking a re-send.
        dup = [e for e in excs if e.type == "DUPLICATE"]
        decisions = [self._decide_exception(vendor, e) for e in (dup or excs)]

        auto = all(d.auto for d in decisions)
        overall = max((d.decision for d in decisions), key=SEVERITY.index)
        cited = [p for d in decisions for p in d.precedents]
        result = {
            "invoice_id": invoice["id"], "vendor": vendor["name"], "vendor_id": vendor["id"],
            "total": invoice_total(invoice), "straight_through": False,
            "exceptions": [d.__dict__ for d in decisions],
            "decision": overall if auto else "ESCALATE", "auto": auto,
            "suggested": None if auto else self._lean(decisions),
        }
        if any(e.type in NEVER_AUTO for e in excs):
            result["explanation"] = ("Held for a call-back to the vendor's number on file. A changed remit-to account "
                                     "is the classic invoice-fraud pattern, so no amount of history lets me pay this alone.")
        else:
            result["explanation"] = llm.explain(result["decision"], "; ".join(e.summary for e in excs), cited)
        if auto and overall in ("REJECT", "PARTIAL"):
            issue = "; ".join(d.exception["summary"] for d in decisions)
            ask = ("Please send a credit note or a revised invoice." if overall == "REJECT"
                   else "We will pay for the quantity received and raise a debit note for the balance.")
            result["vendor_email"] = llm.vendor_email(vendor, invoice["id"], issue, ask)
        return result

    @staticmethod
    def _lean(decisions: list[ExceptionDecision]) -> str | None:
        """What memory hints at, for the reviewer — never acted on automatically."""
        leans = []
        for d in decisions:
            if d.exception["type"] in NEVER_AUTO:
                leans.append("ESCALATE")
            elif "Leaning REJECT" in d.rule:
                leans.append("REJECT")
            elif "Leaning APPROVE" in d.rule:
                leans.append("APPROVE")
            else:
                human = [p for p in d.precedents if p["is_human"]]
                if human:
                    leans.append(human[-1]["decision"])
        return max(leans, key=SEVERITY.index) if leans else None

    def record_human(self, invoice: dict, result: dict, decision: str, reason: str):
        for d in result["exceptions"]:
            self.retain_decision(invoice, d["exception"], decision, reason, self.reviewer)

    def record_auto(self, invoice: dict, result: dict):
        for d in result["exceptions"]:
            self.retain_decision(invoice, d["exception"], d["decision"],
                                 d["rule"], "Ledgerwise agent (auto)")


def score(result: dict, truth: dict | None) -> str:
    """correct | wrong | escalated — how an auto decision compares to the AP lead's."""
    if not result["auto"]:
        return "correct" if truth and truth["decision"] == "ESCALATE" else "escalated"
    return "correct" if truth and truth["decision"] == result["decision"] else "wrong"
