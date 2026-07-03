"""GDELT — free, no key. Real-time global event tone/conflict signal.
This uses the DOC 2.0 timeline API as a lightweight tone proxy; for a production
conflict gauge, pull the Events table via BigQuery and compute Goldstein averages.
Returns a 0..100 normalized 'stress' reading (higher = more conflictual tone)."""
from __future__ import annotations
from datetime import date, datetime

import requests

from .base import Source

_DOC = "https://api.gdeltproject.org/api/v2/doc/doc"


class GdeltSource(Source):
    name = "gdelt"

    def __init__(self, timeout: int = 40):
        self.timeout = timeout

    def series(self, series_id: str) -> tuple[date, float]:
        """series_id is a GDELT query string, e.g. 'sourcecountry:US (conflict OR sanctions)'."""
        params = {
            "query": series_id,
            "mode": "timelinetone",
            "format": "json",
            "timespan": "3months",
        }
        r = requests.get(_DOC, params=params, timeout=self.timeout)
        r.raise_for_status()
        pts = r.json().get("timeline", [{}])[0].get("data", [])
        if not pts:
            raise ValueError(f"no GDELT timeline for query: {series_id}")
        tone = pts[-1]["value"]                     # GDELT tone: roughly -10..+10
        stress = max(0.0, min(100.0, (5.0 - tone) * 10.0))   # invert -> 0..100
        return date.today(), stress
