"""Research charts only. Not a ROLLER UI."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def write_reliability_chart(path: Path, reliability: list[dict], title: str) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    xs, ys = [], []
    for b in reliability:
        if b.get("pred") is None:
            continue
        xs.append(b["pred"])
        ys.append(b["obs"])
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "--", color="gray")
    if xs:
        ax.scatter(xs, ys)
    ax.set_xlabel("predicted P(home win)")
    ax.set_ylabel("observed frequency")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def write_hist(path: Path, values: np.ndarray, title: str) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.hist(values, bins=20, range=(0, 1))
    ax.set_title(title)
    ax.set_xlabel("P(home win)")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
