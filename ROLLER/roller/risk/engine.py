"""Risk engine consumer. Research result ≠ simulation result."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from roller.risk.formulas import (
    RiskConfigError,
    bankroll_loss_return,
    bankroll_win_return,
    break_even_probability,
    compound_if_constant,
    dollar_trade_ev,
    min_wins_for_target,
    required_win_probability,
    target_ev_per_trade,
    trade_capital,
    trade_ev,
    validate_config,
    weekly_distribution,
    weekly_ev,
    weekly_rate_for_growth,
    weekly_return_from_wins,
    weekly_volatility,
    wilson_interval,
)
from roller.risk.simulation import simulate_mode_a, simulate_mode_b, simulate_mode_c


def _hash(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _controls(cfg: dict[str, Any], f: float, ev_t: float, p: float, p_be: float) -> dict[str, Any]:
    controls = cfg.get("controls") if isinstance(cfg.get("controls"), dict) else {}
    violations: list[str] = []
    max_alloc = controls.get("MAX_TRADE_ALLOCATION")
    if max_alloc is not None and f > float(max_alloc):
        violations.append("MAX_TRADE_ALLOCATION")
    min_edge = controls.get("MINIMUM_MODEL_EDGE")
    if min_edge is not None and ev_t < float(min_edge):
        violations.append("MINIMUM_MODEL_EDGE")
    min_conf = controls.get("MINIMUM_CONFIDENCE")
    if min_conf is not None and p < float(min_conf):
        violations.append("MINIMUM_CONFIDENCE")
    return {
        "configured": {k: controls[k] for k in controls},
        "violations": violations,
        "acceptable": not violations,
        "note": "Controls are constraints, not expected-value assumptions.",
    }


def run_risk(body: dict[str, Any]) -> dict[str, Any]:
    mode = str(body.get("mode") or "A").upper()
    seed = int(body.get("seed") or 20260913)
    research_hash = str(body.get("research_result_hash") or "")
    cfg = validate_config(body.get("config") or {})
    B = float(cfg["initial_bankroll"])
    f = float(cfg["trade_allocation"])
    r_w = float(cfg["win_return"])
    r_l = float(cfg["loss_return"])
    p = float(cfg["win_probability"])
    N = int(cfg["trades_per_week"])
    T_w = float(cfg["target_weekly_ev"])
    weeks = int(cfg["weeks_per_year"])
    C = trade_capital(B, f)
    R_w = bankroll_win_return(f, r_w)
    R_l = bankroll_loss_return(f, r_l)
    ev_t = trade_ev(p, R_w, R_l)
    p_be = break_even_probability(R_w, R_l)
    T_t = target_ev_per_trade(T_w, N)
    p_target = required_win_probability(T_t, R_w, R_l)
    ev_w = weekly_ev(N, ev_t)
    table = weekly_distribution(N, p, R_w, R_l)
    min_wins = min_wins_for_target(N, R_w, R_l, T_w)
    p_target_week = sum(float(row["probability"]) for row in table if int(row["wins"]) >= (min_wins or N + 1))
    p_below = 1.0 - p_target_week
    p_neg = sum(float(row["probability"]) for row in table if float(row["weekly_return"]) < 0)
    sigma = weekly_volatility(N, p, R_w, R_l)
    r_50 = weekly_rate_for_growth(1.5, weeks)
    p_50 = required_win_probability(r_50 / N, R_w, R_l)

    sigma_in = body.get("sigma")
    correlation: dict[str, Any]
    if sigma_in is None:
        correlation = {"status": "CORRELATION_DATA_REQUIRED"}
    else:
        correlation = {"status": "SUPPLIED", "note": "w^T Sigma w interface only; no manufactured covariance."}

    costs = {
        "gross_ev": ev_t,
        "fees": "UNAVAILABLE",
        "slippage": "UNAVAILABLE",
        "net_ev": "NOT_COMPUTABLE",
    }
    if body.get("theoretical_zero_cost"):
        costs["net_ev"] = ev_t
        costs["note"] = "User selected theoretical zero-cost model."

    empirical_rows = body.get("classifications") or body.get("outcomes") or []
    uncertainty: dict[str, Any] | None = None
    if empirical_rows:
        wins = sum(1 for x in empirical_rows if x == "WIN")
        n = sum(1 for x in empirical_rows if x in {"WIN", "LOSS"})
        if n:
            p_hat, lo, hi = wilson_interval(wins, n)
            uncertainty = {
                "estimated_win_probability": p_hat,
                "lower_bound": lo,
                "upper_bound": hi,
                "n": n,
                "robust_vs_break_even": lo > p_be,
            }

    if mode == "A":
        sim = simulate_mode_a(cfg, seed=seed)
    elif mode == "B":
        sim = simulate_mode_b(
            cfg,
            list(empirical_rows),
            seed=seed,
            theoretical_zero_cost=bool(body.get("theoretical_zero_cost")),
        )
    elif mode == "C":
        probs = body.get("probabilities")
        if not isinstance(probs, list):
            raise RiskConfigError("model_probabilities_required")
        sim = simulate_mode_c(cfg, [float(x) for x in probs], seed=seed)
    else:
        raise RiskConfigError("invalid_mode")

    deterministic = {
        "capital_per_trade": C,
        "win_pnl": C * r_w,
        "loss_pnl": C * r_l,
        "R_w": R_w,
        "R_l": R_l,
        "break_even_probability": p_be,
        "trade_ev": ev_t,
        "trade_ev_dollars": dollar_trade_ev(p, C, r_w, r_l),
        "weekly_ev": ev_w,
        "weekly_ev_dollars": dollar_trade_ev(p, C, r_w, r_l) * N,
        "target_ev_per_trade": T_t,
        "required_win_probability": p_target,
        "weekly_volatility": sigma,
        "weekly_table": table,
        "min_wins_for_target": min_wins,
        "P_target_week": p_target_week,
        "P_below_target": p_below,
        "P_negative_week": p_neg,
        "anchors": {
            "wins_10": weekly_return_from_wins(N, N, R_w, R_l),
            "wins_7": weekly_return_from_wins(7, N, R_w, R_l) if N >= 7 else None,
            "wins_6": weekly_return_from_wins(6, N, R_w, R_l) if N >= 6 else None,
            "wins_0": weekly_return_from_wins(0, N, R_w, R_l),
        },
        "deterministic_compound_if_ev_realized": compound_if_constant(B, ev_w, weeks),
        "weekly_rate_for_50pct_annual": r_50,
        "win_probability_for_50pct_annual": p_50,
        "compounding_note": "(1+EV)^52 is not a Monte Carlo substitute.",
    }
    payload = {
        "artifact": "risk_result",
        "mode": mode,
        "seed": seed,
        "research_result_hash": research_hash,
        "config": cfg,
        "deterministic": deterministic,
        "monte_carlo": sim,
        "correlation": correlation,
        "costs": costs,
        "model_uncertainty": uncertainty,
        "controls": _controls(body, f, ev_t, p, p_be),
        "static_weekly_sizing": True,
        "not": ["fill", "live_trading", "executable_performance", "research_csv"],
    }
    payload["risk_result_hash"] = _hash(
        {
            "mode": mode,
            "seed": seed,
            "research_result_hash": research_hash,
            "config": cfg,
            "deterministic": deterministic,
            "monte_carlo_seed_mode": sim.get("mode"),
        }
    )
    return payload
