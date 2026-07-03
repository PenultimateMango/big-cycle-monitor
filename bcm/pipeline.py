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
            elif spec.kind == "csv_mean":
                # derived composite: mean of each sub-CSV's latest value. Each
                # sub-series is ALSO stored under its own name (stem of the
                # filename) so it gets charted individually.
                subs = []
                for f in spec.series:
                    sd, sv = csvs.series(f)
                    sub_name = f.rsplit(".", 1)[0]
                    store.upsert(Observation(sub_name, sv, sd, "csv", f, spec.unit),
                                 country=country)
                    subs.append((sd, sv))
                if len(subs) < len(spec.series):
                    raise ValueError(f"only {len(subs)}/{len(spec.series)} sub-series present")
                val = sum(v for _, v in subs) / len(subs) * spec.scale
                d = max(sd for sd, _ in subs)
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


def _align_ratio(num: list, den: list, scale: float, tol_days: int = 400) -> list:
    """Pair each numerator obs with the nearest denominator obs (within tol),
    ascending. Handles mixed cadence cleanly — e.g. quarterly FDHBFIN over
    annual FYGFDPUN — by matching DATES instead of just dividing latest values."""
    import bisect
    if not num or not den:
        return []
    den_ord = [d.toordinal() for d, _ in den]
    out = []
    for d, v in num:
        i = bisect.bisect_left(den_ord, d.toordinal())
        best = None
        for j in (i - 1, i):
            if 0 <= j < len(den):
                gap = abs(den_ord[j] - d.toordinal())
                if gap <= tol_days and (best is None or gap < best[0]):
                    best = (gap, den[j][1])
        if best and best[1]:
            out.append((d, v / best[1] * scale))
    return out


def _ffill_mean(series_list: list[list]) -> list:
    """Composite history from N sub-series: at every date in the union (from the
    point all N have started), carry each series' last value forward and average.
    This is how a judgment composite honestly evolves — a sub-war re-rating moves
    the composite from that date on, without inventing data between ratings."""
    if not series_list or any(not s for s in series_list):
        return []
    all_dates = sorted({d for s in series_list for d, _ in s})
    start = max(s[0][0] for s in series_list)      # composite defined once all exist
    idx = [0] * len(series_list)
    last = [s[0][1] for s in series_list]
    out = []
    for d in all_dates:
        for k, s in enumerate(series_list):
            while idx[k] < len(s) and s[idx[k]][0] <= d:
                last[k] = s[idx[k]][1]; idx[k] += 1
        if d >= start:
            out.append((d, sum(last) / len(last)))
    return out


def backfill(store: Store, country: str = "US", manual_dir=None, verbose: bool = True) -> dict[str, str]:
    """Load FULL history for every indicator that has one — decades of FRED /
    World Bank data plus all manual CSV rows — so time-series charts are dense
    from the first run. Idempotent: the store dedupes per obs_date on read, and
    the CI runner rebuilds the DB from scratch anyway. GDELT has no usable
    history endpoint; its chart grows from data/history.csv git commits instead."""
    root = Path(__file__).resolve().parents[1]
    if manual_dir is None:
        manual_dir = root / "data" / "manual" if country == "US" else root / "data" / "manual" / country
    fred, wb = FredSource(), WorldBankSource()
    csvs = CsvSource(manual_dir)
    status: dict[str, str] = {}

    for name, spec in indicators_for(country).items():
        try:
            if spec.kind == "fred":
                rows = [(d, v * spec.scale) for d, v in fred.history(spec.series[0])]
            elif spec.kind == "wb":
                rows = [(d, v * spec.scale) for d, v in wb.history(spec.series[0])]
            elif spec.kind == "fred_ratio":
                rows = _align_ratio(fred.history(spec.series[0]),
                                    fred.history(spec.series[1]), spec.scale)
            elif spec.kind == "wb_ratio":
                rows = _align_ratio(wb.history(spec.series[0]),
                                    wb.history(spec.series[1]), spec.scale)
            elif spec.kind == "csv":
                rows = [(d, v * spec.scale) for d, v in csvs.history(spec.series[0])]
            elif spec.kind == "csv_mean":
                subs = []
                for f in spec.series:
                    sub_rows = csvs.history(f)
                    sub_name = f.rsplit(".", 1)[0]
                    store.insert_many(sub_name, sub_rows, "csv", f, spec.unit,
                                      country=country)
                    subs.append(sub_rows)
                rows = [(d, v * spec.scale) for d, v in _ffill_mean(subs)]
            else:                               # gdelt & friends: no history API
                status[name] = "skip (no history endpoint)"; continue
            n = store.insert_many(name, rows, spec.kind.split("_")[0],
                                  ",".join(spec.series), spec.unit, country=country)
            status[name] = f"ok  {n} obs  ({rows[0][0]} → {rows[-1][0]})" if n else "ok  0 obs"
        except Exception as e:
            status[name] = f"FAIL  {type(e).__name__}: {e}"

    if verbose:
        for k, v in status.items():
            print(f"  {k:<24} {v}")
    return status
