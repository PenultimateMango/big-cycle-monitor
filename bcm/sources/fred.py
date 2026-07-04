"""FRED client. Free key: https://fred.stlouisfed.org/docs/api/api_key.html
Set FRED_API_KEY in the environment. Handles the many-per-day cadence differences
by always taking the latest non-missing observation."""
from __future__ import annotations
import os
from datetime import date

import requests

from .base import Source

_ENDPOINT = "https://api.stlouisfed.org/fred/series/observations"


class FredSource(Source):
    name = "fred"

    def __init__(self, api_key: str | None = None, timeout: int = 30):
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        self.timeout = timeout

    def series(self, series_id: str) -> tuple[date, float]:
        if not self.api_key:
            raise RuntimeError("FRED_API_KEY not set — export it or pass api_key=")
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 12,            # grab a few; skip trailing '.' missing values
        }
        r = requests.get(_ENDPOINT, params=params, timeout=self.timeout)
        r.raise_for_status()
        for obs in r.json()["observations"]:
            if obs["value"] not in (".", "", None):
                return date.fromisoformat(obs["date"]), float(obs["value"])
        raise ValueError(f"no valid observations for {series_id}")

    def history(self, series_id: str, units: str | None = None) -> list[tuple[date, float]]:
        """Full series, ascending. One call returns everything (FRED caps at
        100k obs per request — even daily fed funds since 1954 fits).
        units='pc1' asks FRED to return YoY % change server-side."""
        if not self.api_key:
            raise RuntimeError("FRED_API_KEY not set — export it or pass api_key=")
        params = {"series_id": series_id, "api_key": self.api_key,
                  "file_type": "json", "sort_order": "asc", "limit": 100000}
        if units:
            params["units"] = units
        r = requests.get(_ENDPOINT, params=params, timeout=self.timeout)
        r.raise_for_status()
        return [(date.fromisoformat(o["date"]), float(o["value"]))
                for o in r.json()["observations"]
                if o["value"] not in (".", "", None)]
