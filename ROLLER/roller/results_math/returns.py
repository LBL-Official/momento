"""Observed path returns. CANDLE PATH ≠ FILL. Missing exit stays unavailable."""

from __future__ import annotations

from typing import Any

from roller.results_math.means import (
    excess_kurtosis,
    mean,
    median,
    quantiles,
    sample_std,
    sample_variance,
    skewness,
    t_interval,
)
from roller.results_math.models import OBSERVED, UNAVAILABLE
from roller.results_math.observations import chronological_returns, valid_returns
from roller.results_math.path_metrics import observed_path_sharpe, path_economics


def trade_sharpe(xs: list[int] | list[float]) -> float | None:
    """Alias for unannualized observed-path Sharpe. Never sqrt(252)."""
    return observed_path_sharpe([float(x) for x in xs])


def return_distribution(xs: list[int] | list[float]) -> dict[str, Any]:
    n = len(xs)
    if n == 0:
        return {
            "status": UNAVAILABLE,
            "n": 0,
            "reason": "Need >= 1 observed return. Missing exit is not zero return.",
        }
    floats = [float(x) for x in xs]
    econ = path_economics(floats)
    return {
        "status": OBSERVED,
        "label": "OBSERVED PATH RETURN · CANDLE PATH · NOT A FILL",
        "n": n,
        "mean_cents": mean(floats),
        "median_cents": median(floats),
        "std_cents": sample_std(floats),
        "variance_cents": sample_variance(floats),
        "min_cents": min(floats),
        "max_cents": max(floats),
        "quantiles": quantiles(floats),
        "skewness": skewness(floats),
        "excess_kurtosis": excess_kurtosis(floats),
        "sharpe_trade": econ.get("sharpe"),
        "observed_path_sharpe": econ.get("sharpe"),
        "sharpe_label": "UNANNUALIZED OBSERVED PATH SHARPE",
        "sortino": econ.get("sortino"),
        "downside_deviation_cents": econ.get("downside_deviation_cents"),
        "mean_positive_cents": econ.get("mean_positive_cents"),
        "mean_negative_cents": econ.get("mean_negative_cents"),
        "payoff_ratio": econ.get("payoff_ratio"),
        "profit_factor": econ.get("profit_factor"),
        "expected_shortfall_p5": econ.get("expected_shortfall_p5"),
        "expected_shortfall_p10": econ.get("expected_shortfall_p10"),
        "sign_fractions": econ.get("sign_fractions"),
        "ev_ci": t_interval(floats),
        "sum_cents": sum(floats),
        "economics": econ,
    }


def observed_from_rows(obs: list[dict[str, Any]]) -> dict[str, Any]:
    xs = valid_returns(obs)
    dist = return_distribution(xs)
    dist["n_population"] = len(obs)
    dist["n_missing_exit"] = len(obs) - len(xs)
    dist["chronological_returns"] = chronological_returns(obs)
    return dist
