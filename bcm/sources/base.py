"""Common types for data sources. A Source turns a series_id into (date, value)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Observation:
    indicator: str          # matches a key in thresholds.yaml
    value: float            # already in the unit the anchors expect
    obs_date: date          # date of the underlying data point
    source: str             # 'fred' | 'treasury' | 'gdelt' | 'manual' | 'seed'
    series_id: str = ""
    unit: str = ""
    as_of: datetime = field(default_factory=datetime.utcnow)   # when we pulled it


class Source:
    """Minimal contract: return the most recent (date, value) for a series_id."""
    name = "base"

    def series(self, series_id: str) -> tuple[date, float]:
        raise NotImplementedError
