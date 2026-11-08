"""Checks HindsightMemory calls the hindsight-client API with the documented arguments,
using a fake client so the test runs offline."""
import sys
import types
from types import SimpleNamespace

from ledgerwise.data_gen import generate
from ledgerwise.sim import Simulation


class FakeHindsight:
    def __init__(self, base_url, timeout=30.0, api_key=None):
        self.base_url, self.api_key, self.calls, self.store = base_url, api_key, [], []

    def create_bank(self, **kw):
        self.calls.append(("create_bank", kw))

    def retain(self, **kw):
        self.calls.append(("retain", kw))
        self.store.append(kw["content"])

    def recall(self, **kw):
        self.calls.append(("recall", kw))
        results = [SimpleNamespace(text=c.split("\n")[0], chunk_id=str(i)) for i, c in enumerate(self.store)]
        chunks = {str(i): SimpleNamespace(text=c) for i, c in enumerate(self.store)}
        return SimpleNamespace(results=results, chunks=chunks)

    def reflect(self, **kw):
        self.calls.append(("reflect", kw))
        return SimpleNamespace(text="brief")


def test_hindsight_backend_drives_learning(monkeypatch):
    monkeypatch.setitem(sys.modules, "hindsight_client", types.SimpleNamespace(Hindsight=FakeHindsight))
    from ledgerwise.memory import HindsightMemory

    mem = HindsightMemory("http://hs.local", api_key="k")
    sim = Simulation(mem, data=generate())
    sim.run()
    names = [c[0] for c in mem.client.calls]
    assert names[0] == "create_bank" and "retain" in names and "recall" in names
    retain = next(kw for n, kw in mem.client.calls if n == "retain")
    assert retain["retain_async"] is False and ":" in retain["document_id"]
    recall = next(kw for n, kw in mem.client.calls if n == "recall")
    assert recall["include_chunks"] is True and recall["bank_id"] == mem.bank_id
    assert sim.stats()["total_auto"] > 0 and sim.stats()["total_wrong"] == 0
    assert sim.agent.vendor_brief("V-102") == "brief"
