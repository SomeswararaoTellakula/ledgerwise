"""Replay 8 weeks of invoices with and without memory and print the learning curve.

    python scripts/replay.py            # uses Hindsight if HINDSIGHT_URL is set
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ledgerwise.memory import make_memory  # noqa: E402
from ledgerwise.sim import Simulation  # noqa: E402


def main():
    mem = make_memory()
    print(f"memory backend: {mem.info()}\n")
    for enabled in (False, True):
        mem.reset()
        sim = Simulation(mem, memory_enabled=enabled)
        sim.run()
        st = sim.stats()
        label = "WITH memory   " if enabled else "WITHOUT memory"
        bars = "  ".join(f"W{w['week']}:{w['auto_rate']:>5.1f}%" for w in st["weeks"])
        print(f"{label}  auto-resolved {st['auto_rate']:>5.1f}%  wrong={st['total_wrong']}  | {bars}")
    print("\nVendor brief (reflect) — Sharma Logistics:\n")
    print(sim.agent.vendor_brief("V-102"))


if __name__ == "__main__":
    main()
