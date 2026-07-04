"""Renders the gauge panels: for each cycle, a labeled 3-column grid
(Indicator | Value | Stage) with no visible gridlines, natural-language labels,
and a click-to-expand definition behind an unobtrusive info icon (native
<details> — no JavaScript). Also assembles a standalone dashboard page combining
the arc + panels so you can see everything by opening one file."""
from __future__ import annotations
from pathlib import Path

import yaml

from .arc import render_arc
from .scoring import CYCLES

_INFO = ("<svg viewBox='0 0 16 16' width='13' height='13' fill='none' "
         "stroke='currentColor' stroke-width='1.4'><circle cx='8' cy='8' r='6.4'/>"
         "<line x1='8' y1='7.2' x2='8' y2='11'/><circle cx='8' cy='4.9' r='.5' fill='currentColor'/></svg>")


def load_meta(path: str | Path = "config/indicator_meta.yaml") -> dict:
    return yaml.safe_load(open(path))


# ---- the "About" content, shared by the static page and the Streamlit app ----
ABOUT_SECTIONS: list[tuple[str, str]] = [
    ("What the Big Cycle is",
     "Ray Dalio studied 500 years of empires and found they rise and decline through a "
     "repeatable life cycle, pushed along by three interacting forces: a debt & money cycle, "
     "an internal-order cycle driven by wealth, values, and political gaps, and an external-order "
     "cycle of rivalry between powers. The internal cycle runs through six stages — from a new "
     "order (1), through peace and prosperity (3), into excess and widening gaps (4), then bad "
     "finances and acute conflict (5), and finally civil war or revolution (6), which resets it."),
    ("Why it matters",
     "Knowing roughly where a country sits tells you which risks are rising and which are fading — "
     "whether it's early in a build-out or late in a fragile, indebted, divided phase. It's a lens "
     "for context and preparation, not a prediction of dates or events."),
    ("How to read the arc",
     "The curve is the archetypal rise and decline. The glowing marker is the composite estimate; "
     "the three smaller ticks are the individual cycle gauges, placed where each one lands. When "
     "they spread apart, that disagreement is the signal — the cycles are telling different stories."),
    ("Read the band, not the decimal",
     "The composite is shown as a range, not a point, because the inputs are noisy and the cycles "
     "are correlated — a debt crisis feeds internal disorder, so they partly measure the same stress. "
     "Accounting for that widens the band by about 40%, a deliberate guard against false confidence. "
     "Treat “Stage 5” as “roughly late-cycle,” never as a precise measurement."),
    ("The indicator panels",
     "Each cycle lists its indicators with the actual underlying value and its 1–6 stage score. "
     "Click the ⓘ beside any one for what it measures, why Dalio weights it, and its data source."),
    ("How to use it",
     "This is a structured argument, not an oracle. In the interactive app the weight controls let "
     "you re-weight the three cycles and watch the estimate move — poke at it rather than trusting it. "
     "And the stage numbers are only as good as the anchors behind them, which are documented judgment; "
     "until they're calibrated against real data, treat the readings as illustrative."),
]


def about_html() -> str:
    body = "".join(f"<p><b>{h}.</b> {b}</p>" for h, b in ABOUT_SECTIONS)
    return f'''<details class="bcm-about"><summary>{_INFO}
        <span>About · what the Big Cycle is and how to read this dashboard</span>
        <span class="caret">&#9662;</span></summary>
      <div class="bcm-about-body">{body}</div></details>'''


def _fmt(value: float, suffix: str) -> str:
    return f"{value:g}{suffix}"


def _panel(label: str, stage: float, sigma: float, rows: list[dict]) -> str:
    body = "".join(
        f'''<div class="bcm-row">
              <div class="bcm-lab">{r['label']}
                <details class="bcm-def"><summary aria-label="definition">{_INFO}</summary>
                  <div class="bcm-body">{r['definition']}
                    <div class="bcm-src">Source: {r['source']}</div></div></details>
              </div>
              <div class="bcm-num">{r['value']}</div>
              <div class="bcm-num bcm-stage">{r['stage']:.1f}</div>
            </div>''' for r in rows)
    return f'''<div class="bcm-panel">
        <div class="bcm-h">{label}</div>
        <div class="bcm-cap">stage {stage:.2f} · σ {sigma:.2f}</div>
        <div class="bcm-row bcm-hdr"><div>Indicator</div>
          <div class="bcm-num">Value</div><div class="bcm-num">Stage</div></div>
        {body}
      </div>'''


def render_panels(result: dict, readings: dict, cfg: dict, meta: dict) -> str:
    panels = ""
    for c in CYCLES:
        rows = []
        for name, stage in result["details"][c].items():
            m = meta.get(name, {})
            rows.append({
                "label": m.get("label", name),
                "definition": m.get("definition", "No definition available."),
                "source": m.get("source", "—"),
                "value": _fmt(readings.get(name, float("nan")), m.get("suffix", "")),
                "stage": stage,
            })
        panels += _panel(cfg[c]["label"], result["gauges"][c], result["sigmas"][c], rows)
    return f'<div class="bcm-panels">{panels}</div>'


