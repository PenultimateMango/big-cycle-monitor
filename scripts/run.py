#!/usr/bin/env python
"""Big Cycle Monitor CLI.

    python scripts/run.py demo      # seed offline values + score  (no network)
    python scripts/run.py refresh   # pull live sources into the store (needs FRED_API_KEY)
    python scripts/run.py score     # score whatever is in the store
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bcm import pipeline, scoring, seed as seed_mod
from bcm.store import Store

CONFIG = str(Path(__file__).resolve().parents[1] / "config" / "thresholds.yaml")
DB = str(Path(__file__).resolve().parents[1] / "data" / "bcm.duckdb")


def _report(cfg, readings):
    res = scoring.run(cfg, readings)
    print(f"\nBIG CYCLE MONITOR — {cfg.get('_name', cfg['meta']['country'])}\n" + "-" * 52)
    for c in scoring.CYCLES:
        print(f"{cfg[c]['label']:<28} stage {res['gauges'][c]:4.2f}   sigma {res['sigmas'][c]:.2f}")
        print(f"    {res['details'][c]}")
    print("-" * 52)
    lo, hi = res["band"]; nlo, nhi = res["band_naive"]
    print(f"COMPOSITE stage        {res['composite']:4.2f}")
    print(f"  naive band (indep)   [{nlo:.2f}, {nhi:.2f}]")
    print(f"  correlated band      [{lo:.2f}, {hi:.2f}]")
    print(f"  -> correlation widens the band by {res['widening_pct']:.0f}%\n")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    country = sys.argv[2] if len(sys.argv) > 2 else "US"
    cfg = scoring.resolve_country(scoring.load_config(CONFIG), country)
    store = Store(DB)

    if cmd == "demo":
        n = seed_mod.seed(cfg, store, country=country)
        print(f"seeded {n} indicators for {country} (offline)")
        _report(cfg, store.latest_values(country=country))
    elif cmd == "refresh":
        print(f"refreshing live sources for {country}...")
        pipeline.refresh(store, country=country)
        _report(cfg, store.latest_values(country=country))
    elif cmd == "score":
        _report(cfg, store.latest_values(country=country))
    else:
        print(__doc__)
    store.close()


if __name__ == "__main__":
    main()
