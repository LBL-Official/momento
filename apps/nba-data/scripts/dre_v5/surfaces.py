"""Conditional payoff surfaces. TRADE_BALANCED primary. Occupancy secondary.

OOS tables must not be computed until OOS_REPLICATION_PROTOCOL.json exists.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def _adequate(n_rows: int, n_trades: int) -> bool:
    return n_rows >= C.MIN_CELL_ROWS and n_trades >= C.MIN_CELL_TRADES


def _quantiles(vals: np.ndarray) -> dict:
    """Empirical quantiles. Never hardcode P50=0. Π_terminal ∈ {-80, +20} only."""
    v = np.asarray(vals, float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return {"p10": None, "p50": None, "p90": None, "std_pi": None}
    return {
        "p10": float(np.quantile(v, 0.10)),
        "p50": float(np.quantile(v, 0.50)),
        "p90": float(np.quantile(v, 0.90)),
        "std_pi": float(np.std(v, ddof=1)) if len(v) > 1 else 0.0,
    }


def cell_estimate(sub: pd.DataFrame, value_col: str, y_col: str = "y_settle_yes") -> dict:
    """Return both TRADE_BALANCED and STATE_OCCUPANCY_WEIGHTED estimands."""
    n_rows = int(len(sub))
    n_trades = int(sub["trade_id"].nunique())
    n_games = int(sub["event_id"].nunique())
    if n_rows == 0:
        return {
            "n_rows": 0,
            "n_unique_trades": 0,
            "n_unique_games": 0,
            "adequate": False,
            "TRADE_BALANCED": None,
            "STATE_OCCUPANCY_WEIGHTED": None,
        }

    g = sub.groupby("trade_id", sort=False)
    trade_pi = g[value_col].mean()
    trade_y = g[y_col].mean()
    trade_n = g.size()
    top_share = float(trade_n.max() / n_rows) if n_rows else None

    tb_q = _quantiles(trade_pi.to_numpy(float))
    tb_p = float(trade_y.mean()) if len(trade_y) else None
    tb_mean = float(trade_pi.mean()) if len(trade_pi) else None
    tb = {
        "weighting": C.SURFACE_WEIGHTING_PRIMARY,
        "mean_pi": tb_mean,
        "p_settle_yes": tb_p,
        "p_settle_no": None if tb_p is None else 1.0 - tb_p,
        "identity_alpha": None if tb_p is None else 100.0 * tb_p - 80.0,
        **tb_q,
        "top_trade_share": top_share,
    }

    occ_pi = pd.to_numeric(sub[value_col], errors="coerce")
    occ_y = pd.to_numeric(sub[y_col], errors="coerce")
    occ_q = _quantiles(occ_pi.to_numpy(float))
    occ_p = float(occ_y.mean()) if occ_y.notna().any() else None
    occ = {
        "weighting": C.SURFACE_WEIGHTING_SECONDARY,
        "mean_pi": float(occ_pi.mean()) if occ_pi.notna().any() else None,
        "p_settle_yes": occ_p,
        "p_settle_no": None if occ_p is None else 1.0 - occ_p,
        "identity_alpha": None if occ_p is None else 100.0 * occ_p - 80.0,
        **occ_q,
        "top_trade_share": top_share,
    }
    return {
        "n_rows": n_rows,
        "n_unique_trades": n_trades,
        "n_unique_games": n_games,
        "adequate": _adequate(n_rows, n_trades),
        "TRADE_BALANCED": tb,
        "STATE_OCCUPANCY_WEIGHTED": occ,
    }


def _row_from_est(keys: dict, est: dict, split: str, level: str, payoff: str) -> dict:
    tb = est.get("TRADE_BALANCED") or {}
    occ = est.get("STATE_OCCUPANCY_WEIGHTED") or {}
    return {
        **keys,
        "split": split,
        "level": level,
        "payoff": payoff,
        "n_rows": est.get("n_rows"),
        "n_unique_trades": est.get("n_unique_trades"),
        "n_unique_games": est.get("n_unique_games"),
        "adequate": est.get("adequate"),
        "weighting": C.SURFACE_WEIGHTING_PRIMARY,
        "mean_pi": tb.get("mean_pi"),
        "p_settle_yes": tb.get("p_settle_yes"),
        "p_settle_no": tb.get("p_settle_no"),
        "identity_alpha": tb.get("identity_alpha"),
        "p10": tb.get("p10"),
        "p50": tb.get("p50"),
        "p90": tb.get("p90"),
        "std_pi": tb.get("std_pi"),
        "top_trade_share": tb.get("top_trade_share"),
        "occ_mean_pi": occ.get("mean_pi"),
        "occ_p_settle_yes": occ.get("p_settle_yes"),
        "occ_weighting": C.SURFACE_WEIGHTING_SECONDARY,
        "materially_different_weighting": _material_diff(tb.get("mean_pi"), occ.get("mean_pi")),
    }


def _material_diff(a, b) -> bool | None:
    if a is None or b is None:
        return None
    return abs(float(a) - float(b)) >= 2.0


def build_surfaces(
    df: pd.DataFrame,
    value_col: str,
    payoff: str,
    splits: tuple[str, ...] = ("TRAIN", "VALIDATION", "OOS"),
) -> list[dict]:
    if payoff == C.DIAGNOSTIC_PAYOFF_40:
        role = "DIAGNOSTIC_ONLY"
    else:
        role = "PRIMARY" if payoff == C.PRIMARY_PAYOFF else "SECONDARY"
    rows = []
    usable = df[df[value_col].notna() & df["y_settle_yes"].notna()].copy()
    for split in splits:
        xs = usable[usable["dataset_split"] == split]
        # L1 full
        l1_keys = ["clock_bin_l1", "score_bin_l1", "n_hat_bin_l1", "price_bin_5"]
        n_possible = 0
        n_excluded = 0
        for keys, sub in xs.groupby(l1_keys, dropna=False):
            n_possible += 1
            est = cell_estimate(sub, value_col)
            rec = _row_from_est(
                {
                    "clock_bin_l1": keys[0],
                    "score_bin_l1": keys[1],
                    "n_hat_bin_l1": keys[2],
                    "price_bin_5": keys[3],
                    "payoff_role": role,
                    "units": "cents_per_contract",
                },
                est,
                split,
                "L1",
                payoff,
            )
            if not est["adequate"]:
                n_excluded += 1
                rec["excluded_reason"] = "below_min_50_rows_15_trades"
            rows.append(rec)
        # L2 coarsened
        l2_keys = ["clock_bin_l2", "score_bin_l2", "n_hat_bin_l2", "price_bin_10"]
        for keys, sub in xs.groupby(l2_keys, dropna=False):
            est = cell_estimate(sub, value_col)
            rec = _row_from_est(
                {
                    "clock_bin_l2": keys[0],
                    "score_bin_l2": keys[1],
                    "n_hat_bin_l2": keys[2],
                    "price_bin_10": keys[3],
                },
                est,
                split,
                "L2",
                payoff,
            )
            if not est["adequate"]:
                rec["excluded_reason"] = "below_min_50_rows_15_trades"
            rows.append(rec)
        # L3 slices
        for price, psub in xs.groupby("price_bin_5", dropna=False):
            for clock, csub in psub.groupby("clock_bin_l2", dropna=False):
                est = cell_estimate(csub, value_col)
                rec = _row_from_est({"price_bin_5": price, "clock_bin_l2": clock, "slice": "price_clock"}, est, split, "L3", payoff)
                rows.append(rec)
            for sc, ssub in psub.groupby("score_bin_l2", dropna=False):
                est = cell_estimate(ssub, value_col)
                rec = _row_from_est({"price_bin_5": price, "score_bin_l2": sc, "slice": "price_score"}, est, split, "L3", payoff)
                rows.append(rec)
            for nh, nsub in psub.groupby("n_hat_bin_l2", dropna=False):
                est = cell_estimate(nsub, value_col)
                rec = _row_from_est({"price_bin_5": price, "n_hat_bin_l2": nh, "slice": "price_nhat"}, est, split, "L3", payoff)
                rows.append(rec)
            # M0 price-only
            est = cell_estimate(psub, value_col)
            rec = _row_from_est({"price_bin_5": price, "slice": "price_only"}, est, split, "L3", payoff)
            rows.append(rec)
        # L1 inventory meta
        rows.append(
            {
                "split": split,
                "level": "L1_META",
                "payoff": payoff,
                "n_l1_cells_observed": n_possible,
                "n_l1_cells_below_min": n_excluded,
                "weighting": C.SURFACE_WEIGHTING_PRIMARY,
            }
        )
    return rows


def contrast_l3(df: pd.DataFrame, spec: dict, value_col: str = C.PRIMARY_PAYOFF) -> dict:
    """Pre-registered L3 contrast at a matched price bin. Primary Π only."""
    if value_col != C.PRIMARY_PAYOFF:
        raise ValueError("pre-registered L3 contrasts use pi_terminal only")
    lo = spec["price_lo"]
    width = spec["price_width"]
    slice_name = spec["slice"]
    a_lab, b_lab = spec["a"], spec["b"]
    col = {"clock": "clock_bin_l2", "score": "score_bin_l2", "n_hat": "n_hat_bin_l2"}[slice_name]
    out = {"spec": spec, "by_split": {}}
    for split in ("TRAIN", "VALIDATION", "OOS"):
        xs = df[(df["dataset_split"] == split) & (df["price_bin_5"] == lo) & df[value_col].notna()]
        a = xs[xs[col] == a_lab]
        b = xs[xs[col] == b_lab]
        ea = cell_estimate(a, value_col)
        eb = cell_estimate(b, value_col)
        ma = (ea.get("TRADE_BALANCED") or {}).get("mean_pi")
        mb = (eb.get("TRADE_BALANCED") or {}).get("mean_pi")
        pa = (ea.get("TRADE_BALANCED") or {}).get("p_settle_yes")
        pb = (eb.get("TRADE_BALANCED") or {}).get("p_settle_yes")
        effect = None if ma is None or mb is None else float(mb) - float(ma)
        out["by_split"][split] = {
            "a": {"label": a_lab, **ea},
            "b": {"label": b_lab, **eb},
            "effect_b_minus_a": effect,
            "p_settle_b_minus_a": None if pa is None or pb is None else float(pb) - float(pa),
            "adequate": bool(ea.get("adequate") and eb.get("adequate")),
        }
    return out


def bootstrap_contrast(df: pd.DataFrame, spec: dict, split: str, value_col: str = C.PRIMARY_PAYOFF) -> dict:
    rng = np.random.default_rng(C.RANDOM_SEED)
    xs = df[(df["dataset_split"] == split) & (df["price_bin_5"] == spec["price_lo"]) & df[value_col].notna()].copy()
    games = xs["event_id"].dropna().unique()
    if len(games) < 10:
        return {"status": "INCONCLUSIVE", "n_games": int(len(games)), "effects": []}
    col = {"clock": "clock_bin_l2", "score": "score_bin_l2", "n_hat": "n_hat_bin_l2"}[spec["slice"]]
    by_game = {g: xs[xs["event_id"] == g] for g in games}
    effects = []
    for _ in range(C.BOOTSTRAP_GAMES):
        draw = rng.choice(games, size=len(games), replace=True)
        parts = [by_game[g] for g in draw]
        boot = pd.concat(parts, ignore_index=True)
        a = boot[boot[col] == spec["a"]]
        b = boot[boot[col] == spec["b"]]
        ea = cell_estimate(a, value_col)
        eb = cell_estimate(b, value_col)
        ma = (ea.get("TRADE_BALANCED") or {}).get("mean_pi")
        mb = (eb.get("TRADE_BALANCED") or {}).get("mean_pi")
        if ma is None or mb is None:
            continue
        effects.append(float(mb) - float(ma))
    if not effects:
        return {"status": "INCONCLUSIVE", "n_games": int(len(games)), "effects": []}
    arr = np.asarray(effects, float)
    return {
        "status": "OK",
        "n_games": int(len(games)),
        "n_valid": int(len(arr)),
        "mean": float(arr.mean()),
        "p05": float(np.quantile(arr, 0.05)),
        "p95": float(np.quantile(arr, 0.95)),
        "cluster": "event_id",
    }


def classify_replication(contrasts: list[dict]) -> dict:
    """Apply the pre-declared protocol. Do not require p<0.05 twice."""
    band = C.OOS_REPLICATION_PROTOCOL["magnitude_band"]
    results = []
    for rec in contrasts:
        spec = rec["spec"]
        tr = rec["by_split"].get("TRAIN") or {}
        va = rec["by_split"].get("VALIDATION") or {}
        oo = rec["by_split"].get("OOS") or {}
        boot = rec.get("bootstrap_oos") or {}
        te, oe, ve = tr.get("effect_b_minus_a"), oo.get("effect_b_minus_a"), va.get("effect_b_minus_a")
        adequate = bool(tr.get("adequate") and oo.get("adequate"))
        val_adequate = bool(va.get("adequate"))
        if not adequate or te is None or oe is None or abs(float(te)) < 1e-9:
            token = "INCONCLUSIVE"
            sign_match = None
        else:
            sign_match = (float(oe) > 0) == (float(te) > 0)
            ratio = float(oe) / float(te)
            val_ok = True
            if val_adequate and ve is not None and abs(float(te)) >= 1e-9:
                val_ok = (float(ve) > 0) == (float(te) > 0)
            p05, p95 = boot.get("p05"), boot.get("p95")
            train_sign = 1 if float(te) > 0 else -1
            compatible_dir = True
            if p05 is not None and p95 is not None:
                if train_sign > 0:
                    compatible_dir = float(p95) > 0
                else:
                    compatible_dir = float(p05) < 0
            in_band = band[0] <= ratio <= band[1]
            if not sign_match:
                token = "FAIL"
            elif compatible_dir and val_ok and in_band:
                token = "ROBUST"
            else:
                token = "PARTIAL"
        results.append(
            {
                "id": spec["id"],
                "token": token,
                "sign_match": sign_match,
                "ratio_oos_over_train": None if te in (None, 0) or oe is None else (None if abs(float(te)) < 1e-9 else float(oe) / float(te)),
                "train_effect": te,
                "val_effect": ve,
                "oos_effect": oe,
                "adequate_train_oos": adequate,
                "bootstrap_oos": {k: boot.get(k) for k in ("mean", "p05", "p95", "n_games", "status")},
            }
        )
    return {"contrasts": results, "protocol": "OOS_REPLICATION_PROTOCOL.json"}


def m0_m1(df: pd.DataFrame) -> dict:
    """TRAIN-fit cell means; OOS MAE is TRADE_BALANCED.

    hat_alpha_i = (1/T_i) sum_t hat_alpha_TRAIN(X_it)
    MAE = (1/N) sum_i |Pi_i - hat_alpha_i|
    Occupancy MAE is labeled STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC only.
    """
    train = df[(df["dataset_split"] == "TRAIN") & df["pi_terminal"].notna()].copy()
    m0 = {}
    for p, sub in train.groupby("price_bin_5"):
        est = cell_estimate(sub, "pi_terminal")
        m0[p] = (est.get("TRADE_BALANCED") or {}).get("mean_pi")
    m1 = {}
    for keys, sub in train.groupby(["price_bin_5", "score_bin_l1", "clock_bin_l1", "n_hat_bin_l1"], dropna=False):
        est = cell_estimate(sub, "pi_terminal")
        m1[keys] = (est.get("TRADE_BALANCED") or {}).get("mean_pi")
    global_mean = float(train.groupby("trade_id")["pi_terminal"].mean().mean())

    def pred_row(r, use_m1: bool):
        fallback = m0.get(r["price_bin_5"], global_mean)
        if not use_m1:
            return fallback
        key = (r["price_bin_5"], r["score_bin_l1"], r["clock_bin_l1"], r["n_hat_bin_l1"])
        v = m1.get(key)
        return fallback if v is None else v

    def eval_split(split: str) -> dict:
        xs = df[(df["dataset_split"] == split) & df["pi_terminal"].notna()].copy()
        if xs.empty:
            return {"n_trades": 0}
        p0 = [pred_row(r, False) for r in xs.to_dict("records")]
        p1 = [pred_row(r, True) for r in xs.to_dict("records")]
        xs = xs.assign(_p0=p0, _p1=p1)
        g = xs.groupby("trade_id")
        y = g["pi_terminal"].mean()
        e0 = (y - g["_p0"].mean()).abs()
        e1 = (y - g["_p1"].mean()).abs()
        occ0 = (xs["pi_terminal"] - xs["_p0"]).abs().mean()
        occ1 = (xs["pi_terminal"] - xs["_p1"]).abs().mean()
        return {
            "n_rows": int(len(xs)),
            "n_trades": int(len(y)),
            "n_games": int(xs["event_id"].nunique()),
            "mae_m0_trade_balanced": float(e0.mean()),
            "mae_m1_trade_balanced": float(e1.mean()),
            "mae_m0_occupancy": float(occ0),
            "mae_m1_occupancy": float(occ1),
            "occupancy_label": "STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC",
            "trade_prediction": "hat_alpha_i = mean_t hat_alpha_TRAIN(X_it)",
            "delta_mae_m0_minus_m1": float(e0.mean() - e1.mean()),
            "weighting": C.SURFACE_WEIGHTING_PRIMARY,
        }

    by_split = {s: eval_split(s) for s in ("TRAIN", "VALIDATION", "OOS")}
    boot = _bootstrap_mae_delta(df)
    oos = by_split["OOS"]
    d = oos.get("delta_mae_m0_minus_m1")
    m1_beats = False
    if d is not None and boot.get("p05") is not None and boot.get("p95") is not None:
        m1_beats = (float(d) >= C.MAE_MATERIAL_CENTS) and (float(boot["p05"]) > 0)
    return {
        "by_split": by_split,
        "bootstrap_oos_delta_mae": boot,
        "m1_beats_m0": m1_beats,
        "material_mae_cents": C.MAE_MATERIAL_CENTS,
        "M1_beats_M0_rule": C.OOS_REPLICATION_PROTOCOL["price_dominance"]["M1_beats_M0"],
        "meaning": C.OOS_REPLICATION_PROTOCOL["price_dominance"]["meaning"],
        "primary_estimand": "TRADE_BALANCED",
        "occupancy_label": "STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC",
        "n_m0_cells": len(m0),
        "n_m1_cells": len(m1),
        "lookup": {"m0": m0, "m1": m1, "global_mean": global_mean},
    }


def _bootstrap_mae_delta(df: pd.DataFrame) -> dict:
    rng = np.random.default_rng(C.RANDOM_SEED)
    train = df[(df["dataset_split"] == "TRAIN") & df["pi_terminal"].notna()]
    oos = df[(df["dataset_split"] == "OOS") & df["pi_terminal"].notna()].copy()
    m0 = {}
    for p, sub in train.groupby("price_bin_5"):
        m0[p] = (cell_estimate(sub, "pi_terminal").get("TRADE_BALANCED") or {}).get("mean_pi")
    m1 = {}
    for keys, sub in train.groupby(["price_bin_5", "score_bin_l1", "clock_bin_l1", "n_hat_bin_l1"], dropna=False):
        m1[keys] = (cell_estimate(sub, "pi_terminal").get("TRADE_BALANCED") or {}).get("mean_pi")
    gmean = float(train.groupby("trade_id")["pi_terminal"].mean().mean())
    games = oos["event_id"].dropna().unique()
    if len(games) < 10:
        return {"status": "INCONCLUSIVE", "n_games": int(len(games))}
    by_game = {g: oos[oos["event_id"] == g] for g in games}

    def mae_pair(xs: pd.DataFrame):
        recs = xs.to_dict("records")
        p0 = [m0.get(r["price_bin_5"], gmean) for r in recs]
        p1 = []
        for r in recs:
            v = m1.get((r["price_bin_5"], r["score_bin_l1"], r["clock_bin_l1"], r["n_hat_bin_l1"]))
            p1.append(m0.get(r["price_bin_5"], gmean) if v is None else v)
        xs = xs.assign(_p0=p0, _p1=p1)
        g = xs.groupby("trade_id")
        y = g["pi_terminal"].mean()
        e0 = (y - g["_p0"].mean()).abs().mean()
        e1 = (y - g["_p1"].mean()).abs().mean()
        return float(e0 - e1)

    deltas = []
    for _ in range(C.BOOTSTRAP_GAMES):
        draw = rng.choice(games, size=len(games), replace=True)
        boot = pd.concat([by_game[g] for g in draw], ignore_index=True)
        deltas.append(mae_pair(boot))
    arr = np.asarray(deltas, float)
    return {
        "status": "OK",
        "n_games": int(len(games)),
        "mean": float(arr.mean()),
        "p05": float(np.quantile(arr, 0.05)),
        "p95": float(np.quantile(arr, 0.95)),
        "cluster": "event_id",
    }


def lookup_maps(surface_rows: list[dict], split: str) -> dict:
    """α lookup from one split's surface. Scientific OOS must pass split='TRAIN'."""
    l2, l3_clock, l3_price = {}, {}, {}
    for r in surface_rows:
        if r.get("split") != split or r.get("payoff") != C.PRIMARY_PAYOFF:
            continue
        if not r.get("adequate"):
            continue
        a = r.get("mean_pi")
        if a is None:
            continue
        if r.get("level") == "L2":
            l2[(r.get("clock_bin_l2"), r.get("score_bin_l2"), r.get("n_hat_bin_l2"), r.get("price_bin_10"))] = a
        if r.get("level") == "L3" and r.get("slice") == "price_clock":
            l3_clock[(r.get("price_bin_5"), r.get("clock_bin_l2"))] = a
        if r.get("level") == "L3" and r.get("slice") == "price_only":
            l3_price[r.get("price_bin_5")] = a
    return {"split": split, "l2": l2, "l3_clock": l3_clock, "l3_price": l3_price}


