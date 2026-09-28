"""TK Ultra V0 constants and JSON helpers. Not live."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Any

ASSESSMENT_SCHEMA = "tk_ultra.assessment.v0"
STATE_SCHEMA = "tk_ultra.state.v0"
LIST_SCHEMA = "tk_ultra.position_list.v1"
DESK_SCHEMA = "tk_ultra_desk_v1"
LIVE_EXECUTION = False
PRODUCT = "TK Ultra"
SYSTEM_ID = "relative_value_hedging"
MODEL_GENERIC = "GENERIC_RV"
MODEL_BINARY = "BINARY_COMPLEMENT_V0"
BETA_SOURCE = "STRUCTURAL_COMPLEMENT"
BETA_VERSION = "tk_ultra.beta.v0"
AUSTIN_UNIVERSE = "choosin_nba_2q3q_604"
AUSTIN_N = 604
CHOOSIN_UNIVERSE = "derived_four_936"
CHOOSIN_N = 936
UNAVAILABLE = "UNAVAILABLE"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def frac_decimal(value: Fraction | None, places: int) -> str | None:
    if value is None:
        return None
    quant = Decimal("1").scaleb(-places)
    number = Decimal(value.numerator) / Decimal(value.denominator)
    return str(number.quantize(quant, rounding=ROUND_HALF_UP))


def as_fraction(raw: object, *, field: str) -> Fraction:
    if raw is None or raw == "" or raw == UNAVAILABLE:
        raise ValueError(f"{field} is missing")
    try:
        return Fraction(str(raw).strip())
    except (ValueError, ZeroDivisionError, TypeError) as exc:
        raise ValueError(f"{field} is not a number") from exc


def optional_fraction(raw: object) -> Fraction | None:
    if raw is None or raw == "" or raw == UNAVAILABLE:
        return None
    try:
        return Fraction(str(raw).strip())
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def unavailable(value: object) -> bool:
    return value is None or value == "" or value == UNAVAILABLE


def json_unavail(value: object) -> Any:
    if unavailable(value):
        return UNAVAILABLE
    return value
