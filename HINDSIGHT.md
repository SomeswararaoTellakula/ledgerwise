# How Ledgerwise uses Hindsight memory

## The problem memory solves

A 3-way match (PO vs goods receipt vs invoice) is easy to automate. What it produces — the
*exceptions* — is not, because the right answer depends on history no rule engine has:
a contract clause someone negotiated, an email from Ops, the fact that this vendor always
bills full quantity on short trucks. That history lives in the AP lead's head. Ledgerwise
moves it into a Hindsight memory bank, one decision at a time, and only acts on it when it is
consistent.

Without memory the agent is a good exception *detector*: 0% of exceptions resolved automatically.
With memory, the same agent on the same invoices resolves 56% overall and 60–100% from week 3,
with zero decisions the AP lead would overturn.

## 1. Bank — `memory.py: HindsightMemory._ensure_bank`

```python
client.create_bank(
    bank_id=self.bank_id, name="Ledgerwise AP desk", mission=self.MISSION,
    disposition={"skepticism": 5, "literalism": 4, "empathy": 2},
)
```

The mission tells Hindsight what this memory is for (vendor exceptions, who decided, why; prefer
amounts, clauses and dates). The disposition is deliberately skeptical and literal: one approval of a
3% variance is not permission for "price variances" in general.

## 2. Retain — every human decision, with its reason

`agent.py: APAgent.retain_decision`

```python
self.memory.retain(
    precedent_text(vendor, exc["type"], exc["magnitude"], decision, invoice["id"], decided_by, reason),
    context=f"accounts payable exception resolution — {vendor['category'].lower()} vendor",
    document_id=f"{invoice['id']}:{exc['type']}",
    metadata={"vendor_id": ..., "exception": ..., "decision": ..., "decided_by": ...},
    timestamp=invoice["date"],
)
```

Each memory is written twice in one string:

* a **prose sentence** Hindsight extracts facts and entities from — *"On invoice 102/1035, Sharma
  Logistics LLP had an unpo charge exception (magnitude 6800). Priya Nair (AP lead) decided REJECT:
  Surcharge above the ₹2,500 cap agreed with Ops…"*
* a **structured line** (`AP precedent | vendor: … | magnitude: 6800 | decision: REJECT | …`) the policy parses.

`document_id` makes a re-decision on the same invoice an update rather than a duplicate, and
`timestamp` lets Hindsight reason about *when* things happened ("since August").

The reviewer's **reason is the most valuable field**. The UI won't save a decision without one,
because that sentence is what the next escalation shows and what `reflect` summarises.

## 3. Recall — precedent before every decision

`agent.py: APAgent.recall_precedents`

```python
resp = client.recall(bank_id=..., query="How were price variance exceptions on invoices from "
                     "Tata Steel Distributors Pvt Ltd resolved, and why?",
                     types=["world", "experience", "observation"], budget="mid",
                     max_tokens=4096, include_chunks=True, max_chunk_tokens=600)
```

`include_chunks=True` returns the source chunk behind each fact, so the structured precedent line comes
back intact. Results are filtered to the same vendor and exception type, and only **human** decisions
count. The UI's *Recall trace* panel shows each query and how many memories/precedents it returned;
each auto decision shows the precedent invoices it relied on as chips.

## 4. Policy — when is memory enough?

`agent.py: APAgent._decide_exception`

| Situation | Behaviour |
|---|---|
| < 2 human precedents | escalate (your note becomes the precedent) |
| Amount-type exception (price %, ₹ surcharge) inside the range humans approved (+10%) and below any rejected amount | auto-approve |
| At/above amounts humans rejected, beyond anything approved | auto-reject + drafted vendor email |
| Outside the learned range | escalate with a *lean* ("close to past approvals" / "far from anything approved") |
| Categorical exception (short shipment, GST, duplicate) where the last 3 human decisions agree | apply that decision |
| Last 3 human decisions disagree | escalate |
| Bank-account change / unknown PO | always escalate (guardrail) |

The agent's own decisions are retained too (`decided_by: Ledgerwise agent (auto)`) for audit and for
`reflect`, but are excluded from precedent — memory can't become a self-reinforcing loop.

## 5. Reflect — the vendor brief

`agent.py: APAgent.vendor_brief`

```python
client.reflect(bank_id=..., query="What should an AP clerk know about Sharma Logistics LLP before "
               "approving their next invoice? List recurring exceptions, how they were resolved, "
               "limits that were enforced, and red flags.", budget="low",
               context="vendor brief before payment run")
```

This is the "new joiner" view: everything the desk learned about a vendor, synthesised from individual
decisions — e.g. that fuel surcharges up to ₹2,500 are pre-agreed and one at ₹6,800 was rejected.

## Before / after in one example

**Week 1, Kaveri invoice at 18% GST (PO says 12%)** — no memory: escalated. The lead rejects:
*"HSN 2839 is contracted at 12% GST; ask Kaveri for a credit note. Never pay the 18% version."*

**Week 3, same quirk** — recall returns two human REJECTs. The agent rejects automatically, cites
`104/1004` and `104/1011`, and drafts the credit-note email. Nobody touches it.

**Week 6, Meridian bank change** — memory has six clean Meridian invoices. It still escalates.
