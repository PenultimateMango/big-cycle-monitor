# Big Cycle Monitor

Tracks where a country sits on Ray Dalio's Big Cycle framework — the three
stage-mapped cycles (internal order, debt/money, external order) blended into a
single composite **band** (not a false-precision point). Built US-first, designed
to clone per country by config.

## Quick start

```bash
pip install -r requirements.txt

python scripts/init_manual.py     # bootstrap data/manual/*.csv from illustrative values
python scripts/run.py demo        # seed + score (NO network/keys)
python scripts/run.py refresh     # pull live sources (needs FRED_API_KEY); CSV + GDELT work without
python scripts/run.py score       # re-score whatever is in the store
python -m bcm.arc                 # render live_arc.html from current scores

pip install streamlit
streamlit run dashboard.py        # live dashboard: arc + gauges + adjustable weights
```

`demo` proves the transform → store → score wiring with placeholder readings.
`refresh` overwrites automatable indicators with live data; unreachable sources
fail per-indicator and leave the last value standing. The dashboard re-weights
the three gauges and the band width live.

## Layout

```
config/thresholds.yaml     scoring rules: anchors, weights, correlation, country overrides
bcm/
  sources/                 one client per API — all return (date, value)
    fred.py                real; needs FRED_API_KEY  (6 indicators)
    treasury.py            real; no key (interest cost / receipts)
    gdelt.py               real; no key (conflict-tone proxy)
    csv_source.py          local CSVs for BIS/SIPRI/COFER/DW-NOMINATE/Pew/ACLED
    base.py                Observation + Source contract
  registry.py              indicator -> (source, series_id, transform)
  store.py                 DuckDB: tidy long table + latest-per-indicator read
  scoring.py               anchors -> gauges -> correlated composite band
  arc.py                   scoring result -> the rise/decline arc SVG
  pipeline.py              refresh(): fetch what it can, never halt
  seed.py                  offline seeding from config current_reading
dashboard.py               Streamlit: live arc + gauges + adjustable weights
scripts/
  run.py                   CLI: demo | refresh | score
  init_manual.py           bootstrap data/manual/*.csv
data/
  bcm.duckdb               created at runtime
  manual/*.csv             two-column date,value files you append to
```

## What automates vs what's manual

Only ~6 indicators pull cleanly from FRED today (debt/GDP, interest/revenue,
Fed balance sheet, policy rate, top-1% wealth, Gini). Conflict tone comes from
GDELT. The rest — reserve share (IMF COFER), polarization (DW-NOMINATE), trust
(Pew), SIPRI military balance, populist vote, unrest (ACLED) — need specialized
loaders or manual updates and are marked `manual` in `registry.py`. That split is
deliberate and honest: the geopolitical/social signals don't have clean public
APIs. Add them as dedicated `Source` subclasses over time.

To go live:
1. `export FRED_API_KEY=...` (free: https://fred.stlouisfed.org/docs/api/api_key.html)
2. `python scripts/run.py refresh`
3. Wire manual indicators via CSV loaders or a small admin step.
4. Schedule `refresh` on mixed cadences (GitHub Actions cron per source).

## Adding a country

Everything is US-first but country-ready. Add a block under `country_overrides`
in `thresholds.yaml` (see the `CHN` stub) overriding only what differs — reserve
applicability, FX-denominated debt, anchor shifts, source swaps, `rival_power_gap`
sign for a rising power. The store already partitions by `country`; scoring and
composite math are country-agnostic. Regions (Europe, Africa, S. America) can be
GDP-weighted composites of member states, the way Dalio treats the Eurozone.

## Honesty notes

- Composite is a **band**; correlation between cycles widens it ~40% vs assuming
  independence. Don't report the decimal as if it were measured.
- Anchors and correlations are documented judgment, not fitted parameters.
  Calibrate against Dalio's Great Powers Index or US historical percentiles.
- `current_reading` values in the config are illustrative until `refresh` runs.
```
