"""Macro Health page — a second dashboard of core economic vitals with a
red/amber/green stoplight per metric and a heat-map strip up top, so the whole
economy reads at a glance.

Design decisions:
* Bands are EXPLICIT config (config/macro.yaml) — documented judgment, exactly
  like the Big Cycle anchors. Anything not matching a green/amber rule is red.
* Charts show the series the transform produces; for asset prices the chart
  shows the LEVEL but the stoplight judges the YoY CHANGE (status_on: yoy),
  because a price level has no health meaning but a spike or drawdown does.
* No DuckDB — this page fetches live at build time (CI or local) and renders
  static HTML. FRED does YoY server-side (units=pc1); Stooq covers gold,
  equities, and Bitcoin.
"""
from __future__ import annotations

import bisect
import html as _html
from datetime import date, timedelta
from pathlib import Path

import yaml

from .charts import HISTORY_STYLE, fmt_val, render_chart
from .pipeline import _align_ratio
from .sources.fred import FredSource
from .sources.stooq import StooqSource

Rows = list[tuple[date, float]]


def load_macro_config(path: str | Path = "config/macro.yaml") -> dict:
    return yaml.safe_load(open(path))


# ---------------------------------------------------------------- transforms
def yoy(rows: Rows, tol_days: int = 45) -> Rows:
    """Year-over-year % change: each point vs the nearest obs ~365 days back."""
    if len(rows) < 2:
        return []
    ords = [d.toordinal() for d, _ in rows]
    out: Rows = []
    for d, v in rows:
        target = d.toordinal() - 365
        i = bisect.bisect_left(ords, target)
        best = None
        for j in (i - 1, i):
            if 0 <= j < len(rows):
                gap = abs(ords[j] - target)
                if gap <= tol_days and (best is None or gap < best[0]):
                    best = (gap, rows[j][1])
        if best and best[1]:
            out.append((d, (v / best[1] - 1) * 100))
    return out


def _trim(rows: Rows, years: int | None) -> Rows:
    if not years or not rows:
        return rows
    cutoff = rows[-1][0] - timedelta(days=int(years * 365.25))
    return [r for r in rows if r[0] >= cutoff]


# ------------------------------------------------------------------ fetching
def fetch_metric(m: dict, fred: FredSource, stooq: StooqSource) -> Rows:
    kind, series = m["kind"], m["series"]
    tr = m.get("transform", "level")
    if kind == "fred":
        rows = fred.history(series[0], units="pc1" if tr == "pc1" else None)
    elif kind == "fred_ratio":
        rows = _align_ratio(fred.history(series[0]), fred.history(series[1]), 1.0)
    elif kind == "stooq":
        rows = stooq.history(series[0])
    else:
        raise ValueError(f"unknown kind {kind}")
    if tr == "yoy":
        rows = yoy(rows)
    return rows


# ----------------------------------------------------------------- stoplight
def status_for(value: float, bands: list) -> str:
    """First matching [lo, hi, color] wins; null = open end; no match = red."""
    for lo, hi, color in bands or []:
        if (lo is None or value >= lo) and (hi is None or value < hi):
            return color
    return "red"


def evaluate(m: dict, rows: Rows) -> tuple[str, float | None]:
    """(stoplight color, the value the light judged)."""
    if not rows:
        return "red", None
    judged = yoy(rows) if m.get("status_on") == "yoy" else rows
    if not judged:
        return "red", None
    v = judged[-1][1]
    return status_for(v, m.get("bands")), v


# ----------------------------------------------------------------- rendering
def _fmt(v: float | None, suffix: str, decimals: int | None = None) -> str:
    return "—" if v is None else fmt_val(v, decimals, suffix)


