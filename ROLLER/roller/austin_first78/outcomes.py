"""78/67 candle-path outcomes after snapshot t. Not a fill."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.austin.bars_join import first_close_at_or_below
from roller.austin_first78.config import EV_DEFINITION, GAIN_CENTS, HOLD_LOSS_CENTS, STOP_CENTS

NOT_APPLICABLE = "NOT_APPLICABLE"


def official_pnl_cents(*, won: bool, stopped: bool) -> int:
    if stopped:
        return int(STOP_CENTS) - 78
    return int(GAIN_CENTS) if won else -int(HOLD_LOSS_CENTS)


def outcome_after_snapshot(
    trade: dict[str, Any],
    *,
    snapshot_ts: datetime,
    favorite_post: list,
) -> dict[str, Any]:
    prior = [row for row in favorite_post if row[0] <= snapshot_ts]
    future = [row for row in favorite_post if row[0] > snapshot_ts]
    entry = float(trade["entry_price_cents"])
    prices = [row[1] for row in future]
    mfe = max([p - entry for p in prices], default=None)
    mae = max([entry - p for p in prices], default=None)
    hit = first_close_at_or_below(future, float(STOP_CENTS))
    hit_68 = first_close_at_or_below(future, 68.0)
    hit_69 = first_close_at_or_below(future, 69.0)
    already = first_close_at_or_below(prior, float(STOP_CENTS)) is not None
    won = bool(trade["w"])
    stopped_trade = bool(trade["t67"])
    if already:
        path_pnl: int | None = official_pnl_cents(won=won, stopped=True)
        path_status = "ALREADY_STOPPED"
    else:
        path_pnl = official_pnl_cents(won=won, stopped=hit is not None)
        path_status = "VALUE"
    full = official_pnl_cents(won=won, stopped=stopped_trade)
    return {
        "settlement": "YES" if won else "NO",
        "won": won,
        "csv_t40": stopped_trade,
        "t67": stopped_trade,
        "t40_already": already,
        "t67_already": already,
        "hit_40_after": hit is not None,
        "hit_67_after": hit is not None,
        "hit_67_time": None if hit is None else hit[0].isoformat(),
        "hit_68_after": hit_68 is not None,
        "hit_69_after": hit_69 is not None,
        "max_favorable_excursion_after": None if mfe is None else float(max(0.0, mfe)),
        "max_adverse_excursion_after": None if mae is None else float(max(0.0, mae)),
        "pnl_hold_after_t": path_pnl,
        "pnl_8040_after_t": path_pnl,
        "pnl_8040_after_t_status": path_status,
        "pnl_7867_after_t": path_pnl,
        "pnl_7867_after_t_status": path_status,
        "final_pnl_hold_cents": full,
        "final_pnl_taker_8040_cents": full,
        "final_pnl_taker_7867_cents": full,
        "ev_definition_hold": EV_DEFINITION,
        "candle_path_not_fill": True,
    }
