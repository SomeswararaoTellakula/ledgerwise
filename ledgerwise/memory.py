"""Memory layer.

`HindsightMemory` is the real backend: every human AP decision is *retained* as an
experience in a Hindsight memory bank, the agent *recalls* precedents before it
touches a new exception, and *reflect* produces a vendor brief from everything
the desk has learned.

`LocalMemory` is a tiny keyword store with the same interface. It exists so the
unit tests and an offline smoke run work without network access. The product
runs on Hindsight (set HINDSIGHT_URL); the UI shows which backend is live.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

PRECEDENT_RE = re.compile(
    r"AP precedent \| vendor: (?P<vendor>.+?) \((?P<vendor_id>V-\d+)\) \| exception: (?P<type>[A-Z_]+)"
    r" \| magnitude: (?P<magnitude>-?[\d.]+) \| decision: (?P<decision>[A-Z_]+)"
    r" \| invoice: (?P<invoice>\S+) \| decided_by: (?P<decided_by>[^|]+?) \| reason: (?P<reason>[^\n]+)"
)


@dataclass
class Precedent:
    vendor_id: str
    vendor: str
    type: str
    magnitude: float
    decision: str
    invoice: str
    decided_by: str
    reason: str

    @property
    def is_human(self) -> bool:
        return not self.decided_by.lower().startswith("ledgerwise")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_human"] = self.is_human
        return d


def precedent_text(vendor: dict, exc_type: str, magnitude: float, decision: str,
                   invoice_id: str, decided_by: str, reason: str) -> str:
    """One memory = one sentence a human could read + a machine-parseable line.

    Hindsight extracts facts from the prose; the structured line survives in the
    source chunk, which we request with include_chunks=True.
    """
    prose = (f"On invoice {invoice_id}, {vendor['name']} had a {exc_type.replace('_', ' ').lower()} "
             f"exception (magnitude {magnitude:g}). {decided_by} decided {decision}: {reason}")
    line = (f"AP precedent | vendor: {vendor['name']} ({vendor['id']}) | exception: {exc_type} | "
            f"magnitude: {magnitude:g} | decision: {decision} | invoice: {invoice_id} | "
            f"decided_by: {decided_by} | reason: {reason}")
    return prose + "\n" + line


def parse_precedents(texts: list[str]) -> list[Precedent]:
    seen, out = set(), []
    for t in texts:
        for m in PRECEDENT_RE.finditer(t or ""):
            key = (m["invoice"], m["type"], m["decided_by"].strip())
            if key in seen:
                continue
            seen.add(key)
            out.append(Precedent(
                vendor_id=m["vendor_id"], vendor=m["vendor"], type=m["type"],
                magnitude=float(m["magnitude"]), decision=m["decision"], invoice=m["invoice"],
                decided_by=m["decided_by"].strip(), reason=m["reason"].strip()))
    return out


class MemoryBase:
    backend = "base"

    def retain(self, content: str, *, context: str, document_id: str,
               metadata: dict, timestamp: str | None = None) -> None: ...

    def recall(self, query: str) -> list[str]: ...

    def reflect(self, query: str, context: str = "") -> str: ...

    def reset(self) -> None: ...

    def info(self) -> dict:
        return {"backend": self.backend}


class HindsightMemory(MemoryBase):
    backend = "hindsight"

    MISSION = ("You are the institutional memory of an accounts-payable desk. Track how each vendor's "
               "invoice exceptions were resolved, who decided, and why. Prefer precise amounts, "
               "percentages, contract clauses and dates.")

    def __init__(self, base_url: str, api_key: str | None = None, bank_prefix: str = "ledgerwise-ap"):
        from hindsight_client import Hindsight  # pip install hindsight-client

        kwargs = {"base_url": base_url, "timeout": 60.0}
        if api_key:
            kwargs["api_key"] = api_key
        self.client = Hindsight(**kwargs)
        self.bank_prefix = bank_prefix
        self.bank_id = os.getenv("HINDSIGHT_BANK_ID") or f"{bank_prefix}-{uuid.uuid4().hex[:6]}"
        self._ensure_bank()

    def _ensure_bank(self) -> None:
        try:
            self.client.create_bank(
                bank_id=self.bank_id, name="Ledgerwise AP desk", mission=self.MISSION,
                # Skeptical + literal: an AP desk should not "generalise" a one-off approval.
                disposition={"skepticism": 5, "literalism": 4, "empathy": 2},
            )
        except Exception:
            pass  # bank already exists

    def retain(self, content, *, context, document_id, metadata, timestamp=None):
        kwargs = dict(bank_id=self.bank_id, content=content, context=context,
                      document_id=document_id, metadata={k: str(v) for k, v in metadata.items()},
                      retain_async=False)
        if timestamp:
            kwargs["timestamp"] = datetime.fromisoformat(timestamp)
        self.client.retain(**kwargs)

    def recall(self, query):
        resp = self.client.recall(bank_id=self.bank_id, query=query,
                                  types=["world", "experience", "observation"],
                                  budget="mid", max_tokens=4096,
                                  include_chunks=True, max_chunk_tokens=600)
        texts = []
        chunks = getattr(resp, "chunks", None) or {}
        for r in resp.results:
            texts.append(r.text)
            cid = getattr(r, "chunk_id", None)
            chunk = chunks.get(cid) if cid else None
            if chunk is not None:
                texts.append(getattr(chunk, "text", str(chunk)))
        return texts

    def reflect(self, query, context=""):
        return self.client.reflect(bank_id=self.bank_id, query=query, budget="low",
                                   context=context or "accounts payable review").text

    def reset(self):
        # Fresh bank per demo run keeps the learning curve honest and reproducible.
        self.bank_id = f"{self.bank_prefix}-{uuid.uuid4().hex[:6]}"
        self._ensure_bank()

    def info(self):
        return {"backend": self.backend, "bank_id": self.bank_id}


class LocalMemory(MemoryBase):
    """Offline stand-in used by tests. Keyword overlap, no extraction, no reflection model."""

    backend = "local"

    def __init__(self, path: Path | None = None):
        self.path = path
        self.records: list[dict] = []
        if path and path.exists():
            self.records = json.loads(path.read_text(encoding="utf-8"))

    def _save(self):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.records, indent=1), encoding="utf-8")

    def retain(self, content, *, context, document_id, metadata, timestamp=None):
        self.records.append({"content": content, "context": context, "document_id": document_id,
                             "metadata": metadata, "timestamp": timestamp})
        self._save()

    def recall(self, query, k: int = 25):
        q = set(re.findall(r"[a-z0-9_]+", query.lower()))
        scored = []
        for r in self.records:
            toks = set(re.findall(r"[a-z0-9_]+", r["content"].lower()))
            s = len(q & toks)
            if s:
                scored.append((s, r["content"]))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:k]]

    def reflect(self, query, context=""):
        precs = [p for p in parse_precedents(self.recall(query, k=200)) if p.vendor in query]
        if not precs:
            return "No history with this vendor yet."
        by = {}
        for p in precs:
            by.setdefault((p.type, p.decision), []).append(p)
        human = lambda ps: [p for p in ps if p.is_human] or ps  # noqa: E731
        lines = [f"- {t.replace('_', ' ').lower()}: {d} x{len(ps)} (range {min(p.magnitude for p in ps):g}–"
                 f"{max(p.magnitude for p in ps):g}) — \"{human(ps)[-1].reason}\""
                 for (t, d), ps in by.items()]
        return "What this desk has learned:\n" + "\n".join(lines)

    def reset(self):
        self.records = []
        self._save()


def make_memory() -> MemoryBase:
    url = os.getenv("HINDSIGHT_URL")
    if url:
        return HindsightMemory(url, os.getenv("HINDSIGHT_API_KEY"))
    return LocalMemory(Path(os.getenv("LEDGERWISE_LOCAL_MEMORY", ".ledgerwise_memory.json")))
