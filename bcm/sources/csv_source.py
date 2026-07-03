"""CSV source for the indicators that have no clean API — BIS, SIPRI, IMF COFER,
DW-NOMINATE, Pew, ACLED, etc. You download/curate these periodically into
data/manual/<indicator>.csv with two columns: date,value (ISO date). This source
returns the latest row, so appending a new line each quarter is the whole workflow.
"""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path

from .base import Source


class CsvSource(Source):
    name = "csv"

    def __init__(self, base_dir: str | Path = "data/manual"):
        self.base_dir = Path(base_dir)

    def series(self, series_id: str) -> tuple[date, float]:
        """series_id is a filename, e.g. 'reserve_currency_share.csv'."""
        path = self.base_dir / series_id
        if not path.exists():
            raise FileNotFoundError(f"no CSV at {path}")
        latest_d, latest_v = None, None
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                if not row.get("value") or row["value"].strip() in (".", ""):
                    continue
                d = date.fromisoformat(row["date"].strip())
                if latest_d is None or d > latest_d:
                    latest_d, latest_v = d, float(row["value"])
        if latest_d is None:
            raise ValueError(f"no valid rows in {path}")
        return latest_d, latest_v

    def history(self, series_id: str) -> list[tuple[date, float]]:
        """Every valid row, ascending — the payoff for appending, not replacing."""
        path = self.base_dir / series_id
        if not path.exists():
            raise FileNotFoundError(f"no CSV at {path}")
        rows: list[tuple[date, float]] = []
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                if not row.get("value") or row["value"].strip() in (".", ""):
                    continue
                rows.append((date.fromisoformat(row["date"].strip()),
                             float(row["value"])))
        if not rows:
            raise ValueError(f"no valid rows in {path}")
        return sorted(rows)
