# Video script — ~3 minutes (screen recording + optional face cam)

**Before recording:** Hindsight running (Cloud or Docker) and `HINDSIGHT_URL` set so the header badge reads
`Hindsight · ledgerwise-ap-xxxx`. Browser zoom 110%. Close notifications. 1080p.

---

### 0:00–0:30 · Intro
**Screen:** Ledgerwise home page, empty feed. (Face cam corner if you have it.)

> Hi, I'm Someswara Rao. This is Ledgerwise — an accounts-payable agent that resolves invoice exceptions
> the way your team resolved them last time. Every AP desk answers the same questions every month:
> this vendor's price is 3% high again, that one billed the wrong GST again. The matching software flags
> it; nobody remembers the answer. Ledgerwise remembers, using Hindsight.

### 0:30–1:00 · The problem: no memory
**Screen:** untick **Memory** → click **Run all 8 weeks**. Point at the flat 0% chart and the "needs you" cards.

> Here's the same agent with memory off, across eight weeks and 48 invoices. It detects every
> exception fine — but it resolves zero of them. Thirty-two invoices, all on a human's desk, including
> the same GST mistake from the same vendor eight weeks in a row.

### 1:00–2:30 · Live demo with memory
**Screen:** tick **Memory** (resets). Click **Process next invoice**.

> Memory on. Week one, Tata Steel is 2.8% over PO. No history, so it asks me. I approve and — this is
> the important part — I type *why*: clause 7.2 allows a steel-index adjustment up to 5%. That
> sentence is retained in Hindsight.

**Screen:** decide 2–3 more (use "AP lead's notebook → Use this" to save time). Point at the **Recall trace** panel.

> Every time it sees an exception it runs a recall — "how were price variances from Tata Steel
> resolved, and why?" You can see the queries and how many precedents came back.

**Screen:** click **Run to end of week** until week 4. Point at the 75% bars, then open an auto-resolved Kaveri card and its precedent chips and drafted email.

> By week three it's resolving 75% on its own. This Kaveri invoice: rejected automatically, citing my two
> earlier rejections by invoice number, with the credit-note email drafted.

**Screen:** step into week 5 until Tata +3.1% shows up as "needs you".

> Now the part I like. Tata at +3.1%. I'd only ever approved up to 2.8, so it doesn't extrapolate — it
> escalates and says it's leaning approve. I approve; the learned range widens.

**Screen:** run to week 6; show the Meridian bank-change card, then Sharma ₹6,800.

> Week six: Meridian says they've changed banks. Six clean invoices in memory — still escalated. That's
> a hard guardrail. And a ₹6,800 fuel surcharge when everything approved was under ₹2,400 — escalated,
> I reject, and that becomes the ceiling.

**Screen:** click **Brief** on Sharma Logistics.

> And this is Hindsight's reflect: a vendor brief for whoever runs the next payment cycle.

### 2:30–3:00 · Takeaway
**Screen:** full learning-curve panel: 0 → 75 → 100%, "0 auto decisions the lead would overturn".

> What surprised me: the hard part wasn't recall, it was deciding when memory is *enough*. Store the
> amount, not just the outcome; never let the agent count its own decisions; and decide upfront what
> memory can never override. Code's on GitHub — link below.

---

## YouTube titles (pick one)
1. My AI Agent Learned Our Vendors' Invoice Quirks (Hindsight Memory)
2. 0% → 100%: Teaching an Accounts-Payable Agent With Memory
3. This Agent Remembers Every Invoice Decision Your Team Ever Made
4. Why My AP Agent Still Calls You About Bank Changes
5. Building an Invoice Exception Agent That Learns From Humans

## YouTube description
Ledgerwise resolves accounts-payable invoice exceptions using past human decisions stored in Hindsight agent memory — and escalates when that memory isn't enough.
Code: https://github.com/SomeswararaoTellakula/ledgerwise
Article: <ARTICLE_URL>
Hindsight: https://github.com/vectorize-io/hindsight
