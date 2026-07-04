#!/usr/bin/env python
"""Big Cycle Monitor — live dashboard.

    pip install streamlit
    streamlit run dashboard.py

Two pages (sidebar): the Big Cycle monitor and the Macro Health stoplight grid.
The Big Cycle store starts empty locally — use the in-app backfill button (or
`python scripts/run.py backfill`) to load full history; charts appear after.
The Macro page fetches FRED + Stooq live on load (cached ~1h)."""
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from bcm import scoring
from bcm.arc import render_arc
from bcm.charts import HISTORY_STYLE, render_history_section
from bcm.panels import ABOUT_SECTIONS, STYLE, load_meta, render_panels
from bcm.seed import seed
from bcm.store import Store

st.set_page_config(page_title="Big Cycle Monitor", layout="wide")

st.markdown("""<style>
  .stApp{background:#0d1420;color:#e8e6df}
  .block-container{max-width:1120px;padding-top:1.4rem}
  h1,h2,h3{font-family:Spectral,Georgia,serif!important}
  [data-testid="stMetricValue"]{font-family:Spectral,serif;color:#e8e6df}
  .cap{font-family:'IBM Plex Mono',monospace;color:#8a93a6;font-size:12px;letter-spacing:.04em}
</style>""", unsafe_allow_html=True)

page = st.sidebar.radio("Page", ["Big Cycle", "Macro Health"])


@st.cache_resource
def _base_cfg():
    return scoring.load_config(ROOT / "config" / "thresholds.yaml")


# ============================================================ MACRO HEALTH ==
if page == "Macro Health":
    st.markdown("# Macro Health")
    st.markdown("<div class='cap'>28 vitals, each judged red/amber/green against the "
                "bands in <code>config/macro.yaml</code>. Fetches FRED + Stooq live; "
                "cached for an hour.</div>", unsafe_allow_html=True)

    if not os.environ.get("FRED_API_KEY"):
        k = st.text_input("FRED API key (free at fred.stlouisfed.org — FRED metrics "
                          "show red 'fetch failed' without it; Stooq assets work regardless)",
                          type="password")
        if k:
            os.environ["FRED_API_KEY"] = k

    @st.cache_data(ttl=3600, show_spinner="Fetching ~28 series from FRED and Stooq…")
    def _macro_html(_key_fingerprint: str) -> str:
        from bcm.macro import build
        return build(ROOT / "config" / "macro.yaml", verbose=False)

    html = _macro_html(os.environ.get("FRED_API_KEY", "")[-4:])
    st.components.v1.html(html, height=5200, scrolling=True)
    st.stop()

# ============================================================== BIG CYCLE ==
def _readings(cfg, country):
    store = Store(ROOT / "data" / "bcm.duckdb")
    vals = store.latest_values(country=country)
    if not vals:                                  # empty store -> seed for first run
        seed(cfg, store, country=country)
        vals = store.latest_values(country=country)
    store.close()
    return vals


base = _base_cfg()
countries = list((base.get("country_meta") or {"US": "United States"}).keys())
choice = st.sidebar.selectbox("Country / region", countries,
                              format_func=lambda c: base.get("country_meta", {}).get(c, c))
cfg = scoring.resolve_country(base, choice)
readings = _readings(cfg, choice)

# ---- sidebar: live weights + band width -----------------------------------
st.sidebar.header("Weights")
st.sidebar.caption("How much each cycle counts toward the composite. Re-weight and watch the arc move.")
wi = st.sidebar.slider("Internal order", 0.0, 1.0, float(cfg["composite"]["gauge_weights"]["internal_order"]), 0.05)
wd = st.sidebar.slider("Debt & money", 0.0, 1.0, float(cfg["composite"]["gauge_weights"]["debt_money"]), 0.05)
we = st.sidebar.slider("External order", 0.0, 1.0, float(cfg["composite"]["gauge_weights"]["external_order"]), 0.05)
z = st.sidebar.slider("Band width (z)", 0.5, 2.0, float(cfg["composite"]["band_z"]), 0.1,
                      help="1.0 ≈ 68%, 1.28 ≈ 80%, 1.64 ≈ 90%")

cfg["composite"]["gauge_weights"] = {"internal_order": wi, "debt_money": wd, "external_order": we}
cfg["composite"]["band_z"] = z
res = scoring.run(cfg, readings)

# ---- header ---------------------------------------------------------------
lo, hi = res["band"]
st.markdown(f"# Big Cycle Monitor — {cfg.get('_name', cfg['meta']['country'])}")

with st.expander("About · what the Big Cycle is and how to read this dashboard"):
    for _h, _b in ABOUT_SECTIONS:
        st.markdown(f"**{_h}.** {_b}")

c1, c2, c3 = st.columns([1, 1, 2])
c1.metric("Composite stage", f"{res['composite']:.1f}", help="1 = new order · 6 = civil war/revolution")
c2.metric("Band", f"{lo:.1f}–{hi:.1f}", f"+{res['widening_pct']:.0f}% vs independent", delta_color="off")
c3.markdown(f"<div class='cap'>correlation between cycles widens the band by "
            f"{res['widening_pct']:.0f}% — the anti-double-count adjustment. "
            f"Read the band, not the decimal.</div>", unsafe_allow_html=True)

# ---- the arc --------------------------------------------------------------
st.components.v1.html(
    f"<div style='background:#0d1420'>{render_arc(res, cfg)}</div>", height=340)

# ---- gauge panels: labeled Value/Stage columns + expandable definitions ----
meta = load_meta(ROOT / "config" / "indicator_meta.yaml")
panels_html = STYLE + render_panels(res, readings, cfg, meta)
st.components.v1.html(
    f"<div style='background:#0d1420;font-family:sans-serif'>{panels_html}</div>",
    height=560, scrolling=True)

st.caption("Click the ⓘ beside any indicator for what it measures and why it matters. "
           "Values illustrative until `refresh` pulls live sources. "
           "Anchors and correlations are documented judgment, not fitted parameters.")

# ---- indicator history charts ----------------------------------------------
def _histories(country):
    store = Store(ROOT / "data" / "bcm.duckdb")
    hs = store.all_series(country=country)
    store.close()
    return hs


hists = _histories(choice)
if any(len(v) >= 3 for v in hists.values()):
    hist_html = HISTORY_STYLE + render_history_section(hists, cfg, meta)
    st.components.v1.html(
        f"<div style='background:#0d1420;font-family:sans-serif'>{hist_html}</div>",
        height=2400, scrolling=True)
else:
    # Local store is fresh (the CI database is never committed) — offer one-click backfill.
    st.info("No time-series history in the local store yet — history lives only in CI. "
            "Load it here once and the charts appear.")
    k = st.text_input("FRED API key (optional — without it, manual-CSV indicators "
                      "like media trust and the five wars still chart; FRED/World Bank ones need it)",
                      type="password", key="bf_key")
    if st.button("Load full history into local store (backfill)"):
        if k:
            os.environ["FRED_API_KEY"] = k
        from bcm.pipeline import backfill
        store = Store(ROOT / "data" / "bcm.duckdb")
        with st.spinner("Backfilling full history…"):
            status = backfill(store, country=choice, verbose=False)
        store.close()
        ok = sum(1 for v in status.values() if v.startswith("ok"))
        fails = ", ".join(f"{n}" for n, v in status.items() if v.startswith("FAIL"))
        st.success(f"{ok}/{len(status)} indicators backfilled."
                   + (f" Failed: {fails}" if fails else ""))
        st.rerun()
