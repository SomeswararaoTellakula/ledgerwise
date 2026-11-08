import copy

import pytest

from ledgerwise.agent import APAgent
from ledgerwise.data_gen import generate
from ledgerwise.matching import three_way_match
from ledgerwise.memory import LocalMemory, parse_precedents, precedent_text
from ledgerwise.sim import Simulation


@pytest.fixture
def data():
    return generate()


def test_precedent_roundtrip():
    v = {"id": "V-101", "name": "Tata Steel Distributors Pvt Ltd"}
    t = precedent_text(v, "PRICE_VARIANCE", 3.1, "APPROVE", "101/1002", "Priya Nair (AP lead)", "Clause 7.2 index.")
    [p] = parse_precedents([t, t])  # duplicates collapse
    assert (p.vendor_id, p.type, p.magnitude, p.decision, p.is_human) == ("V-101", "PRICE_VARIANCE", 3.1, "APPROVE", True)


def test_matcher_flags_each_quirk(data):
    sim = Simulation(LocalMemory(), data=data)
    types = set()
    for inv in data["invoices"]:
        v = sim.agent.vendors[inv["vendor_id"]]
        excs = three_way_match(inv, sim.agent.pos.get(inv["po_id"]), sim.agent.grns.get(inv["po_id"]), v, sim.agent.seen)
        sim.agent.seen.append(inv)
        types |= {e.type for e in excs}
    assert {"PRICE_VARIANCE", "UNPO_CHARGE", "QTY_SHORT", "TAX_MISMATCH", "DUPLICATE", "BANK_CHANGE"} <= types


def test_no_memory_means_no_automation(data):
    sim = Simulation(LocalMemory(), memory_enabled=False, data=data)
    sim.run()
    assert sim.stats()["total_auto"] == 0


def test_memory_learns_without_wrong_auto_decisions(data):
    sim = Simulation(LocalMemory(), data=data)
    sim.run()
    st = sim.stats()
    assert st["total_wrong"] == 0
    assert st["weeks"][0]["auto"] == 0          # nothing to recall in week 1
    assert st["weeks"][-2]["auto_rate"] >= 75   # by week 7 most exceptions are handled


def test_bank_change_always_escalates_even_with_history(data):
    sim = Simulation(LocalMemory(), data=data)
    sim.run()
    bank = [r for r in sim.results if any(e["exception"]["type"] == "BANK_CHANGE" for e in r["exceptions"])]
    assert bank and all(not r["auto"] for r in bank)


def test_agent_never_learns_from_its_own_decisions(data):
    mem = LocalMemory()
    agent = APAgent(mem, data)
    inv = next(i for i in data["invoices"] if i["vendor_id"] == "V-104")
    v = agent.vendors["V-104"]
    for n in range(3):  # three *agent* decisions in memory
        mem.retain(precedent_text(v, "TAX_MISMATCH", 6, "APPROVE", f"104/9{n}", "Ledgerwise agent (auto)", "x"),
                   context="c", document_id=str(n), metadata={})
    res = agent.process(inv)
    assert res["decision"] == "ESCALATE"


def test_out_of_range_magnitude_escalates(data):
    sim = Simulation(LocalMemory(), data=data)
    sim.run()
    big = next(r for r in sim.results if r["vendor_id"] == "V-102" and any(
        e["exception"]["magnitude"] > 5000 for e in r["exceptions"]))
    assert not big["auto"] and big["human_decision"] == "REJECT"


def test_human_override_breaks_consensus(data):
    mem = LocalMemory()
    d = copy.deepcopy(data)
    agent = APAgent(mem, d)
    v = agent.vendors["V-103"]
    for n, dec in enumerate(["PARTIAL", "PARTIAL", "APPROVE"]):
        mem.retain(precedent_text(v, "QTY_SHORT", 200, dec, f"103/8{n}", "Priya Nair (AP lead)", "r"),
                   context="c", document_id=str(n), metadata={})
    inv = next(i for i in d["invoices"] if i["vendor_id"] == "V-103" and i["truth"]["decision"] == "PARTIAL")
    assert agent.process(inv)["decision"] == "ESCALATE"
