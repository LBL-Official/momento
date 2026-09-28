"""Constructibility taxonomy. Statuses are not interchangeable.

NOT_YET_IMPLEMENTED ≠ NOT_CONSTRUCTIBLE.

OHLC ≠ ORDER BOOK
CANDLE RETURN ≠ SIGNED FLOW
HIGH/LOW ≠ MICROPRICE
VOLUME ≠ QUEUE STATE
DATA EXISTS ≠ MEASUREMENT IS VALID
MORE DERIVATION ≠ MORE INFORMATION
"""

from __future__ import annotations

from typing import Any

from roller.state.capabilities import REAL, capability as sport_capability

ARCHITECTURE_STATUSES = frozenset(
    {
        "IMPLEMENTED",
        "PARTIAL",
        "NOT_YET_IMPLEMENTED",
        "NOT_CONSTRUCTIBLE",
    }
)

INSTANCE_STATUSES = frozenset(
    {
        "DATA_UNAVAILABLE",
        "INSUFFICIENT_SUPPORT",
        "INVALID_INPUT",
    }
)

MAPPED_STATUSES = frozenset({"IMPLEMENTED", "PARTIAL"})

DATA_UNAVAILABLE_SOURCE = frozenset(
    {
        "MISSING_K",
        "MISSING_F",
        "NO_PRIOR_CANDLE",
        "NO_PRIOR_F",
        "MISSING_REQUIRED_INPUT",
    }
)

INSUFFICIENT_SOURCE = frozenset(
    {
        "TIME_GAP",
        "MIXED_INTERVAL",
        "INSUFFICIENT_HISTORY",
        "INSUFFICIENT_SUPPORT",
        "PERIOD_OR_SEQUENCE_GAP",
    }
)

INVALID_SOURCE = frozenset(
    {
        "RECONCILIATION_FAILED",
        "INVALID_INPUT",
        "ZERO_SCORE_DELTA",
        "ZERO_ELAPSED",
        "ZERO_RANGE",
    }
)

# Structural substitutions that must fail even if a caller asks.
FORBIDDEN_SUBSTITUTIONS = {
    ("OHLC", "order_book"): "OHLC ≠ ORDER BOOK",
    ("OHLC", "FULL_ORDER_BOOK"): "OHLC ≠ ORDER BOOK",
    ("candle_volume", "signed_flow"): "CANDLE RETURN ≠ SIGNED FLOW",
    ("candle_volume", "signed_flow_lambda"): "CANDLE RETURN ≠ SIGNED FLOW",
    ("high_low", "microprice"): "HIGH/LOW ≠ MICROPRICE",
    ("OHLC", "microprice"): "HIGH/LOW ≠ MICROPRICE",
    ("volume", "queue"): "VOLUME ≠ QUEUE STATE",
    ("volume", "psi_resilience"): "VOLUME ≠ QUEUE STATE",
    ("candle_sequence", "second_level"): "CANDLE SEQUENCE ≠ SECOND-LEVEL MEASUREMENT",
    ("candle_sequence", "market_delta_1s"): "CANDLE SEQUENCE ≠ SECOND-LEVEL MEASUREMENT",
    ("possession_data", "possession_delta"): "DATA EXISTS ≠ MEASUREMENT IS VALID",
}


class ProxyProhibitedError(ValueError):
    """A prohibited proxy was requested. More derivation is not more information."""


def refuse_proxy(source: str, target: str) -> None:
    key = (str(source), str(target))
    if key in FORBIDDEN_SUBSTITUTIONS:
        raise ProxyProhibitedError(FORBIDDEN_SUBSTITUTIONS[key])
    raise ProxyProhibitedError(f"prohibited proxy {source} → {target}")


def refuse_registry_proxy(row: dict[str, Any], attempted: str) -> None:
    prohibited = [str(x) for x in (row.get("not") or [])]
    if attempted in prohibited:
        name = row.get("measurement_name")
        raise ProxyProhibitedError(f"{attempted} is a prohibited substitute for {name}")
    refuse_proxy(attempted, str(row.get("measurement_name") or ""))


def constructible(
    *,
    data_available: bool,
    information_regime_valid: bool,
    point_in_time_valid: bool,
    definition_exists: bool,
    definition_implemented: bool,
    identity_unambiguous: bool,
    proxy_prohibition_satisfied: bool,
) -> bool:
    """CONSTRUCTIBLE(M) requires all seven conjuncts."""
    return (
        data_available
        and information_regime_valid
        and point_in_time_valid
        and definition_exists
        and definition_implemented
        and identity_unambiguous
        and proxy_prohibition_satisfied
    )


def possession_conditioned_f_validated() -> bool:
    """Separate measurement contract. Not implied by NBA possessions=REAL."""
    return False


def possession_delta_authorized(sport: str = "NBA") -> bool:
    """NBA possessions=REAL is never sufficient for possession_delta."""
    data_exists = sport_capability(sport, "possessions") == REAL
    if data_exists and not possession_conditioned_f_validated():
        return False
    return possession_conditioned_f_validated()


def instance_status(v4b_status: str | None, registry_status: str) -> str:
    """Map a V4B instance state. Catalog None is not this function."""
    raw = str(v4b_status or "")
    if raw == "valid":
        return registry_status
    if raw in DATA_UNAVAILABLE_SOURCE:
        return "DATA_UNAVAILABLE"
    if raw in INSUFFICIENT_SOURCE:
        return "INSUFFICIENT_SUPPORT"
    if raw in INVALID_SOURCE:
        return "INVALID_INPUT"
    if not raw:
        return "DATA_UNAVAILABLE"
    return "DATA_UNAVAILABLE"
