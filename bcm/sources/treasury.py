"""U.S. Treasury Fiscal Data — free, no key. https://fiscaldata.treasury.gov/api-documentation/
Included as a real client because it's the authoritative source for interest cost
and receipts (the debt-cycle tripwire). Endpoints vary per dataset; pass the full
resource path and the field to read."""
from __future__ import annotations
from datetime import date

import requests

from .base import Source

_BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"


class TreasurySource(Source):
    name = "treasury"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def series(self, series_id: str) -> tuple[date, float]:
        """series_id encodes 'resource_path::value_field::date_field'."""
        resource, value_field, date_field = series_id.split("::")
        params = {
            "fields": f"{value_field},{date_field}",
            "sort": f"-{date_field}",
            "page[size]": 1,
        }
        r = requests.get(f"{_BASE}{resource}", params=params, timeout=self.timeout)
        r.raise_for_status()
        row = r.json()["data"][0]
        return date.fromisoformat(row[date_field]), float(row[value_field])
