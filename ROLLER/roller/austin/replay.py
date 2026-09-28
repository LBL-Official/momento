"""Candle-path replay for a historical trade. Not a fill tape."""

from __future__ import annotations

from typing import Any

from roller.austin.bars_join import first_close_at_or_below, parse_entry, split_post
from roller.austin.pbp_join import state_at


def replay_trade(
    trade: dict[str, Any],
    *,
    favorite_bars: list,
    opponent_bars: list,
    pbp_events: list[dict[str, Any]],
) -> dict[str, Any]:
    entry = parse_entry(trade)
    fav = [] if entry is None else split_post(favorite_bars, entry)
    opp = [] if entry is None else split_post(opponent_bars, entry)
    path = []
    if entry is not None:
        path.append(
            {
                "t": entry.isoformat(),
                "t_sec": 0,
                "price_cents": int(trade["entry_price_cents"]),
                "home_score": trade.get("home_score_entry"),
                "away_score": trade.get("away_score_entry"),
                "label": "ENTRY",
            }
        )
    for row in fav:
        pbp = state_at(pbp_events, row[0])
        path.append(
            {
                "t": row[0].isoformat(),
                "t_sec": None if entry is None else int((row[0] - entry).total_seconds()),
                "price_cents": int(round(row[1])),
                "home_score": None if pbp is None else pbp.get("home_score"),
                "away_score": None if pbp is None else pbp.get("away_score"),
                "label": "PATH",
            }
        )
    marks = {
        "hit_42": _mark(fav, 42),
        "hit_41": _mark(fav, 41),
        "hit_40": _mark(fav, 40),
        "opponent_40": None
        if not opp
        else next((row[0].isoformat() for row in opp if row[1] >= 40), None),
    }
    return {
        "trade_id": trade["trade_id"],
        "ticker": trade["ticker"],
        "game_date": trade["game_date"],
        "quarter": trade["quarter"],
        "entry_price_cents": trade["entry_price_cents"],
        "settlement": "YES" if trade["w"] else "NO",
        "csv_t40": bool(trade["t40"]),
        "candle_path_not_fill": True,
        "path": path,
        "marks": marks,
        "hedge_fill_status": "FILL_UNAVAILABLE",
    }


def _mark(series: list, cents: int) -> str | None:
    hit = first_close_at_or_below(series, float(cents))
    return None if hit is None else hit[0].isoformat()
