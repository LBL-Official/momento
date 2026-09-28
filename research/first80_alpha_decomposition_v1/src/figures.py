"""Static figures. Research labels only."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as C


def _banner(ax):
    ax.set_title(ax.get_title() + "\nRESEARCH ONLY — NOT A FILL — NOT LIVE", fontsize=8, color="#8a6d3b")


def threshold_calibration(surf: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    q = surf["threshold_cents"].to_numpy(float)
    p = surf["p_hat"].to_numpy(float)
    lo = [r["wilson"]["lo"] if isinstance(r.get("wilson"), dict) else None for r in surf.to_dict("records")]
    # wilson stored as nested in parquet might flatten; use calibration_deviation
    ax.plot(q, q / 100.0, ls="--", color="#888", label="q (null if calibrated)")
    ax.plot(q, p, marker="o", color="#1f4e79", label="P(W | FirstReach(q))")
    ax.set_xlabel("threshold q (cents)")
    ax.set_ylabel("terminal win rate")
    ax.legend()
    ax.set_title("Threshold calibration surface")
    _banner(ax)
    fig.tight_layout()
    fig.savefig(C.FIGURES / "threshold_calibration.png", dpi=140)
    plt.close(fig)


def terminal_ci(cal: dict):
    fig, ax = plt.subplots(figsize=(7, 4))
    labels = ["TRAIN", "VALIDATION", "OOS", "FULL"]
    p = []
    lo = []
    hi = []
    for s in labels:
        b = cal[s]
        p.append(b["estimate"])
        lo.append(b["wilson"]["lo"])
        hi.append(b["wilson"]["hi"])
    y = np.arange(len(labels))
    ax.errorbar(p, y, xerr=[np.array(p) - np.array(lo), np.array(hi) - np.array(p)], fmt="o", color="#1f4e79")
    ax.axvline(0.80, color="#c0392b", ls="--", label="80% null")
    ax.set_yticks(y, labels)
    ax.set_xlabel("P(W | FIRST80)")
    ax.set_title("Terminal win rate Wilson 95% CI")
    ax.legend()
    _banner(ax)
    fig.tight_layout()
    fig.savefig(C.FIGURES / "terminal_winrate_ci.png", dpi=140)
    plt.close(fig)


def path_comparison(path: dict):
    fig, ax = plt.subplots(figsize=(7, 4))
    names = ["FIRST80", "FIRST75", "NON_FIRST80"]
    ps, lo, hi, ns = [], [], [], []
    for n in names:
        b = path[n]["full"]
        ps.append(b.get("estimate"))
        lo.append((b.get("wilson") or {}).get("lo"))
        hi.append((b.get("wilson") or {}).get("hi"))
        ns.append(b.get("n"))
    y = np.arange(len(names))
    ax.barh(y, [0 if v is None else v for v in ps], color="#1f4e79", alpha=0.7)
    ax.set_yticks(y, [f"{n}\nn={ns[i]}" for i, n in enumerate(names)])
    ax.set_xlabel("P(¬T40 | W)")
    ax.set_title("Conditional path survival vs controls")
    _banner(ax)
    fig.tight_layout()
    fig.savefig(C.FIGURES / "path_survival_comparison.png", dpi=140)
    plt.close(fig)


def outcome_tree(tree: dict):
    fig, ax = plt.subplots(figsize=(6, 4))
    labels = ["WIN ¬T40", "WIN T40", "LOSS ¬T40", "LOSS T40"]
    vals = [tree["WIN_NEVER_T40"], tree["WIN_TOUCH40"], tree["LOSS_NEVER_T40"], tree["LOSS_TOUCH40"]]
    ax.bar(labels, vals, color=["#2e7d32", "#f9a825", "#6d4c41", "#c62828"])
    ax.set_ylabel("count")
    ax.set_title("FIRST80 outcome tree (candle path)")
    _banner(ax)
    fig.tight_layout()
    fig.savefig(C.FIGURES / "outcome_tree.png", dpi=140)
    plt.close(fig)


def hedge_freq(by_h: dict):
    fig, ax = plt.subplots(figsize=(7, 4))
    hs = sorted(int(k) for k in by_h)
    p = [by_h[h]["FULL"]["p"] for h in hs]
    ax.plot(hs, p, marker="o", color="#1f4e79")
    ax.axvline(20, color="#c0392b", ls="--", label="theoretical HB<20¢ if EA=80 and complement=1")
    ax.set_xlabel("opponent yes_bid_close threshold (cents)")
    ax.set_ylabel("P(reach | FIRST80)")
    ax.set_title("Quoted hedge-state frequency (not fills)")
    ax.legend(fontsize=8)
    _banner(ax)
    fig.tight_layout()
    fig.savefig(C.FIGURES / "hedge_frequency_by_threshold.png", dpi=140)
    plt.close(fig)


def hedge_time(ev: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(7, 4))
    col = "h20_delay_s"
    if col not in ev.columns:
        return
    x = ev.loc[ev["h20_reached"] == True, col].dropna() / 60.0
    if len(x):
        ax.hist(x, bins=30, color="#1f4e79", alpha=0.85)
    ax.set_xlabel("minutes after FIRST80 until opponent bid_close ≤ 20¢")
    ax.set_title("Hedge-state timing (quoted, not filled)")
    _banner(ax)
    fig.tight_layout()
    fig.savefig(C.FIGURES / "hedge_time_distribution.png", dpi=140)
    plt.close(fig)


def sensitivity(surf: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(6.5, 5))
    pv = np.sort(surf["P_W"].unique())
    ps = np.sort(surf["P_not_T40_given_W"].unique())
    z = surf.pivot_table(index="P_not_T40_given_W", columns="P_W", values="P_W_and_not_T40").to_numpy()
    im = ax.imshow(z, origin="lower", aspect="auto", cmap="viridis", extent=[pv.min(), pv.max(), ps.min(), ps.max()])
    fig.colorbar(im, ax=ax, label="P(W ∩ ¬T40)")
    ax.set_xlabel("P(W)")
    ax.set_ylabel("P(¬T40 | W)")
    ax.set_title("HYPOTHETICAL SENSITIVITY — NOT A FORECAST — NOT A TRADING SIGNAL")
    fig.tight_layout()
    fig.savefig(C.FIGURES / "sensitivity_surface.png", dpi=140)
    plt.close(fig)


def run(cal, surf_a, path, tree, hedge, ev, sens):
    C.FIGURES.mkdir(parents=True, exist_ok=True)
    threshold_calibration(surf_a)
    terminal_ci(cal)
    path_comparison(path)
    outcome_tree(tree)
    hedge_freq(hedge)
    hedge_time(ev)
    sensitivity(sens)
