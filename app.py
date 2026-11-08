"""Ledgerwise web app — `python app.py` then open http://localhost:5050"""
from __future__ import annotations

import os
import threading

from flask import Flask, jsonify, render_template, request

from ledgerwise.memory import make_memory
from ledgerwise.sim import Simulation

try:
    from dotenv import load_dotenv  # optional
    load_dotenv()
except Exception:
    pass

app = Flask(__name__)
lock = threading.Lock()
sim = Simulation(make_memory())


def state() -> dict:
    return {
        "memory": {**sim.memory.info(), "enabled": sim.memory_enabled},
        "vendors": sim.data["vendors"],
        "results": list(reversed(sim.results)),
        "pending": list(sim.pending),
        "next": [{"id": i["id"], "vendor_id": i["vendor_id"], "date": i["date"], "week": i["week"]}
                 for i in sim.invoices[sim.cursor:sim.cursor + 6]],
        "stats": sim.stats(),
        "recall_log": sim.agent.recall_log[-8:],
        "llm": bool(os.getenv("GROQ_API_KEY")),
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def api_state():
    return jsonify(state())


@app.post("/api/next")
def api_next():
    with lock:
        res = sim.step()
    return jsonify({"result": res, "state": state(),
                    "blocked": bool(sim.pending), "done": sim.done})


@app.post("/api/decide")
def api_decide():
    body = request.get_json(force=True)
    decision = body.get("decision", "").upper()
    reason = (body.get("reason") or "").strip()
    if decision not in {"APPROVE", "REJECT", "PARTIAL", "HOLD_DUPLICATE", "ESCALATE"} or not reason:
        return jsonify({"error": "decision and reason are required"}), 400
    with lock:
        if body.get("invoice_id") not in sim.pending:
            return jsonify({"error": "invoice is not awaiting review"}), 404
        res = sim.decide(body["invoice_id"], decision, reason)
    return jsonify({"result": res, "state": state()})


@app.post("/api/run")
def api_run():
    body = request.get_json(silent=True) or {}
    with lock:
        week = body.get("until_week")
        if week is None and not sim.done:
            week = sim.invoices[sim.cursor]["week"]
        sim.run(until_week=week)
    return jsonify({"state": state()})


@app.post("/api/reset")
def api_reset():
    body = request.get_json(silent=True) or {}
    with lock:
        sim.reset(memory_enabled=bool(body.get("memory_enabled", True)))
    return jsonify({"state": state()})


@app.get("/api/brief/<vendor_id>")
def api_brief(vendor_id):
    try:
        return jsonify({"vendor_id": vendor_id, "brief": sim.agent.vendor_brief(vendor_id)})
    except Exception as e:  # reflect is a network call; never take the page down
        return jsonify({"vendor_id": vendor_id, "brief": f"Memory brief unavailable: {e}"}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5050)), debug=False)
