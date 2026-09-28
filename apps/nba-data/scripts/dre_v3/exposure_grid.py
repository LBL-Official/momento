"""Evaluate Value(h) on the discrete grid. Theoretical retained exposure only."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .objective_n1_utility import N1_GRID, expected_utility, realized_utility, reference_score
from .objective_n2_tailrisk import cvar_from_bins, n2_eu, n2_linear
from .objective_n3_recovery import expected_path_moment, n3_value
from .objective_n4_asymmetric import expected_ddp, n4_value


H = np.array(C.H_GRID, dtype=float)


def choose_h(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """values (n, H). Tie-break: among near-max, preserve higher h. Report plateau width.

    Near-optimal uses a relative tolerance of the row's value range so high-γ CRRA
    (tiny absolute utils) is not declared a full-grid tie. A numerically flat row
    (range below FLAT_ABS) is left as NaN rather than a fake corner.
    """
    if not np.all(np.isfinite(values)):
        raise RuntimeError("objective values numerically invalid")
    vmax = values.max(axis=1, keepdims=True)
    vmin = values.min(axis=1, keepdims=True)
    span = vmax - vmin
    flat = span.ravel() < C.FLAT_ABS
    rel = np.maximum(C.NEAR_OPT_ABS, C.NEAR_OPT_REL * np.maximum(span, C.FLAT_ABS))
    near = values >= (vmax - rel)
    h_idx = np.where(near, np.arange(values.shape[1])[None, :], -1).max(axis=1)
    exact = np.abs(values - vmax) <= np.maximum(C.TIE_ABS, C.NEAR_OPT_REL * np.maximum(span, C.FLAT_ABS))
    plateau = exact.sum(axis=1)
    h_star = H[h_idx].astype(float)
    h_star[flat] = np.nan
    plateau[flat] = values.shape[1]
    return h_star, plateau.astype(int), vmax.ravel()


def _p_bins(df: pd.DataFrame, hz: str = "end") -> np.ndarray:
    cols = [f"p_{b}_{hz}" for b in C.PATH_BINS]
    p = df[cols].to_numpy(float)
    ok = np.isfinite(p).all(axis=1)
    p = np.where(ok[:, None], p, np.nan)
    s = np.nansum(p, axis=1, keepdims=True)
    with np.errstate(invalid="ignore"):
        p = p / s
    return p


def _assign(n: int, mask: np.ndarray, values: np.ndarray) -> np.ndarray:
    out = np.full(n, np.nan)
    out[mask] = values
    return out


def select_and_apply(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Select hyperparameters on VALIDATION only; apply frozen rules to valid rows.

    Missing path probabilities are left as NaN h*. They are not filled with a uniform prior.
    """
    work = df.copy()
    n = len(work)
    p = work["p_terminal"].to_numpy(float)
    y = work["y_settle_yes"].to_numpy(float)
    dd = work["dd_end"].to_numpy(float)
    uu = work["uu_end"].to_numpy(float)
    pb = _p_bins(work, "end")
    ok_p = np.isfinite(p)
    ok_path = np.isfinite(pb).all(axis=1) & ok_p
    ok_y = np.isfinite(y)
    is_val = (work["dataset_split"] == "VALIDATION").to_numpy()
    path_valid = work["path_valid_end"].to_numpy(bool) if "path_valid_end" in work.columns else np.ones(n, bool)
    val_term = is_val & ok_p & ok_y
    val_path = val_term & ok_path & path_valid & np.isfinite(dd) & np.isfinite(uu)
    if not val_term.any():
        raise RuntimeError("VALIDATION terminal mask empty — cannot select N1")
    if not val_path.any():
        raise RuntimeError("VALIDATION path mask empty — cannot select N2/N3/N4")

    selected = {}
    curves_idx = _curve_indices(work)

    # ----- N1 (VALIDATION only for selection) -----
    best, best_score = None, None
    n1_grid = []
    p_val = p[val_term]
    y_val = y[val_term]
    for kind, param in N1_GRID:
        h_star, plateau, _ = choose_h(expected_utility(p_val, H, kind, param))
        usable = np.isfinite(h_star)
        if usable.sum() < 20:
            n1_grid.append({"kind": kind, "param": param, "val_score": None, "val_interior": None, "n_val": int(usable.sum()), "status": "NUMERICALLY_FLAT"})
            continue
        sc = reference_score(y_val[usable], h_star[usable])
        n1_grid.append({"kind": kind, "param": param, "val_score": sc, "val_interior": _interior_rate(h_star), "n_val": int(usable.sum()), "flat_rate": float((plateau >= len(H)).mean())})
        if best_score is None or sc > best_score:
            best, best_score = (kind, param), sc
    if best is None:
        raise RuntimeError("all N1 utilities were numerically flat on VALIDATION")
    selected["N1"] = {
        "kind": best[0],
        "param": best[1],
        "val_score": best_score,
        "grid": n1_grid,
        "oos_used": False,
        "selection_yardstick": "realized_CRRA_gamma_2",
    }
    h_star, plateau, vmax = choose_h(expected_utility(p[ok_p], H, best[0], best[1]))
    work["h_N1"] = _assign(n, ok_p, h_star)
    work["plateau_N1"] = _assign(n, ok_p, plateau.astype(float))
    work["vmax_N1"] = _assign(n, ok_p, vmax)
    work["interior_N1"] = (work["h_N1"] > 0) & (work["h_N1"] < 1)
    if int(np.isfinite(work["h_N1"]).sum()) < 100:
        raise RuntimeError("selected N1 produced too few finite h*")
    n1_sens = []
    is_oos = (work["dataset_split"] == "OOS").to_numpy()
    for kind, param in N1_GRID:
        hs, _, _ = choose_h(expected_utility(p[ok_p], H, kind, param))
        full = _assign(n, ok_p, hs)
        n1_sens.append(
            {
                "kind": kind,
                "param": param,
                "val_interior": _interior_rate(full[val_term]),
                "oos_interior": _interior_rate(full[is_oos & ok_p]),
                "oos_mean_h": (None if not np.isfinite(full[is_oos & ok_p]).any() else float(np.nanmean(full[is_oos & ok_p]))),
            }
        )
    selected["N1"]["sensitivity"] = n1_sens

    # ----- N2 -----
    best, best_score = None, None
    n2_grid = []
    p_vp = p[val_path]
    y_vp = y[val_path]
    pb_vp = pb[val_path]
    dd_vp = dd[val_path]
    for q in C.CVAR_Q:
        cvar_v = cvar_from_bins(pb_vp, q)
        for lam in C.LAMBDA_TAIL:
            for kind in ("linear", "eu"):
                vals = n2_linear(p_vp, cvar_v, lam, H) if kind == "linear" else n2_eu(p_vp, cvar_v, lam, H, gamma=2.0)
                h_star, _, _ = choose_h(vals)
                sc = reference_score(y_vp, h_star)
                n2_grid.append({"q": q, "lam": lam, "kind": kind, "val_score": sc, "val_interior": _interior_rate(h_star), "n_val": int(val_path.sum())})
                if best_score is None or sc > best_score:
                    best, best_score = (q, lam, kind), sc
    selected["N2"] = {
        "q": best[0],
        "lam": best[1],
        "kind": best[2],
        "val_score": best_score,
        "grid": n2_grid,
        "oos_used": False,
        "selection_yardstick": "realized_CRRA_gamma_2",
    }
    cvar = cvar_from_bins(pb[ok_path], best[0])
    vals = n2_linear(p[ok_path], cvar, best[1], H) if best[2] == "linear" else n2_eu(p[ok_path], cvar, best[1], H)
    h_star, plateau, vmax = choose_h(vals)
    work["h_N2"] = _assign(n, ok_path, h_star)
    work["plateau_N2"] = _assign(n, ok_path, plateau.astype(float))
    work["vmax_N2"] = _assign(n, ok_path, vmax)
    work["interior_N2"] = (work["h_N2"] > 0) & (work["h_N2"] < 1)

    cvar10 = cvar_from_bins(pb[ok_path], 0.10)
    h_lin, _, _ = choose_h(n2_linear(p[ok_path], cvar10, 1.0, H))
    work["h_N2_LINEAR"] = _assign(n, ok_path, h_lin)

    # ----- N3 -----
    rec_v = expected_path_moment(pb_vp, C.BIN_UU)
    down_v = expected_path_moment(pb_vp, C.BIN_DD)
    uu_vp = uu[val_path]
    best, best_score = None, None
    n3_grid = []
    for lr in C.LAMBDA_R:
        for ld in C.LAMBDA_D:
            h_star, _, _ = choose_h(n3_value(p_vp, rec_v, down_v, lr, ld, H))
            sc = reference_score(y_vp, h_star)
            n3_grid.append({"lam_r": lr, "lam_d": ld, "val_score": sc, "val_interior": _interior_rate(h_star), "n_val": int(val_path.sum())})
            if best_score is None or sc > best_score:
                best, best_score = (lr, ld), sc
    selected["N3"] = {
        "lam_r": best[0],
        "lam_d": best[1],
        "val_score": best_score,
        "grid": n3_grid,
        "oos_used": False,
        "selection_yardstick": "realized_CRRA_gamma_2",
    }
    rec = expected_path_moment(pb[ok_path], C.BIN_UU)
    down = expected_path_moment(pb[ok_path], C.BIN_DD)
    h_star, plateau, vmax = choose_h(n3_value(p[ok_path], rec, down, best[0], best[1], H))
    work["h_N3"] = _assign(n, ok_path, h_star)
    work["plateau_N3"] = _assign(n, ok_path, plateau.astype(float))
    work["vmax_N3"] = _assign(n, ok_path, vmax)
    work["interior_N3"] = (work["h_N3"] > 0) & (work["h_N3"] < 1)

    # ----- N4 -----
    best, best_score = None, None
    n4_grid = []
    for pwr in C.N4_P:
        e_ddp_v = expected_ddp(pb_vp, pwr)
        for a in C.N4_A:
            for b in C.N4_B:
                h_star, _, _ = choose_h(n4_value(p_vp, e_ddp_v, rec_v, a, b, pwr, H))
                sc = reference_score(y_vp, h_star)
                n4_grid.append({"p": pwr, "a": a, "b": b, "val_score": sc, "val_interior": _interior_rate(h_star), "n_val": int(val_path.sum())})
                if best_score is None or sc > best_score:
                    best, best_score = (pwr, a, b), sc
    selected["N4"] = {
        "p": best[0],
        "a": best[1],
        "b": best[2],
        "val_score": best_score,
        "grid": n4_grid,
        "oos_used": False,
        "selection_yardstick": "realized_CRRA_gamma_2",
    }
    e_ddp = expected_ddp(pb[ok_path], best[0])
    h_star, plateau, vmax = choose_h(n4_value(p[ok_path], e_ddp, rec, best[1], best[2], best[0], H))
    work["h_N4"] = _assign(n, ok_path, h_star)
    work["plateau_N4"] = _assign(n, ok_path, plateau.astype(float))
    work["vmax_N4"] = _assign(n, ok_path, vmax)
    work["interior_N4"] = (work["h_N4"] > 0) & (work["h_N4"] < 1)

    work["h_E0"] = 1.0
    work["h_E1"] = 0.0
    work["h_E2"] = pd.to_numeric(work["target_delta_M3_A"], errors="coerce")
    work["h_E3"] = _e3_price_bins(work, y, val_term)

    work["curve_sample"] = False
    work.loc[curves_idx, "curve_sample"] = True
    selected["accounting"] = {
        "W0_cents": C.W0_CENTS,
        "X_yes": C.X_YES,
        "X_no": C.X_NO,
        "basis": "entry_80_sunk_no_sale_assumption",
        "label": "THEORETICAL RETAINED EXPOSURE",
    }
    selected["n_ok_terminal"] = int(ok_p.sum())
    selected["n_ok_path"] = int(ok_path.sum())
    selected["n_val_terminal"] = int(val_term.sum())
    selected["n_val_path"] = int(val_path.sum())
    return work, selected


