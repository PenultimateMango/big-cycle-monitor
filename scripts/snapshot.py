#!/usr/bin/env python
"""Score the current store and emit committable text artifacts:
  data/snapshot.json   latest scores + readings (full detail)
  data/history.csv     one appended row per run -> git history IS the time series
  docs/index.html      the rendered arc (serve via GitHub Pages -> /docs)

Called by the GitHub Actions refresh workflow after `run.py refresh`."""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bcm import scoring
from bcm.arc import page, render_arc
from bcm.store import Store


def main():
    cfg = scoring.load_config(ROOT / "config" / "thresholds.yaml")
    readings = Store(ROOT / "data" / "bcm.duckdb").latest_values()
    res = scoring.run(cfg, readings)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    country = cfg["meta"]["country"]
    lo, hi = res["band"]

    # 1) full snapshot
    snap = {
        "as_of": now, "country": country,
        "composite": round(res["composite"], 3),
        "band": [round(lo, 3), round(hi, 3)],
        "widening_pct": round(res["widening_pct"], 1),
        "gauges": {k: round(v, 3) for k, v in res["gauges"].items()},
        "sigmas": {k: round(v, 3) for k, v in res["sigmas"].items()},
        "readings": {k: round(v, 4) for k, v in readings.items()},
    }
    (ROOT / "data" / "snapshot.json").write_text(json.dumps(snap, indent=2))

    # 2) append one history row (create header once)
    hist = ROOT / "data" / "history.csv"
    new = not hist.exists()
    with open(hist, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["as_of", "country", "composite", "band_lo", "band_hi",
                        "internal_order", "debt_money", "external_order"])
        w.writerow([now, country, f"{res['composite']:.3f}", f"{lo:.3f}", f"{hi:.3f}",
                    f"{res['gauges']['internal_order']:.3f}",
                    f"{res['gauges']['debt_money']:.3f}",
                    f"{res['gauges']['external_order']:.3f}"])

    # 3) rendered arc for GitHub Pages
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "index.html").write_text(page(render_arc(res, cfg), res))

    print(f"snapshot {country} composite={res['composite']:.2f} band=[{lo:.2f},{hi:.2f}] @ {now}")


if __name__ == "__main__":
    main()