def build_page(cfg: dict, fetched: dict[str, tuple[dict, Rows, str, float | None]],
               failures: dict[str, str]) -> str:
    """fetched: name -> (metric_cfg, rows, color, judged_value)."""
    counts = {"green": 0, "amber": 0, "red": 0}
    tiles, sections = "", ""
    for group in cfg["groups"]:
        cards = ""
        for name, m in group["metrics"].items():
            mcfg, rows, color, jv = fetched[name]
            counts[color] += 1
            # tiles judged on YoY show the YoY % (1dp); others use their own units
            if mcfg.get("status_on") == "yoy":
                tv = "—" if jv is None else f"{jv:+.1f}% YoY"
            else:
                tv = _fmt(jv, mcfg.get("suffix", ""), mcfg.get("decimals"))
            tiles += (f'<a class="mh-tile mh-{color}" href="#{name}">'
                      f'<span class="mh-dot"></span><span class="mh-tl">{mcfg["label"]}</span>'
                      f'<span class="mh-tv">{tv}</span></a>')
            chart = render_chart(_trim(rows, mcfg.get("window_years")), mcfg["label"],
                                 mcfg.get("suffix", ""), None, badge=color, card_id=name,
                                 decimals=mcfg.get("decimals"))
            note = failures.get(name)
            if note:  # escape HTML; also break Liquid tokens so a raw error
                # body can never trip Jekyll even without .nojekyll
                note = _html.escape(note).replace("{%", "{ %").replace("{{", "{ {")
            src = (f'<div class="mh-src">{mcfg.get("source","")}'
                   + (f' · <span class="mh-fail">fetch failed: {note}</span>' if note else "")
                   + f'</div><div class="mh-def">{mcfg.get("definition","")}</div>')
            cards += f'<div class="mh-card">{chart}{src}</div>'
        sections += (f'<div class="bcm-hist-cycle"><div class="bcm-hist-h">{group["label"]}</div>'
                     f'<div class="bcm-hist-grid">{cards}</div></div>')

    n = sum(counts.values()) or 1
    summary = " · ".join(f"{counts[c]} {c}" for c in ("green", "amber", "red"))
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Macro Health — Big Cycle Monitor</title>
<link href="https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,500;1,400&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono&display=swap" rel="stylesheet">
{HISTORY_STYLE}
<style>
  body{{margin:0;background:#0d1420;color:#e8e6df;font-family:'IBM Plex Sans',sans-serif;padding:30px 22px 60px}}
  .wrap{{max-width:1120px;margin:0 auto}}
  h1{{font-family:Spectral,serif;font-weight:500;font-size:34px;margin:0}}
  .cap{{font-family:'IBM Plex Mono',monospace;color:#8a93a6;font-size:12px;letter-spacing:.04em;margin-top:4px}}
  .cap a{{color:#c6a15b;text-decoration:none}}
  .mh-strip{{display:grid;grid-template-columns:repeat(auto-fill,minmax(196px,1fr));gap:8px;margin:20px 0 8px}}
  .mh-tile{{display:flex;align-items:center;gap:8px;padding:9px 11px;border-radius:9px;text-decoration:none;
            background:rgba(23,34,53,.5);border:1px solid rgba(232,230,223,.07);transition:border-color .15s}}
  .mh-tile:hover{{border-color:rgba(198,161,91,.4)}}
  .mh-dot{{width:10px;height:10px;border-radius:50%;flex:none}}
  .mh-green .mh-dot{{background:#5da364;box-shadow:0 0 7px rgba(93,163,100,.55)}}
  .mh-amber .mh-dot{{background:#d9a94b;box-shadow:0 0 7px rgba(217,169,75,.55)}}
  .mh-red .mh-dot{{background:#c4553b;box-shadow:0 0 7px rgba(196,85,59,.65)}}
  .mh-tl{{font-size:11.5px;color:#d7d9de;line-height:1.25;flex:1}}
  .mh-tv{{font-family:'IBM Plex Mono',monospace;font-size:10.5px;color:#8a93a6;white-space:nowrap}}
  .mh-card .bcm-chart{{border-radius:12px 12px 0 0;border-bottom:none}}
  .mh-src{{font-family:'IBM Plex Mono',monospace;font-size:10px;color:#6b7488;padding:8px 13px 0;
           background:rgba(23,34,53,.5);border-left:1px solid rgba(232,230,223,.08);border-right:1px solid rgba(232,230,223,.08)}}
  .mh-fail{{color:#c4553b}}
  .mh-def{{font-size:11.5px;line-height:1.5;color:#9aa4b8;padding:4px 13px 11px;background:rgba(23,34,53,.5);
           border:1px solid rgba(232,230,223,.08);border-top:none;border-radius:0 0 12px 12px}}
</style></head><body><div class="wrap">
  <h1>Macro Health</h1>
  <div class="cap">{summary} of {n} · stoplights judge the latest reading against
    documented bands in <code>config/macro.yaml</code> · asset lights judge YoY change, charts show level
    · <a href="index.html">← Big Cycle Monitor</a></div>
  <div class="mh-strip">{tiles}</div>
  {sections}
  <div class="cap" style="margin-top:22px">Sources are official (BLS/BEA/Census/Treasury/Fed via FRED)
    except gold, equity indices, and Bitcoin, which use Stooq (unofficial, labeled). Bands are judgment —
    edit them in the config rather than trusting them.</div>
</div></body></html>'''


def build(config_path: str | Path = "config/macro.yaml",
          fred: FredSource | None = None, stooq: StooqSource | None = None,
          verbose: bool = True) -> str:
    """Fetch everything, evaluate stoplights, return the rendered page.
    Per-metric failures render as an empty chart + red light + failure note —
    one dead source never kills the page."""
    cfg = load_macro_config(config_path)
    fred, stooq = fred or FredSource(), stooq or StooqSource(timeout=8)
    fetched, failures = {}, {}

    def _one(name, mm):
        """(rows, color, judged_value, failure_note|None) — never raises."""
        try:
            rows = fetch_metric(mm, fred, stooq)
            c, jv = evaluate(mm, rows)
            return rows, c, jv, None
        except Exception as e:
            fb = mm.get("fred_fallback")
            if fb:
                try:
                    rows = fred.history(fb)
                    c, jv = evaluate(mm, rows)
                    return rows, c, jv, f"Stooq unavailable — served from FRED {fb}"
                except Exception as e2:
                    return [], "red", None, f"{type(e).__name__}: {e} | fallback {fb}: {e2}"
            return [], "red", None, f"{type(e).__name__}: {e}"

    # parallel fetch: wall time ~= slowest single request instead of the sum of
    # 28 sequential ones (a hanging Stooq made the Streamlit page look frozen)
    from concurrent.futures import ThreadPoolExecutor
    items = [(name, mm) for g in cfg["groups"] for name, mm in g["metrics"].items()]
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda nm: _one(*nm), items))
    for (name, mm), (rows, color, jv, note) in zip(items, results):
        if note:
            failures[name] = note
        fetched[name] = (mm, rows, color, jv)
        if verbose:
            tail = failures.get(name, f"{color}  ({jv if jv is None else round(jv,2)})")
            print(f"  {name:<22} {len(rows):>6} obs   {tail}")
    return build_page(cfg, fetched, failures)
