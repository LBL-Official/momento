"""Observed-path economic diagnostics. CANDLE PATH ≠ FILL. Missing ≠ 0."""

from __future__ import annotations

from typing import Any

from roller.results_math.means import mean, median, quantile, sample_std
from roller.results_math.models import DERIVED, OBSERVED, UNAVAILABLE


def downside_deviation(xs: list[float], *, target: float = 0.0) -> float | None:
    """sqrt(mean of squared deviations below target). Population form."""
    if not xs:
        return None
    acc = 0.0
    for x in xs:
        d = min(0.0, x - target)
        acc += d * d
    return (acc / len(xs)) ** 0.5


def sortino_ratio(xs: list[float]) -> float | None:
    m = mean(xs)
    d = downside_deviation(xs)
    if m is None or d is None or d == 0:
        return None
    return m / d


def observed_path_sharpe(xs: list[float]) -> float | None:
    """Unannualized. Games are not a fixed-frequency IID series."""
    if len(xs) < 2:
        return None
    m = mean(xs)
    s = sample_std(xs)
    if m is None or s is None or s == 0:
        return None
    return m / s


def mean_positive(xs: list[float]) -> float | None:
    pos = [x for x in xs if x > 0]
    return mean(pos)


def mean_negative(xs: list[float]) -> float | None:
    neg = [x for x in xs if x < 0]
    return mean(neg)


def payoff_ratio(xs: list[float]) -> dict[str, Any]:
    mp = mean_positive(xs)
    mn = mean_negative(xs)
    if mp is None or mn is None or mn == 0:
        return {
            "status": UNAVAILABLE,
            "reason": "Need both positive and negative observed returns. Zero not substituted.",
        }
    return {
        "status": DERIVED,
        "value": mp / abs(mn),
        "mean_positive_cents": mp,
        "mean_negative_cents": mn,
    }


def profit_factor(xs: list[float]) -> dict[str, Any]:
    pos = sum(x for x in xs if x > 0)
    neg = sum(x for x in xs if x < 0)
    if neg == 0:
        return {
            "status": UNAVAILABLE,
            "reason": "No negative observed returns. Zero not substituted.",
        }
    return {
        "status": DERIVED,
        "value": pos / abs(neg),
        "sum_positive_cents": pos,
        "sum_negative_cents": neg,
    }


def empirical_sign_fractions(xs: list[float]) -> dict[str, Any]:
    n = len(xs)
    if n == 0:
        return {"status": UNAVAILABLE, "reason": "Need >= 1 observed return."}
    n_lt = sum(1 for x in xs if x < 0)
    n_le = sum(1 for x in xs if x <= 0)
    n_gt = sum(1 for x in xs if x > 0)
    n_ge = sum(1 for x in xs if x >= 0)
    n_eq = sum(1 for x in xs if x == 0)
    return {
        "status": OBSERVED,
        "label": "EMPIRICAL SAMPLE FRACTION · not a future probability",
        "n": n,
        "fraction_positive": n_gt / n,
        "fraction_negative": n_lt / n,
        "fraction_zero": n_eq / n,
        "p_return_lt_0": n_lt / n,
        "p_return_le_0": n_le / n,
        "p_return_gt_0": n_gt / n,
        "p_return_ge_0": n_ge / n,
    }


def expected_shortfall(xs: list[float], p: float, *, min_tail: int = 2) -> dict[str, Any]:
    if len(xs) < min_tail:
        return {"status": UNAVAILABLE, "reason": "Insufficient tail observations."}
    q = quantile(xs, p)
    if q is None:
        return {"status": UNAVAILABLE, "reason": "Quantile unavailable."}
    tail = [x for x in xs if x <= q]
    if len(tail) < min_tail:
        return {"status": UNAVAILABLE, "reason": "Insufficient tail observations."}
    return {
        "status": OBSERVED,
        "label": "EMPIRICAL EXPECTED SHORTFALL · not a parametric CVaR",
        "threshold_p": p,
        "threshold_cents": q,
        "n_tail": len(tail),
        "mean_cents": mean(tail),
    }


def path_economics(xs: list[float]) -> dict[str, Any]:
    if not xs:
        return {"status": UNAVAILABLE, "reason": "Need >= 1 observed return."}
    return {
        "status": OBSERVED,
        "expected_return_per_contract_cents": mean(xs),
        "median_return_per_contract_cents": median(xs),
        "std_per_contract_cents": sample_std(xs),
        "downside_deviation_cents": downside_deviation(xs),
        "mean_positive_cents": mean_positive(xs),
        "mean_negative_cents": mean_negative(xs),
        "payoff_ratio": payoff_ratio(xs),
        "profit_factor": profit_factor(xs),
        "sortino": sortino_ratio(xs),
        "sharpe": observed_path_sharpe(xs),
        "sharpe_label": "UNANNUALIZED OBSERVED PATH SHARPE",
        "expected_shortfall_p5": expected_shortfall(xs, 0.05),
        "expected_shortfall_p10": expected_shortfall(xs, 0.10),
        "sign_fractions": empirical_sign_fractions(xs),
    }
