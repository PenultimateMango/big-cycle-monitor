"""Scoring: raw readings dict -> per-gauge stages -> correlated composite band.
Same math proven in the standalone scorer.py, now consuming values from the store."""
from __future__ import annotations
import itertools
from pathlib import Path

import numpy as np
import yaml

CYCLES = ["internal_order", "debt_money", "external_order"]


def load_config(path: str | Path = "config/thresholds.yaml") -> dict:
    return yaml.safe_load(open(path))


def score_indicator(value: float, anchors: list) -> float:
    pts = sorted(anchors, key=lambda p: p[0])
    xs = np.array([p[0] for p in pts], float)
    ys = np.array([p[1] for p in pts], float)
    return float(np.interp(value, xs, ys))


def score_gauge(cycle_cfg: dict, readings: dict[str, float]) -> tuple[float, float, dict]:
    stages, weights, detail = [], [], {}
    for name, ind in cycle_cfg["indicators"].items():
        if ind.get("applicable") is False or "anchors" not in ind:
            continue
        if name not in readings:                 # no data yet -> skip, renormalize
            continue
        s = score_indicator(readings[name], ind["anchors"])
        stages.append(s); weights.append(ind["weight"]); detail[name] = round(s, 2)
    if not stages:
        return float("nan"), float("nan"), detail
    stages, weights = np.array(stages), np.array(weights)
    weights = weights / weights.sum()
    mean = float(weights @ stages)
    sigma = float(np.sqrt(weights @ (stages - mean) ** 2))
    return mean, sigma, detail


def _cov(sigmas: dict, corr: dict) -> np.ndarray:
    d = np.array([sigmas[c] for c in CYCLES])
    R = np.eye(3)
    for i, j in itertools.combinations(range(3), 2):
        key = f"{CYCLES[i]}__{CYCLES[j]}"
        R[i, j] = R[j, i] = corr.get(key, corr.get(f"{CYCLES[j]}__{CYCLES[i]}", 0.0))
    return np.diag(d) @ R @ np.diag(d)


def run(cfg: dict, readings: dict[str, float]) -> dict:
    gauges, sigmas, details = {}, {}, {}
    for c in CYCLES:
        m, disp, detail = score_gauge(cfg[c], readings)
        gauges[c] = m
        sigmas[c] = max(disp, cfg["composite"]["gauge_sigma"][c]) if disp == disp else cfg["composite"]["gauge_sigma"][c]
        details[c] = detail

    comp = cfg["composite"]
    w = np.array([comp["gauge_weights"][c] for c in CYCLES]); w = w / w.sum()
    g = np.array([gauges[c] for c in CYCLES])
    point = float(w @ g)
    z = comp["band_z"]
    Sigma = _cov(sigmas, comp["correlation"])
    sd_corr = float(np.sqrt(w @ Sigma @ w))
    sd_naive = float(np.sqrt(np.sum((w * np.array([sigmas[c] for c in CYCLES])) ** 2)))
    return {
        "gauges": gauges, "sigmas": sigmas, "details": details,
        "composite": point,
        "band_naive": (point - z * sd_naive, point + z * sd_naive),
        "band": (point - z * sd_corr, point + z * sd_corr),
        "widening_pct": (sd_corr / sd_naive - 1) * 100 if sd_naive else 0.0,
    }
