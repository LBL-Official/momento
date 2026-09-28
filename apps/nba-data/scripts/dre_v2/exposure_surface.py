"""Theoretical exposure-value surface. Not executable. No fills invented."""

from __future__ import annotations

import numpy as np

from . import config as C
from .models import _scalar


def batch_predict(rows, fitted, fam: str, yname: str) -> np.ndarray:
    """Vectorized probabilities; NaN where complete-case fails."""
    n = len(rows)
    out = np.full(n, np.nan, dtype=float)
    pack = fitted.get((fam, yname))
    if not pack or pack["model"] is None:
        return out
    cols = pack["cols"]
    vecs = []
    idx = []
    for i, r in enumerate(rows):
        vec = []
        ok = True
        for c in cols:
            v = _scalar(r.get(c))
            if v is None:
                ok = False
                break
            vec.append(v)
        if ok:
            vecs.append(vec)
            idx.append(i)
    if not vecs:
        return out
    p = pack["model"].predict_proba(np.asarray(vecs, dtype=float))[:, 1]
    out[np.asarray(idx, dtype=int)] = p
    return out


def attach_probabilities(rows, fitted) -> None:
    """Attach B0/M3/M5 probabilities used by exposure and remaining-alpha objects."""
    for fam in ("B0", "M3", "M5"):
        p_yes = batch_predict(rows, fitted, fam, "y_settle_yes")
        p_rec = batch_predict(rows, fitted, fam, "y_rec_ge_10_k5")
        p_down = batch_predict(rows, fitted, fam, "y_det_ge_10_end")
        for i, r in enumerate(rows):
            r[f"p_settle_{fam}"] = None if np.isnan(p_yes[i]) else float(p_yes[i])
            r[f"p_rec10_k5_{fam}"] = None if np.isnan(p_rec[i]) else float(p_rec[i])
            r[f"p_det10_end_{fam}"] = None if np.isnan(p_down[i]) else float(p_down[i])
            if r.get(f"p_settle_{fam}") is not None and r.get("current_price") is not None:
                px = float(r["current_price"])
                p = r[f"p_settle_{fam}"]
                r[f"terminal_probability_edge_{fam}"] = p - (px / 100.0)
                r[f"ev_hold_mtm_cents_{fam}"] = (C.SETTLEMENT_YES_CENTS * p) - px
                r[f"ev_hold_from_entry_cents_{fam}"] = (C.SETTLEMENT_YES_CENTS * p) - float(C.ENTRY_CENTS)


def score_h(h, ev, p_down, p_rec, family: str, lam_d: float, lam_r: float, gamma: float) -> float:
    """Theoretical objective at exposure fraction h. Linear families are corner-prone."""
    if family == "A":
        return h * ev
    if family == "B":
        return h * ev - lam_d * h * p_down
    if family == "C":
        return h * ev - lam_d * h * p_down + lam_r * h * p_rec
    if family == "D":
        return h * ev - 0.5 * gamma * h * h
    raise ValueError(family)


def choose_h(ev, p_down, p_rec, family: str, lam_d: float, lam_r: float, gamma: float) -> tuple[float, list[float]]:
    scores = [
        score_h(h, ev, p_down, p_rec, family, lam_d, lam_r, gamma) for h in C.H_GRID
    ]
    best_i = int(np.argmax(scores))
    return float(C.H_GRID[best_i]), [float(s) for s in scores]


def realized_continuation_cents(r) -> float | None:
    """Candle-settlement continuation vs current bid. Not a fill P&L."""
    y = r.get("y_settle_yes")
    px = r.get("current_price")
    if y is None or px is None:
        return None
    settle = C.SETTLEMENT_YES_CENTS if int(y) == 1 else C.SETTLEMENT_NO_CENTS
    return float(settle) - float(px)


