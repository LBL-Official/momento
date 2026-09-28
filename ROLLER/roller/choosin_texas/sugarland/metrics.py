"""Bid appreciation summaries. Empty samples stay unavailable."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from fractions import Fraction
from typing import Any

from roller.choosin_texas.sugarland.constants import BOOTSTRAP_REPS, BOOTSTRAP_SEED


def dpp(bid0: int, bid30: int) -> Fraction:
    return Fraction(bid30 - bid0, 100)


def relative_return(bid0: int, bid30: int) -> Fraction | None:
    if bid0 <= 0:
        return None
    return Fraction(bid30 - bid0, bid0)


def upside_share(bid0: int, bid30: int) -> Fraction | None:
    if bid0 >= 10000:
        return None
    return Fraction(bid30 - bid0, 10000 - bid0)


def log_odds_change(bid0: int, bid30: int) -> float | None:
    if min(bid0, bid30) <= 0 or max(bid0, bid30) >= 10000:
        return None
    p0 = bid0 / 10000.0
    p30 = bid30 / 10000.0
    return math.log(p30 / (1.0 - p30)) - math.log(p0 / (1.0 - p0))


def gross_dollars(entry_ask: int, exit_bid: int) -> Fraction:
    return Fraction(exit_bid - entry_ask, 10000)


def return_on_ask(entry_ask: int, exit_bid: int) -> Fraction | None:
    if entry_ask <= 0:
        return None
    return Fraction(exit_bid - entry_ask, entry_ask)


def taker_fee_estimate(price_e4: int, contracts: int = 1) -> Fraction | None:
    """Published quadratic taker estimate. Not a date-matched historical fee."""
    if price_e4 <= 0 or price_e4 >= 10000 or contracts <= 0:
        return None
    p = Fraction(price_e4, 10000)
    raw = Fraction(7, 100) * contracts * p * (1 - p)
    micros = raw * 1_000_000
    ceiled = (micros.numerator + micros.denominator - 1) // micros.denominator
    return Fraction(int(ceiled), 1_000_000)


def _quantile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def _as_float(value: Fraction | float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def summarize_dpp(
    rows: list[dict[str, Any]],
    *,
    reps: int = BOOTSTRAP_REPS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """rows need game_date, dpp (Fraction or float), and optional return_on_ask."""
    eligible = len(rows)
    usable = [row for row in rows if row.get("dpp") is not None]
    n = len(usable)
    if n == 0:
        return {
            "eligible_n": eligible,
            "endpoint_n": 0,
            "mean_dpp": None,
            "median_dpp": None,
            "sd_dpp": None,
            "q10": None,
            "q25": None,
            "q75": None,
            "q90": None,
            "share_rising": None,
            "share_unchanged": None,
            "share_falling": None,
            "ci95_low": None,
            "ci95_high": None,
            "mean_return_on_ask": None,
            "share_gross_positive": None,
            "status": "UNAVAILABLE",
        }
    values = [float(row["dpp"]) for row in usable]
    ordered = sorted(values)
    mean = sum(values) / n
    if n > 1:
        var = sum((v - mean) ** 2 for v in values) / (n - 1)
        sd = math.sqrt(var)
    else:
        sd = None
    rising = sum(1 for v in values if v > 0)
    flat = sum(1 for v in values if v == 0)
    falling = sum(1 for v in values if v < 0)
    asks = [float(row["return_on_ask"]) for row in usable if row.get("return_on_ask") is not None]
    gross_flags = [row.get("gross_positive") for row in usable if row.get("gross_positive") is not None]
    ci_low, ci_high = _bootstrap_mean(usable, reps=reps, seed=seed)
    return {
        "eligible_n": eligible,
        "endpoint_n": n,
        "mean_dpp": mean,
        "median_dpp": _quantile(ordered, 0.5),
        "sd_dpp": sd,
        "q10": _quantile(ordered, 0.10),
        "q25": _quantile(ordered, 0.25),
        "q75": _quantile(ordered, 0.75),
        "q90": _quantile(ordered, 0.90),
        "share_rising": rising / n,
        "share_unchanged": flat / n,
        "share_falling": falling / n,
        "ci95_low": ci_low,
        "ci95_high": ci_high,
        "mean_return_on_ask": (sum(asks) / len(asks)) if asks else None,
        "share_gross_positive": (sum(1 for flag in gross_flags if flag) / len(gross_flags)) if gross_flags else None,
        "status": "OBSERVED",
    }


def summarize_series(
    rows: list[dict[str, Any]],
    key: str,
    *,
    reps: int = BOOTSTRAP_REPS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Mean of one numeric field. Interval is INSUFFICIENT_SAMPLE when N < 2."""
    usable = [row for row in rows if row.get(key) is not None]
    n = len(usable)
    if n == 0:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "share_positive": None,
            "ci95_low": None,
            "ci95_high": None,
            "interval_status": "UNAVAILABLE",
        }
    values = [float(row[key]) for row in usable]
    ordered = sorted(values)
    mean = sum(values) / n
    positive = sum(1 for value in values if value > 0)
    if n < 2:
        return {
            "n": n,
            "mean": mean,
            "median": _quantile(ordered, 0.5),
            "share_positive": positive / n,
            "ci95_low": None,
            "ci95_high": None,
            "interval_status": "INSUFFICIENT_SAMPLE",
        }
    ci_low, ci_high = _bootstrap_mean(usable, reps=reps, seed=seed, field=key)
    return {
        "n": n,
        "mean": mean,
        "median": _quantile(ordered, 0.5),
        "share_positive": positive / n,
        "ci95_low": ci_low,
        "ci95_high": ci_high,
        "interval_status": "OBSERVED",
    }


def _bootstrap_mean(
    rows: list[dict[str, Any]],
    *,
    reps: int,
    seed: int,
    field: str = "dpp",
) -> tuple[float | None, float | None]:
    groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        groups[str(row.get("game_date") or "")].append(float(row[field]))
    dates = list(groups)
    if not dates:
        return None, None
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(reps):
        draw = [dates[rng.randrange(len(dates))] for _ in range(len(dates))]
        vals = [v for day in draw for v in groups[day]]
        if not vals:
            continue
        means.append(sum(vals) / len(vals))
    if not means:
        return None, None
    means.sort()
    return _quantile(means, 0.025), _quantile(means, 0.975)


def without_largest_gain(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    usable = [row for row in rows if row.get("dpp") is not None]
    if not usable:
        return rows
    top = max(usable, key=lambda row: float(row["dpp"]))
    return [row for row in rows if row is not top]


def json_number(value: Any) -> Any:
    if value is None:
        return "UNAVAILABLE"
    if isinstance(value, Fraction):
        return float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return "UNAVAILABLE"
    return value
