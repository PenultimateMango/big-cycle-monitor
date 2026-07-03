"""Orchestration. `refresh` pulls what it can from live sources and stores it;
manual indicators are skipped (their last stored/seeded value stands)."""
from __future__ import annotations
from datetime import date

from pathlib import Path

from .registry import INDICATORS, indicators_for
from .sources.base import Observation
from .sources.csv_source import CsvSource
from .sources.fred import FredSource
from .sources.gdelt import GdeltSource
from .sources.treasury import TreasurySource
from .sources.worldbank import WorldBankSource
from .store import Store


def refresh(store: Store, country: str = "US", manual_dir=None, verbose: bool = True) -> dict[str, str]:
    """Fetch every indicator we can for `country`. Returns {indicator: status}."""
    root = Path(__file__).resolve().parents[1]
    if manual_dir is None:
        # US keeps data/manual; other countries get data/manual/<country>
        manual_dir = root / "data" / "manual" if country == "US" else root / "data" / "manual" / country
    fred, gdelt, treasury, wb = FredSource(), GdeltSource(), TreasurySource(), WorldBankSource()
    csvs = CsvSource(manual_dir)
    indicators = indicators_for(country)
    status: dict[str, str] = {}

    for name, spec in indicators.items():
        try:
            if spec.kind == "fred":
                d, v = fred.series(spec.series[0]); val = v * spec.scale
            elif spec.kind == "wb":
                d, v = wb.series(spec.series[0]); val = v * spec.scale
            elif spec.kind == "fred_ratio":
                d0, v0 = fred.series(spec.series[0])
                d1, v1 = fred.series(spec.series[1])
                val, d = (v0 / v1) * spec.scale, max(d0, d1)
            elif spec.kind == "wb_ratio":
                d0, v0 = wb.series(spec.series[0])
                d1, v1 = wb.series(spec.series[1])
                val, d = (v0 / v1) * spec.scale, max(d0, d1)
            elif spec.kind == "treasury":
                d, v = treasury.series(spec.series[0]); val = v * spec.scale
            elif spec.kind == "gdelt":
                d, v = gdelt.series(spec.series[0]); val = v * spec.scale
            elif spec.kind == "csv":
                d, v = csvs.series(spec.series[0]); val = v * spec.scale
            else:
                status[name] = f"unknown kind {spec.kind}"; continue

            store.upsert(
                Observation(name, val, d, spec.kind.split("_")[0],
                            ",".join(spec.series), spec.unit),
                country=country,
            )
            status[name] = f"ok  {val:.2f}  ({d})"
        except Exception as e:                     # never let one bad source halt the run
            status[name] = f"FAIL  {type(e).__name__}: {e}"

    if verbose:
        for k, v in status.items():
            print(f"  {k:<24} {v}")
    return status
