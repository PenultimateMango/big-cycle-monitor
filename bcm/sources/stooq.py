"""Stooq — free daily OHLC history as plain CSV, no key. Used for the series
FRED can't serve freely: gold (ICE licensing killed FRED's LBMA series), full
S&P history (FRED is capped to a 10-year trailing window), and Bitcoin.

Endpoint: https://stooq.com/q/d/l/?s=<symbol>&i=d
Returns:  Date,Open,High,Low,Close,Volume   (ascending)
Symbols used here: xauusd (gold), ^spx (S&P 500), ^ndq (Nasdaq Comp), btcusd.

UNOFFICIAL source — reliable and widely used, but label it honestly on the
dashboard and expect no SLA. We take the Close.
"""
from __future__ import annotations
import csv
import io
from datetime import date

import requests

from .base import Source

_ENDPOINT = "https://stooq.com/q/d/l/"


class StooqSource(Source):
    name = "stooq"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def history(self, series_id: str) -> list[tuple[date, float]]:
        r = requests.get(_ENDPOINT, params={"s": series_id, "i": "d"},
                         timeout=self.timeout,
                         headers={"User-Agent": "big-cycle-monitor"})
        r.raise_for_status()
        text = r.text.strip()
        if not text or text.lower().startswith(("no data", "<html")):
            raise ValueError(f"stooq returned no data for {series_id}")
        rows: list[tuple[date, float]] = []
        for row in csv.DictReader(io.StringIO(text)):
            c = row.get("Close")
            if c in (None, "", "N/A"):
                continue
            rows.append((date.fromisoformat(row["Date"]), float(c)))
        if not rows:
            raise ValueError(f"no parseable rows from stooq for {series_id}")
        return sorted(rows)

    def series(self, series_id: str) -> tuple[date, float]:
        return self.history(series_id)[-1]
