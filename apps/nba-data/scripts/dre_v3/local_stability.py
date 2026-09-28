"""Local sensitivity of theoretical h* to small as-of state perturbations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .exposure_grid import H, choose_h
from .models import predict_binary, predict_multinomial
from .objective_n1_utility import expected_utility
from .objective_n3_recovery import expected_path_moment
from .objective_n4_asymmetric import expected_ddp, n4_value


PERTS = {
    "price_plus": ("current_price", 1.0),
    "price_minus": ("current_price", -1.0),
    "score_plus": ("score_differential_from_A1", 1.0),
    "score_minus": ("score_differential_from_A1", -1.0),
    "clock_plus": ("game_seconds_remaining", 30.0),
    "clock_minus": ("game_seconds_remaining", -30.0),
    "poss_plus": ("possessions_since_entry", 1.0),
    "poss_minus": ("possessions_since_entry", -1.0),
}


def analyze(df: pd.DataFrame, fitted: dict, selected: dict, n: int = 2500) -> dict:
    oos = df[(df["dataset_split"] == "OOS") & df["p_terminal"].notna() & df["h_N1"].notna()].copy()
    if oos.empty:
        return {"status": "INSUFFICIENT"}
    if len(oos) > n:
        oos = oos.sample(n, random_state=C.RANDOM_SEED)
    families = {
        "N1": _h_n1,
        "N4": _h_n4,
    }
    out = {"n": int(len(oos)), "note": "THEORETICAL h* sensitivity. Not an execution stress test.", "families": {}}
    all_flip = []
    for fam, fn in families.items():
        base = fn(oos, fitted, selected)
        by = {}
        sens_all = []
        for name, (col, delta) in PERTS.items():
            alt = oos.copy()
            alt[col] = pd.to_numeric(alt[col], errors="coerce") + delta
            h2 = fn(alt, fitted, selected)
            ok = np.isfinite(base) & np.isfinite(h2)
            sens = np.abs(h2[ok] - base[ok])
            sens_all.append(sens)
            by[name] = _summ(sens)
        cat = np.concatenate(sens_all) if sens_all else np.array([])
        rec = {"overall": _summ(cat), "by_perturbation": by, "flip_01_rate": float(np.mean(cat >= 0.99)) if len(cat) else None}
        out["families"][fam] = rec
        all_flip.append(rec["flip_01_rate"])
    # backward-compatible N1 overall for reports
    n1 = out["families"]["N1"]
    out["overall"] = n1["overall"]
    out["by_perturbation"] = n1["by_perturbation"]
    out["flip_01_rate"] = n1["flip_01_rate"]
    out["family"] = "N1"
    return out


def _h_n1(xs: pd.DataFrame, fitted: dict, selected: dict) -> np.ndarray:
    p = predict_binary(fitted.get("p_terminal"), xs)
    out = np.full(len(xs), np.nan)
    ok = np.isfinite(p)
    if not ok.any():
        return out
    vals = expected_utility(p[ok], H, selected["N1"]["kind"], selected["N1"]["param"])
    h, _, _ = choose_h(vals)
    out[ok] = h
    return out


def _h_n4(xs: pd.DataFrame, fitted: dict, selected: dict) -> np.ndarray:
    p = predict_binary(fitted.get("p_terminal"), xs)
    pb = predict_multinomial(fitted.get("path_end"), xs, C.PATH_BINS)
    out = np.full(len(xs), np.nan)
    ok = np.isfinite(p) & np.isfinite(pb).all(axis=1)
    if not ok.any():
        return out
    rec = expected_path_moment(pb[ok], C.BIN_UU)
    e_ddp = expected_ddp(pb[ok], selected["N4"]["p"])
    vals = n4_value(p[ok], e_ddp, rec, selected["N4"]["a"], selected["N4"]["b"], selected["N4"]["p"], H)
    h, _, _ = choose_h(vals)
    out[ok] = h
    return out


def _summ(s: np.ndarray) -> dict:
    if len(s) == 0:
        return {"n": 0}
    return {
        "n": int(len(s)),
        "median": float(np.median(s)),
        "p90": float(np.quantile(s, 0.90)),
        "max": float(s.max()),
        "mean": float(s.mean()),
    }
