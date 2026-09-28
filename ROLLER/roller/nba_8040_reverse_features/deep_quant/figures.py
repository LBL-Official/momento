"""PHASE 20 — standalone research figures. SVG only."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.locks import figures_dir


def _svg(path: Path, body: str, width: int = 720, height: int = 400) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="background:#111">{body}</svg>\n',
        encoding="utf-8",
    )


def _hist(path: Path, left: np.ndarray, right: np.ndarray, title: str, legend: str) -> None:
    a = left[np.isfinite(left)]
    b = right[np.isfinite(right)]
    if len(a) == 0 or len(b) == 0:
        _svg(path, f'<text x="20" y="40" fill="#eee">{title}: unavailable</text>')
        return
    lo = float(min(a.min(), b.min()))
    hi = float(max(a.max(), b.max()))
    if hi <= lo:
        hi = lo + 1
    bins = np.linspace(lo, hi, 16)
    ha, _ = np.histogram(a, bins=bins)
    hb, _ = np.histogram(b, bins=bins)
    peak = max(int(ha.max()), int(hb.max()), 1)
    parts = [f'<text x="16" y="24" fill="#e8e6df" font-size="14">{title}</text>']
    for i, (ca, cb) in enumerate(zip(ha, hb)):
        x = 40 + i * (640 / len(ha))
        w = (640 / len(ha)) / 2.3
        parts.append(f'<rect x="{x}" y="{340-260*ca/peak}" width="{w}" height="{260*ca/peak}" fill="#7dce9a"/>')
        parts.append(f'<rect x="{x+w}" y="{340-260*cb/peak}" width="{w}" height="{260*cb/peak}" fill="#6e8cff"/>')
    parts.append(f'<text x="40" y="380" fill="#8b8f98" font-size="11">{legend}</text>')
    _svg(path, "".join(parts))


def _scatter(path: Path, x: np.ndarray, y: np.ndarray, colors: list[str], title: str) -> None:
    if len(x) == 0:
        _svg(path, f'<text x="20" y="40" fill="#eee">{title}</text>')
        return
    xs = (x - x.min()) / (x.max() - x.min() + 1e-12)
    ys = (y - y.min()) / (y.max() - y.min() + 1e-12)
    parts = [f'<text x="16" y="24" fill="#e8e6df" font-size="14">{title}</text>']
    for px, py, color in zip(xs, ys, colors):
        parts.append(
            f'<circle cx="{50+px*640:.1f}" cy="{350-py*300:.1f}" r="3" fill="{color}" opacity="0.75"/>'
        )
    _svg(path, "".join(parts))


def _bars(path: Path, labels: list[str], values: list[float], title: str) -> None:
    parts = [f'<text x="16" y="24" fill="#e8e6df" font-size="14">{title}</text>']
    peak = max(values) if values else 1
    for i, (lab, val) in enumerate(zip(labels, values)):
        h = 260 * val / (peak + 1e-12)
        x = 40 + i * (640 / max(len(labels), 1))
        parts.append(f'<rect x="{x}" y="{340-h}" width="28" height="{h}" fill="#c4b48a"/>')
        parts.append(f'<text x="{x}" y="370" fill="#8b8f98" font-size="10">{lab}</text>')
    _svg(path, "".join(parts))


def write_figures(payload: dict) -> list[str]:
    dest = figures_dir()
    dest.mkdir(parents=True, exist_ok=True)
    pca = payload["pca"]
    aligned = payload["aligned"]
    scores = pca["scores"]
    names = []

    _bars(
        dest / "01_pca_explained_variance.svg",
        [f"PC{i+1}" for i in range(min(8, len(pca["explained"])))],
        pca["explained"][:8],
        "PCA explained variance",
    )
    names.append("01_pca_explained_variance.svg")

    period_colors = ["#7dce9a" if p == "Q2" else "#6e8cff" for p in aligned["period"]]
    _scatter(dest / "02_pc1_pc2_by_period.svg", scores[:, 0], scores[:, 1], period_colors, "PC1 vs PC2 by period")
    names.append("02_pc1_pc2_by_period.svg")
    t40_colors = ["#e07a7a" if t else "#7dce9a" for t in aligned["t40"]]
    _scatter(dest / "03_pc1_pc2_by_t40.svg", scores[:, 0], scores[:, 1], t40_colors, "PC1 vs PC2 by T40")
    names.append("03_pc1_pc2_by_t40.svg")
    s_colors = ["#7dce9a" if s else "#e07a7a" for s in aligned["s"]]
    _scatter(dest / "04_pc1_pc2_by_survival.svg", scores[:, 0], scores[:, 1], s_colors, "PC1 vs PC2 by survival")
    names.append("04_pc1_pc2_by_survival.svg")

    q2 = scores[aligned["period"].eq("Q2"), 0]
    q3 = scores[aligned["period"].eq("Q3"), 0]
    _hist(dest / "05_pc1_q2_vs_q3.svg", q2, q3, "PC1 Q2 vs Q3", "Q2 green · Q3 blue")
    names.append("05_pc1_q2_vs_q3.svg")

    geom = payload["geometry"]
    _hist(
        dest / "06_cross_period_nearest_distance.svg",
        geom["nearest_q2_to_q3"],
        geom["nearest_q3_to_q2"],
        "Nearest cross-period distance",
        "Q2→Q3 green · Q3→Q2 blue",
    )
    names.append("06_cross_period_nearest_distance.svg")

    null = payload["null"]["agreement"]
    _bars(
        dest / "07_knn_agreement_vs_null.svg",
        [f"k={row['k']}" for row in null],
        [row["observed_agreement"] for row in null],
        "Observed KNN agreement (null bands in report)",
    )
    names.append("07_knn_agreement_vs_null.svg")

    msum = payload["match_summary"]
    q2m = next(row for row in msum if row["source_period"] == "Q2")
    q3m = next(row for row in msum if row["source_period"] == "Q3")
    _bars(
        dest / "08_q2_to_q3_matched_t40.svg",
        ["Q2 own", "matched Q3"],
        [q2m["source_t40"], q2m["matched_t40"]],
        "Q2 → Q3 matched T40",
    )
    names.append("08_q2_to_q3_matched_t40.svg")
    _bars(
        dest / "09_q3_to_q2_matched_t40.svg",
        ["Q3 own", "matched Q2"],
        [q3m["source_t40"], q3m["matched_t40"]],
        "Q3 → Q2 matched T40",
    )
    names.append("09_q3_to_q2_matched_t40.svg")

    share = pca["class_share"][0] if pca["class_share"] else {}
    keys = [k for k in share if k != "pc"]
    _bars(
        dest / "10_pc1_feature_class_share.svg",
        keys,
        [float(share[k]) for k in keys],
        "PC1 squared-loading share by feature class",
    )
    names.append("10_pc1_feature_class_share.svg")

    temporal = payload["temporal"]
    _bars(
        dest / "11_temporal_pc1_smd.svg",
        list(temporal.keys()),
        [abs((temporal[k]["composition"][0]["smd"] or 0.0)) for k in temporal],
        "PC1 |SMD| Q2 vs Q3 under time variants",
    )
    names.append("11_temporal_pc1_smd.svg")

    thr = [row for row in payload["thresholds"] if row.get("direction") == "Q2_to_Q3" and "difference" in row]
    _bars(
        dest / "12_matched_state_t40_diff.svg",
        [f"q={row['quantile']}" for row in thr],
        [row["difference"] for row in thr],
        "Q2−matched-Q3 T40 at pre-specified distance quantiles",
    )
    names.append("12_matched_state_t40_diff.svg")
    return names
