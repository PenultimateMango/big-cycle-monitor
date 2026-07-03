"""Time-series charts: one SVG per indicator, styled to match the dashboard.

Design notes
------------
* Pure inline SVG, no JS — consistent with arc.py, works on GitHub Pages and
  inside Streamlit components.html alike.
* Background STAGE BANDS: the indicator's own (value, stage) anchors are
  inverted to find the value at each integer stage boundary, and those
  horizontal regions get a red tint that deepens toward stage 6. The line
  crossing into a darker band IS the story — "when did this metric enter
  Stage-5 territory" is readable at a glance. Anchors that fall (e.g. trust:
  lower = later stage) invert cleanly too; if anchors aren't monotonic in
  stage the bands are skipped rather than drawn wrong.
* Dense series (daily fed funds ~ 26k points) are downsampled by stride to
  ~240 points, always keeping the final observation.
"""
from __future__ import annotations

from datetime import date

W, H = 560, 190
PAD_L, PAD_R, PAD_T, PAD_B = 46, 34, 12, 22
MAX_PTS = 240

# stage tint: transparent through deepening ember (matches #c4553b accent)
_BAND_ALPHA = {1: 0.0, 2: 0.0, 3: 0.025, 4: 0.06, 5: 0.115, 6: 0.18}


def _downsample(rows: list[tuple[date, float]]) -> list[tuple[date, float]]:
    if len(rows) <= MAX_PTS:
        return rows
    stride = len(rows) / (MAX_PTS - 1)
    keep = [rows[int(i * stride)] for i in range(MAX_PTS - 1)]
    keep.append(rows[-1])                       # never lose the latest point
    return keep


def _stage_boundaries(anchors: list) -> list[tuple[float, float]] | None:
    """Invert (value, stage) anchors -> [(boundary_value, upper_stage), ...].

    Returns the value at each integer stage crossing within the anchor range,
    or None if stage isn't monotonic across value-sorted anchors (can't invert).
    """
    import numpy as np
    pts = sorted(anchors, key=lambda p: p[0])
    vals = [float(p[0]) for p in pts]
    stgs = [float(p[1]) for p in pts]
    diffs = np.diff(stgs)
    if len(pts) < 2 or not (all(d >= 0 for d in diffs) or all(d <= 0 for d in diffs)):
        return None
    rising = stgs[-1] >= stgs[0]
    s_sorted = stgs if rising else stgs[::-1]
    v_sorted = vals if rising else vals[::-1]
    lo_s, hi_s = min(stgs), max(stgs)
    out = []
    for s in range(2, 7):                       # boundaries entering stages 2..6
        if lo_s <= s <= hi_s:
            out.append((float(np.interp(s, s_sorted, v_sorted)), float(s)))
    return out