def select_hyperparams(rows, model_fam: str = "M3") -> dict:
    """Select lambdas on VALIDATION only. Freeze before OOS."""
    val = [
        r
        for r in rows
        if r["dataset_split"] == "VALIDATION"
        and r.get(f"p_settle_{model_fam}") is not None
        and r.get(f"p_det10_end_{model_fam}") is not None
        and r.get(f"p_rec10_k5_{model_fam}") is not None
        and r.get("y_settle_yes") is not None
        and r.get("current_price") is not None
    ]

    def mean_realized(family, lam_d, lam_r, gamma):
        xs = []
        for r in val:
            ev = r[f"ev_hold_mtm_cents_{model_fam}"]
            pdn = r[f"p_det10_end_{model_fam}"]
            pr = r[f"p_rec10_k5_{model_fam}"]
            h, _ = choose_h(ev, pdn, pr, family, lam_d, lam_r, gamma)
            cont = realized_continuation_cents(r)
            if cont is None:
                continue
            y_down = r.get("y_det_ge_10_end")
            y_rec = r.get("y_rec_ge_10_k5")
            if y_down is None:
                y_down = 0
            if y_rec is None:
                y_rec = 0
            if family == "A":
                xs.append(h * cont)
            elif family == "B":
                xs.append(h * cont - lam_d * h * float(y_down))
            elif family == "C":
                xs.append(h * cont - lam_d * h * float(y_down) + lam_r * h * float(y_rec))
            else:
                xs.append(h * cont - 0.5 * gamma * h * h)
        return float(np.mean(xs)) if xs else None, len(xs)

    selected = {
        "A": {"lam_d": 0.0, "lam_r": 0.0, "gamma": 0.0, "selection": "no_hyperparameter"},
        "model_family": model_fam,
        "split_used": "VALIDATION",
        "oos_used": False,
        "note": "Hyperparameters frozen on VALIDATION. OOS is evaluation only.",
    }

    best_b, best_b_score = None, None
    grid_b = []
    for lam in C.LAMBDA_D_GRID:
        sc, n = mean_realized("B", lam, 0.0, 0.0)
        grid_b.append({"lam_d": lam, "val_score": sc, "n": n})
        if sc is not None and (best_b_score is None or sc > best_b_score):
            best_b, best_b_score = lam, sc
    selected["B"] = {"lam_d": best_b, "lam_r": 0.0, "gamma": 0.0, "val_score": best_b_score, "grid": grid_b}

    best_c, best_c_score = None, None
    grid_c = []
    for ld in C.LAMBDA_D_GRID:
        for lr in C.LAMBDA_R_GRID:
            sc, n = mean_realized("C", ld, lr, 0.0)
            grid_c.append({"lam_d": ld, "lam_r": lr, "val_score": sc, "n": n})
            if sc is not None and (best_c_score is None or sc > best_c_score):
                best_c, best_c_score = (ld, lr), sc
    selected["C"] = {
        "lam_d": best_c[0] if best_c else None,
        "lam_r": best_c[1] if best_c else None,
        "gamma": 0.0,
        "val_score": best_c_score,
        "grid": grid_c,
    }

    best_d, best_d_score = None, None
    grid_d = []
    for g in C.GAMMA_GRID:
        sc, n = mean_realized("D", 0.0, 0.0, g)
        grid_d.append({"gamma": g, "val_score": sc, "n": n})
        if sc is not None and (best_d_score is None or sc > best_d_score):
            best_d, best_d_score = g, sc
    selected["D"] = {"lam_d": 0.0, "lam_r": 0.0, "gamma": best_d, "val_score": best_d_score, "grid": grid_d}
    return selected


def apply_target_delta(rows, selected, model_fam: str = "M3") -> None:
    for r in rows:
        ev = r.get(f"ev_hold_mtm_cents_{model_fam}")
        pdn = r.get(f"p_det10_end_{model_fam}")
        pr = r.get(f"p_rec10_k5_{model_fam}")
        if ev is None or pdn is None or pr is None:
            r[f"target_delta_{model_fam}_A"] = None
            r[f"target_delta_{model_fam}_B"] = None
            r[f"target_delta_{model_fam}_C"] = None
            r[f"target_delta_{model_fam}_D"] = None
            continue
        for fam in ("A", "B", "C", "D"):
            hp = selected[fam]
            h, scores = choose_h(ev, pdn, pr, fam, hp["lam_d"] or 0.0, hp["lam_r"] or 0.0, hp["gamma"] or 0.0)
            r[f"target_delta_{model_fam}_{fam}"] = h
            r[f"objective_scores_{model_fam}_{fam}"] = scores


