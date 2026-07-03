"""Turns a scoring.run() result into the rise-and-decline arc SVG from the mockup,
with the composite marker, per-gauge ticks, and the uncertainty band all placed
from live numbers. Pure function -> string, so it works in Streamlit, a static
page, or a PNG export. Run this module directly to write live_arc.html."""
from __future__ import annotations
import math
from pathlib import Path

# plot geometry (viewBox 1000 x 300)
X0, X1, BASE, AMP, TP, WD = 60, 940, 262, 190, 0.42, 0.24
STAGE_LABELS = ["New order", "Institutions", "Peace &\nprosperity",
                "Excess &\ngaps", "Bad finances\n& conflict", "Civil war /\nrevolution"]


def _t(stage: float) -> float:
    return max(0.0, min(1.0, (stage - 1) / 5.0))


def _x(stage: float) -> float:
    return X0 + _t(stage) * (X1 - X0)


def _y(stage: float) -> float:
    t = _t(stage)
    return BASE - AMP * math.exp(-(((t - TP) / WD) ** 2))


def _curve_path(n: int = 64) -> str:
    pts = []
    for i in range(n + 1):
        s = 1 + 5 * i / n
        pts.append(f"{_x(s):.1f},{_y(s):.1f}")
    return "M" + " L".join(pts)


def render_arc(result: dict, cfg: dict) -> str:
    comp = result["composite"]
    lo, hi = result["band"]
    xlo, xhi = _x(lo), _x(hi)

    # per-gauge ticks
    tick_svg = ""
    tick_color = {"internal_order": "#c4553b", "debt_money": "#d9a441", "external_order": "#c98a2e"}
    tick_short = {"internal_order": "internal", "debt_money": "debt", "external_order": "external"}
    for c, stage in result["gauges"].items():
        x, y = _x(stage), _y(stage)
        tick_svg += (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{tick_color[c]}"/>'
            f'<text x="{x:.1f}" y="{y-11:.1f}" text-anchor="middle" '
            f'font-family="IBM Plex Mono,monospace" font-size="10.5" fill="#9aa4b8">'
            f'{tick_short[c]} {stage:.1f}</text>'
        )

    # stage dividers + labels
    div_svg, lab_svg = "", ""
    for k in range(1, 6):
        xd = X0 + k * (X1 - X0) / 6
        div_svg += f'<line x1="{xd:.1f}" y1="20" x2="{xd:.1f}" y2="272" stroke="rgba(232,230,223,.09)"/>'
    for k, lab in enumerate(STAGE_LABELS):
        xc = X0 + (k + 0.5) * (X1 - X0) / 6
        cur = " font-weight='600' fill='#e8e6df'" if (k + 1) == round(comp) else " fill='#8a93a6'"
        for li, line in enumerate(lab.split("\n")):
            safe = line.replace("&", "&amp;")
            lab_svg += (f'<text x="{xc:.1f}" y="{288 + li*11:.1f}" text-anchor="middle" '
                        f'font-family="IBM Plex Sans,sans-serif" font-size="10"{cur}>{safe}</text>')
        lab_svg += (f'<text x="{xc:.1f}" y="{16:.1f}" text-anchor="middle" '
                    f'font-family="IBM Plex Mono,monospace" font-size="10" fill="#c6a15b">0{k+1}</text>')

    cx, cy = _x(comp), _y(comp)
    return f'''<svg viewBox="0 0 1000 305" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Rise and decline arc; composite stage {comp:.2f}">
  <defs>
    <linearGradient id="band" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#3f7a5c"/><stop offset="42%" stop-color="#5aa17a"/>
      <stop offset="58%" stop-color="#d9a441"/><stop offset="78%" stop-color="#c98a2e"/>
      <stop offset="100%" stop-color="#c4553b"/>
    </linearGradient>
    <filter id="glow"><feGaussianBlur stdDeviation="4" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  {div_svg}
  <rect x="{xlo:.1f}" y="20" width="{max(xhi-xlo,2):.1f}" height="252" fill="rgba(232,230,223,.06)"/>
  <line x1="{xlo:.1f}" y1="20" x2="{xlo:.1f}" y2="272" stroke="rgba(232,230,223,.18)" stroke-dasharray="2 3"/>
  <line x1="{xhi:.1f}" y1="20" x2="{xhi:.1f}" y2="272" stroke="rgba(232,230,223,.18)" stroke-dasharray="2 3"/>
  <path d="{_curve_path()}" fill="none" stroke="url(#band)" stroke-width="3.5" stroke-linecap="round"/>
  {tick_svg}
  <g filter="url(#glow)">
    <line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx:.1f}" y2="272" stroke="rgba(232,230,223,.28)" stroke-dasharray="2 4"/>
    <circle cx="{cx:.1f}" cy="{cy:.1f}" r="8.5" fill="#0d1420" stroke="#e8e6df" stroke-width="2"/>
    <circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.4" fill="#e8e6df"/>
  </g>
  <text x="{cx:.1f}" y="{cy-16:.1f}" text-anchor="middle" font-family="Spectral,serif"
        font-style="italic" font-size="15" fill="#e8e6df">{cfg['meta']['country']} · {comp:.2f}</text>
  {lab_svg}
</svg>'''


def page(svg: str, result: dict) -> str:
    lo, hi = result["band"]
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,500;1,400&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono&display=swap" rel="stylesheet">
<style>body{{margin:0;background:#0d1420;color:#e8e6df;font-family:'IBM Plex Sans',sans-serif;padding:28px}}
.h{{font-family:Spectral,serif;font-size:26px;margin:0 0 2px}}.s{{color:#8a93a6;font-family:'IBM Plex Mono',monospace;font-size:12px;letter-spacing:.04em}}
.wrap{{max-width:1040px;margin:0 auto}}</style></head>
<body><div class="wrap"><div class="h">Composite stage {result['composite']:.2f}
<span style="color:#c4553b">· band [{lo:.2f}, {hi:.2f}]</span></div>
<div class="s">rendered from live scoring · correlation widens the band by {result['widening_pct']:.0f}%</div>
<div style="margin-top:18px">{svg}</div></div></body></html>'''


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from bcm import scoring
    from bcm.store import Store

    root = Path(__file__).resolve().parents[1]
    cfg = scoring.load_config(root / "config" / "thresholds.yaml")
    store = Store(root / "data" / "bcm.duckdb")
    result = scoring.run(cfg, store.latest_values())
    out = root / "live_arc.html"
    out.write_text(page(render_arc(result, cfg), result))
    print(f"wrote {out}")
