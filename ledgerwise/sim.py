"""Replays the invoice stream through the agent, week by week.

Used by the web app and by scripts/replay.py. The `truth` on each invoice plays
the AP lead: when the agent escalates, the lead's decision and reason are what
get retained into memory.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .agent import APAgent, score
from .memory import MemoryBase

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_data(path: Path = DATA_DIR) -> dict:
    if not (path / "invoices.json").exists():
        from .data_gen import write
        write(path)
    return {k: json.loads((path / f"{k}.json").read_text(encoding="utf-8"))
            for k in ("vendors", "pos", "grns", "invoices")}


class Simulation:
    def __init__(self, memory: MemoryBase, memory_enabled: bool = True, data: dict | None = None):
        self.data = data or load_data()
        self.memory = memory
        self.memory_enabled = memory_enabled
        self.invoices = self.data["invoices"]
        self.agent = APAgent(memory, self.data, memory_enabled)
        self.cursor = 0
        self.results: list[dict] = []
        self.pending: dict[str, dict] = {}

    def reset(self, memory_enabled: bool = True):
        self.memory.reset()
        self.__init__(self.memory, memory_enabled, self.data)

    @property
    def done(self) -> bool:
        return self.cursor >= len(self.invoices)

    def invoice(self, invoice_id: str) -> dict:
        return next(i for i in self.invoices if i["id"] == invoice_id)

    def step(self) -> dict | None:
        if self.done or self.pending:
            return None
        inv = self.invoices[self.cursor]
        self.cursor += 1
        res = self.agent.process(inv)
        res.update(week=inv["week"], date=inv["date"], note=inv.get("note", ""),
                   lines=inv["lines"], bank=inv["bank"])
        res["outcome"] = score(res, inv["truth"])
        if res["exceptions"] and res["auto"]:
            self.agent.record_auto(inv, res)
        if not res["auto"]:
            res["status"] = "awaiting_review"
            res["reviewer_hint"] = inv["truth"]
            self.pending[inv["id"]] = res
        else:
            res["status"] = "auto_resolved" if res["exceptions"] else "straight_through"
        self.results.append(res)
        return res

    def decide(self, invoice_id: str, decision: str, reason: str) -> dict:
        res = self.pending.pop(invoice_id)
        self.agent.record_human(self.invoice(invoice_id), res, decision, reason)
        res.update(status="human_resolved", human_decision=decision, human_reason=reason)
        return res

    def lead_decides(self, invoice_id: str) -> dict:
        t = self.invoice(invoice_id)["truth"]
        return self.decide(invoice_id, t["decision"], t["reason"])

    def run(self, until_week: int | None = None) -> int:
        """Fast-forward; the AP lead answers every escalation from their notes."""
        n = 0
        while not self.done:
            if until_week and self.invoices[self.cursor]["week"] > until_week:
                break
            for pid in list(self.pending):
                self.lead_decides(pid)
            if self.step():
                n += 1
        for pid in list(self.pending):
            self.lead_decides(pid)
        return n

    def stats(self) -> dict:
        weeks = defaultdict(lambda: {"invoices": 0, "exceptions": 0, "auto": 0, "correct": 0,
                                     "wrong": 0, "escalated": 0, "human_touches": 0})
        for r in self.results:
            w = weeks[r["week"]]
            w["invoices"] += 1
            if not r["exceptions"]:
                continue
            w["exceptions"] += 1
            w["auto"] += r["auto"]
            w[r["outcome"]] += 1
            w["human_touches"] += not r["auto"]
        rows = []
        for k in sorted(weeks):
            w = weeks[k]
            w["week"] = k
            w["auto_rate"] = round(100 * w["auto"] / w["exceptions"], 1) if w["exceptions"] else 0.0
            rows.append(w)
        exc = sum(w["exceptions"] for w in rows)
        auto = sum(w["auto"] for w in rows)
        wrong = sum(w["wrong"] for w in rows)
        return {"weeks": rows, "total_exceptions": exc, "total_auto": auto, "total_wrong": wrong,
                "auto_rate": round(100 * auto / exc, 1) if exc else 0.0,
                "processed": self.cursor, "total": len(self.invoices)}
