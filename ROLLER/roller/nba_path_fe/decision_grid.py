"""One decision-layer τ grid. Frozen representation. No new features."""

from __future__ import annotations

from typing import Any

import numpy as np

from roller.nba_path_fe.config import DEFAULT, PathFeConfig
from roller.nba_path_fe.errors import PathFeError
from roller.nba_path_fe.pca_rep import fit_pca, transform_pca
from roller.nba_path_fe.tau_policy import r_in_band, tau_in_spec_band
from roller.nba_path_fe.walkforward import (
    SCORE_COLS,
    _apply,
    _era_order,
    _filled_join,
    _inner_dists,
    _metrics,
    _pool,
    _purge,
    _test_eras,
)

DECISION_TAU_GRID = (0.80, 0.82, 0.84, 0.86, 0.88, 0.90)
FIXED_K = 25  # existing default_k; not an expanded grid

CONCLUSION = (
    "Residual enter/skip at τ=0.77 with current A+B+C (no L2, candle fills) "
    "does not raise EV vs take-all touch-80. Rejects are not failure-enriched: "
    "the decision surface scrambles winners rather than cutting losers. "
    "EV-max under no-overfit is BASELINE: take the touch-80 enter/skip=ALWAYS "
    "(no second filter), subject to existing desk execution (78–82 / bail-40), "
    "until a decision-layer tighten recovers p_K>p0 with r∈[0.12,0.25] and "
    "p_R<p0 on game-purged WF. Ambition p_K≥0.82 is not claimable and is not "
    "the next milestone. Next milestone is p_K>p0 with r in band. If that "
    "cannot be hit without new features, archive the filter as inactive — "
    "do not keep tuning forever."
)


def meets_recover_criteria(pooled: dict, folds: list[dict], cfg: PathFeConfig = DEFAULT) -> tuple[bool, list[str]]:
    """Recover-or-retire success. Not p_K≥0.82."""
    misses: list[str] = []
    ok = [f for f in folds if f.get("status") == "OK"]
    in_band = sum(1 for f in ok if r_in_band(float(f.get("r", float("nan"))), cfg))
    r_vals = [float(f["r"]) for f in ok if f.get("r") == f.get("r")]
    pooled_r = float(pooled.get("r", float("nan")))
    alt = r_in_band(pooled_r, cfg) and (not r_vals or max(r_vals) <= 0.35)
    if in_band < 4 and not alt:
        misses.append("r_band")
    p0 = float(pooled.get("p_0", float("nan")))
    pk = float(pooled.get("p_K", float("nan")))
    pr = float(pooled.get("p_R", float("nan")))
    if not (pk == pk and p0 == p0 and pk >= p0 + 0.01):
        misses.append("p_K_not_above_p0")
    if not (pr == pr and p0 == p0 and pr <= p0 - 0.02):
        misses.append("p_R_not_below_p0")
    return (len(misses) == 0, misses)


def run_decision_grid(
    features,
    labels,
    cfg: PathFeConfig = DEFAULT,
    *,
    taus: tuple[float, ...] = DECISION_TAU_GRID,
    k: int = FIXED_K,
) -> dict[str, Any]:
    data = _filled_join(features, labels)
    eras = _era_order(data, cfg.source_tag)
    test_eras = _test_eras(eras, cfg.source_tag)
    if len(test_eras) < 3:
        raise PathFeError("WALKFORWARD_DATA_REQUIRED", f"need ≥3 test eras, got {test_eras}")
    prepared: list[tuple[str, Any, Any, list[str], float]] = []
    for te_era in test_eras:
        te_i = eras.index(te_era)
        raw_tr = data.loc[data["era"].isin(eras[:te_i])].copy()
        raw_te = data.loc[data["era"] == te_era].copy()
        tr = _purge(raw_tr, raw_te, cfg)
        if len(tr) < 40 or len(raw_te) < 8:
            continue
        pca = fit_pca(tr, cfg)
        tr = tr.copy()
        te = raw_te.copy()
        tr_pc = transform_pca(tr, pca)
        te_pc = transform_pca(te, pca)
        for c in tr_pc.columns:
            tr[c] = tr_pc[c].to_numpy()
            te[c] = te_pc[c].to_numpy()
        x_cols = [c for c in SCORE_COLS if c in tr.columns][: pca.m]
        dmax = float(np.quantile(_inner_dists(tr.dropna(subset=x_cols), x_cols), cfg.dmax_percentile))
        prepared.append((te_era, tr, te, x_cols, dmax))
    if len(prepared) < 3:
        raise PathFeError("WALKFORWARD_DATA_REQUIRED", "too few prepared folds")

    rows: list[dict[str, Any]] = []
    winner: dict[str, Any] | None = None
    for tau in taus:
        folds: list[dict] = []
        for te_era, tr, te, x_cols, dmax in prepared:
            dec = _apply(tr, te, x_cols, k, float(tau), dmax, cfg, adaptive=False)
            m = _metrics(te["Y"].to_numpy(), dec["keep"].to_numpy(), cfg)
            m.update(
                {
                    "era": te_era,
                    "status": "OK",
                    "k": float(k),
                    "tau": float(tau),
                    "tau_in_spec_band": tau_in_spec_band(float(tau), cfg),
                    "r_in_band": r_in_band(m["r"], cfg),
                    "adaptive_knn": False,
                }
            )
            folds.append(m)
        pooled = _pool(folds, cfg)
        ok_r, misses = meets_recover_criteria(pooled, folds, cfg)
        row = {
            "tau": float(tau),
            "k": int(k),
            "tau_in_promotion_band": tau_in_spec_band(float(tau), cfg),
            "pooled": {
                "n": pooled["n"],
                "p_0": pooled["p_0"],
                "p_K": pooled["p_K"],
                "p_R": pooled["p_R"],
                "r": pooled["r"],
            },
            "folds": [
                {
                    "era": f["era"],
                    "p_0": f["p_0"],
                    "p_K": f["p_K"],
                    "p_R": f["p_R"],
                    "r": f["r"],
                    "r_in_band": f["r_in_band"],
                    "n": f["n"],
                    "n_keep": f["n_keep"],
                }
                for f in folds
            ],
            "meets_recover_criteria": ok_r,
            "recover_misses": misses,
        }
        rows.append(row)
        if ok_r and winner is None:
            winner = row
    return {
        "grid": "tau_decision_layer_v1",
        "k": int(k),
        "adaptive_knn": False,
        "taus": list(taus),
        "rows": rows,
        "any_success": winner is not None,
        "winner": winner,
    }
