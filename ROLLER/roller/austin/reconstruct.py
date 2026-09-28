"""Reconstruct a QueryState from warehouse game + timestamp / clock.

Price: last 1m TRADABLE_YES_BID with available_at < t.
Score/clock: last PBP with event_timestamp <= t.
PBP_SEQUENCE_NOT_PIT. Candle path ≠ fill.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.austin.bars_join import load_opponent_tickers, ticker_game_ids
from roller.austin.clock import parse_utc, period_to_quarter
from roller.austin.config import DEFAULT
from roller.austin.errors import AustinError
from roller.austin.games import asked_six_entries, get_game, locked_tickers
from roller.austin.instances import load_trades
from roller.austin.pbp_join import load_pbp, state_at
from roller.austin.raw_state import PathPoint, RawState
from roller.nba_8040_reverse_features.bars import load_ticker_bars

Bar = tuple[datetime, float, float, float]


def _int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def last_bar_before(series: list[Bar], when: datetime) -> Bar | None:
    chosen: Bar | None = None
    for row in series:
        if row[0] < when:
            if row[1] > 0:
                chosen = row
        else:
            break
    return chosen


def first_close_ge(series: list[Bar], cents: float) -> Bar | None:
    for row in series:
        if row[1] >= cents:
            return row
    return None


def first_close_le(series: list[Bar], cents: float) -> Bar | None:
    for row in series:
        if row[1] <= cents:
            return row
    return None


def _trade_for_ticker(ticker: str) -> dict[str, Any] | None:
    for row in load_trades():
        if row["ticker"] == ticker:
            return row
    return None


def resolve_entry(
    ticker: str,
    bars: list[Bar],
    when: datetime,
) -> dict[str, Any]:
    locked = _trade_for_ticker(ticker)
    if locked is not None:
        entry_ts = parse_utc(locked["entry_timestamp"])
        if entry_ts is not None and entry_ts <= when:
            return {
                "entry_source": "CHOOSIN_604_CSV",
                "entry_ts": entry_ts,
                "entry_price_cents": int(locked["entry_price_cents"]),
                "home_score_entry": locked.get("home_score_entry"),
                "away_score_entry": locked.get("away_score_entry"),
                "entry_quarter": locked.get("quarter"),
                "entry_seconds_remaining": _int(locked.get("entry_seconds_remaining")),
                "trade_id": locked["trade_id"],
                "event_id": locked.get("event_id"),
                "side": locked["entry_side"],
            }
    asked = asked_six_entries().get(ticker)
    if asked:
        entry_ts = parse_utc(asked.get("entry_timestamp"))
        price = _int(asked.get("entry_price_cents"))
        if entry_ts is not None and entry_ts <= when and price is not None:
            return {
                "entry_source": "ASKED_SIX_FIRST80",
                "entry_ts": entry_ts,
                "entry_price_cents": price,
                "home_score_entry": _int(asked.get("home_score_entry")),
                "away_score_entry": _int(asked.get("away_score_entry")),
                "entry_quarter": period_to_quarter(asked.get("quarter")),
                "entry_seconds_remaining": _int(asked.get("entry_seconds_remaining")),
                "trade_id": None,
                "event_id": asked.get("event_id"),
                "side": asked.get("side") or None,
            }
    hit = first_close_ge([row for row in bars if row[0] < when], 80.0)
    if hit is not None:
        return {
            "entry_source": "WAREHOUSE_FIRST_GE_80",
            "entry_ts": hit[0],
            "entry_price_cents": int(round(hit[1])),
            "home_score_entry": None,
            "away_score_entry": None,
            "entry_quarter": None,
            "entry_seconds_remaining": None,
            "trade_id": None,
            "event_id": None,
            "side": None,
        }
    return {
        "entry_source": "NONE",
        "entry_ts": None,
        "entry_price_cents": None,
        "home_score_entry": None,
        "away_score_entry": None,
        "entry_quarter": None,
        "entry_seconds_remaining": None,
        "trade_id": None,
        "event_id": None,
        "side": None,
    }


def resolve_timestamp(
    events: list[dict[str, Any]],
    *,
    timestamp_utc: str | None,
    quarter: int | None,
    seconds_remaining: int | None,
) -> datetime:
    if timestamp_utc:
        stamp = parse_utc(timestamp_utc)
        if stamp is None:
            raise AustinError("QUERY_REJECTED", f"bad timestamp_utc {timestamp_utc!r}")
        return stamp
    if quarter is None or seconds_remaining is None:
        raise AustinError("QUERY_REJECTED", "need timestamp_utc or quarter + seconds_remaining")
    chosen: datetime | None = None
    for row in events:
        if row.get("period") == int(quarter) and row.get("seconds_remaining") == int(seconds_remaining):
            chosen = row["ts"]
        elif chosen is None and row.get("period") == int(quarter) and row.get("seconds_remaining") is not None:
            if int(row["seconds_remaining"]) >= int(seconds_remaining):
                chosen = row["ts"]
    if chosen is None:
        raise AustinError("DATA_REQUIRED", f"no PBP row for Q{quarter} {seconds_remaining}s")
    return chosen


def build_historical_query_state(
    *,
    game_id: str,
    side: str,
    timestamp_utc: str | None = None,
    quarter: int | None = None,
    seconds_remaining: int | None = None,
    query_mode: str | None = None,
) -> dict[str, Any]:
    game = get_game(game_id)
    side_n = str(side or "").strip().lower()
    if side_n not in {"home", "away"}:
        raise AustinError("QUERY_REJECTED", "side must be home|away")
    ticker = game.get("home_ticker") if side_n == "home" else game.get("away_ticker")
    if not ticker:
        raise AustinError("DATA_REQUIRED", f"no {side_n} ticker for {game['internal_game_id']}")
    gid = game["internal_game_id"]
    opp_map = load_opponent_tickers({ticker})
    games_map = ticker_game_ids({ticker})
    bars = load_ticker_bars({ticker})
    fav = bars.get(ticker, [])
    pbp = load_pbp({gid}).get(gid, [])
    when = resolve_timestamp(pbp, timestamp_utc=timestamp_utc, quarter=quarter, seconds_remaining=seconds_remaining)
    # refuse future: only bars < t and pbp <= t
    price_bar = last_bar_before(fav, when)
    pbp_row = state_at(pbp, when)
    entry = resolve_entry(ticker, fav, when)
    if entry.get("side") in {"home", "away"} and entry["side"] != side_n:
        # asked-six may lock the other side; keep requested side, keep that ticker's entry if it is this ticker
        pass
    mode = str(query_mode or "").strip().upper().replace("-", "_")
    if mode not in {"PRE_80", "INTRA_80", "POST_80"}:
        mode = "PRE_80" if entry["entry_source"] == "NONE" else "POST_80"
    if mode != "PRE_80" and entry["entry_source"] == "NONE":
        mode = "PRE_80"
    availability: dict[str, str] = {
        "current_price": "VALUE" if price_bar is not None else "UNAVAILABLE",
        "score": "VALUE" if pbp_row is not None else "UNAVAILABLE",
        "pbp": DEFAULT.pbp_status,
        "l2": DEFAULT.l2_status,
        "fill": DEFAULT.fill_status,
        "entry": "VALUE" if entry["entry_source"] != "NONE" else "NOT_APPLICABLE",
    }
    path_to_t: list[PathPoint] = []
    entry_ts = entry.get("entry_ts")
    if entry_ts is not None and entry["entry_price_cents"] is not None and mode != "PRE_80":
        path_to_t.append(
            PathPoint(
                t_sec=0,
                price_cents=int(entry["entry_price_cents"]),
                home_score=entry.get("home_score_entry"),
                away_score=entry.get("away_score_entry"),
            )
        )
        for row in fav:
            if row[0] <= entry_ts:
                continue
            if row[0] >= when:
                break
            pbp_at = state_at(pbp, row[0])
            path_to_t.append(
                PathPoint(
                    t_sec=max(0, int((row[0] - entry_ts).total_seconds())),
                    price_cents=int(round(row[1])),
                    home_score=None if pbp_at is None else pbp_at.get("home_score"),
                    away_score=None if pbp_at is None else pbp_at.get("away_score"),
                )
            )
    wall = None
    if entry_ts is not None and mode != "PRE_80":
        wall = max(0, int((when - entry_ts).total_seconds()))
    raw = RawState(
        is_query=True,
        trade_id=entry.get("trade_id") if ticker in locked_tickers() else None,
        side=side_n,
        entry_price_cents=None if mode == "PRE_80" else entry.get("entry_price_cents"),
        current_price_cents=None if price_bar is None else int(round(price_bar[1])),
        home_score_entry=None if mode == "PRE_80" else entry.get("home_score_entry"),
        away_score_entry=None if mode == "PRE_80" else entry.get("away_score_entry"),
        home_score_current=None if pbp_row is None else pbp_row.get("home_score"),
        away_score_current=None if pbp_row is None else pbp_row.get("away_score"),
        entry_quarter=None if mode == "PRE_80" else entry.get("entry_quarter"),
        current_quarter=None if pbp_row is None else pbp_row.get("period"),
        entry_seconds_remaining=None if mode == "PRE_80" else entry.get("entry_seconds_remaining"),
        current_seconds_remaining=None if pbp_row is None else pbp_row.get("seconds_remaining"),
        time_since_entry_sec=None if mode == "PRE_80" else wall,
        lookbacks=[],
        path_to_t=path_to_t,
        snapshot_kind="historical_reconstruct",
        availability_timestamp=when.isoformat(),
        query_mode=mode,
        query_source="HISTORICAL_RECONSTRUCT",
        entry_source="NONE" if mode == "PRE_80" else str(entry["entry_source"]),
        internal_game_id=gid,
        ticker=ticker,
        event_id=entry.get("event_id") or game.get("event_ticker"),
        snapshot_id=None,
    )
    status = "QUERY_PARTIAL" if price_bar is None or pbp_row is None else "OBSERVED"
    marks = {
        "first_80": None if first_close_ge(fav, 80) is None else first_close_ge(fav, 80)[0].isoformat(),
        "first_42": None if first_close_le(fav, 42) is None else first_close_le(fav, 42)[0].isoformat(),
        "first_41": None if first_close_le(fav, 41) is None else first_close_le(fav, 41)[0].isoformat(),
        "first_40": None if first_close_le(fav, 40) is None else first_close_le(fav, 40)[0].isoformat(),
    }
    return {
        "status": status,
        "game": game,
        "ticker": ticker,
        "opponent_ticker": opp_map.get(ticker),
        "internal_game_id": gid,
        "warehouse_game_id": games_map.get(ticker),
        "query_timestamp": when.isoformat(),
        "query_mode": mode,
        "entry_source": raw.entry_source,
        "in_austin_604": bool(game.get("in_austin_604")),
        "availability": availability,
        "pbp_status": DEFAULT.pbp_status,
        "l2_status": DEFAULT.l2_status,
        "fill_status": DEFAULT.fill_status,
        "candle_path_not_fill": True,
        "marks": marks,
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
    first80 = first_close_ge(live, 80.0)
    after80 = live if first80 is None else [row for row in live if row[0] >= first80[0]]
    marks = []
    for label, pred in (
        ("80", lambda c: c >= 80),
        ("70", lambda c: c <= 70),
        ("60", lambda c: c <= 60),
        ("50", lambda c: c <= 50),
        ("42", lambda c: c <= 42),
        ("41", lambda c: c <= 41),
        ("40", lambda c: c <= 40),
    ):
        pool = live if label == "80" else after80
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
    return {
        "status": "OBSERVED",
        "game": game,
        "ticker": ticker,
        "side": side_n,
        "n_bars": len(bars),
        "n_pbp": len(pbp),
        "first_available_at": None if not bars else bars[0][0].isoformat(),
        "last_available_at": None if not bars else bars[-1][0].isoformat(),
        "marks": marks,
        "pbp_status": DEFAULT.pbp_status,
        "in_austin_604": bool(game.get("in_austin_604")),
        "note": "Moments are 1m candle closes. Candle path ≠ fill.",
    }
