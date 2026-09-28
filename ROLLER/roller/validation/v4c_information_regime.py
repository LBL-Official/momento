"""V4C information-regime audit. Modalities, not a quality ladder."""

from __future__ import annotations

from typing import Any

from roller.v4c.availability import DECLARED_CLOCKS, FUTURE_REGIME_CLOCKS
from roller.v4c.information_regimes import ACTIVE_REGIMES, REGIMES, RESOLUTIONS, quality_rank


def audit_information_regimes() -> list[str]:
    errors: list[str] = []
    expected = {
        "CANDLE_1M",
        "EVENT_SEQUENCE",
        "POSSESSION_STATE",
        "TRADE_TICK",
        "SECOND_SNAPSHOT",
        "FULL_ORDER_BOOK",
    }
    if set(REGIMES) != expected:
        errors.append(f"information regimes drifted: {REGIMES}")
    if ACTIVE_REGIMES != {"CANDLE_1M"}:
        errors.append("only CANDLE_1M may be active")
    if quality_rank("FULL_ORDER_BOOK") is not None or quality_rank("CANDLE_1M") is not None:
        errors.append("regimes must not expose a quality rank")
    if "60_SECOND_CANDLE" not in RESOLUTIONS or "1_SECOND" not in RESOLUTIONS:
        errors.append("resolution vocabulary incomplete")
    return errors


def audit_declared_clocks() -> list[str]:
    errors: list[str] = []
    for name in (
        "state_available_at",
        "candle_available_at",
        "measurement_available_at",
        "event_available_at",
        "trade_available_at",
        "book_snapshot_available_at",
    ):
        if name not in DECLARED_CLOCKS:
            errors.append(f"missing declared clock {name}")
    if FUTURE_REGIME_CLOCKS != {
        "event_available_at",
        "trade_available_at",
        "book_snapshot_available_at",
    }:
        errors.append("future-regime clocks drifted")
    return errors


def run_v4c_information_regime_validate() -> dict[str, Any]:
    errors = audit_information_regimes() + audit_declared_clocks()
    return {"status": "FAIL" if errors else "PASS", "errors": errors}
