"""Decimal conversions, proportional no-vig, and analytical partitions."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite

from roller.ontologic_x import METHOD

CENT = Decimal("0.0001")
ONE = Decimal(1)
HUNDRED = Decimal(100)


class InvalidPrice(ValueError):
    """A price is missing, zero, or not finite."""


def _decimal(value: object) -> Decimal:
    if value is None or isinstance(value, bool):
        raise InvalidPrice("missing")
    if isinstance(value, float):
        if not isfinite(value):
            raise InvalidPrice("non-finite")
        value = format(value, "f")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise InvalidPrice("invalid") from exc
    if not number.is_finite():
        raise InvalidPrice("non-finite")
    return number


def percent_points(probability: Decimal) -> Decimal:
    return (probability * HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)


def percent_text(probability: Decimal) -> str:
    return f"{percent_points(probability)}%"


def american_implied(american: object) -> tuple[Decimal, Decimal]:
    """Return (decimal_odds, raw_implied) for an American price."""
    price = _decimal(american)
    if price == 0:
        raise InvalidPrice("zero")
    if price > 0:
        return (ONE + price / HUNDRED, HUNDRED / (price + HUNDRED))
    absolute = abs(price)
    return (ONE + HUNDRED / absolute, absolute / (absolute + HUNDRED))


def decimal_implied(decimal_odds: object) -> Decimal:
    price = _decimal(decimal_odds)
    if price <= 1:
        raise InvalidPrice("decimal<=1")
    return ONE / price


def proportional_no_vig(raw: list[Decimal]) -> dict:
    """Normalize one complete mutually exclusive set. No clipping."""
    if len(raw) < 2:
        return {"method": METHOD, "status": "INCOMPLETE", "normalized": []}
    if any(item <= 0 or not item.is_finite() for item in raw):
        return {"method": METHOD, "status": "INVALID_PRICE", "normalized": []}
    total = sum(raw, Decimal(0))
    overround = total - ONE
    normalized = []
    for implied in raw:
        probability = implied / total
        normalized.append(
            {
                "implied": implied,
                "probability": probability,
                "fair_decimal": ONE / probability,
                "display_percent": percent_text(probability),
                "raw_display_percent": percent_text(implied),
            }
        )
    mass = sum((item["probability"] for item in normalized), Decimal(0))
    return {
        "method": METHOD,
        "status": "OK",
        "implied_total": total,
        "overround": overround,
        "overround_points": f"{percent_points(overround)}",
        "normalized": normalized,
        "mass": mass,
    }


def _format_line(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def is_integer_line(line: object) -> bool:
    number = _decimal(line)
    return number == number.to_integral_value()


def analytical_partition(points: list[tuple[Decimal, Decimal]], variable: str) -> dict:
    """Finite buckets from survival points P(X > threshold). No score matrix."""
    if not points:
        return {
            "method": METHOD,
            "status": "UNAVAILABLE",
            "reason": "NO_COMPLETE_PAIR",
            "buckets": [],
            "variable": variable,
        }
    ordered = sorted(points, key=lambda item: item[0])
    thresholds = [item[0] for item in ordered]
    if len(thresholds) != len(set(thresholds)):
        return _broken(variable, "DUPLICATE_THRESHOLD")
    survivals = [item[1] for item in ordered]
    if any(not item.is_finite() or item < 0 or item > 1 for item in survivals):
        return _broken(variable, "SURVIVAL_OUT_OF_RANGE")
    if any(left < right for left, right in zip(survivals, survivals[1:])):
        return _broken(variable, "INCONSISTENT_LADDER")
    buckets: list[dict] = []
    first_line = _format_line(ordered[0][0])
    buckets.append(
        {
            "label": f"{variable} ≤ {first_line}",
            "probability": ONE - ordered[0][1],
            "unbounded_below": True,
            "unbounded_above": False,
        }
    )
    for (left_line, left_p), (right_line, right_p) in zip(ordered, ordered[1:]):
        buckets.append(
            {
                "label": f"{_format_line(left_line)} < {variable} ≤ {_format_line(right_line)}",
                "probability": left_p - right_p,
                "unbounded_below": False,
                "unbounded_above": False,
            }
        )
    last_line = _format_line(ordered[-1][0])
    buckets.append(
        {
            "label": f"{variable} > {last_line}",
            "probability": ordered[-1][1],
            "unbounded_below": False,
            "unbounded_above": True,
        }
    )
    if any(bucket["probability"] < 0 for bucket in buckets):
        return _broken(variable, "NEGATIVE_MASS")
    mass = sum((bucket["probability"] for bucket in buckets), Decimal(0))
    if mass != ONE:
        return _broken(variable, "MASS_NOT_ONE")
    for bucket in buckets:
        bucket["display_percent"] = percent_text(bucket["probability"])
        bucket["probability"] = format(bucket["probability"], "f")
    return {
        "method": METHOD,
        "status": "OK",
        "reason": None,
        "variable": variable,
        "buckets": buckets,
        "mass": "1",
        "assumptions": "market-derived under PROPORTIONAL_NO_VIG_V1; not an observed score distribution",
    }


def _broken(variable: str, reason: str) -> dict:
    return {
        "method": METHOD,
        "status": "SUPPRESSED",
        "reason": reason,
        "variable": variable,
        "buckets": [],
    }