def _e3_price_bins(work: pd.DataFrame, y, val_mask) -> np.ndarray:
    """VAL-select a constant h per 5¢ price bin. Price-only descriptive baseline."""
    px = work["current_price"].to_numpy(float)
    h_out = np.full(len(work), np.nan)
    for lo in range(0, 100, 5):
        in_bin = (px >= lo) & (px < lo + 5) & np.isfinite(px)
        vm = val_mask & in_bin
        if vm.sum() < 20:
            # fallback: retain if mean price suggests positive EV vs 50
            h_out[in_bin] = 1.0 if lo >= 50 else 0.0
            continue
        best_h, best_sc = 1.0, None
        for hv in H:
            sc = float(np.nanmean(realized_utility(y[vm], np.full(vm.sum(), hv), "crra", 2.0)))
            if best_sc is None or sc > best_sc:
                best_h, best_sc = float(hv), sc
        h_out[in_bin] = best_h
    return h_out


def _interior_rate(h) -> float | None:
    h = np.asarray(h, float)
    h = h[np.isfinite(h)]
    if len(h) == 0:
        return None
    return float(np.mean((h > 0) & (h < 1)))


def _curve_indices(work: pd.DataFrame, n: int = 12) -> np.ndarray:
    idx = []
    for split in ("TRAIN", "VALIDATION", "OOS"):
        xs = work.index[work["dataset_split"] == split].to_numpy()
        if len(xs) == 0:
            continue
        step = max(1, len(xs) // 4)
        idx.extend(xs[::step][:4])
    return np.array(idx[:n], dtype=int)


def objective_curves(df: pd.DataFrame, selected: dict) -> list[dict]:
    """Full Value(h) for representative states — to see sharp / flat / unstable interiors."""
    samp = df[df["curve_sample"]].copy()
    p = samp["p_terminal"].to_numpy(float)
    pb = _p_bins(samp, "end")
    ok = np.isfinite(p) & np.isfinite(pb).all(axis=1)
    samp = samp.loc[ok].copy()
    p = p[ok]
    pb = pb[ok]
    if len(samp) == 0:
        return []
    rec = expected_path_moment(pb, C.BIN_UU)
    down = expected_path_moment(pb, C.BIN_DD)
    cvar = cvar_from_bins(pb, selected["N2"]["q"])
    n1 = expected_utility(p, H, selected["N1"]["kind"], selected["N1"]["param"])
    if selected["N2"]["kind"] == "linear":
        n2 = n2_linear(p, cvar, selected["N2"]["lam"], H)
    else:
        n2 = n2_eu(p, cvar, selected["N2"]["lam"], H)
    n3 = n3_value(p, rec, down, selected["N3"]["lam_r"], selected["N3"]["lam_d"], H)
    e_ddp = expected_ddp(np.nan_to_num(pb, nan=1.0 / len(C.PATH_BINS)), selected["N4"]["p"])
    n4 = n4_value(p, e_ddp, rec, selected["N4"]["a"], selected["N4"]["b"], selected["N4"]["p"], H)
    out = []
    for i, r in enumerate(samp.itertuples()):
        out.append(
            {
                "trade_id": r.trade_id,
                "event_id": r.event_id,
                "split": r.dataset_split,
                "current_price": r.current_price,
                "period": r.period,
                "game_seconds_remaining": r.game_seconds_remaining,
                "score_differential_from_A1": r.score_differential_from_A1,
                "p_terminal": None if np.isnan(p[i]) else float(p[i]),
                "h_grid": list(C.H_GRID),
                "V_N1": [float(x) for x in n1[i]],
                "V_N2": [float(x) for x in n2[i]],
                "V_N3": [float(x) for x in n3[i]],
                "V_N4": [float(x) for x in n4[i]],
                "h_N1": float(r.h_N1) if pd.notna(r.h_N1) else None,
                "h_N2": float(r.h_N2) if pd.notna(r.h_N2) else None,
                "h_N3": float(r.h_N3) if pd.notna(r.h_N3) else None,
                "h_N4": float(r.h_N4) if pd.notna(r.h_N4) else None,
                "label": "THEORETICAL RETAINED EXPOSURE — NOT EXECUTED",
            }
        )
    return out
