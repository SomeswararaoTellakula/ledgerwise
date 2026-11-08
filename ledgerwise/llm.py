"""Optional LLM narration via Groq's OpenAI-compatible endpoint.

The LLM never makes the pay/no-pay decision — the policy in agent.py does, from
recalled precedents. The LLM only writes the human-facing note and the vendor
email. If GROQ_API_KEY is unset or the call fails, a template is used instead,
so a flaky model can never block an invoice.
"""
from __future__ import annotations

import os

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.getenv("LEDGERWISE_MODEL", "openai/gpt-oss-120b")


def _chat(system: str, user: str, max_tokens: int = 300) -> str | None:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    try:
        r = requests.post(GROQ_URL, timeout=20, headers={"Authorization": f"Bearer {key}"}, json={
            "model": MODEL, "temperature": 0.2, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        })
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
        return text or None
    except Exception:
        return None


def vendor_email(vendor: dict, invoice_id: str, issue: str, ask: str) -> str:
    text = _chat(
        "You write short, polite, firm emails from an Indian accounts-payable team to a supplier. "
        "Max 90 words. No subject line. Sign off as 'Accounts Payable, Ledgerwise Demo Co.'",
        f"Supplier: {vendor['name']}\nInvoice: {invoice_id}\nIssue: {issue}\nWhat we need: {ask}")
    if text:
        return text
    return (f"Dear {vendor['name']} team,\n\nWe are unable to process invoice {invoice_id} as submitted: "
            f"{issue}. {ask}\n\nThanks,\nAccounts Payable, Ledgerwise Demo Co.")


def explain(decision: str, summary: str, precedents: list[dict], vendor_brief: str = "") -> str:
    cites = "; ".join(f"{p['invoice']} ({p['decision']}, {p['decided_by']})" for p in precedents[:3])
    text = _chat(
        "You are an AP agent explaining one decision to a busy AP lead in 2 sentences. "
        "Cite the precedent invoice numbers given. No hedging, no fluff.",
        f"Decision: {decision}\nException: {summary}\nPrecedents: {cites or 'none'}\nVendor brief: {vendor_brief[:600]}")
    if text:
        return text
    if not precedents:
        return "No precedent for this vendor and exception yet, so you decide — and your note becomes the precedent."
    if decision == "ESCALATE":
        return f"Not enough consistent precedent to act alone. Closest history: {cites}."
    return f"{decision.replace('_', ' ').title()}, consistent with {len(precedents)} earlier decision(s): {cites}."