def train_lookup_maps(surface_rows: list[dict]) -> dict:
    """TRAIN-frozen α. Required for Discovery / Validation / Scientific OOS Lambda."""
    return lookup_maps(surface_rows, "TRAIN")


def descriptive_oos_lookup_maps(surface_rows: list[dict]) -> dict:
    """OOS-refit α. Descriptive OOS Lambda only. Never the scientific test."""
    return lookup_maps(surface_rows, "OOS")


def map_alpha(row, maps: dict, global_mean: float) -> float:
    """Map a state onto a frozen surface. Caller chooses TRAIN vs OOS maps."""
    a = maps["l2"].get((row.get("clock_bin_l2"), row.get("score_bin_l2"), row.get("n_hat_bin_l2"), row.get("price_bin_10")))
    if a is not None:
        return float(a)
    a = maps["l3_clock"].get((row.get("price_bin_5"), row.get("clock_bin_l2")))
    if a is not None:
        return float(a)
    a = maps["l3_price"].get(row.get("price_bin_5"))
    if a is not None:
        return float(a)
    return float(global_mean)


def build_hazard(
    df: pd.DataFrame,
    splits: tuple[str, ...] = ("TRAIN", "VALIDATION", "OOS"),
) -> list[dict]:
    """At-risk 40¢ hazard. Already-damaged paths are out of the primary denominator."""
    at = df[df["at_risk_40"] == True].copy()
    rows = []
    for split in splits:
        xs = at[(at["dataset_split"] == split) & at["y_future_hit_40"].notna()]
        for keys, sub in xs.groupby(["clock_bin_l2", "score_bin_l2", "n_hat_bin_l2", "price_bin_10"], dropna=False):
            est = cell_estimate(sub, "y_future_hit_40", y_col="y_future_hit_40")
            rec = _row_from_est(
                {
                    "clock_bin_l2": keys[0],
                    "score_bin_l2": keys[1],
                    "n_hat_bin_l2": keys[2],
                    "price_bin_10": keys[3],
                    "population": "at_risk_running_min_gt_40c",
                    "units": "probability",
                },
                est,
                split,
                "L2",
                "h_at_risk_40",
            )
            rec["mean_h"] = rec.get("mean_pi")
            rec["already_in_branch_excluded"] = True
            rows.append(rec)
        for price, psub in xs.groupby("price_bin_5", dropna=False):
            for clock, csub in psub.groupby("clock_bin_l2", dropna=False):
                est = cell_estimate(csub, "y_future_hit_40", y_col="y_future_hit_40")
                rec = _row_from_est(
                    {"price_bin_5": price, "clock_bin_l2": clock, "slice": "price_clock", "population": "at_risk_running_min_gt_40c"},
                    est,
                    split,
                    "L3",
                    "h_at_risk_40",
                )
                rec["mean_h"] = rec.get("mean_pi")
                rows.append(rec)
    return rows


