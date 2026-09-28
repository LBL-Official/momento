"""Historical 78¢ query state from a warehouse game. Candle path is not a fill."""

from __future__ import annotations

from typing import Any

from roller.austin.bars_join import load_opponent_tickers, ticker_game_ids
from roller.austin.clock import parse_utc
from roller.austin.errors import AustinError
from roller.austin.games import get_game
from roller.austin.pbp_join import load_pbp, state_at
from roller.austin.raw_state import RawState
from roller.austin.reconstruct import first_close_ge, first_close_le, last_bar_before
from roller.austin_first78.config import ENTRY_CENTS, STOP_CENTS
from roller.austin_first78.store import load_trades_frame
from roller.nba_8040_reverse_features.bars import load_ticker_bars


def _trade(ticker: str) -> dict[str, Any] | None:
    frame = load_trades_frame()
    hit = frame[frame["ticker"].astype(str) == str(ticker)]
    if hit.empty:
        return None
    return hit.iloc[0].to_dict()


def build_historical_query_state(
    *,
    game_id: str,
    side: str,
    timestamp_utc: str | None = None,
    quarter: object = None,
    seconds_remaining: object = None,
    query_mode: str | None = None,
) -> dict[str, Any]:
    game = get_game(game_id)
    side_n = str(side or "home").strip().lower()
    ticker = game.get("home_ticker") if side_n == "home" else game.get("away_ticker")
    if not ticker:
        raise AustinError("DATA_REQUIRED", f"no {side_n} ticker")
    bars = load_ticker_bars({ticker}).get(ticker, [])
    when = parse_utc(timestamp_utc) if timestamp_utc else (bars[-1][0] if bars else None)
    if when is None:
        raise AustinError("DATA_REQUIRED", "no timestamp and no bars")
    trained = _trade(ticker)
    entry_ts = None
    entry_price = None
    trade_id = None
    source = "NONE"
    if trained is not None:
        entry_ts = parse_utc(trained.get("entry_timestamp"))
        entry_price = int(trained["entry_price_cents"])
        trade_id = str(trained["trade_id"])
        source = "DERIVED_FOUR_FIRST78"
    else:
        hit = first_close_ge([row for row in bars if row[0] < when], float(ENTRY_CENTS))
        if hit is not None:
            entry_ts = hit[0]
            entry_price = int(round(hit[1]))
            source = "WAREHOUSE_FIRST_GE_78"
    explicit = str(query_mode or "").upper().replace("-", "_")
    before = entry_ts is None or entry_ts > when
    if explicit in {"PRE_78", "PRE_80"} or before:
        mode = "PRE_80"
        entry_price = None
        entry_ts = None
    else:
        mode = "POST_80"
    price_bar = last_bar_before(bars, when)
    gid = game["internal_game_id"]
    pbp = load_pbp({gid}).get(gid, [])
    pbp_row = state_at(pbp, when)
    entry_pbp = None if entry_ts is None else state_at(pbp, entry_ts)
    raw = RawState(
        is_query=True,
        trade_id=trade_id,
        side=side_n,
        entry_price_cents=entry_price,
        current_price_cents=None if price_bar is None else int(round(price_bar[1])),
        home_score_entry=None if entry_pbp is None else entry_pbp.get("home_score"),
        away_score_entry=None if entry_pbp is None else entry_pbp.get("away_score"),
        home_score_current=None if pbp_row is None else pbp_row.get("home_score"),
        away_score_current=None if pbp_row is None else pbp_row.get("away_score"),
        entry_quarter=None if entry_pbp is None else entry_pbp.get("period"),
        current_quarter=None if pbp_row is None else pbp_row.get("period"),
        entry_seconds_remaining=None if entry_pbp is None else entry_pbp.get("seconds_remaining"),
        current_seconds_remaining=None if pbp_row is None else pbp_row.get("seconds_remaining"),
        time_since_entry_sec=None if entry_ts is None else max(0, int((when - entry_ts).total_seconds())),
        query_mode=mode,
        query_source="HISTORICAL_RECONSTRUCT",
        entry_source="NONE",
        internal_game_id=gid,
        ticker=ticker,
    )
    if quarter is not None:
        try:
            raw.current_quarter = int(quarter)
        except (TypeError, ValueError):
            pass
    if seconds_remaining is not None:
        try:
            raw.current_seconds_remaining = int(seconds_remaining)
        except (TypeError, ValueError):
            pass
    marks = {
        "first_78": None if first_close_ge(bars, 78) is None else first_close_ge(bars, 78)[0].isoformat(),
        "first_69": None if first_close_le(bars, 69) is None else first_close_le(bars, 69)[0].isoformat(),
        "first_68": None if first_close_le(bars, 68) is None else first_close_le(bars, 68)[0].isoformat(),
        "first_67": None if first_close_le(bars, 67) is None else first_close_le(bars, 67)[0].isoformat(),
    }
    return {
        "status": "OBSERVED" if price_bar is not None else "QUERY_PARTIAL",
        "game": game,
        "ticker": ticker,
        "internal_game_id": gid,
        "query_timestamp": when.isoformat(),
        "query_mode": "PRE_78" if mode == "PRE_80" else "POST_78",
        "entry_source": source if mode != "PRE_80" else "NONE",
        "in_austin_78": trained is not None,
        "marks": marks,
        "pbp_status": "PBP_SEQUENCE_NOT_PIT",
        "l2_status": "SOURCE_UNAVAILABLE",
        "fill_status": "FILL_UNAVAILABLE",
        "candle_path_not_fill": True,
        "raw": raw,
    }


