"""Maps each thresholds.yaml indicator to how it's fetched.

kinds:
  fred          value = series(s0) * scale
  fred_ratio    value = series(s0) / series(s1) * scale
  gdelt         value = series(s0)                (query string)
  csv           value = latest row of data/manual/<file> * scale   (no network)

Everything that lacks a clean public API is `csv`: you keep a two-column
date,value file per indicator (BIS, SIPRI, COFER, DW-NOMINATE, Pew, ACLED, ...)
and append a row when new data drops. `scripts/init_manual.py` bootstraps those
files from the config's illustrative readings so the repo runs before you've
sourced anything by hand.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Spec:
    kind: str
    series: list[str] = field(default_factory=list)
    scale: float = 1.0
    unit: str = ""
    note: str = ""


INDICATORS: dict[str, Spec] = {
    # ---- automatable from FRED --------------------------------------------
    "gov_debt_gdp":         Spec("fred", ["GFDEGDQ188S"], 1.0, "% of GDP"),
    "policy_room":          Spec("fred", ["DFF"], 1.0, "policy rate %"),
    "top1_wealth_share":    Spec("fred", ["WFRBST01134"], 1.0, "% of net worth"),
    "income_gini":          Spec("fred", ["SIPOVGINIUSA"], 0.01, "Gini 0..1"),
    "interest_pct_revenue": Spec("fred_ratio", ["A091RC1Q027SBEA", "W006RC1Q027SBEA"], 100.0, "% fed revenue"),
    "cb_balance_sheet_gdp": Spec("fred_ratio", ["WALCL", "GDP"], 0.1, "% of GDP"),

    # ---- real-time geopolitical proxy (GDELT) -----------------------------
    "conflict_intensity":   Spec("gdelt", ["(conflict OR war OR sanctions OR military)"], 1.0, "0..100"),

    # ---- periodic download / curated -> CSV -------------------------------
    "total_nonfin_debt_gdp":  Spec("csv", ["total_nonfin_debt_gdp.csv"], 1.0, "% of GDP", "BIS credit-to-non-financial-sector"),
    "foreign_treasury_share": Spec("csv", ["foreign_treasury_share.csv"], 1.0, "%", "Treasury TIC"),
    "reserve_currency_share": Spec("csv", ["reserve_currency_share.csv"], 1.0, "%", "IMF COFER"),
    "political_polarization": Spec("csv", ["political_polarization.csv"], 1.0, "0..1", "Voteview DW-NOMINATE"),
    "institutional_trust":    Spec("csv", ["institutional_trust.csv"], 1.0, "%", "Pew / Gallup"),
    "populist_vote_share":    Spec("csv", ["populist_vote_share.csv"], 1.0, "%", "curated election data"),
    "unrest_events":          Spec("csv", ["unrest_events.csv"], 1.0, "0..100", "ACLED US Crisis Monitor"),
    "rival_power_gap":        Spec("csv", ["rival_power_gap.csv"], 1.0, "0..1", "power index vs top rival"),
    "military_balance":       Spec("csv", ["military_balance.csv"], 1.0, "%", "SIPRI milex ratio"),
    "five_wars_composite":    Spec("csv", ["five_wars_composite.csv"], 1.0, "0..1", "5 war-type sub-gauges"),
    "bloc_alignment":         Spec("csv", ["bloc_alignment.csv"], 1.0, "0..1", "GDELT alliance clustering"),
}