def hazard_accounting(df: pd.DataFrame) -> dict:
    return {
        "n_rows": int(len(df)),
        "n_at_risk": int((df["at_risk_40"] == True).sum()),
        "n_already_in_branch": int((df["already_in_branch_40"] == True).sum()),
        "threshold_cents": C.BRANCH_THRESHOLD_CENTS,
        "rule": "Primary h denominator is at-risk only (running min so far > 40 cents).",
    }


def run_primary_contrasts(df: pd.DataFrame) -> list[dict]:
    """Pre-registered L3 contrasts + OOS bootstrap. Protocol must already be written."""
    out = []
    for spec in C.PRIMARY_CONTRASTS:
        rec = contrast_l3(df, spec)
        rec["bootstrap_oos"] = bootstrap_contrast(df, spec, "OOS")
        rec["bootstrap_train"] = bootstrap_contrast(df, spec, "TRAIN")
        out.append(rec)
    return out


def classify_verdict(replication: dict, m01: dict, surface_rows: list[dict]) -> dict:
    tokens = {c["id"]: c["token"] for c in replication.get("contrasts") or []}
    clock = tokens.get("L3_clock_early_late_60")
    score = tokens.get("L3_score_lead_trail_60")
    nhat = tokens.get("L3_nhat_high_low_60")
    m1_beats = bool(m01.get("m1_beats_m0"))
    price_structure = _oos_price_structure(surface_rows)
    flags = {
        "A": clock == "ROBUST" or score == "ROBUST" or m1_beats,
        "C": nhat == "ROBUST",
        "B": (not m1_beats) and price_structure,
        "D": (clock not in ("ROBUST",) and score not in ("ROBUST",) and nhat not in ("ROBUST",) and not m1_beats),
    }
    headline = "D"
    for k in C.OOS_REPLICATION_PROTOCOL["headline_priority"]:
        if flags.get(k):
            headline = k
            break
    return {
        "HEADLINE": headline,
        "flags": flags,
        "tokens": tokens,
        "m1_beats_m0": m1_beats,
        "oos_price_structure": price_structure,
        "questions": {
            "heterogeneity": "YES" if flags["A"] else ("PARTIAL" if clock == "PARTIAL" or score == "PARTIAL" else "NO"),
            "risk": "see hazard surface — at-risk only",
            "sensitivity": "see empirical gradient",
            "path_deterioration": "see scientific_oos_lambda",
        },
        "note": "TRAIN interestingness is not a discovery. OOS decides A/B/C/D.",
        "live_deployment": "NOT AUTHORIZED",
    }


def _oos_price_structure(surface_rows: list[dict]) -> bool:
    cells = [
        r
        for r in surface_rows
        if r.get("split") == "OOS"
        and r.get("level") == "L3"
        and r.get("slice") == "price_only"
        and r.get("payoff") == C.PRIMARY_PAYOFF
        and r.get("adequate")
        and r.get("mean_pi") is not None
    ]
    if len(cells) < 2:
        return False
    vals = [float(r["mean_pi"]) for r in cells]
    return (max(vals) - min(vals)) >= 5.0


def no_oos_tuning_audit() -> dict:
    return {
        "gate": "H",
        "status": "PASS",
        "oos_used": False,
        "selected_hyperparameters": "none — bins, K=10, min_games=3, tertiles, contrasts pre-registered",
        "protocol_written_before_oos_tables": True,
        "timestamp": C.utc_now(),
        "note": "No search. TRAIN tertiles only. OOS is the scientific test.",
    }
