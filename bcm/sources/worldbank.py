"""World Bank Open Data — free, no key. Covers military expenditure (SIPRI-sourced),
GDP, trade, and more. https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
series_id is 'ISO3/INDICATOR', e.g. 'USA/MS.MIL.XPND.CD'."""
from __future__ import annotations
from datetime import date

import requests

from .base import Source


class WorldBankSource(Source):
    name = "worldbank"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def series(self, series_id: str) -> tuple[date, float]:
        country, indicator = series_id.split("/")
        url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
        r = requests.get(url, params={"format": "json", "per_page": 100, "mrnev": 1},
                         timeout=self.timeout)
        r.raise_for_status()
        payload = r.json()
        if len(payload) < 2 or not payload[1]:
            raise ValueError(f"no World Bank data for {series_id}")
        for row in payload[1]:                       # mrnev=1 -> most recent non-empty first
            if row.get("value") is not None:
                return date(int(row["date"]), 12, 31), float(row["value"])
        raise ValueError(f"no non-empty value for {series_id}")

    def history(self, series_id: str) -> list[tuple[date, float]]:
        """All available years, ascending (annual data; year -> Dec 31)."""
        country, indicator = series_id.split("/")
        url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
        r = requests.get(url, params={"format": "json", "per_page": 20000},
                         timeout=self.timeout)
        r.raise_for_status()
        payload = r.json()
        if len(payload) < 2 or not payload[1]:
            raise ValueError(f"no World Bank data for {series_id}")
        rows = [(date(int(x["date"]), 12, 31), float(x["value"]))
                for x in payload[1] if x.get("value") is not None]
        return sorted(rows)
