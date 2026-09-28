"""Static SVG figures. No invented points."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.locks import reports_dir


def _svg(path: Path, body: str, width: int = 640, height: int = 360) -> None:
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">{body}</svg>\n',
        encoding="utf-8",
    )


def histogram(path: Path, q2: pd.Series, q3: pd.Series, title: str) -> None:
    a = q2.dropna().astype(float).to_numpy()
    b = q3.dropna().astype(float).to_numpy()
    if len(a) == 0 or len(b) == 0:
        _svg(path, f'<text x="20" y="40">{title}: OBSERVATION_UNAVAILABLE</text>')
        return
    lo = float(min(a.min(), b.min()))
    hi = float(max(a.max(), b.max()))
    if hi <= lo:
        hi = lo + 1
    bins = np.linspace(lo, hi, 13)
    ha, _ = np.histogram(a, bins=bins)
    hb, _ = np.histogram(b, bins=bins)
    peak = max(int(ha.max()), int(hb.max()), 1)
    parts = [f'<text x="16" y="24" fill="#e8e6df" font-size="14">{title}</text>']
    width = 640
    height = 360
    for i, (ca, cb) in enumerate(zip(ha, hb)):
        x = 40 + i * ((width - 80) / len(ha))
        w = ((width - 80) / len(ha)) / 2.2
        ha_h = 260 * ca / peak
        hb_h = 260 * cb / peak
        parts.append(f'<rect x="{x}" y="{300-ha_h}" width="{w}" height="{ha_h}" fill="#7dce9a"/>')
        parts.append(f'<rect x="{x+w}" y="{300-hb_h}" width="{w}" height="{hb_h}" fill="#6e8cff"/>')
    parts.append('<text x="40" y="330" fill="#8b8f98" font-size="11">Q2 green · Q3 blue</text>')
    _svg(path, "".join(parts), width, height)


def scatter(path: Path, x: np.ndarray, y: np.ndarray, labels: list[str], title: str) -> None:
    if len(x) == 0:
        _svg(path, f'<text x="20" y="40">{title}: no points</text>')
        return
    xs = (x - x.min()) / (x.max() - x.min() + 1e-12)
    ys = (y - y.min()) / (y.max() - y.min() + 1e-12)
    parts = [f'<text x="16" y="24" fill="#e8e6df" font-size="14">{title}</text>']
    for px, py, lab in zip(xs, ys, labels):
        color = "#7dce9a" if lab in {"Q2", "survive", True, "1"} else "#6e8cff"
        if lab in {False, "T40", "0"}:
            color = "#e07a7a"
        parts.append(
            f'<circle cx="{40 + px * 560:.1f}" cy="{320 - py * 270:.1f}" r="3" fill="{color}" opacity="0.75"/>'
        )
    _svg(path, "".join(parts))


def write_figures(features: pd.DataFrame, labels: pd.DataFrame, pca: dict, dest: Path | None = None) -> list[str]:
    folder = dest or reports_dir()
    folder.mkdir(parents=True, exist_ok=True)
    joined = features.merge(labels[["instance_id", "s"]], on="instance_id")
    q2 = joined[joined["period"] == "Q2"]
    q3 = joined[joined["period"] == "Q3"]
    names = []
    pairs = [
        ("fig01_margin.svg", "bought_margin", "Q2 vs Q3 score margin"),
        ("fig02_clock.svg", "frac_period_remaining", "Q2 vs Q3 period remaining"),
        ("fig03_open.svg", "pregame_cents", "Q2 vs Q3 opening price"),
        ("fig04_velocity.svg", "velocity_5m", "Q2 vs Q3 pre-80 5m velocity"),
        ("fig05_range.svg", "range_5m", "Q2 vs Q3 pre-80 5m range"),
    ]
    for fname, col, title in pairs:
        path = folder / fname
        histogram(path, q2[col], q3[col], title)
        names.append(str(path.name))
    points = pca["points"]
    scatter(
        folder / "fig06_pca_period.svg",
        np.array([p["pc1"] for p in points]),
        np.array([p["pc2"] for p in points]),
        [p["period"] for p in points],
        "PCA Q2 vs Q3",
    )
    scatter(
        folder / "fig07_pca_outcome.svg",
        np.array([p["pc1"] for p in points]),
        np.array([p["pc2"] for p in points]),
        ["survive" if p["s"] else "T40" for p in points],
        "PCA survive vs T40",
    )
    names.extend(["fig06_pca_period.svg", "fig07_pca_outcome.svg"])
    missing = []
    for col in [c for c in features.columns if c.endswith("__status")]:
        missing.append(float((features[col] != "OBSERVED").mean()))
    body = ['<text x="16" y="24" fill="#e8e6df" font-size="14">Feature missingness</text>']
    for i, rate in enumerate(missing[:40]):
        body.append(
            f'<rect x="20" y="{40 + i * 7}" width="{max(1, rate * 600):.1f}" height="5" fill="#c4b48a"/>'
        )
    _svg(folder / "fig10_missingness.svg", "".join(body), 640, max(360, 50 + 7 * min(40, len(missing))))
    names.append("fig10_missingness.svg")
    return names
