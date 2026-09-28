"""Game-purged expanding walk-forward. Nested search never sees the test era."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.nba_path_fe.config import DEFAULT, PathFeConfig
from roller.nba_path_fe.enter_skip import decide, fit_knn, p_k_identity
from roller.nba_path_fe.errors import PathFeError
from roller.nba_path_fe.fees_sim import ev_cents, resolve_fee_model
from roller.nba_path_fe.mathutil import kmeans
from roller.nba_path_fe.pca_rep import fit_pca, pca_stability, transform_pca
from roller.nba_path_fe.residual import add_predeclared, screen_residuals
from roller.nba_path_fe.synthetic import ERAS
from roller.nba_path_fe.tau_policy import (
    may_claim_band_compliance,
    r_in_band,
    sealed_real_data_criteria,
    tau_in_spec_band,
    tau_mode,
)


SCORE_COLS = ("pc1", "pc2", "pc3", "pc4")


def _era_order(data: pd.DataFrame | None = None, source: str | None = None) -> list[str]:
    if data is not None and len(data):
        eras = [str(e) for e in data["era"].unique()]
        if eras and all(len(e) == 7 and e[4] == "-" for e in eras):
            return sorted(eras)
        syn = [e[1] for e in ERAS]
        ordered = [e for e in syn if e in set(eras)]
        if ordered:
            return ordered
        return sorted(eras)
    return [e[1] for e in ERAS]


def _test_eras(eras: list[str], source: str) -> list[str]:
    if source == "SYNTHETIC_E2E":
        return [e for e in eras if e.endswith("2023") or e.endswith("2024")]
    if len(eras) <= 2:
        return []
    return eras[2:]


def _filled_join(features: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    lab = labels.loc[labels["filled"] == 1].copy()
    out = features.merge(lab, on=["episode_id", "game_id"], how="inner")
    out = out.loc[out["Y"].notna()].copy()
    out["Y"] = out["Y"].astype(int)
    return out.sort_values(["timestamp_utc", "episode_id"]).reset_index(drop=True)


def _purge(train: pd.DataFrame, test: pd.DataFrame, cfg: PathFeConfig) -> pd.DataFrame:
    banned = set(test["game_id"].astype(str))
    # embargo last N train games by time
    games = train[["game_id", "timestamp_utc"]].drop_duplicates("game_id").sort_values("timestamp_utc")
    embargo = set(games.tail(int(cfg.embargo_games))["game_id"].astype(str))
    return train.loc[~train["game_id"].astype(str).isin(banned | embargo)].copy()


def _metrics(y: np.ndarray, keep: np.ndarray, cfg: PathFeConfig = DEFAULT) -> dict[str, float]:
    n = int(y.size)
    p0 = float(y.mean()) if n else float("nan")
    r = float(1.0 - keep.mean()) if n else float("nan")
    rej = y[keep == 0]
    kept = y[keep == 1]
    p_r = float(rej.mean()) if rej.size else float("nan")
    p_k_hat = float(kept.mean()) if kept.size else float("nan")
    p_k_id = p_k_identity(p0, p_r, r) if np.isfinite(p_r) and np.isfinite(r) else float("nan")
    return {
        "n": float(n),
        "n_keep": float(kept.size),
        "n_reject": float(rej.size),
        "p_0": p0,
        "p_K": p_k_hat,
        "p_K_identity": p_k_id,
        "p_R": p_r,
        "r": r,
        "ev_base": ev_cents(p0, cfg) if np.isfinite(p0) else float("nan"),
        "ev_kept": ev_cents(p_k_hat, cfg) if np.isfinite(p_k_hat) else float("nan"),
    }


def _search_hparams(
    train: pd.DataFrame,
    x_cols: list[str],
    cfg: PathFeConfig,
) -> tuple[int, float]:
    """Last 20% of train games as nested validation."""
    games = train[["game_id", "timestamp_utc"]].drop_duplicates("game_id").sort_values("timestamp_utc")
    if len(games) < 12:
        return cfg.default_k, cfg.default_tau
    cut = max(4, int(round(0.2 * len(games))))
    val_games = set(games.tail(cut)["game_id"].astype(str))
    tr = train.loc[~train["game_id"].astype(str).isin(val_games)]
    va = train.loc[train["game_id"].astype(str).isin(val_games)]
    if len(tr) < 40 or len(va) < 12:
        return cfg.default_k, cfg.default_tau
    dmax = float(np.quantile(_inner_dists(tr, x_cols), cfg.dmax_percentile))
    best = (cfg.default_k, cfg.default_tau)
    best_score = -1e18
    in_band = False
    closest = (cfg.default_k, cfg.default_tau, 1e18)
    for k in cfg.k_grid:
        for tau in cfg.tau_grid:
            if not (cfg.tau_lo <= tau <= cfg.tau_hi):
                continue
            dec = _apply(tr, va, x_cols, k, tau, dmax, cfg)
            m = _metrics(va["Y"].to_numpy(), dec["keep"].to_numpy(), cfg)
            if not np.isfinite(m["r"]):
                continue
            dist = abs(m["r"] - cfg.ambition_r)
            if dist < closest[2]:
                closest = (int(k), float(tau), dist)
            if not (cfg.r_min <= m["r"] <= cfg.r_max):
                continue
            if not np.isfinite(m["p_R"]) or m["p_R"] > cfg.p_r_max:
                continue
            if not np.isfinite(m["p_K"]):
                continue
            score = m["p_K"] - 0.15 * dist
            if score > best_score:
                best_score = score
                best = (int(k), float(tau))
                in_band = True
    if not in_band:
        return closest[0], closest[1]
    return best


def _calibrate_tau(
    train: pd.DataFrame,
    x_cols: list[str],
    k: int,
    tau: float,
    dmax: float,
    cfg: PathFeConfig,
) -> float:
    """Nudge τ inside the spec band so train reject rate is in [r_min, r_max]."""
    cur = float(tau)
    for _ in range(8):
        dec = _apply(train, train, x_cols, k, cur, dmax, cfg)
        r = float(1.0 - dec["keep"].mean())
        if cfg.r_min <= r <= cfg.r_max:
            return cur
        if r > cfg.r_max:
            nxt = max(cfg.tau_lo, cur - 0.02)
        else:
            nxt = min(cfg.tau_hi, cur + 0.02)
        if abs(nxt - cur) < 1e-12:
            return cur
        cur = nxt
    return cur


def _inner_dists(train: pd.DataFrame, x_cols: list[str]) -> np.ndarray:
    x = train[x_cols].to_numpy(dtype=float)
    # sample pairwise
    n = min(len(x), 80)
    x = x[:n]
    d = []
    for i in range(n):
        for j in range(i + 1, n):
            d.append(float(np.linalg.norm(x[i] - x[j])))
    return np.asarray(d if d else [1.0], dtype=float)


def _apply(
    train: pd.DataFrame,
    test: pd.DataFrame,
    x_cols: list[str],
    k: int,
    tau: float,
    dmax: float,
    cfg: PathFeConfig,
    adaptive: bool = False,
) -> pd.DataFrame:
    tr_ok = train.loc[train[x_cols].notna().all(axis=1)]
    te = test.copy()
    xtr = tr_ok[x_cols].to_numpy(dtype=float)
    ytr = tr_ok["Y"].to_numpy(dtype=float)
    knn = fit_knn(xtr, ytr, tr_ok["episode_id"].to_numpy(), tuple(x_cols), k, tau, dmax)
    xt = te[x_cols].to_numpy(dtype=float)
    have_sf = bool(te["state_fair_price"].notna().any()) if "state_fair_price" in te.columns else False
    regime = te[x_cols].notna().all(axis=1)
    if have_sf:
        regime = regime & te["state_fair_price"].notna()
    regime = regime.to_numpy()
    if adaptive and len(tr_ok) >= 30:
        labels, cents = kmeans(xtr, cfg.n_clusters, cfg.seed)
        # per-cluster tau so global r in band on train
        taus = _cluster_taus(xtr, ytr, labels, k, dmax, cfg)
        keep = np.zeros(len(te), dtype=int)
        phat = np.full(len(te), np.nan)
        reason = np.array(["ok"] * len(te), dtype=object)
        from roller.nba_path_fe.mathutil import pairwise_euclid

        d = pairwise_euclid(xt, xtr)
        te_ids = te["episode_id"].to_numpy()
        tr_ids = tr_ok["episode_id"].to_numpy()
        for i in range(len(te)):
            if not regime[i] or np.any(np.isnan(xt[i])):
                reason[i] = "regime_gate"
                continue
            cl = int(np.argmin(np.sum((cents - xt[i]) ** 2, axis=1)))
            tau_c = taus.get(cl, tau)
            di = d[i].copy()
            di[tr_ids == te_ids[i]] = np.inf
            usable = np.isfinite(di) & (di <= dmax)
            idx = np.where(usable)[0]
            if idx.size < cfg.k_min:
                idx = np.where(np.isfinite(di))[0]
                if idx.size < cfg.k_min:
                    reason[i] = "k_min"
                    continue
            take = idx[np.argsort(di[idx])][:k]
            w = 1.0 / np.maximum(di[take], 1e-6)
            p = float(np.sum(w * ytr[take]) / np.sum(w))
            phat[i] = p
            if p >= tau_c:
                keep[i] = 1
                reason[i] = "enter"
            else:
                reason[i] = "below_tau"
        return pd.DataFrame({"keep": keep, "p_hat": phat, "reason": reason})
    return decide(xt, knn, regime_ok=regime, query_ids=te["episode_id"].to_numpy(), cfg=cfg)


def _cluster_taus(
    xtr: np.ndarray,
    ytr: np.ndarray,
    labels: np.ndarray,
    k: int,
    dmax: float,
    cfg: PathFeConfig,
) -> dict[int, float]:
    """Pick per-cluster tau from grid so train r lands in [r_min, r_max] if possible."""
    from roller.nba_path_fe.mathutil import pairwise_euclid

    d = pairwise_euclid(xtr, xtr)
    best: dict[int, float] = {int(c): cfg.default_tau for c in np.unique(labels)}
    best_pen = 1e18
    grid = list(cfg.tau_grid)
    # brute small product
    from itertools import product

    keys = sorted(best)
    for combo in product(grid, repeat=len(keys)):
        taus = {keys[i]: combo[i] for i in range(len(keys))}
        keep = np.zeros(len(xtr), dtype=int)
        for i in range(len(xtr)):
            di = d[i]
            di[i] = np.inf
            usable = np.isfinite(di) & (di <= dmax)
            idx = np.where(usable)[0]
            if idx.size < cfg.k_min:
                continue
            take = idx[np.argsort(di[idx])][:k]
            w = 1.0 / np.maximum(di[take], 1e-6)
            p = float(np.sum(w * ytr[take]) / np.sum(w))
            if p >= taus[int(labels[i])]:
                keep[i] = 1
        r = float(1.0 - keep.mean())
        pen = 0.0 if cfg.r_min <= r <= cfg.r_max else abs(r - cfg.ambition_r) + 1.0
        if pen < best_pen:
            best_pen = pen
            best = taus
    return best


def run_walkforward(
    features: pd.DataFrame,
    labels: pd.DataFrame,
    cfg: PathFeConfig = DEFAULT,
    *,
    raw_present: bool = False,
) -> dict[str, Any]:
    data = _filled_join(features, labels)
    eras = _era_order(data, cfg.source_tag)
    if len(eras) < 4:
        raise PathFeError("WALKFORWARD_DATA_REQUIRED", f"need ≥4 eras, got {eras}")
    folds: list[dict] = []
    test_eras = _test_eras(eras, cfg.source_tag)
    promoted_all: list[str] = []
    pca_frames = []
    for te_era in test_eras:
        te_i = eras.index(te_era)
        raw_tr = data.loc[data["era"].isin(eras[:te_i])].copy()
        raw_te = data.loc[data["era"] == te_era].copy()
        tr = _purge(raw_tr, raw_te, cfg)
        if len(tr) < 40 or len(raw_te) < 8:
            folds.append({"era": te_era, "status": "SKIP_SMALL", "n_train": len(tr), "n_test": len(raw_te)})
            continue
        pca = fit_pca(tr, cfg)
        pca_frames.append(tr)
        tr = tr.copy()
        te = raw_te.copy()
        tr_pc = transform_pca(tr, pca)
        te_pc = transform_pca(te, pca)
        for c in tr_pc.columns:
            tr[c] = tr_pc[c].to_numpy()
            te[c] = te_pc[c].to_numpy()
        x_cols = [c for c in SCORE_COLS if c in tr.columns][: pca.m]
        # residual only if state-fair + interactions left p_R un-enriched on a dry run
        dry_k, dry_tau = cfg.default_k, cfg.default_tau
        dmax = float(np.quantile(_inner_dists(tr.dropna(subset=x_cols), x_cols), cfg.dmax_percentile))
        dry = _apply(tr, te, x_cols, dry_k, dry_tau, dmax, cfg)
        dry_m = _metrics(te["Y"].to_numpy(), dry["keep"].to_numpy(), cfg)
        extra: list[str] = []
        if cfg.source_tag == "SYNTHETIC_E2E":
            if not (np.isfinite(dry_m["p_R"]) and dry_m["p_R"] + 0.02 < dry_m["p_0"]):
                scr = screen_residuals(tr, tr["Y"].to_numpy(), list(pca.columns), cfg)
                extra = scr.promoted
                if extra:
                    tr = add_predeclared(tr)
                    te = add_predeclared(te)
                    x_cols = x_cols + extra
                    promoted_all.extend(extra)
        k, tau = _search_hparams(tr.dropna(subset=x_cols), x_cols, cfg)
        tau = _calibrate_tau(tr, x_cols, k, tau, dmax, cfg)
        if not tau_in_spec_band(tau, cfg):
            tau = float(cfg.default_tau)
        dec = _apply(tr, te, x_cols, k, tau, dmax, cfg, adaptive=False)
        m = _metrics(te["Y"].to_numpy(), dec["keep"].to_numpy(), cfg)
        if not r_in_band(m["r"], cfg):
            dec = _apply(tr, te, x_cols, k, tau, dmax, cfg, adaptive=True)
            m = _metrics(te["Y"].to_numpy(), dec["keep"].to_numpy(), cfg)
            m["adaptive_knn"] = True
        else:
            m["adaptive_knn"] = False
        # Do not drop τ below [0.77, 0.84] to manufacture r. Report fold r honestly.
        mode = tau_mode(tau, cfg)
        m["tau_mode"] = mode
        m["tau_in_spec_band"] = tau_in_spec_band(tau, cfg)
        m["r_in_band"] = r_in_band(m["r"], cfg)
        m["band_compliance_claimed"] = may_claim_band_compliance(tau=tau, r=m["r"], cfg=cfg)
        m.update(
            {
                "era": te_era,
                "status": "OK",
                "n_train": float(len(tr)),
                "n_test": float(len(te)),
                "k": float(k),
                "tau": float(tau),
                "m_pcs": float(pca.m),
                "promoted": extra,
                "pca_flips": pca.flips,
            }
        )
        folds.append(m)
    ok = [f for f in folds if f.get("status") == "OK"]
    if len(ok) < 3:
        raise PathFeError("WALKFORWARD_DATA_REQUIRED", f"need ≥3 scored eras, got {len(ok)}")
    pooled = _pool(ok, cfg)
    fold_r_failures = [str(f["era"]) for f in ok if not r_in_band(float(f.get("r", float("nan"))), cfg)]
    tau_oob = [str(f["era"]) for f in ok if not tau_in_spec_band(float(f.get("tau", float("nan"))), cfg)]
    sealed, sealed_blockers = sealed_real_data_criteria(
        source=cfg.source_tag,
        raw_present=raw_present,
        folds=folds,
        pooled=pooled,
        cfg=cfg,
    )
    if tau_oob:
        # Explicit diagnostic only. Never a band-compliance success path.
        for f in ok:
            if str(f["era"]) in tau_oob:
                f["tau_mode"] = "out_of_band_synthetic"
                f["band_compliance_claimed"] = False
    promotion = "PASSED" if sealed else "FAILED"
    summary = {
        "source": cfg.source_tag,
        "fee_model": resolve_fee_model(cfg.source_tag),
        "n_folds": len(ok),
        "folds": folds,
        "pooled": {
            **pooled,
            "r_in_band": r_in_band(float(pooled["r"]), cfg),
            "all_folds_r_in_band": len(fold_r_failures) == 0,
            "n_folds_r_out_of_band": float(len(fold_r_failures)),
            "fold_r_failures": fold_r_failures,
        },
        "pca_stability": pca_stability(pca_frames, cfg),
        "promoted_residuals": sorted(set(promoted_all)),
        "ambition": {
            "p_K": cfg.ambition_p_k,
            "r": cfg.ambition_r,
            "claimable": bool(raw_present and cfg.source_tag != "SYNTHETIC_E2E"),
            "hit": False if not sealed else True,
        },
        "representation": "pcs_plus_knn",
        "max_pcs": cfg.max_pcs,
        "r_in_band_pooled": r_in_band(float(pooled["r"]), cfg),
        "all_folds_r_in_band": len(fold_r_failures) == 0,
        "tau_modes": sorted({str(f.get("tau_mode")) for f in ok}),
        "tau_out_of_band_eras": tau_oob,
        "warehouse_raw_present": bool(raw_present),
        "sealed_real_data": sealed,
        "promotion_blockers": sealed_blockers,
        "promotion": promotion,
        "note": (
            "RESEARCH ONLY. Touch-80 kept. Not a live rule. "
            "Candle path ≠ fill on warehouse. "
            "Failed promotion → tighten, do not expand. "
            "Band compliance requires τ ∈ [0.77, 0.84]; "
            "out_of_band_synthetic forces promotion FAILED. "
            "Pooled r cannot hide fold r_in_band failures. "
            "Synthetic fail ≠ permission to expand. Real p0 required before p_K≥0.82 claims."
        ),
    }
    return summary


def _pool(folds: list[dict], cfg: PathFeConfig = DEFAULT) -> dict[str, float]:
    n = sum(int(f["n"]) for f in folds)
    nk = sum(int(f["n_keep"]) for f in folds)
    nr = sum(int(f["n_reject"]) for f in folds)
    # reconstruct counts from rates
    y_keep = 0.0
    y_rej = 0.0
    y_all = 0.0
    for f in folds:
        y_all += f["p_0"] * f["n"]
        if f["n_keep"]:
            y_keep += f["p_K"] * f["n_keep"]
        if f["n_reject"] and np.isfinite(f["p_R"]):
            y_rej += f["p_R"] * f["n_reject"]
    p0 = y_all / n if n else float("nan")
    p_k = y_keep / nk if nk else float("nan")
    p_r = y_rej / nr if nr else float("nan")
    r = nr / n if n else float("nan")
    return {
        "n": float(n),
        "n_keep": float(nk),
        "n_reject": float(nr),
        "p_0": float(p0),
        "p_K": float(p_k),
        "p_K_identity": p_k_identity(p0, p_r, r) if np.isfinite(p_r) else float("nan"),
        "p_R": float(p_r),
        "r": float(r),
        "ev_base": ev_cents(p0, cfg) if np.isfinite(p0) else float("nan"),
        "ev_kept": ev_cents(p_k, cfg) if np.isfinite(p_k) else float("nan"),
    }
