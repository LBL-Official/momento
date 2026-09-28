"""Favorite + opponent 1m TRADABLE_YES_BID paths. Candle path, not a fill."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from roller.austin.clock import parse_utc
from roller.austin.config import DEFAULT
from roller.austin.errors import AustinError
from roller.config import RollerConfig
from roller.nba_8040_reverse_features.bars import load_ticker_bars
from roller.warehouse.layout import markets_path


Bar = tuple[datetime, float, float, float]


def load_opponent_tickers(tickers: set[str]) -> dict[str, str]:
    cfg = RollerConfig()
    path = markets_path(cfg)
    if not path.is_file():
        raise AustinError("DATA_REQUIRED", f"missing {path}")
    frame = pd.read_parquet(path, columns=["ticker", "internal_game_id", "team_side"])
    frame["ticker"] = frame["ticker"].astype(str)
    wanted = frame[frame["ticker"].isin(tickers)]
    game_ids = {str(x) for x in wanted["internal_game_id"].tolist()}
    scoped = frame[frame["internal_game_id"].astype(str).isin(game_ids)]
    by_game: dict[str, dict[str, str]] = {}
    for rec in scoped.itertuples(index=False):
        by_game.setdefault(str(rec.internal_game_id), {})[str(rec.team_side)] = str(rec.ticker)
    opp: dict[str, str] = {}
    for rec in wanted.itertuples(index=False):
        sides = by_game.get(str(rec.internal_game_id)) or {}
        other = "away" if str(rec.team_side) == "home" else "home"
        peer = sides.get(other)
        if peer:
            opp[str(rec.ticker)] = peer
    return opp


def ticker_game_ids(tickers: set[str]) -> dict[str, str]:
    cfg = RollerConfig()
    path = markets_path(cfg)
    if not path.is_file():
        raise AustinError("DATA_REQUIRED", f"missing {path}")
    frame = pd.read_parquet(path, columns=["ticker", "internal_game_id"])
    out: dict[str, str] = {}
    for rec in frame.itertuples(index=False):
        ticker = str(rec.ticker)
        if ticker in tickers:
            out[ticker] = str(rec.internal_game_id)
    return out


def load_paths(trades: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = {str(row["ticker"]) for row in trades}
    opponents = load_opponent_tickers(tickers)
    games = ticker_game_ids(tickers)
    needed = set(tickers)
    needed.update(opponents.values())
    bars = load_ticker_bars(needed)
    return {
        "favorite": bars,
        "opponent_ticker": opponents,
        "internal_game_id": games,
        "l2_status": DEFAULT.l2_status,
    }


def split_post(series: list[Bar], entry: datetime) -> list[Bar]:
    return [row for row in series if row[0] > entry]


def first_close_at_or_below(series: list[Bar], cents: float) -> Bar | None:
    for row in series:
        if row[1] <= cents:
            return row
    return None


def first_close_at_or_above(series: list[Bar], cents: float) -> Bar | None:
    for row in series:
        if row[1] >= cents:
            return row
    return None


def first_high_at_or_above(series: list[Bar], cents: float) -> Bar | None:
    for row in series:
        if row[2] >= cents:
            return row
    return None


def parse_entry(trade: dict[str, Any]) -> datetime | None:
    return parse_utc(trade.get("entry_timestamp"))
