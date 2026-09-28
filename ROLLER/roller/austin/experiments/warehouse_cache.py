"""One NCAAB warehouse scan per discovery/grid run. Not a second warehouse."""

from __future__ import annotations

from typing import Any

from roller.austin.pbp_join import load_pbp
from roller.nba_8040_reverse_features.bars import load_ticker_bars


def load_trade_warehouse(trades: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = {str(t.get("ticker") or "") for t in trades if t.get("ticker")}
    gids = {str(t.get("internal_game_id") or "") for t in trades if t.get("internal_game_id")}
    bars: dict[str, list] = {}
    pbp: dict[str, list] = {}
    if tickers:
        bars = load_ticker_bars(tickers, sport="NCAAB")
    if gids:
        pbp = load_pbp(gids, sport="NCAAB")
    return {"bars": bars, "pbp": pbp}
