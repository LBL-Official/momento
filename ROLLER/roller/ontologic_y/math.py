"""Fair odds from an in-house probability. No vig removal."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite

from roller.ontologic_y import SOURCE, VIG_REMOVAL

CENT = Decimal("0.0001")
ONE = Decimal(1)
HUNDRED = Decimal(100)


class InvalidProbability(ValueError):
    """A probability is missing or not finite."""


def _decimal(value: object) -> Decimal:
    if value is None or isinstance(value, bool):
        raise InvalidProbability("missing")
    if isinstance(value, float):
        if not isfinite(value):
            raise InvalidProbability("non-finite")
        value = format(value, "f")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise InvalidProbability("invalid") from exc
    if not number.is_finite():
        raise InvalidProbability("non-finite")
    return number


def percent_text(probability: Decimal) -> str:
    points = (probability * HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)
    return f"{points}%"


def complement(home: object) -> dict:
    """Binary complement. Valid only for a two-outcome market."""
    probability = _decimal(home)
    if probability < 0 or probability > 1:
        return {"status": "INCOHERENT_PARTITION", "home": None, "away": None}
    away = ONE - probability
    return {
        "status": "OK",
        "home": probability,
        "away": away,
        "source": SOURCE,
        "vig_removal": VIG_REMOVAL,
        "home_display_percent": percent_text(probability),
        "away_display_percent": percent_text(away),
    }


def fair_decimal(probability: object) -> str | None:
    probability = _decimal(probability)
    if probability <= 0 or probability >= 1:
        return None
    return format(ONE / probability, "f")


def american_from_probability(probability: object) -> str | None:
    probability = _decimal(probability)
    if probability <= 0 or probability >= 1:
        return None
    if probability > Decimal("0.5"):
        price = -(HUNDRED * probability / (ONE - probability))
    else:
        price = HUNDRED * (ONE - probability) / probability
    return format(price.quantize(CENT, rounding=ROUND_HALF_UP), "f")
