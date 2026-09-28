"""Trade-level residual-on-residual. Measurements only. Occupancy is diagnostic."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import rank as RK
from . import replication as R
from .sir import split_trades


def _spearman(x, y) -> float | None:
    a = pd.Series(x, dtype=float)
    b = pd.Series(y, dtype=float)
    m = a.notna() & b.notna()
    if int(m.sum()) < 3:
        return None
    return float(a[m].rank().corr(b[m].rank()))


def _split_table(tr: pd.DataFrame, edges: np.ndarray) -> dict:
    if tr.empty:
        return {"n_trades": 0}
    dec = RK.assign_decile(tr["mean_sir"].to_numpy(float), edges)
    xs = tr.assign(decile=dec)
    rows = []
    for d in range(1, C.N_DECILES + 1):
        sub = xs[xs["decile"] == d]
        rows.append(
            {
                "decile": d,
                "n_trades": int(len(sub)),
                "mean_sir": float(sub["mean_sir"].mean()) if len(sub) else None,
                "mean_r": float(sub["mean_r"].mean()) if len(sub) else None,
                "weighting": C.SURFACE_WEIGHTING_PRIMARY,
            }
        )
    lo = xs[xs["decile"] == 1]
    hi = xs[xs["decile"] == C.N_DECILES]
    spread = None
    if len(lo) and len(hi):
        spread = float(hi["mean_r"].mean() - lo["mean_r"].mean())
    return {
        "n_trades": int(len(xs)),
        "n_games": int(xs["event_id"].nunique()),
        "deciles": rows,
        "spread_hi_minus_lo": spread,
        "n_lo": int(len(lo)),
        "n_hi": int(len(hi)),
        "adequate": R.coverage_adequate(len(lo), len(hi)),
        "spearman_sir_r": _spearman(xs["mean_sir"], xs["mean_r"]),
        "weighting": C.SURFACE_WEIGHTING_PRIMARY,
    }


def _bootstrap_spread(tr: pd.DataFrame, edges: np.ndarray) -> dict:
    xs = tr.dropna(subset=["mean_sir", "mean_r", "event_id"]).copy()
    xs["decile"] = RK.assign_decile(xs["mean_sir"].to_numpy(float), edges)
    games = xs["event_id"].dropna().unique()
    if len(games) < 10:
        return {"status": "INCONCLUSIVE", "n_games": int(len(games))}
    by_game = {g: xs[xs["event_id"] == g] for g in games}
    rng = np.random.default_rng(C.RANDOM_SEED)
    vals = []
    for _ in range(C.BOOTSTRAP_GAMES):
        draw = rng.choice(games, size=len(games), replace=True)
        boot = pd.concat([by_game[g] for g in draw], ignore_index=True)
        lo = boot[boot["decile"] == 1]["mean_r"]
        hi = boot[boot["decile"] == C.N_DECILES]["mean_r"]
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


def _occupancy(state_df: pd.DataFrame, edges: np.ndarray) -> dict:
    by_split = {}
    for split in C.SPLITS:
        st = state_df[(state_df["dataset_split"] == split) & state_df["da_state"].notna() & state_df["r_t"].notna()]
        if st.empty:
            by_split[split] = {"n_rows": 0, "label": C.OCCUPANCY_LABEL}
            continue
        dec = RK.assign_decile(st["da_state"].to_numpy(float), edges)
        xs = st.assign(decile=dec)
        rows = []
        for d in range(1, C.N_DECILES + 1):
            sub = xs[xs["decile"] == d]
            rows.append(
                {
                    "decile": d,
                    "n_rows": int(len(sub)),
                    "mean_da": float(sub["da_state"].mean()) if len(sub) else None,
                    "mean_r_t": float(sub["r_t"].mean()) if len(sub) else None,
                }
            )
        by_split[split] = {
            "label": C.OCCUPANCY_LABEL,
            "n_rows": int(len(xs)),
            "spearman_da_rt": _spearman(xs["da_state"], xs["r_t"]),
            "deciles": rows,
            "note": "Diagnostic only. Long trades overweight this table.",
        }
    return {"label": C.OCCUPANCY_LABEL, "by_split": by_split}


def measure(trades, state_df, edges: np.ndarray) -> dict:
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
        "primary": C.SURFACE_WEIGHTING_PRIMARY,
        "object": "E[mean_R_i | mean_SIR_i] via TRAIN-frozen SIR deciles",
        "by_split": by_split,
        "bootstrap_oos": boot_oos,
        "coverage": coverage,
        "replication": rep,
        "occupancy": _occupancy(state_df, edges),
        "note": "Primary is trade-level. Occupancy residual-on-residual is diagnostic.",
    }
