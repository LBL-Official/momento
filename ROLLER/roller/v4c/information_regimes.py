"""Information regimes are modalities, not a linear quality ladder.

EVENT_SEQUENCE is not 'better than' CANDLE_1M. FULL_ORDER_BOOK does not
encode a complete basketball event sequence. Resolution is a separate field.
"""

from __future__ import annotations

from typing import Any

REGIMES = (
    "CANDLE_1M",
    "EVENT_SEQUENCE",
    "POSSESSION_STATE",
    "TRADE_TICK",
    "SECOND_SNAPSHOT",
    "FULL_ORDER_BOOK",
)

RESOLUTIONS = (
    "60_SECOND_CANDLE",
    "1_SECOND",
    "EVENT_TIMESTAMP",
    "TRADE_TIMESTAMP",
    "BOOK_SNAPSHOT",
)

ACTIVE_REGIMES = frozenset({"CANDLE_1M"})

REGIME_META: dict[str, dict[str, Any]] = {
    "CANDLE_1M": {
        "active": True,
        "modality": "one_minute_ohlc_candle",
        "not": ["order_book", "signed_flow", "second_snapshot"],
    },
    "EVENT_SEQUENCE": {
        "active": False,
        "modality": "sport_event_sequence",
        "not": ["lower_resolution_candle"],
    },
    "POSSESSION_STATE": {
        "active": False,
        "modality": "possession_state",
        "not": ["candle_inferred_possession"],
    },
    "TRADE_TICK": {
        "active": False,
        "modality": "trade_prints",
        "not": ["candle_volume"],
    },
    "SECOND_SNAPSHOT": {
        "active": False,
        "modality": "one_second_market_snapshot",
        "not": ["resampled_candle"],
    },
    "FULL_ORDER_BOOK": {
        "active": False,
        "modality": "full_limit_order_book",
        "not": ["ohlc", "high_low", "midpoint_proxy"],
    },
}


def is_regime(name: str) -> bool:
    return str(name) in REGIMES


def is_resolution(name: str) -> bool:
    return str(name) in RESOLUTIONS


def regime_of(row: dict[str, Any]) -> str:
    return str(row.get("information_regime") or row.get("required_information_regime") or "")


def quality_rank(_regime: str) -> None:
    """Regimes are not ordered. Do not call this to compare information quality."""
    return None
