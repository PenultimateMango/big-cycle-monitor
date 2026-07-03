#!/usr/bin/env python
"""Bootstrap data/manual/<indicator>.csv for every csv-kind indicator, using the
config's illustrative current_reading as the first row. Existing files are left
untouched (so you never clobber real data you've added). Then you just append a
new date,value line whenever fresh data drops."""
import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bcm import scoring
from bcm.registry import INDICATORS
from bcm.scoring import CYCLES

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / "data" / "manual"


def main():
    cfg = scoring.load_config(ROOT / "config" / "thresholds.yaml")
    readings = {}
    for c in CYCLES:
        for name, ind in cfg[c]["indicators"].items():
            if "current_reading" in ind:
                readings[name] = ind["current_reading"]

    MANUAL.mkdir(parents=True, exist_ok=True)
    made = 0
    for name, spec in INDICATORS.items():
        if spec.kind != "csv":
            continue
        path = MANUAL / spec.series[0]
        if path.exists():
            continue
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "value"])
            w.writerow([date.today().isoformat(), readings.get(name, "")])
        made += 1
    print(f"created {made} manual CSV templates in {MANUAL}")


if __name__ == "__main__":
    main()
