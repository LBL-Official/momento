#!/usr/bin/env python3
"""Model 1 — TRAIN univariate relationships. OOS is not used for discovery."""

from __future__ import annotations

from common import (
    MODELS,
    OBS,
    REP,
    col_array,
    ev_from_q,
    quintile_edges,
    read_parquet_rows,
    roc_auc,
    spearman,
    utc_now,
    wilson,
    write_json,
)


HYP = [
    ("H0", None, "unconditional_q", "baseline"),
    ("HG1", "game_score_differential", "score_differential", "game"),
    ("HG2", "game_d_star", "time_normalized_lead", "game"),
    ("HG3", "dyn_score_vel_5m", "score_velocity_5m", "game"),
    ("HG4", "game_lsi", "lead_stability_index", "game"),
    ("HG5", "game_score_std_5m", "score_vol_5m", "game"),
    ("HM1", "dyn_market_mom_5m", "momentum_5m", "market"),
    ("HM2", "dyn_market_vol_5m", "vol_5m_proxy", "market"),
    ("HC1", "coupling_residual", "market_game_residual", "coupling"),
    ("HP1", "path_efficiency_market", "market_path_efficiency", "path"),
    ("HP2", "path_efficiency_game", "game_path_efficiency", "path"),
]


def split_rows(rows, name):
    return [r for r in rows if r.get("dataset_split") == name]


def bucket_table(x, y, edges):
    out = []
    for lo, hi in edges:
        m = (x >= lo) & (x < hi) & np_isfinite(x)
        n = int(m.sum())
        k = int(y[m].sum()) if n else 0
        p, lo_ci, hi_ci = wilson(k, n)
        out.append(
            {
                "lo": lo,
                "hi": hi,
                "n": n,
                "k": k,
                "q": p,
                "ev": ev_from_q(p),
                "wilson_lo": lo_ci,
                "wilson_hi": hi_ci,
            }
        )
    return out


def np_isfinite(x):
    import numpy as np

    return np.isfinite(x)


def apply_edges(x, y, edges):
    return bucket_table(x, y, edges)


def main() -> int:
    import numpy as np

    rows = read_parquet_rows(OBS / "first80_game_state.parquet")
    tr = split_rows(rows, "TRAIN")
    va = split_rows(rows, "VALIDATION")
    oo = split_rows(rows, "OOS")
    y_tr = np.array([r["Y_40_CLOSE"] for r in tr], dtype=float)
    q0 = float(y_tr.mean()) if len(y_tr) else None
    tests = {
        "H0": {
            "hypothesis_id": "H0",
            "block": "baseline",
            "name": "unconditional_q",
            "train_q": q0,
            "train_n": len(tr),
            "train_k": int(y_tr.sum()),
            "train_ev": ev_from_q(q0),
            "status": "SUPPORTED",
            "note": "Frozen universe benchmark. Not a filter.",
        }
    }
    for hid, key, name, block in HYP:
        if key is None:
            continue
        x_tr = col_array(tr, key)
        x_va = col_array(va, key)
        x_oo = col_array(oo, key)
        y_va = np.array([r["Y_40_CLOSE"] for r in va], dtype=float)
        y_oo = np.array([r["Y_40_CLOSE"] for r in oo], dtype=float)
        m = np.isfinite(x_tr)
        edges = quintile_edges(x_tr)
        if edges is None or int(m.sum()) < 80:
            tests[hid] = {
                "hypothesis_id": hid,
                "block": block,
                "name": name,
                "feature": key,
                "status": "DATA_LIMITED",
                "n_finite_train": int(m.sum()),
            }
            continue
        bucks_tr = bucket_table(x_tr, y_tr, edges)
        bucks_va = apply_edges(x_va, y_va, edges)
        bucks_oo = apply_edges(x_oo, y_oo, edges)
        mids = [0.5 * (b["lo"] + b["hi"]) for b in bucks_tr]
        rates = [b["q"] if b["q"] is not None else np.nan for b in bucks_tr]
        rho = spearman(mids, rates)
        auc = roc_auc(y_tr[m], x_tr[m])
        usable = [b for b in bucks_tr if b["n"] >= 40 and b["q"] is not None]
        spread = None
        if len(usable) >= 2:
            spread = max(b["q"] for b in usable) - min(b["q"] for b in usable)
        val_spread = None
        vu = [b for b in bucks_va if b["n"] >= 25 and b["q"] is not None]
        if len(vu) >= 2:
            val_spread = max(b["q"] for b in vu) - min(b["q"] for b in vu)
        train_dir = None
        if rho is not None:
            train_dir = 1 if rho > 0 else (-1 if rho < 0 else 0)
        val_rho = spearman(
            [0.5 * (b["lo"] + b["hi"]) for b in bucks_va],
            [b["q"] if b["q"] is not None else np.nan for b in bucks_va],
        )
        val_dir = None if val_rho is None else (1 if val_rho > 0 else (-1 if val_rho < 0 else 0))
        oos_rho = spearman(
            [0.5 * (b["lo"] + b["hi"]) for b in bucks_oo],
            [b["q"] if b["q"] is not None else np.nan for b in bucks_oo],
        )
        status = "INCONCLUSIVE"
        if spread is None or spread < 0.04:
            status = "INCONCLUSIVE"
        elif abs(rho or 0) < 0.4:
            status = "INCONCLUSIVE"
        elif val_dir is not None and train_dir is not None and val_dir != train_dir:
            status = "REJECTED"
        elif val_spread is not None and val_spread < 0.02:
            status = "INCONCLUSIVE"
        elif spread >= 0.08 and abs(rho or 0) >= 0.6 and val_dir == train_dir:
            status = "SUPPORTED"
        else:
            status = "INCONCLUSIVE"
        tests[hid] = {
            "hypothesis_id": hid,
            "block": block,
            "name": name,
            "feature": key,
            "n_finite_train": int(m.sum()),
            "train_auc": auc,
            "train_spearman_q_vs_mid": rho,
            "val_spearman_q_vs_mid": val_rho,
            "oos_spearman_frozen_eval": oos_rho,
            "train_q_spread": spread,
            "val_q_spread": val_spread,
            "train_buckets": bucks_tr,
            "val_buckets_frozen_edges": bucks_va,
            "oos_buckets_frozen_eval": bucks_oo,
            "status": status,
            "oos_used_for_discovery": False,
        }

    # Regimes on TRAIN
    from collections import defaultdict

    by_reg = defaultdict(list)
    for r in tr:
        by_reg[r.get("regime") or "OTHER"].append(int(r["Y_40_CLOSE"]))
    tests["HR1"] = {
        "hypothesis_id": "HR1",
        "block": "regime",
        "name": "interpretable_regimes_A_E",
        "train": {
            k: {"n": len(v), "k": int(sum(v)), "q": float(np.mean(v)), "ev": ev_from_q(float(np.mean(v)))}
            for k, v in sorted(by_reg.items(), key=lambda x: -len(x[1]))
        },
        "status": "PRE_REGISTERED",
        "note": "Boundaries frozen from TRAIN percentiles. Not K-means.",
    }

    write_json(
        MODELS / "model1_univariate" / "results.json",
        {"written_utc": utc_now(), "tests": tests, "train_q": q0},
    )
    write_json(REP / "univariate_results.json", {"written_utc": utc_now(), "tests": tests})
    n_sup = sum(1 for v in tests.values() if v.get("status") == "SUPPORTED")
    print(f"univariate tests={len(tests)} SUPPORTED={n_sup} (H0 counts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