def list_moments(game_id: str, *, side: str = "home") -> dict[str, Any]:
    game = get_game(game_id)
    side_n = str(side or "home").strip().lower()
    ticker = game.get("home_ticker") if side_n == "home" else game.get("away_ticker")
    if not ticker:
        raise AustinError("DATA_REQUIRED", f"no {side_n} ticker")
    bars = load_ticker_bars({ticker}).get(ticker, [])
    gid = game["internal_game_id"]
    pbp = load_pbp({gid}).get(gid, [])
    live = [row for row in bars if row[1] > 0]
    first = first_close_ge(live, float(ENTRY_CENTS))
    after = live if first is None else [row for row in live if row[0] >= first[0]]
    marks = []
    for label, pred, pool in (
        ("78", lambda c: c >= ENTRY_CENTS, live),
        ("75", lambda c: c <= 75, after),
        ("72", lambda c: c <= 72, after),
        ("69", lambda c: c <= 69, after),
        ("68", lambda c: c <= 68, after),
        (str(STOP_CENTS), lambda c: c <= STOP_CENTS, after),
    ):
        hit = next((row for row in pool if pred(row[1])), None)
        if hit is None:
            continue
        pbp_row = state_at(pbp, hit[0])
        marks.append(
            {
                "label": label,
                "timestamp_utc": hit[0].isoformat(),
                "price_cents": int(round(hit[1])),
                "quarter": None if pbp_row is None else pbp_row.get("period"),
                "seconds_remaining": None if pbp_row is None else pbp_row.get("seconds_remaining"),
            }
        )
    trained = _trade(str(ticker))
    return {
        "status": "OBSERVED",
        "game": game,
        "ticker": ticker,
        "side": side_n,
        "marks": marks,
        "in_austin_78": trained is not None,
        "note": "Moments are 1m candle closes around the 78 entry and the 67 stop. Candle path ≠ fill.",
    }


def replay_trade(trade: dict[str, Any]) -> dict[str, Any]:
    from roller.austin.bars_join import first_close_at_or_below, parse_entry, split_post

    paths_tickers = {str(trade["ticker"])}
    opp = load_opponent_tickers(paths_tickers)
    games = ticker_game_ids(paths_tickers)
    bars = load_ticker_bars(set(paths_tickers) | set(opp.values())).get(str(trade["ticker"]), [])
    entry = parse_entry(trade)
    fav = [] if entry is None else split_post(bars, entry)
    gid = games.get(str(trade["ticker"]))
    events = load_pbp({gid}).get(gid, []) if gid else []
    path = []
    if entry is not None:
        path.append({"t": entry.isoformat(), "t_sec": 0, "price_cents": int(trade["entry_price_cents"]), "label": "ENTRY"})
    for row in fav:
        pbp_row = state_at(events, row[0])
        path.append(
            {
                "t": row[0].isoformat(),
                "t_sec": int((row[0] - entry).total_seconds()) if entry is not None else None,
                "price_cents": int(round(row[1])),
                "home_score": None if pbp_row is None else pbp_row.get("home_score"),
                "away_score": None if pbp_row is None else pbp_row.get("away_score"),
                "label": "PATH",
            }
        )
    return {
        "trade_id": trade["trade_id"],
        "ticker": trade["ticker"],
        "game_date": trade["game_date"],
        "quarter": trade["quarter"],
        "entry_price_cents": int(trade["entry_price_cents"]),
        "settlement": "YES" if bool(trade["w"]) else "NO",
        "t67": bool(trade["t67"]),
        "candle_path_not_fill": True,
        "path": path,
        "marks": {
            "hit_69": None if first_close_at_or_below(fav, 69) is None else first_close_at_or_below(fav, 69)[0].isoformat(),
            "hit_68": None if first_close_at_or_below(fav, 68) is None else first_close_at_or_below(fav, 68)[0].isoformat(),
            "hit_67": None if first_close_at_or_below(fav, 67) is None else first_close_at_or_below(fav, 67)[0].isoformat(),
        },
        "hedge_fill_status": "FILL_UNAVAILABLE",
    }
