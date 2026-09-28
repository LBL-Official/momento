"""Monte Carlo paths. Mode A is theoretical binary. Mode B/C consume supplied data only."""

from __future__ import annotations

from typing import Any

import numpy as np

from roller.risk.formulas import RiskConfigError, bankroll_loss_return, bankroll_win_return


PERCENTILES = (5, 10, 25, 50, 75, 90, 95, 99)
BAND_PERCENTILES = (5, 25, 50, 75, 95)


def _percentiles(values: np.ndarray) -> dict[str, float]:
    qs = np.percentile(values, PERCENTILES)
    return {
        **{f"p{int(p)}": float(q) for p, q in zip(PERCENTILES, qs)},
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "minimum": float(values.min()),
        "maximum": float(values.max()),
    }


def _optional_levels(
    cfg: dict[str, float | int],
    *,
    final: np.ndarray,
    min_b: np.ndarray,
    bankroll: np.ndarray,
) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    probs: dict[str, float] = {}
    floor = cfg.get("bankroll_floor")
    target = cfg.get("target_bankroll")
    if floor is not None:
        probs["P_min_bankroll_le_floor"] = float((min_b <= float(floor)).mean())
    if target is not None:
        probs["P_final_ge_target"] = float((final >= float(target)).mean())
    extra["level_probabilities"] = probs
    if floor is not None or target is not None:
        weeks = int(bankroll.shape[1])
        bands: list[dict[str, float | int]] = []
        for week in range(weeks):
            qs = np.percentile(bankroll[:, week], BAND_PERCENTILES)
            bands.append(
                {
                    "week": week + 1,
                    **{f"p{int(p)}": float(q) for p, q in zip(BAND_PERCENTILES, qs)},
                }
            )
        extra["weekly_path_bands"] = bands
    return extra


def simulate_mode_a(cfg: dict[str, float | int], *, seed: int) -> dict[str, Any]:
    B0 = float(cfg["initial_bankroll"])
    f = float(cfg["trade_allocation"])
    r_w = float(cfg["win_return"])
    r_l = float(cfg["loss_return"])
    p = float(cfg["win_probability"])
    N = int(cfg["trades_per_week"])
    weeks = int(cfg["weeks_per_year"])
    paths = int(cfg["monte_carlo_paths"])
    T_w = float(cfg["target_weekly_ev"])
    R_w = bankroll_win_return(f, r_w)
    R_l = bankroll_loss_return(f, r_l)
    rng = np.random.default_rng(seed)
    # Static weekly sizing: all N trades use the week-start bankroll.
    wins = rng.random((paths, weeks, N)) < p
    k = wins.sum(axis=2)
    weekly_r = k * R_w + (N - k) * R_l
    growth = 1.0 + weekly_r
    bankroll = B0 * np.cumprod(growth, axis=1)
    peak = np.maximum.accumulate(bankroll, axis=1)
    drawdown = (bankroll - peak) / peak
    final = bankroll[:, -1]
    total_return = final / B0 - 1.0
    mdd = drawdown.min(axis=1)
    min_b = bankroll.min(axis=1)
    pos_weeks = (weekly_r > 0).sum(axis=1)
    neg_weeks = (weekly_r < 0).sum(axis=1)
    target_weeks = (weekly_r + 1e-15 >= T_w).sum(axis=1)
    mean_weekly = float(weekly_r.mean())
    extra = _optional_levels(cfg, final=final, min_b=min_b, bankroll=bankroll)
    probabilities = {
        "P_final_ge_1_5x": float((final >= 1.5 * B0).mean()),
        "P_final_lt_B0": float((final < B0).mean()),
        "P_mdd_le_neg_5": float((mdd <= -0.05).mean()),
        "P_mdd_le_neg_10": float((mdd <= -0.10).mean()),
        "P_mdd_le_neg_20": float((mdd <= -0.20).mean()),
        **extra["level_probabilities"],
    }
    out = {
        "mode": "A",
        "seed": seed,
        "paths": paths,
        "mean_weekly_return": mean_weekly,
        "terminal_bankroll": _percentiles(final),
        "annual_return": _percentiles(total_return),
        "max_drawdown": _percentiles(mdd),
        "probabilities": probabilities,
        "path_summaries": {
            "mean_final_bankroll": float(final.mean()),
            "median_final_bankroll": float(np.median(final)),
            "mean_max_drawdown": float(mdd.mean()),
            "median_max_drawdown": float(np.median(mdd)),
            "mean_minimum_bankroll": float(min_b.mean()),
            "mean_positive_weeks": float(pos_weeks.mean()),
            "mean_negative_weeks": float(neg_weeks.mean()),
            "mean_target_weeks": float(target_weeks.mean()),
        },
        "static_weekly_sizing": True,
        "note": "Theoretical binary. Arithmetic EV is not a realized weekly path.",
    }
    if "weekly_path_bands" in extra:
        out["weekly_path_bands"] = extra["weekly_path_bands"]
    return out


