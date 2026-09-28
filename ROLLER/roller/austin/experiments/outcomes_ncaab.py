"""After-t outcomes for locked NCAAB trades. Primary target is hold-to-settlement."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.austin.outcomes import hold_pnl_cents, outcome_after_snapshot, taker_8040_pnl_cents


def baseline_hold_cents(trade: dict[str, Any]) -> int:
    return hold_pnl_cents(won=bool(trade.get("won")))


def baseline_8040_cents(trade: dict[str, Any]) -> int:
    return taker_8040_pnl_cents(won=bool(trade.get("won")), hit_40=bool(trade.get("t40")))


def outcomes_for_trade(
    trade: dict[str, Any],
    *,
    snapshot_ts: datetime,
    bars: list[tuple[datetime, float, float, float]],
) -> dict[str, Any]:
    mapped = {
        "entry_price_cents": trade.get("entry_price_cents") or 80,
        "w": bool(trade.get("won")),
        "t40": bool(trade.get("t40")),
    }
    return outcome_after_snapshot(
        mapped,
        snapshot_ts=snapshot_ts,
        favorite_post=bars,
        opponent_post=[],
    )
