#!/usr/bin/env python
"""Big Cycle Monitor — live dashboard.

    pip install streamlit
    streamlit run dashboard.py

Reads whatever is in the store (run `scripts/run.py refresh` first for live data;
falls back to `demo` seed values otherwise). The sidebar re-weights the three
gauges and the band width live — so 'is Dalio right?' becomes something you can
poke at, not take on faith."""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from bcm import scoring
from bcm.arc import render_arc
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


@st.cache_resource
def _base_cfg():
    return scoring.load_config(ROOT / "config" / "thresholds.yaml")


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
c1.metric("Composite stage", f"{res['composite']:.2f}", help="1 = new order · 6 = civil war/revolution")
c2.metric("Band", f"{lo:.2f}–{hi:.2f}", f"+{res['widening_pct']:.0f}% vs independent", delta_color="off")
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