def exposure_aggregates(rows, model_fam: str = "M3") -> list[dict]:
    out = []
    for split in ("TRAIN", "VALIDATION", "OOS"):
        xs = [r for r in rows if r["dataset_split"] == split and r.get(f"p_settle_{model_fam}") is not None]
        for lo in range(5, 85, 5):
            bucket = [r for r in xs if r.get("current_price") is not None and lo <= r["current_price"] < lo + 5]
            if not bucket:
                continue
            rec = {
                "split": split,
                "model_family": model_fam,
                "price_lo": lo,
                "price_hi": lo + 5,
                "n": len(bucket),
                "mean_p_settle": _mean(bucket, f"p_settle_{model_fam}"),
                "mean_p_rec": _mean(bucket, f"p_rec10_k5_{model_fam}"),
                "mean_p_down": _mean(bucket, f"p_det10_end_{model_fam}"),
                "mean_edge": _mean(bucket, f"terminal_probability_edge_{model_fam}"),
                "mean_ev_mtm": _mean(bucket, f"ev_hold_mtm_cents_{model_fam}"),
                "emp_settle": _mean(bucket, "y_settle_yes"),
                "emp_rec10_k5": _mean(bucket, "y_rec_ge_10_k5"),
                "emp_det10_end": _mean(bucket, "y_det_ge_10_end"),
                "mean_h_A": _mean(bucket, f"target_delta_{model_fam}_A"),
                "mean_h_B": _mean(bucket, f"target_delta_{model_fam}_B"),
                "mean_h_C": _mean(bucket, f"target_delta_{model_fam}_C"),
                "mean_h_D": _mean(bucket, f"target_delta_{model_fam}_D"),
                "frac_h_A_pos": _frac_pos(bucket, f"target_delta_{model_fam}_A"),
                "frac_h_D_interior": _frac_interior(bucket, f"target_delta_{model_fam}_D"),
                "label": "THEORETICAL — NOT EXECUTION",
            }
            out.append(rec)
    return out


def _mean(rows, key):
    vs = [r.get(key) for r in rows if r.get(key) is not None]
    if not vs:
        return None
    return float(np.mean(np.asarray(vs, dtype=float)))


def _frac_pos(rows, key):
    vs = [r.get(key) for r in rows if r.get(key) is not None]
    if not vs:
        return None
    return float(np.mean([1.0 if v and v > 0 else 0.0 for v in vs]))


def _frac_interior(rows, key):
    vs = [r.get(key) for r in rows if r.get(key) is not None]
    if not vs:
        return None
    return float(np.mean([1.0 if 0 < float(v) < 1 else 0.0 for v in vs]))


def oos_policy_score(rows, selected, model_fam: str = "M3") -> dict:
    """Evaluate frozen VAL hyperparameters on OOS. Not used for selection."""
    out = {}
    oos = [
        r
        for r in rows
        if r["dataset_split"] == "OOS" and r.get(f"target_delta_{model_fam}_A") is not None
    ]
    for fam in ("A", "B", "C", "D"):
        xs = []
        hs = []
        for r in oos:
            h = r.get(f"target_delta_{model_fam}_{fam}")
            cont = realized_continuation_cents(r)
            if h is None or cont is None:
                continue
            xs.append(h * cont)
            hs.append(h)
        out[fam] = {
            "n": len(xs),
            "mean_h": float(np.mean(hs)) if hs else None,
            "mean_realized_h_times_continuation_cents": float(np.mean(xs)) if xs else None,
            "frac_h_gt_0": float(np.mean([1 if h > 0 else 0 for h in hs])) if hs else None,
            "frac_h_eq_1": float(np.mean([1 if abs(h - 1) < 1e-9 else 0 for h in hs])) if hs else None,
            "frac_interior": float(np.mean([1 if 0 < h < 1 else 0 for h in hs])) if hs else None,
            "label": "THEORETICAL candle-settlement continuation × h. NOT a fill P&L.",
        }
    # Stability: B0 vs M3 disagreement on Family A
    both = [
        r
        for r in oos
        if r.get("target_delta_B0_A") is not None and r.get(f"target_delta_{model_fam}_A") is not None
    ]
    if both:
        disagree = sum(
            1
            for r in both
            if abs(float(r["target_delta_B0_A"]) - float(r[f"target_delta_{model_fam}_A"])) > 1e-9
        )
        out["disagreement_B0_vs_model_family_A"] = {
            "n": len(both),
            "n_disagree": disagree,
            "frac_disagree": disagree / len(both),
        }
    return out