def render_chart(rows: list[tuple[date, float]], label: str, suffix: str = "",
                 anchors: list | None = None) -> str:
    """One indicator's history as a self-contained SVG string."""
    rows = sorted(rows, key=lambda r: r[0])
    if len(rows) < 3:
        return (f'<div class="bcm-chart bcm-chart-empty"><div class="bcm-ch-h">{label}</div>'
                f'<div class="bcm-ch-note">history builds as refreshes and manual '
                f'rows accumulate ({len(rows)} point{"s" if len(rows) != 1 else ""} so far)</div></div>')
    rows = _downsample(rows)
    xs = [r[0].toordinal() for r in rows]
    ys = [r[1] for r in rows]
    x0, x1 = min(xs), max(xs)
    y_lo, y_hi = min(ys), max(ys)

    # widen y-range so nearby stage boundaries show as context, then pad
    bounds = _stage_boundaries(anchors) if anchors else None
    if bounds:
        near = [v for v, _ in bounds if y_lo - 0.6 * (y_hi - y_lo or 1) <= v <= y_hi + 0.6 * (y_hi - y_lo or 1)]
        if near:
            y_lo, y_hi = min(y_lo, *near), max(y_hi, *near)
    span = (y_hi - y_lo) or abs(y_hi) or 1.0
    y_lo, y_hi = y_lo - 0.07 * span, y_hi + 0.07 * span

    def X(o): return PAD_L + (o - x0) / max(x1 - x0, 1) * (W - PAD_L - PAD_R)
    def Y(v): return PAD_T + (y_hi - v) / (y_hi - y_lo) * (H - PAD_T - PAD_B)

    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
             f'font-family="IBM Plex Mono,monospace" role="img" aria-label="{label} history">']

    # ---- stage bands (regions between boundary values, tinted by stage) ----
    if bounds:
        rising = len(bounds) < 2 or bounds[0][0] < bounds[-1][0]   # value direction of later stages
        edges = sorted([v for v, _ in bounds])
        # walk regions bottom-of-range -> top; find each region's stage tint
        import numpy as np
        pts = sorted(anchors, key=lambda p: p[0])
        av = [float(p[0]) for p in pts]; ast = [float(p[1]) for p in pts]
        regions = [y_lo] + edges + [y_hi]
        for a, b in zip(regions, regions[1:]):
            if b <= y_lo or a >= y_hi:
                continue
            mid_stage = float(np.interp((a + b) / 2, av, ast))
            # the region between the S(n) and S(n+1) boundaries IS stage-n
            # territory — floor, don't round, or S5 land tints like S6
            alpha = _BAND_ALPHA.get(int(min(max(mid_stage, 1), 6)), 0.0)
            if alpha > 0:
                ya, yb = Y(min(b, y_hi)), Y(max(a, y_lo))
                parts.append(f'<rect x="{PAD_L}" y="{ya:.1f}" width="{W-PAD_L-PAD_R}" '
                             f'height="{max(yb-ya,0):.1f}" fill="rgba(196,85,59,{alpha})"/>')
        for v, s in bounds:                     # hairline + right-edge label
            if y_lo < v < y_hi:
                yy = Y(v)
                parts.append(f'<line x1="{PAD_L}" x2="{W-PAD_R}" y1="{yy:.1f}" y2="{yy:.1f}" '
                             f'stroke="rgba(232,230,223,.07)" stroke-width="1"/>')
                lab_s = int(s) if rising else int(s)  # band ABOVE line is stage s when rising
                parts.append(f'<text x="{W-PAD_R+4}" y="{yy+3:.1f}" font-size="8.5" '
                             f'fill="#5f6a80">S{lab_s}</text>')

    # ---- line + soft area fill ----
    pth = " ".join(f"{X(x):.1f},{Y(v):.1f}" for x, v in zip(xs, ys))
    base = Y(y_lo)
    parts.append(f'<polygon points="{X(xs[0]):.1f},{base:.1f} {pth} {X(xs[-1]):.1f},{base:.1f}" '
                 f'fill="rgba(198,161,91,.07)"/>')
    parts.append(f'<polyline points="{pth}" fill="none" stroke="#c6a15b" '
                 f'stroke-width="1.6" stroke-linejoin="round"/>')

    # ---- latest point + value ----
    lx, ly = X(xs[-1]), Y(ys[-1])
    parts.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="#e3c98a"/>')
    anchor = "end" if lx > W - 90 else "start"
    tx = lx - 7 if anchor == "end" else lx + 7
    parts.append(f'<text x="{tx:.1f}" y="{ly-6:.1f}" font-size="10" text-anchor="{anchor}" '
                 f'fill="#e3c98a">{ys[-1]:g}{suffix}</text>')

    # ---- axes: y min/max, x first/last year ----
    for v, yy in ((y_hi, PAD_T + 8), (y_lo, H - PAD_B - 2)):
        parts.append(f'<text x="{PAD_L-6}" y="{yy:.1f}" font-size="8.5" text-anchor="end" '
                     f'fill="#5f6a80">{v:.3g}</text>')
    parts.append(f'<text x="{PAD_L}" y="{H-6}" font-size="8.5" fill="#5f6a80">{rows[0][0].year}</text>')
    parts.append(f'<text x="{W-PAD_R}" y="{H-6}" font-size="8.5" text-anchor="end" '
                 f'fill="#5f6a80">{rows[-1][0].year}</text>')
    parts.append("</svg>")
    svg = "".join(parts)
    return (f'<div class="bcm-chart"><div class="bcm-ch-h">{label}'
            f'<span class="bcm-ch-n">{len(rows)} obs · {rows[0][0].year}–{rows[-1][0].year}</span>'
            f'</div>{svg}</div>')


def _anchors_for(cfg: dict, name: str):
    from .scoring import CYCLES
    for c in CYCLES:
        ind = cfg[c]["indicators"].get(name)
        if ind and "anchors" in ind:
            return ind["anchors"]
    return None


def render_history_section(histories: dict[str, list], cfg: dict, meta: dict) -> str:
    """Charts grouped by cycle, in config order. Empty histories render a stub."""
    from .scoring import CYCLES
    blocks = ""
    for c in CYCLES:
        cards = ""
        for name, ind in cfg[c]["indicators"].items():
            if ind.get("applicable") is False:
                continue
            m = meta.get(name, {})
            cards += render_chart(histories.get(name, []), m.get("label", name),
                                  m.get("suffix", ""), _anchors_for(cfg, name))
        blocks += (f'<div class="bcm-hist-cycle"><div class="bcm-hist-h">{cfg[c]["label"]}</div>'
                   f'<div class="bcm-hist-grid">{cards}</div></div>')
    return (f'<div class="bcm-history"><div class="bcm-hist-title">Indicator history'
            f'<span class="bcm-hist-cap">shaded bands mark later-stage territory · '
            f'the dot is the latest reading</span></div>{blocks}</div>')


HISTORY_STYLE = """<style>
  .bcm-history{margin-top:26px}
  .bcm-hist-title{font-family:Spectral,Georgia,serif;font-size:19px;color:#e8e6df;margin-bottom:4px}
  .bcm-hist-cap{font-family:'IBM Plex Mono',monospace;font-size:10.5px;color:#5f6a80;margin-left:12px;letter-spacing:.03em}
  .bcm-hist-cycle{margin-top:16px}
  .bcm-hist-h{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.16em;
              text-transform:uppercase;color:#c6a15b;margin:10px 0 8px}
  .bcm-hist-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
  @media(max-width:860px){.bcm-hist-grid{grid-template-columns:1fr}}
  .bcm-chart{background:rgba(23,34,53,.5);border:1px solid rgba(232,230,223,.08);
             border-radius:12px;padding:12px 12px 6px}
  .bcm-chart svg{width:100%;height:auto;display:block}
  .bcm-ch-h{font-size:12.5px;color:#d7d9de;margin-bottom:6px}
  .bcm-ch-n{font-family:'IBM Plex Mono',monospace;font-size:9.5px;color:#5f6a80;float:right}
  .bcm-chart-empty{min-height:70px}
  .bcm-ch-note{font-family:'IBM Plex Mono',monospace;font-size:10px;color:#5f6a80;
               padding:16px 0 12px;line-height:1.5}
</style>"""
