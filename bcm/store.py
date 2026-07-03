"""DuckDB-backed store. One tidy long table of observations; latest-per-indicator
read powers the scorer. File-based, zero-server, fast — ideal for this."""
from __future__ import annotations
from pathlib import Path

import duckdb

from .sources.base import Observation

_SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    indicator  TEXT,
    obs_date   DATE,
    value      DOUBLE,
    source     TEXT,
    series_id  TEXT,
    unit       TEXT,
    as_of      TIMESTAMP,
    country    TEXT DEFAULT 'US'
);
"""


class Store:
    def __init__(self, path: str | Path = "data/bcm.duckdb"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(path))
        self.con.execute(_SCHEMA)

    def upsert(self, obs: Observation, country: str = "US") -> None:
        # append-only history; latest_values() picks the freshest per indicator
        self.con.execute(
            "INSERT INTO observations VALUES (?,?,?,?,?,?,?,?)",
            [obs.indicator, obs.obs_date, obs.value, obs.source,
             obs.series_id, obs.unit, obs.as_of, country],
        )

    def latest_values(self, country: str = "US") -> dict[str, float]:
        rows = self.con.execute(
            """
            SELECT indicator, value FROM observations
            WHERE country = ?
            QUALIFY row_number() OVER
                (PARTITION BY indicator ORDER BY obs_date DESC, as_of DESC) = 1
            """,
            [country],
        ).fetchall()
        return {ind: val for ind, val in rows}

    def close(self) -> None:
        self.con.close()
