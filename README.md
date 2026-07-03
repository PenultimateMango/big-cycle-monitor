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

Every indicator with a real public endpoint is automated and runs on the cron.
The rest have no clean public API or are inherently curated — automating them
would mean fabricating a feed, so they stay CSV files you append to.

| Indicator | Status | Source |
|-----------|--------|--------|
| gov_debt_gdp, policy_room, top1_wealth_share, income_gini | auto | FRED |
| interest_pct_revenue, cb_balance_sheet_gdp | auto | FRED (ratio) |
| foreign_treasury_share | auto | FRED (FDHBFIN / GFDEBTN) |
| military_balance | auto | World Bank (SIPRI mil-exp, CHN/USA) |
| conflict_intensity, unrest_events | auto | GDELT tone proxy |
| total_nonfin_debt_gdp | manual | BIS — quarterly download |
| reserve_currency_share | manual | IMF COFER — SDMX automatable, verify key |
| political_polarization | manual | Voteview — yearly, scriptable |
| institutional_trust | manual | Pew (no API; OECD is a swap option) |
| populist_vote_share | manual | per-election, curated |
| rival_power_gap | manual | output of your own power model |
| five_wars_composite, bloc_alignment | manual | Dalio judgment composites |

The GDELT proxies (conflict, unrest) are tone-based and rough — fine as a live
signal, worth upgrading to the GDELT Events table (Goldstein scores) via BigQuery
later. To go live: `export FRED_API_KEY=...` then `python scripts/run.py refresh`.
World Bank and GDELT need no key. Manual indicators keep their last CSV value.

## Adding a country or region

The machinery is country-first: the store partitions by `country`, scoring is
country-agnostic, and `resolve_country()` deep-merges a profile onto the US base.
A worked example ships — run `python scripts/run.py demo CHN` and China lands at
composite ~3.5 (ascending) vs the US ~4.5 (late), through the merge, not hardcoding.

**Steps to add one (e.g. India):**
1. Add a display name under `country_meta:` in `thresholds.yaml` (`IND: India`).
2. Add an `IND:` block under `country_overrides:` with a `current_reading` for each
   indicator, plus `anchors`/`applicable: false` where the context differs (drop
   reserve status, add `debt_in_own_currency`, flip `rival_power_gap` for a riser).
3. `python scripts/run.py demo IND` to score it offline.
4. For live data, `indicators_for("IND")` already routes to the World Bank profile;
   populate `data/manual/IND/*.csv` for the indicators without a public API.

**Be honest about the difficulty tiers — they are not equal:**

- *Ports cleanly:* the debt cycle and parts of the external cycle. World Bank
  (change the ISO3), BIS, and IMF cover debt/GDP, military spend, and Gini for
  most countries.
- *Needs re-sourcing:* the internal-order cycle. Its US indicators (DW-NOMINATE,
  Pew, Fed DFA) have no global twins — swap to cross-national datasets: WID.world
  (inequality, all countries), V-Dem (polarization, trust), ACLED (unrest).
- *Genuinely hard / caveated:*
  - **Authoritarian states (China, Russia):** "polarization" and "trust" are
    near-meaningless where there are no competitive elections and the press is
    controlled. China's low internal-disorder reading here is partly a measurement
    artifact — note the σ on that gauge blows out to ~1.0, which is the model
    honestly flagging it doesn't trust its own number. Read those with care.
  - **Russia:** official data is opaque and politicized post-sanctions; treat
    everything as low-confidence.
  - **Regions (W. Europe, E. Europe, Africa, S. America):** a continent is not one
    civilization. Options, worst to best: pick the dominant economy as a proxy;
    GDP-weight member states into a composite; or treat a genuine bloc (the Eurozone,
    which Dalio does) as a unit. Africa and South America as single Big Cycle readings
    are the weakest — better as a small panel of their largest economies.

The dashboard's country selector reads `country_meta`, so every profile you add
shows up automatically.

## Honesty notes

- Composite is a **band**; correlation between cycles widens it ~40% vs assuming
  independence. Don't report the decimal as if it were measured.
- Anchors and correlations are documented judgment, not fitted parameters.
  Calibrate against Dalio's Great Powers Index or US historical percentiles.
- `current_reading` values in the config are illustrative until `refresh` runs.
```

## Time-series charts (added)

Every indicator now renders a history chart on the dashboard — line + latest
reading, with **stage-band shading** derived from that indicator's own anchors:
the tint deepens toward Stage-6 territory, so "when did this metric cross into
Stage 5" is readable at a glance (bands sit at the top for rising-is-later
indicators like debt, at the bottom for falling-is-later ones like trust).

Two structural additions:
* **`media_trust`** — Gallup's mass-media trust series (same question since
  1972; 72% then, 28% now), Dalio's loss-of-shared-truth Stage-5 marker, scored
  in `internal_order`. Ships pre-seeded in `data/manual/media_trust.csv`;
  append one row each September when Gallup publishes.
* **Five-wars split** — `five_wars_composite` is now DERIVED: the mean of five
  first-class manual series (`trade_war.csv`, `technology_war.csv`,
  `capital_war.csv`, `geopolitical_war.csv`, `military_war.csv`). Update the
  sub-war you've re-rated; the composite and its history recompute. Only the
  composite is scored (no quintuple-counting), but all five chart individually,
  so divergence between fronts — tech war raging while military stays cool —
  is visible instead of averaged away. `five_wars_composite.csv` is obsolete
  and no longer read.

Where history comes from:
* **FRED / World Bank indicators** — `python scripts/run.py backfill` pulls the
  full published series (decades) in one call per indicator. The CI workflow
  runs this every refresh, since the DuckDB store is rebuilt from scratch each run.
* **Manual indicators** — the chart is your CSV: every row you've appended in
  `data/manual/*.csv` plots. Append, never replace, and the chart grows.
* **GDELT indicators** — no history endpoint; their charts build up from
  accumulated runs.

Ratio indicators are backfilled **date-aligned**: each numerator observation is
paired with the nearest denominator observation (≤400 days), which handles the
quarterly-numerator / annual-denominator cadence of `foreign_treasury_share`
properly across the whole series.