def simulate_mode_b(
    cfg: dict[str, float | int],
    outcomes: list[str],
    *,
    seed: int,
    theoretical_zero_cost: bool = False,
) -> dict[str, Any]:
    classified = [o for o in outcomes if o in {"WIN", "LOSS"}]
    if not classified:
        raise RiskConfigError("empirical_outcomes_unavailable")
    B0 = float(cfg["initial_bankroll"])
    f = float(cfg["trade_allocation"])
    r_w = float(cfg["win_return"])
    r_l = float(cfg["loss_return"])
    N = int(cfg["trades_per_week"])
    weeks = int(cfg["weeks_per_year"])
    paths = int(cfg["monte_carlo_paths"])
    T_w = float(cfg["target_weekly_ev"])
    R_w = bankroll_win_return(f, r_w)
    R_l = bankroll_loss_return(f, r_l)
    mapped = np.array([R_w if o == "WIN" else R_l for o in classified], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(mapped), size=(paths, weeks, N))
    weekly_r = mapped[idx].sum(axis=2)
    growth = 1.0 + weekly_r
    bankroll = B0 * np.cumprod(growth, axis=1)
    final = bankroll[:, -1]
    peak = np.maximum.accumulate(bankroll, axis=1)
    mdd = ((bankroll - peak) / peak).min(axis=1)
    min_b = bankroll.min(axis=1)
    extra = _optional_levels(cfg, final=final, min_b=min_b, bankroll=bankroll)
    out = {
        "mode": "B",
        "seed": seed,
        "paths": paths,
        "sampled_outcomes": len(classified),
        "omitted_classifications": len(outcomes) - len(classified),
        "terminal_bankroll": _percentiles(final),
        "annual_return": _percentiles(final / B0 - 1.0),
        "max_drawdown": _percentiles(mdd),
        "probabilities": {
            "P_final_ge_1_5x": float((final >= 1.5 * B0).mean()),
            "P_final_lt_B0": float((final < B0).mean()),
            "P_mdd_le_neg_5": float((mdd <= -0.05).mean()),
            "P_mdd_le_neg_10": float((mdd <= -0.10).mean()),
            "P_mdd_le_neg_20": float((mdd <= -0.20).mean()),
            **extra["level_probabilities"],
        },
        "mean_weekly_return": float(weekly_r.mean()),
        "P_target_week": float((weekly_r + 1e-15 >= T_w).mean()),
        "fees": "UNAVAILABLE",
        "slippage": "UNAVAILABLE",
        "fills": "UNAVAILABLE",
        "net_ev": "NOT_COMPUTABLE" if not theoretical_zero_cost else "THEORETICAL_ZERO_COST",
        "note": "Candle-path classifications are not fills. Empirical sampling uses WIN/LOSS labels only.",
        "static_weekly_sizing": True,
    }
    if "weekly_path_bands" in extra:
        out["weekly_path_bands"] = extra["weekly_path_bands"]
    return out


def simulate_mode_c(
    cfg: dict[str, float | int],
    probabilities: list[float],
    *,
    seed: int,
) -> dict[str, Any]:
    if not probabilities:
        raise RiskConfigError("model_probabilities_required")
    for p in probabilities:
        if not 0 <= float(p) <= 1:
            raise RiskConfigError("invalid_probability")
    B0 = float(cfg["initial_bankroll"])
    f = float(cfg["trade_allocation"])
    r_w = float(cfg["win_return"])
    r_l = float(cfg["loss_return"])
    N = int(cfg["trades_per_week"])
    weeks = int(cfg["weeks_per_year"])
    paths = int(cfg["monte_carlo_paths"])
    R_w = bankroll_win_return(f, r_w)
    R_l = bankroll_loss_return(f, r_l)
    p = np.array([float(x) for x in probabilities], dtype=float)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(p), size=(paths, weeks, N))
    u = rng.random((paths, weeks, N))
    wins = u < p[pick]
    k = wins.sum(axis=2)
    weekly_r = k * R_w + (N - k) * R_l
    bankroll = B0 * np.cumprod(1.0 + weekly_r, axis=1)
    final = bankroll[:, -1]
    peak = np.maximum.accumulate(bankroll, axis=1)
    mdd = ((bankroll - peak) / peak).min(axis=1)
    return {
        "mode": "C",
        "seed": seed,
        "paths": paths,
        "supplied_probabilities": len(probabilities),
        "terminal_bankroll": _percentiles(final),
        "annual_return": _percentiles(final / B0 - 1.0),
        "max_drawdown": _percentiles(mdd),
        "probabilities": {
            "P_final_ge_1_5x": float((final >= 1.5 * B0).mean()),
            "P_final_lt_B0": float((final < B0).mean()),
            "P_mdd_le_neg_5": float((mdd <= -0.05).mean()),
            "P_mdd_le_neg_10": float((mdd <= -0.10).mean()),
            "P_mdd_le_neg_20": float((mdd <= -0.20).mean()),
        },
        "mean_weekly_return": float(weekly_r.mean()),
        "note": "Conditional probabilities were supplied externally. ROLLER did not invent p_i.",
        "static_weekly_sizing": True,
    }
