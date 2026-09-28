"""Outcome space. Strictly after snapshot t. Not features."""

from __future__ import annotations

from datetime import datetime
from fractions import Fraction
from typing import Any

from roller.austin.bars_join import first_close_at_or_above, first_close_at_or_below, first_high_at_or_above
from roller.austin.config import DEFAULT
from roller.choosin_texas.ev import ev_from_s

NOT_APPLICABLE = "NOT_APPLICABLE"
HOLD_EV_DEFINITION = "hold_80_to_settlement"
CHOOSIN_8040_AFTER_T = "choosin_8040_after_t"


def hold_pnl_cents(*, won: bool, gain: int = DEFAULT.gain_cents, loss: int = DEFAULT.hold_loss_cents) -> int:
    return int(gain) if won else -int(loss)


def taker_8040_pnl_cents(*, won: bool, hit_40: bool) -> int:
    if hit_40:
        return -int(DEFAULT.stop_cents)
    return hold_pnl_cents(won=won)


def theoretical_hold_ev(s: Fraction) -> Fraction:
    return ev_from_s(s, DEFAULT.gain_cents, DEFAULT.hold_loss_cents)


def theoretical_taker_ev(s: Fraction) -> Fraction:
    return ev_from_s(s, DEFAULT.gain_cents, DEFAULT.stop_cents)


def path_after(
    series: list[tuple[datetime, float, float, float]],
    after: datetime,
) -> list[tuple[datetime, float, float, float]]:
    return [row for row in series if row[0] > after]


def path_at_or_before(
    series: list[tuple[datetime, float, float, float]],
    when: datetime,
) -> list[tuple[datetime, float, float, float]]:
    return [row for row in series if row[0] <= when]


def outcome_after_snapshot(
    trade: dict[str, Any],
    *,
    snapshot_ts: datetime,
    favorite_post: list[tuple[datetime, float, float, float]],
    opponent_post: list[tuple[datetime, float, float, float]],
) -> dict[str, Any]:
    """Construct outcomes from events strictly after t.

    If t is already at/after T40, pnl_8040_after_t is NOT_APPLICABLE.
    pnl_hold_after_t still resolves at settlement.
    """
    prior = path_at_or_before(favorite_post, snapshot_ts)
    future = path_after(favorite_post, snapshot_ts)
    prices = [row[1] for row in future]
    entry = float(trade["entry_price_cents"])
    mfe = max([p - entry for p in prices], default=None)
    mae = max([entry - p for p in prices], default=None)
    hit = first_close_at_or_below(future, 40.0)
    hit_41 = first_close_at_or_below(future, 41.0)
    hit_42 = first_close_at_or_below(future, 42.0)
    t40_already = first_close_at_or_below(prior, 40.0) is not None
    won = bool(trade["w"])
    t40_after = hit is not None
    csv_t40 = bool(trade["t40"])
    hold = hold_pnl_cents(won=won)
    if t40_already:
        pnl_8040: int | None = None
        pnl_8040_status = NOT_APPLICABLE
    else:
        pnl_8040 = taker_8040_pnl_cents(won=won, hit_40=t40_after)
        pnl_8040_status = "VALUE"
    return {
        "settlement": "YES" if won else "NO",
        "won": won,
        "csv_t40": csv_t40,
        "t40_already": t40_already,
        "hit_40_after": t40_after,
        "hit_40_time": None if hit is None else hit[0].isoformat(),
        "first_price_le_40": None if hit is None else float(hit[1]),
        "hit_41_after": hit_41 is not None,
        "hit_42_after": hit_42 is not None,
        "max_favorable_excursion_after": None if mfe is None else float(max(0.0, mfe)),
        "max_adverse_excursion_after": None if mae is None else float(max(0.0, mae)),
        "pnl_hold_after_t": hold,
        "pnl_8040_after_t": pnl_8040,
        "pnl_8040_after_t_status": pnl_8040_status,
        "final_pnl_hold_cents": hold,
        "final_pnl_taker_8040_cents": taker_8040_pnl_cents(won=won, hit_40=csv_t40),
        "ev_definition_hold": HOLD_EV_DEFINITION,
        "ev_definition_8040": CHOOSIN_8040_AFTER_T,
        "hedge_fill_status": DEFAULT.fill_status,
        "hedge_fill_observed": False,
        "opponent_40_close_after": first_close_at_or_above(path_after(opponent_post, snapshot_ts), 40.0) is not None,
        "opponent_40_wick_after": first_high_at_or_above(path_after(opponent_post, snapshot_ts), 40.0) is not None,
        "candle_path_not_fill": True,
    }