STYLE = """<style>
  .bcm-panels{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;font-family:'IBM Plex Sans',system-ui,sans-serif}
  @media(max-width:860px){.bcm-panels{grid-template-columns:1fr}}
  .bcm-panel{background:rgba(23,34,53,.5);border:1px solid rgba(232,230,223,.08);border-radius:14px;padding:18px 18px 12px}
  .bcm-h{font-family:Spectral,Georgia,serif;font-size:17px;color:#e8e6df;margin-bottom:2px}
  .bcm-cap{font-family:'IBM Plex Mono',monospace;font-size:11px;color:#8a93a6;margin-bottom:12px}
  .bcm-row{display:grid;grid-template-columns:1fr auto auto;gap:6px 16px;align-items:baseline;padding:7px 0}
  .bcm-hdr{font-family:'IBM Plex Mono',monospace;font-size:9.5px;letter-spacing:.15em;text-transform:uppercase;color:#5f6a80;padding-bottom:2px}
  .bcm-lab{font-size:13px;color:#d7d9de}
  .bcm-num{font-family:'IBM Plex Mono',monospace;font-size:12.5px;text-align:right;color:#9aa4b8;white-space:nowrap}
  .bcm-stage{color:#c6a15b}
  .bcm-def{display:inline}
  .bcm-def summary{list-style:none;cursor:pointer;color:#4d576b;vertical-align:middle;margin-left:5px;transition:color .15s}
  .bcm-def summary::-webkit-details-marker{display:none}
  .bcm-def summary:hover,.bcm-def[open] summary{color:#c6a15b}
  .bcm-body{margin:7px 0 3px;padding:9px 11px;border-left:2px solid rgba(198,161,91,.45);
            background:rgba(232,230,223,.035);border-radius:0 7px 7px 0;
            font-size:12px;line-height:1.55;color:#9aa4b8}
  .bcm-src{margin-top:6px;font-family:'IBM Plex Mono',monospace;font-size:10.5px;
           letter-spacing:.02em;color:#6b7488}
  .bcm-about{background:rgba(23,34,53,.5);border:1px solid rgba(198,161,91,.16);
             border-radius:12px;margin:16px 0 6px;overflow:hidden}
  .bcm-about summary{list-style:none;cursor:pointer;padding:13px 16px;display:flex;
             align-items:center;gap:9px;font-family:'IBM Plex Mono',monospace;font-size:11px;
             letter-spacing:.1em;text-transform:uppercase;color:#c6a15b;transition:color .15s}
  .bcm-about summary::-webkit-details-marker{display:none}
  .bcm-about summary:hover{color:#e3c98a}
  .bcm-about .caret{margin-left:auto;transition:transform .2s;color:#5f6a80}
  .bcm-about[open] .caret{transform:rotate(180deg)}
  .bcm-about-body{padding:2px 18px 16px;max-width:74ch}
  .bcm-about-body p{margin:13px 0;font-size:13px;line-height:1.62;color:#c2c6ce}
  .bcm-about-body b{color:#e8e6df;font-weight:600}
</style>"""


def dashboard_page(result: dict, readings: dict, cfg: dict, meta: dict,
                   histories: dict | None = None) -> str:
    from .charts import render_history_section, HISTORY_STYLE
    lo, hi = result["band"]
    name = cfg.get("_name", cfg["meta"]["country"])
    arc = render_arc(result, cfg)
    panels = render_panels(result, readings, cfg, meta)
    history = render_history_section(histories, cfg, meta) if histories else ""
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Big Cycle Monitor — {name}</title>
<link href="https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,500;1,400&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono&display=swap" rel="stylesheet">
{STYLE}
{HISTORY_STYLE}
<style>
  body{{margin:0;background:#0d1420;color:#e8e6df;font-family:'IBM Plex Sans',sans-serif;padding:30px 22px 60px}}
  .wrap{{max-width:1120px;margin:0 auto}}
  h1{{font-family:Spectral,serif;font-weight:500;font-size:34px;margin:0}}
  .cap{{font-family:'IBM Plex Mono',monospace;color:#8a93a6;font-size:12px;letter-spacing:.04em;margin-top:4px}}
  .big{{font-family:Spectral,serif;font-size:30px}}.big span{{color:#c4553b}}
  .arc-wrap{{margin:20px 0 26px;background:linear-gradient(180deg,#141e2f,#101827);
             border:1px solid rgba(198,161,91,.16);border-radius:16px;padding:18px}}
</style></head><body><div class="wrap">
  <h1>Big Cycle Monitor — {name}</h1>
  <div class="cap">composite <span class="big"><span>{result['composite']:.1f}</span></span>
       · band [{lo:.1f}, {hi:.1f}] · correlation widens the band by {result['widening_pct']:.0f}%
       · <a href="macro.html" style="color:#c6a15b;text-decoration:none">Macro Health →</a></div>
  {about_html()}
  <div class="arc-wrap">{arc}</div>
  {panels}
  {history}
  <div class="cap" style="margin-top:22px">Click the ⓘ beside any indicator for what it measures and why it matters.
       Values illustrative until <code>refresh</code> pulls live sources.</div>
</div></body></html>'''


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from bcm import scoring
    from bcm.store import Store

    root = Path(__file__).resolve().parents[1]
    cfg = scoring.load_config(root / "config" / "thresholds.yaml")
    meta = load_meta(root / "config" / "indicator_meta.yaml")
    readings = Store(root / "data" / "bcm.duckdb").latest_values()
    result = scoring.run(cfg, readings)
    out = root / "live_dashboard.html"
    out.write_text(dashboard_page(result, readings, cfg, meta))
    print(f"wrote {out}")
