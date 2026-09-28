"""Debase Monte Carlo. Uses Roller-derived payoffs, not desk +20/−40."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from roller import desk_settings
from roller.risk.engine import run_risk
from roller.risk.simulation import simulate_mode_a
from roller.superasi.debase.versions import (
    DESK_PATHS,
    DESK_SEED,
    RISK_PROFILE_WEEKS,
    SENSITIVITY_P,
    TARGET_WEEKLY_EV,
    TRADES_PER_WEEK,
)


def _se(p_hat: float, n: int) -> float:
    if n <= 0:
        return 0.0
    p = min(1.0, max(0.0, float(p_hat)))
    return math.sqrt(p * (1.0 - p) / float(n))


def _risk_config(
    payoff: dict[str, float],
    *,
    p: float,
    paths: int,
    desk: dict[str, Any] | None = None,
) -> dict[str, Any]:
    levels = desk if desk is not None else desk_settings.scaled_levels()
    return {
        "initial_bankroll": float(levels["initial_bankroll"]),
        "trade_allocation": float(levels["trade_allocation"]),
        "win_return": float(payoff["win_return_on_capital"]),
        "loss_return": float(payoff["loss_return_on_capital"]),
        "win_probability": float(p),
        "trades_per_week": TRADES_PER_WEEK,
        "target_weekly_ev": TARGET_WEEKLY_EV,
        "weeks_per_year": RISK_PROFILE_WEEKS,
        "monte_carlo_paths": int(paths),
        "bankroll_floor": float(levels["bankroll_floor"]),
        "target_bankroll": float(levels["target_bankroll"]),
    }


def run_bernoulli(
    payoff: dict[str, float],
    *,
    p: float,
    research_result_hash: str,
    paths: int = DESK_PATHS,
    desk: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return run_risk(
        {
            "mode": "A",
            "seed": DESK_SEED,
            "research_result_hash": research_result_hash,
            "config": _risk_config(payoff, p=p, paths=paths, desk=desk),
        }
    )


def run_empirical(
    payoff: dict[str, float],
    outcomes: list[str],
    *,
    research_result_hash: str,
    paths: int = DESK_PATHS,
    p: float,
    desk: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return run_risk(
        {
            "mode": "B",
            "seed": DESK_SEED,
            "research_result_hash": research_result_hash,
            "classifications": list(outcomes),
            "config": _risk_config(payoff, p=p, paths=paths, desk=desk),
        }
    )


def simulate_weekly_bootstrap(
    weekly_returns: list[float],
    *,
    paths: int,
    weeks: int = RISK_PROFILE_WEEKS,
    seed: int = DESK_SEED,
    desk: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if len(weekly_returns) < 2:
        return {"status": "DATA_REQUIRED", "reason": "fewer_than_two_weeks"}
    levels = desk if desk is not None else desk_settings.scaled_levels()
    start = float(levels["initial_bankroll"])
    floor = float(levels["bankroll_floor"])
    target = float(levels["target_bankroll"])
    values = np.array(weekly_returns, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(values), size=(int(paths), int(weeks)))
    weekly_r = values[idx]
    bankroll = start * np.cumprod(1.0 + weekly_r, axis=1)
    final = bankroll[:, -1]
    peak = np.maximum.accumulate(bankroll, axis=1)
    mdd = ((bankroll - peak) / peak).min(axis=1)
    min_b = bankroll.min(axis=1)
    total_return = final / start - 1.0
    n = int(paths)
    p_floor = float((min_b <= floor).mean())
    p_target = float((final >= target).mean())
    p_loss = float((total_return < 0).mean())
    return {
        "status": "MONTE_CARLO",
        "mode": "weekly_bootstrap",
        "seed": seed,
        "paths": n,
        "sampled_weeks": len(weekly_returns),
        "mean_terminal_bankroll": float(final.mean()),
        "median_terminal_bankroll": float(np.median(final)),
        "mean_return": float(total_return.mean()),
        "P_min_bankroll_le_floor": p_floor,
        "P_final_ge_target": p_target,
        "P_return_lt_0": p_loss,
        "se_floor": _se(p_floor, n),
        "se_target": _se(p_target, n),
        "mean_max_drawdown": float(mdd.mean()),
        "note": "Weekly bootstrap of observed ISO weeks. Candle-path W/L mapped through Roller R_w/R_l.",
    }


def sensitivity_monte_carlo(
    payoff: dict[str, float],
    *,
    paths: int,
    desk: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    cfg_base = _risk_config(payoff, p=0.70, paths=paths, desk=desk)
    for p in SENSITIVITY_P:
        cfg = dict(cfg_base)
        cfg["win_probability"] = float(p)
        sim = simulate_mode_a(cfg, seed=DESK_SEED)
        probs = sim.get("probabilities") if isinstance(sim.get("probabilities"), dict) else {}
        ret = sim.get("annual_return") if isinstance(sim.get("annual_return"), dict) else {}
        term = sim.get("terminal_bankroll") if isinstance(sim.get("terminal_bankroll"), dict) else {}
        n = int(sim.get("paths") or paths)
        p_floor = probs.get("P_min_bankroll_le_floor")
        p_target = probs.get("P_final_ge_target")
        p_loss = probs.get("P_final_lt_B0")
        rows.append(
            {
                "p": p,
                "expected_20_week_return": ret.get("mean"),
                "median_terminal_bankroll": term.get("median"),
                "P_min_bankroll_le_floor": p_floor,
                "P_final_ge_target": p_target,
                "P_return_lt_0": p_loss,
                "se_floor": _se(float(p_floor), n) if p_floor is not None else None,
                "se_target": _se(float(p_target), n) if p_target is not None else None,
            }
        )
    return rows


def attach_standard_errors(sim: dict[str, Any]) -> dict[str, Any]:
    mc = sim.get("monte_carlo") if isinstance(sim.get("monte_carlo"), dict) else {}
    probs = mc.get("probabilities") if isinstance(mc.get("probabilities"), dict) else {}
    n = int(mc.get("paths") or 0)
    extra = {}
    for key in ("P_min_bankroll_le_floor", "P_final_ge_target", "P_final_lt_B0"):
        value = probs.get(key)
        if value is None:
            continue
        extra[f"se_{key}"] = _se(float(value), n)
    body = dict(sim)
    body["standard_errors"] = extra
    return body
