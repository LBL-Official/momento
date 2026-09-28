"""Deterministic bankroll formulas. Percentages are decimal fractions."""

from __future__ import annotations

import math
from math import comb
from typing import Any


class RiskConfigError(ValueError):
    pass


def _finite(name: str, value: object) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise RiskConfigError(f"invalid_{name}") from exc
    if not math.isfinite(out):
        raise RiskConfigError(f"invalid_{name}")
    return out


def validate_config(cfg: dict[str, Any]) -> dict[str, float | int]:
    B = _finite("initial_bankroll", cfg.get("initial_bankroll", 20_000))
    f = _finite("trade_allocation", cfg.get("trade_allocation", 0.05))
    r_w = _finite("win_return", cfg.get("win_return", 0.20))
    r_l = _finite("loss_return", cfg.get("loss_return", -0.40))
    p = _finite("win_probability", cfg.get("win_probability", 0.70))
    N = cfg.get("trades_per_week", 10)
    T_w = _finite("target_weekly_ev", cfg.get("target_weekly_ev", 0.01))
    weeks = cfg.get("weeks_per_year", 52)
    paths = cfg.get("monte_carlo_paths", 100_000)
    try:
        N = int(N)
        weeks = int(weeks)
        paths = int(paths)
    except (TypeError, ValueError) as exc:
        raise RiskConfigError("invalid_integer_parameter") from exc
    if B <= 0:
        raise RiskConfigError("zero_bankroll")
    if N <= 0:
        raise RiskConfigError("zero_trades")
    if weeks <= 0:
        raise RiskConfigError("zero_weeks")
    if paths <= 0:
        raise RiskConfigError("invalid_monte_carlo_count")
    if not 0 < f <= 1:
        raise RiskConfigError("invalid_allocation")
    if not 0 <= p <= 1:
        raise RiskConfigError("invalid_probability")
    if r_w <= r_l:
        raise RiskConfigError("invalid_payoff")
    if T_w < 0:
        raise RiskConfigError("negative_target")
    out: dict[str, float | int] = {
        "initial_bankroll": B,
        "trade_allocation": f,
        "win_return": r_w,
        "loss_return": r_l,
        "win_probability": p,
        "trades_per_week": N,
        "target_weekly_ev": T_w,
        "weeks_per_year": weeks,
        "monte_carlo_paths": paths,
    }
    if cfg.get("bankroll_floor") is not None:
        out["bankroll_floor"] = _finite("bankroll_floor", cfg.get("bankroll_floor"))
    if cfg.get("target_bankroll") is not None:
        out["target_bankroll"] = _finite("target_bankroll", cfg.get("target_bankroll"))
    return out


def trade_capital(B: float, f: float) -> float:
    return B * f


def bankroll_win_return(f: float, r_w: float) -> float:
    return f * r_w


def bankroll_loss_return(f: float, r_l: float) -> float:
    return f * r_l


def trade_ev(p: float, R_w: float, R_l: float) -> float:
    return p * R_w + (1.0 - p) * R_l


def dollar_trade_ev(p: float, C: float, r_w: float, r_l: float) -> float:
    return C * (p * r_w + (1.0 - p) * r_l)


def break_even_probability(R_w: float, R_l: float) -> float:
    denom = R_w - R_l
    if denom == 0:
        raise RiskConfigError("invalid_payoff")
    return -R_l / denom


def target_ev_per_trade(T_w: float, N: int) -> float:
    return T_w / float(N)


def required_win_probability(T_t: float, R_w: float, R_l: float) -> float:
    denom = R_w - R_l
    if denom == 0:
        raise RiskConfigError("invalid_payoff")
    return (T_t - R_l) / denom


def weekly_ev(N: int, ev_t: float) -> float:
    return N * ev_t


def weekly_return_from_wins(k: int, N: int, R_w: float, R_l: float) -> float:
    return k * R_w + (N - k) * R_l


def weekly_probability(k: int, N: int, p: float) -> float:
    return comb(N, k) * (p**k) * ((1.0 - p) ** (N - k))


def weekly_distribution(N: int, p: float, R_w: float, R_l: float) -> list[dict[str, float | int]]:
    rows = []
    for k in range(N + 1):
        rows.append(
            {
                "wins": k,
                "losses": N - k,
                "weekly_return": weekly_return_from_wins(k, N, R_w, R_l),
                "probability": weekly_probability(k, N, p),
            }
        )
    return rows


def weekly_volatility(N: int, p: float, R_w: float, R_l: float) -> float:
    return (R_w - R_l) * math.sqrt(N * p * (1.0 - p))


def min_wins_for_target(N: int, R_w: float, R_l: float, T_w: float) -> int | None:
    for k in range(N + 1):
        if weekly_return_from_wins(k, N, R_w, R_l) + 1e-15 >= T_w:
            return k
    return None


def compound_if_constant(B: float, r: float, weeks: int) -> float:
    return B * ((1.0 + r) ** weeks)


def weekly_rate_for_growth(multiple: float, weeks: int) -> float:
    return multiple ** (1.0 / weeks) - 1.0


def wilson_interval_from_p(p: float, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n <= 0:
        raise RiskConfigError("zero_trades")
    rate = min(1.0, max(0.0, float(p)))
    den = 1.0 + z * z / n
    center = (rate + z * z / (2 * n)) / den
    margin = z * math.sqrt((rate * (1.0 - rate) + z * z / (4 * n)) / n) / den
    return rate, max(0.0, center - margin), min(1.0, center + margin)


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n <= 0:
        raise RiskConfigError("zero_trades")
    return wilson_interval_from_p(wins / n, n, z=z)
