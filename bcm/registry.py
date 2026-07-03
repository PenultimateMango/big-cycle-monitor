"""Maps each thresholds.yaml indicator to how it's fetched.

kinds:
  fred          value = series(s0) * scale
  fred_ratio    value = series(s0) / series(s1) * scale
  wb_ratio      value = worldbank(s0) / worldbank(s1) * scale
  gdelt         value = series(s0)                (query string -> 0..100 stress)
  csv           value = latest row of data/manual/<file> * scale   (no network)

AUTOMATION STATUS (see README for the full table):
  auto      FRED, World Bank, GDELT, FRED-ratios — real endpoints, run on the cron
  manual    no clean public API OR inherently curated/judgment — kept as CSV you
            append to. Automating these would mean fabricating a feed, so we don't.
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
    # ---- AUTO: FRED -------------------------------------------------------
    "gov_debt_gdp":         Spec("fred", ["GFDEGDQ188S"], 1.0, "% of GDP"),
    "policy_room":          Spec("fred", ["DFF"], 1.0, "policy rate %"),
    "top1_wealth_share":    Spec("fred", ["WFRBST01134"], 1.0, "% of net worth"),
    "income_gini":          Spec("fred", ["SIPOVGINIUSA"], 0.01, "Gini 0..1"),
    # --- RATIO INDICATORS: two traps to check whenever you swap a series ---
    #   (1) units    — one series in $millions, another in $billions => 1000x error
    #   (2) stock vs flow — a STOCK (a level, e.g. debt outstanding) is the full
    #                       amount at a point in time (a quarterly obs is NOT 1/4).
    #                       a FLOW (per-period, e.g. interest paid) only divides
    #                       cleanly against another flow on the SAME basis. FRED
    #                       flows are often "seasonally adjusted annual rate", so
    #                       flow/flow is safe when BOTH are annualized (it cancels).
    #
    # interest_pct_revenue: FLOW / FLOW. Both are seas.-adj. ANNUAL RATE ($B), so the
    #   annualization cancels -> ~18-20%. scale 100 = percent.
    "interest_pct_revenue": Spec("fred_ratio", ["A091RC1Q027SBEA", "W006RC1Q027SBEA"], 100.0, "% fed revenue"),
    # cb_balance_sheet_gdp: STOCK / FLOW by design (like debt/GDP). WALCL is a stock
    #   ($millions); GDP is annualized flow ($billions). 0.1 scale bridges M vs B.
    "cb_balance_sheet_gdp": Spec("fred_ratio", ["WALCL", "GDP"], 0.1, "% of GDP"),
    # foreign_treasury_share: STOCK / STOCK -> magnitude-safe. FDHBFIN is $billions
    #   (quarterly), FYGFDPUN is $millions (annual) -> x100000 for M-vs-B + percent.
    #   Numerator quarterly, denominator annual: a small TIMING drift, not a scale bug.
    #   Share of debt HELD BY THE PUBLIC (excl. intragov't) — the market-demand basis. ~30%.
    "foreign_treasury_share": Spec("fred_ratio", ["FDHBFIN", "FYGFDPUN"], 100000.0, "%"),

    # ---- AUTO: World Bank (SIPRI-sourced military expenditure, USD) --------
    # military_balance: FLOW / FLOW, both annual mil-spend in current USD -> safe.
    "military_balance":     Spec("wb_ratio", ["CHN/MS.MIL.XPND.CD", "USA/MS.MIL.XPND.CD"], 100.0, "%"),

    # ---- AUTO: GDELT real-time tone proxies -------------------------------
    "conflict_intensity":   Spec("gdelt", ["(conflict OR war OR sanctions OR military)"], 1.0, "0..100"),
    "unrest_events":        Spec("gdelt", ["sourcecountry:US (protest OR riot OR unrest OR strike)"], 1.0, "0..100"),

    # ---- MANUAL: no clean public API -> CSV -------------------------------
    "total_nonfin_debt_gdp":  Spec("csv", ["total_nonfin_debt_gdp.csv"], 1.0, "% of GDP", "BIS credit-to-non-financial-sector (quarterly download)"),
    "reserve_currency_share": Spec("csv", ["reserve_currency_share.csv"], 1.0, "%", "IMF COFER (quarterly; SDMX API automatable — verify series key)"),
    "institutional_trust":    Spec("csv", ["institutional_trust.csv"], 1.0, "%", "Pew (no API; OECD trust is an automatable swap)"),
    "political_polarization": Spec("csv", ["political_polarization.csv"], 1.0, "0..1", "Voteview DW-NOMINATE (yearly; scriptable download + compute)"),

    # ---- MANUAL: inherently curated / judgment ----------------------------
    "populist_vote_share":  Spec("csv", ["populist_vote_share.csv"], 1.0, "%", "per-election; curated"),
    "rival_power_gap":      Spec("csv", ["rival_power_gap.csv"], 1.0, "0..1", "output of your own power model"),
    "five_wars_composite":  Spec("csv", ["five_wars_composite.csv"], 1.0, "0..1", "Dalio escalation ladder; judgment composite"),
    "bloc_alignment":       Spec("csv", ["bloc_alignment.csv"], 1.0, "0..1", "alliance clustering; judgment"),
}


# ---- COUNTRY AWARENESS -------------------------------------------------------
# FRED is US-only. For other countries the automatable backbone is World Bank
# (change the ISO3 code) + GDELT; the rest are per-country CSVs sourced from
# cross-national datasets (WID, V-Dem, ACLED, BIS, IMF). These World Bank series
# IDs are high-confidence but UNVERIFIED against the live API from here — smoke-
# test on first run; a wrong code fails that one indicator, not the whole run.

_ISO2 = {"US": "US", "CHN": "CN", "RUS": "RU", "IND": "IN", "JPN": "JP",
         "DEU": "GM", "BRA": "BR", "ZAF": "SF"}

_CSV_ONLY = (
    "top1_wealth_share", "total_nonfin_debt_gdp", "interest_pct_revenue",
    "cb_balance_sheet_gdp", "policy_room", "foreign_treasury_share",
    "political_polarization", "institutional_trust", "populist_vote_share",
    "rival_power_gap", "five_wars_composite", "bloc_alignment",
)


def intl_profile(iso3: str, reserve_issuer: bool = False) -> dict:
    """World Bank + GDELT where possible, CSV for the rest. iso3 e.g. 'CHN'."""
    iso2 = _ISO2.get(iso3, iso3[:2])
    prof: dict[str, Spec] = {
        "gov_debt_gdp":     Spec("wb", [f"{iso3}/GC.DOD.TOTL.GD.ZS"], 1.0, "% of GDP", "World Bank central-govt debt — verify"),
        "income_gini":      Spec("wb", [f"{iso3}/SI.POV.GINI"], 0.01, "Gini 0..1", "World Bank"),
        "military_balance": Spec("wb_ratio", [f"{iso3}/MS.MIL.XPND.CD", "USA/MS.MIL.XPND.CD"], 100.0, "%", "World Bank (vs US)"),
        "conflict_intensity": Spec("gdelt", ["(conflict OR war OR sanctions OR military)"], 1.0, "0..100"),
        "unrest_events":    Spec("gdelt", [f"sourcecountry:{iso2} (protest OR riot OR unrest OR strike)"], 1.0, "0..100"),
    }
    for name in _CSV_ONLY:
        prof[name] = Spec("csv", [f"{name}.csv"], 1.0, "", "cross-national source (WID / V-Dem / ACLED / BIS) — populate per country")
    if reserve_issuer:
        prof["reserve_currency_share"] = Spec("csv", ["reserve_currency_share.csv"], 1.0, "%", "IMF COFER")
    return prof


def indicators_for(country: str) -> dict:
    """US uses the FRED-rich map; everyone else uses the World Bank profile."""
    if country == "US":
        return INDICATORS
    return intl_profile(country, reserve_issuer=(country in {"JPN"}))
