"""Matched-price state comparison. Pre-registered. Not an execution study."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, wasserstein_distance

from . import config as C


def price_bin(price, width: int) -> float:
    return np.floor(np.asarray(price, float) / width) * width


def slice_masks(df: pd.DataFrame) -> dict:
    per = pd.to_numeric(df["period"], errors="coerce")
    el = pd.to_numeric(df["elapsed_game_seconds"], errors="coerce")
    gsr = pd.to_numeric(df["game_seconds_remaining"], errors="coerce")
    sc = pd.to_numeric(df["score_differential_from_A1"], errors="coerce")
    age = pd.to_numeric(df["market_age_seconds"], errors="coerce")
    rem = pd.to_numeric(df["est_remaining_r1"], errors="coerce")
    det = pd.to_numeric(df["deterioration_cents"], errors="coerce")
    rec = pd.to_numeric(df["recovery_from_trough"], errors="coerce")
    return {
        "early": (per <= 2) | (el < 1440),
        "late": (per >= 4) & (gsr <= 360),
        "leading": sc >= 8,
        "trailing": sc <= -8,
        "fresh": age <= 15,
        "stale": age >= 60,
        "high_remaining": rem >= 80,
        "low_remaining": rem < 40,
        "deteriorating": det >= 10,
        "recovering": (rec >= 5) & (det < 10),
        "stable_det": det < 5,
    }


def _dist(a: np.ndarray, b: np.ndarray) -> dict:
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) < 8 or len(b) < 8:
        return {"wasserstein": None, "ks": None, "n_a": int(len(a)), "n_b": int(len(b))}
    return {
        "wasserstein": float(wasserstein_distance(a, b)),
        "ks": float(ks_2samp(a, b, mode="asymp").statistic),
        "n_a": int(len(a)),
        "n_b": int(len(b)),
    }


def _q(x: np.ndarray) -> dict:
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return {"n": 0}
    qs = np.quantile(x, [0.10, 0.25, 0.50, 0.75, 0.90])
    return {
        "n": int(len(x)),
        "mean": float(x.mean()),
        "median": float(np.median(x)),
        "p10": float(qs[0]),
        "p25": float(qs[1]),
        "p50": float(qs[2]),
        "p75": float(qs[3]),
        "p90": float(qs[4]),
    }


def _rate(s: pd.Series) -> float | None:
    v = pd.to_numeric(s, errors="coerce").dropna()
    if len(v) == 0:
        return None
    return float(v.mean())


def _slice_stats(b: pd.DataFrame, hz: str) -> dict:
    if len(b) == 0:
        return {"n": 0, "trades": 0, "games": 0}
    dd = b[f"dd_{hz}"].to_numpy(float) if f"dd_{hz}" in b.columns else np.array([])
    ue = b[f"ue_{hz}"].to_numpy(float) if f"ue_{hz}" in b.columns else np.array([])
    return {
        "n": int(len(b)),
        "trades": int(b["trade_id"].nunique()),
        "games": int(b["event_id"].nunique()),
        "adequate": bool(len(b) >= C.PRIMARY["min_rows"] and b["trade_id"].nunique() >= C.PRIMARY["min_trades"]),
        "dd": _q(dd),
        "ue": _q(ue),
        "p_settle": _rate(b["y_settle_yes"]),
        "p_rec10": _rate(b[f"y_rec10_{hz}"]) if f"y_rec10_{hz}" in b.columns else None,
        "p_det10": _rate(b[f"y_det10_{hz}"]) if f"y_det10_{hz}" in b.columns else None,
        "p_rec20": _rate(b[f"y_rec20_{hz}"]) if f"y_rec20_{hz}" in b.columns else None,
        "p_det20": _rate(b[f"y_det20_{hz}"]) if f"y_det20_{hz}" in b.columns else None,
        "mean_poss_to_det10": float(np.nanmean(b["poss_to_det10"])) if b["poss_to_det10"].notna().any() else None,
        "mean_poss_to_rec10": float(np.nanmean(b["poss_to_rec10"])) if b["poss_to_rec10"].notna().any() else None,
        "path_class": {c: float((b[f"path_class_{hz}"] == c).mean()) for c in C.PATH_CLASSES if f"path_class_{hz}" in b.columns},
        "top_game_share": float(b.groupby("event_id").size().max() / len(b)) if len(b) else None,
    }


def contrast_pair(df: pd.DataFrame, a: pd.DataFrame, b: pd.DataFrame, hz: str, name: str) -> dict:
    sa, sb = _slice_stats(a, hz), _slice_stats(b, hz)
    dd_d = _dist(a[f"dd_{hz}"].to_numpy(float), b[f"dd_{hz}"].to_numpy(float)) if f"dd_{hz}" in a.columns else {}
    rec_d = None
    if sa.get("p_rec10") is not None and sb.get("p_rec10") is not None:
        rec_d = abs(sa["p_rec10"] - sb["p_rec10"])
    det_d = None
    if sa.get("p_det10") is not None and sb.get("p_det10") is not None:
        det_d = abs(sa["p_det10"] - sb["p_det10"])
    set_d = None
    if sa.get("p_settle") is not None and sb.get("p_settle") is not None:
        set_d = abs(sa["p_settle"] - sb["p_settle"])
    med_d = None
    if sa.get("dd", {}).get("median") is not None and sb.get("dd", {}).get("median") is not None:
        med_d = abs(sa["dd"]["median"] - sb["dd"]["median"])
    material = bool(
        (sa.get("adequate") and sb.get("adequate"))
        and (
            (rec_d is not None and rec_d >= C.PRIMARY["min_abs_rate_delta"])
            or (det_d is not None and det_d >= C.PRIMARY["min_abs_rate_delta"])
            or (set_d is not None and set_d >= C.PRIMARY["min_abs_rate_delta"])
            or (med_d is not None and med_d >= C.PRIMARY["min_abs_median_dd"])
            or ((dd_d.get("wasserstein") or 0) >= C.PRIMARY["min_wasserstein_dd"])
        )
    )
    return {
        "name": name,
        "a": sa,
        "b": sb,
        "delta": {
            "p_settle": set_d,
            "p_rec10": rec_d,
            "p_det10": det_d,
            "median_dd": med_d,
            "wasserstein_dd": dd_d.get("wasserstein"),
            "ks_dd": dd_d.get("ks"),
        },
        "adequate": bool(sa.get("adequate") and sb.get("adequate")),
        "material": material,
        "excluded_reason": None if (sa.get("adequate") and sb.get("adequate")) else "below_min_sample",
        "label": "RESEARCH DISTRIBUTION — NOT A TRADING INSTRUCTION",
    }


def run_matched(df: pd.DataFrame) -> dict:
    masks = slice_masks(df)
    pairs = (
        ("early", "late"),
        ("leading", "trailing"),
        ("fresh", "stale"),
        ("high_remaining", "low_remaining"),
        ("deteriorating", "recovering"),
    )
    out = {"primary_spec": C.PRIMARY, "by_split": {}, "excluded": []}
    for split in ("TRAIN", "VALIDATION", "OOS"):
        xs = df[df["dataset_split"] == split].copy()
        rec = {"bands": {}}
        for width in ROBUST if False else C.ROBUST_BINS:
            xs["_bin"] = price_bin(xs["current_price"], width)
            bands = {}
            for lo in range(40, 85, width):
                band = xs[(xs["_bin"] >= lo) & (xs["_bin"] < lo + width)]
                if len(band) < 20:
                    continue
                sl = {}
                for pa, pb in pairs:
                    ca = contrast_pair(xs, band[masks[pa].reindex(band.index).fillna(False)], band[masks[pb].reindex(band.index).fillna(False)], "5", f"{pa}_vs_{pb}")
                    sl[f"{pa}_vs_{pb}"] = ca
                    if ca["excluded_reason"]:
                        out["excluded"].append({"split": split, "width": width, "price_lo": lo, "pair": f"{pa}_vs_{pb}", "reason": ca["excluded_reason"]})
                bands[str(lo)] = {
                    "n": int(len(band)),
                    "trades": int(band["trade_id"].nunique()),
                    "slices": sl,
                    "emp_settle": _rate(band["y_settle_yes"]),
                }
            rec[f"bin_{width}"] = bands
        # NN ±1¢ around 60
        nn = xs[(xs["current_price"] >= 60 - C.NN_TOLERANCE) & (xs["current_price"] <= 60 + C.NN_TOLERANCE)]
        rec["nn_1c_60"] = {
            "n": int(len(nn)),
            "early_vs_late": contrast_pair(
                xs,
                nn[masks["early"].reindex(nn.index).fillna(False)],
                nn[masks["late"].reindex(nn.index).fillna(False)],
                "5",
                "early_vs_late_nn",
            ),
        }
        out["by_split"][split] = rec
    # primary pointer
    prim = (((out["by_split"].get("OOS") or {}).get("bin_5") or {}).get("60") or {}).get("slices", {}).get("early_vs_late")
    out["primary_oos_early_late_60"] = prim
    return out


def bootstrap_primary(df: pd.DataFrame) -> dict:
    """Game-clustered bootstrap of OOS 60¢ 5-bin early vs late P(settle) and median DD_5."""
    oos = df[df["dataset_split"] == "OOS"].copy()
    oos["_bin"] = price_bin(oos["current_price"], 5)
    band = oos[(oos["_bin"] >= 60) & (oos["_bin"] < 65)]
    masks = slice_masks(band)
    games = band["event_id"].dropna().unique()
    if len(games) < 8:
        return {"status": "INSUFFICIENT", "n_games": int(len(games))}
    rng = np.random.default_rng(C.RANDOM_SEED)
    deltas_s, deltas_d = [], []
    for _ in range(C.BOOTSTRAP_GAMES):
        draw = rng.choice(games, size=len(games), replace=True)
        # stack rows of drawn games
        parts = [band[band["event_id"] == g] for g in draw]
        boot = pd.concat(parts, ignore_index=True)
        m = slice_masks(boot)
        a, b = boot[m["early"]], boot[m["late"]]
        if len(a) < 10 or len(b) < 10:
            continue
        deltas_s.append(float(a["y_settle_yes"].mean() - b["y_settle_yes"].mean()))
        deltas_d.append(float(np.nanmedian(a["dd_5"]) - np.nanmedian(b["dd_5"])))
    if not deltas_s:
        return {"status": "INSUFFICIENT"}
    arr_s, arr_d = np.array(deltas_s), np.array(deltas_d)
    return {
        "status": "OK",
        "n_games": int(len(games)),
        "n_boot": int(len(arr_s)),
        "settle_delta": {"mean": float(arr_s.mean()), "p05": float(np.quantile(arr_s, 0.05)), "p95": float(np.quantile(arr_s, 0.95))},
        "median_dd_delta": {"mean": float(arr_d.mean()), "p05": float(np.quantile(arr_d, 0.05)), "p95": float(np.quantile(arr_d, 0.95))},
        "method": "game-clustered bootstrap",
        "note": "Rows are not independent. Interval is research-only.",
    }
