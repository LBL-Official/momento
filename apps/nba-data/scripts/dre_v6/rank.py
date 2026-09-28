"""TRAIN-frozen deciles of mean_SIR. Measurements only."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import replication as R
from .sir import split_trades


def train_edges(train_sir: np.ndarray) -> np.ndarray:
    v = np.asarray(train_sir, float)
    v = v[np.isfinite(v)]
    if len(v) < C.N_DECILES:
        raise RuntimeError("HALT: fewer TRAIN trades than deciles. Do not invent a coarser rank.")
    cats, edges = pd.qcut(v, C.N_DECILES, retbins=True, duplicates="drop")
    n_bins = int(len(edges) - 1)
    if n_bins != C.N_DECILES:
        raise RuntimeError(
            f"HALT: TRAIN mean_SIR produced {n_bins} distinct decile bins, not {C.N_DECILES}. "
            "Do not resolve by inspecting OOS."
        )
    return np.asarray(edges, float)


def assign_decile(sir: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """CLIP_TO_TRAIN_EXTREMA then pd.cut include_lowest=True, right=True."""
    x = np.asarray(sir, float)
    lo, hi = float(edges[0]), float(edges[-1])
    clipped = np.clip(x, lo, hi)
    lab = pd.cut(clipped, bins=edges, labels=False, include_lowest=True, right=True)
    lab_arr = np.asarray(lab, dtype=float)
    return lab_arr + 1.0


def _spearman(x, y) -> float | None:
    a = pd.Series(x, dtype=float)
    b = pd.Series(y, dtype=float)
    m = a.notna() & b.notna()
    if int(m.sum()) < 3:
        return None
    return float(a[m].rank().corr(b[m].rank()))


def _split_table(tr: pd.DataFrame, edges: np.ndarray) -> dict:
    if tr.empty:
        return {"n_trades": 0, "deciles": [], "spread": None}
    dec = assign_decile(tr["mean_sir"].to_numpy(float), edges)
    xs = tr.assign(decile=dec)
    rows = []
    for d in range(1, C.N_DECILES + 1):
        sub = xs[xs["decile"] == d]
        rows.append(
            {
                "decile": d,
                "n_trades": int(len(sub)),
                "n_games": int(sub["event_id"].nunique()) if len(sub) else 0,
                "mean_sir": float(sub["mean_sir"].mean()) if len(sub) else None,
                "mean_pi": float(sub["pi_terminal"].mean()) if len(sub) else None,
                "p_settle_yes": float(sub["y_settle_yes"].mean()) if len(sub) else None,
                "mean_r": float(sub["mean_r"].mean()) if len(sub) else None,
                "weighting": C.SURFACE_WEIGHTING_PRIMARY,
            }
        )
    lo = xs[xs["decile"] == 1]
    hi = xs[xs["decile"] == C.N_DECILES]
    spread = None
    if len(lo) and len(hi) and lo["pi_terminal"].notna().any() and hi["pi_terminal"].notna().any():
        spread = float(hi["pi_terminal"].mean() - lo["pi_terminal"].mean())
    return {
        "n_trades": int(len(xs)),
        "n_games": int(xs["event_id"].nunique()),
        "deciles": rows,
        "spread_hi_minus_lo": spread,
        "n_lo": int(len(lo)),
        "n_hi": int(len(hi)),
        "adequate": R.coverage_adequate(len(lo), len(hi)),
        "spearman_sir_pi": _spearman(xs["mean_sir"], xs["pi_terminal"]),
        "weighting": C.SURFACE_WEIGHTING_PRIMARY,
    }


def _bootstrap_spread(tr: pd.DataFrame, edges: np.ndarray) -> dict:
    xs = tr.dropna(subset=["mean_sir", "pi_terminal", "event_id"]).copy()
    xs["decile"] = assign_decile(xs["mean_sir"].to_numpy(float), edges)
    games = xs["event_id"].dropna().unique()
    if len(games) < 10:
        return {"status": "INCONCLUSIVE", "n_games": int(len(games))}
    by_game = {g: xs[xs["event_id"] == g] for g in games}
    rng = np.random.default_rng(C.RANDOM_SEED)
    vals = []
    for _ in range(C.BOOTSTRAP_GAMES):
        draw = rng.choice(games, size=len(games), replace=True)
        boot = pd.concat([by_game[g] for g in draw], ignore_index=True)
        lo = boot[boot["decile"] == 1]["pi_terminal"]
        hi = boot[boot["decile"] == C.N_DECILES]["pi_terminal"]
        if len(lo) < C.MIN_SIDE_TRADES or len(hi) < C.MIN_SIDE_TRADES:
            continue
        vals.append(float(hi.mean() - lo.mean()))
    if len(vals) < 20:
        return {"status": "INCONCLUSIVE", "n_valid": int(len(vals)), "n_games": int(len(games))}
    arr = np.asarray(vals, float)
    return {
        "status": "OK",
        "n_games": int(len(games)),
        "n_valid": int(len(arr)),
        "mean": float(arr.mean()),
        "p05": float(np.quantile(arr, 0.05)),
        "p95": float(np.quantile(arr, 0.95)),
        "cluster": "event_id",
        "seed": C.RANDOM_SEED,
    }


def persist_edges(edges: np.ndarray) -> dict:
    payload = {
        "source": "TRAIN mean_SIR_i qcut",
        "n_deciles": C.N_DECILES,
        "edges": [float(x) for x in edges],
        "outside_train_range": "CLIP_TO_TRAIN_EXTREMA",
        "assignment": "pd.cut include_lowest=True right=True after clip",
        "written_utc": C.utc_now(),
        "note": "Persisted before VAL/OOS rank tables. Do not recompute split-specific quantiles.",
    }
    C.write_json(C.OUT / "03_train_decile_edges.json", payload)
    return payload


def measure(trades, edges: np.ndarray | None = None) -> dict:
    if edges is None:
        train = split_trades(trades, "TRAIN")
        edges = train_edges(train["mean_sir"].to_numpy(float))
    by_split = {s: _split_table(split_trades(trades, s), edges) for s in C.SPLITS}
    boot_oos = _bootstrap_spread(split_trades(trades, "OOS"), edges)
    coverage = {
        "adequate_train_oos": bool(by_split["TRAIN"]["adequate"] and by_split["OOS"]["adequate"]),
        "adequate_val": bool(by_split["VALIDATION"]["adequate"]),
    }
    rep = R.replication_directional(
        by_split["TRAIN"]["spread_hi_minus_lo"],
        by_split["VALIDATION"]["spread_hi_minus_lo"],
        by_split["OOS"]["spread_hi_minus_lo"],
        boot_oos,
        coverage,
    )
    return {
        "n_deciles": C.N_DECILES,
        "edges": [float(x) for x in edges],
        "cuts_source": "TRAIN mean_SIR_i",
        "by_split": by_split,
        "bootstrap_oos": boot_oos,
        "coverage": coverage,
        "replication": rep,
        "weighting": C.SURFACE_WEIGHTING_PRIMARY,
        "note": "Spread = E[Pi | decile 10] - E[Pi | decile 1]. Measurement only.",
    }
