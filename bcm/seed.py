"""Offline seeding: write the illustrative current_reading values from the config
into the store so the transform/score/store layers run end-to-end without network.
`refresh` later overwrites the automatable ones with live pulls."""
from __future__ import annotations
from datetime import date, datetime

from .scoring import CYCLES
from .sources.base import Observation
from .store import Store


def seed(cfg: dict, store: Store, country: str = "US") -> int:
    n = 0
    for c in CYCLES:
        for name, ind in cfg[c]["indicators"].items():
            if "current_reading" not in ind:
                continue
            store.upsert(
                Observation(
                    indicator=name,
                    value=float(ind["current_reading"]),
                    obs_date=date.today(),
                    source="seed",
                    unit=ind.get("unit", ""),
                    as_of=datetime.utcnow(),
                ),
                country=country,
            )
            n += 1
    return n
