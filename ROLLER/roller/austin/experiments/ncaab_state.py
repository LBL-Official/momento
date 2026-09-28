"""NCAAB historical reconstruct using locked ASKED_SIX entry. No warehouse FIRST80."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from roller.austin.clock import parse_utc
from roller.austin.config import DEFAULT
from roller.austin.errors import AustinError
from roller.austin.experiments.ids import CLOCK_SPORT, ENTRY_SOURCE
from roller.austin.pbp_join import load_pbp, state_at
from roller.austin.raw_state import PathPoint, RawState
from roller.austin.reconstruct import last_bar_before, resolve_timestamp
from roller.nba_8040_reverse_features.bars import load_ticker_bars
from roller.state.clock import elapsed_game_seconds


def _ncaab_elapsed(period: int | None, remaining: int | None) -> int | None:
    if period is None or remaining is None:
        return None
    return elapsed_game_seconds(period, remaining, sport="NCAAB")


def time_since_entry_ncaab(
    *,
    entry_period: int | None,
    entry_remaining: int | None,
    current_period: int | None,
    current_remaining: int | None,
    wall: int | None,
) -> int | None:
    start = _ncaab_elapsed(entry_period, entry_remaining)
    now = _ncaab_elapsed(current_period, current_remaining)
    if start is not None and now is not None:
        return max(0, now - start)
    return wall


def build_ncaab_query_state(
    trade: dict[str, Any],
    *,
    timestamp_utc: str | None = None,
    period: int | None = None,
    seconds_remaining: int | None = None,
    query_mode: str | None = None,
    bars: list[tuple[datetime, float, float, float]] | None = None,
    pbp: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "")
    gid = str(trade.get("internal_game_id") or "")
    side = str(trade.get("side") or "home").strip().lower()
    if side not in {"home", "away"}:
        raise AustinError("QUERY_REJECTED", "side must be home|away")
    if bars is None:
        bars = load_ticker_bars({ticker}, sport="NCAAB").get(ticker, []) if ticker else []
    if pbp is None:
        pbp = load_pbp({gid}, sport="NCAAB").get(gid, []) if gid else []
    when = resolve_timestamp(pbp, timestamp_utc=timestamp_utc, quarter=period, seconds_remaining=seconds_remaining)
    price_bar = last_bar_before(bars, when)
    pbp_row = state_at(pbp, when)
    entry_ts = parse_utc(trade.get("entry_timestamp"))
    if entry_ts is None:
        raise AustinError("DATA_REQUIRED", f"locked entry timestamp missing for {trade.get('trade_id')}")
    if when < entry_ts:
        mode = "PRE_80"
    else:
        mode = str(query_mode or "POST_80").upper()
        if mode not in {"PRE_80", "INTRA_80", "POST_80"}:
            mode = "POST_80"
    if mode == "PRE_80":
        raw = RawState(
            is_query=True,
            trade_id=str(trade["trade_id"]),
            side=side,
            entry_price_cents=None,
            current_price_cents=None if price_bar is None else int(round(price_bar[1])),
            home_score_entry=None,
            away_score_entry=None,
            home_score_current=None if pbp_row is None else pbp_row.get("home_score"),
            away_score_current=None if pbp_row is None else pbp_row.get("away_score"),
            entry_quarter=None,
            current_quarter=None if pbp_row is None else pbp_row.get("period"),
            entry_seconds_remaining=None,
            current_seconds_remaining=None if pbp_row is None else pbp_row.get("seconds_remaining"),
            time_since_entry_sec=None,
            path_to_t=[],
            snapshot_kind="ncaab_reconstruct",
            availability_timestamp=when.isoformat(),
            query_mode="PRE_80",
            query_source="HISTORICAL_RECONSTRUCT",
            entry_source="NONE",
            internal_game_id=gid or None,
            ticker=ticker,
            event_id=str(trade.get("event_id") or ""),
            clock_sport=CLOCK_SPORT,
        )
        return {
            "status": "QUERY_PARTIAL" if price_bar is None or pbp_row is None else "OBSERVED",
            "raw": raw,
            "when": when,
            "bars": bars,
            "pbp": pbp,
        }

    wall = max(0, int((when - entry_ts).total_seconds()))
    t_sec = time_since_entry_ncaab(
        entry_period=trade.get("period"),
        entry_remaining=trade.get("entry_seconds_remaining"),
        current_period=None if pbp_row is None else pbp_row.get("period"),
        current_remaining=None if pbp_row is None else pbp_row.get("seconds_remaining"),
        wall=wall,
    )
    path: list[PathPoint] = [
        PathPoint(
            t_sec=0,
            price_cents=int(trade["entry_price_cents"] or 80),
            home_score=trade.get("home_score_entry"),
            away_score=trade.get("away_score_entry"),
        )
    ]
    for row in bars:
        if row[0] <= entry_ts or row[0] >= when:
            continue
        at = state_at(pbp, row[0])
        path.append(
            PathPoint(
                t_sec=max(0, int((row[0] - entry_ts).total_seconds())),
                price_cents=int(round(row[1])),
                home_score=None if at is None else at.get("home_score"),
                away_score=None if at is None else at.get("away_score"),
            )
        )
    raw = RawState(
        is_query=True,
        trade_id=str(trade["trade_id"]),
        side=side,
        entry_price_cents=int(trade["entry_price_cents"] or 80),
        current_price_cents=None if price_bar is None else int(round(price_bar[1])),
        home_score_entry=trade.get("home_score_entry"),
        away_score_entry=trade.get("away_score_entry"),
        home_score_current=None if pbp_row is None else pbp_row.get("home_score"),
        away_score_current=None if pbp_row is None else pbp_row.get("away_score"),
        entry_quarter=trade.get("period"),
        current_quarter=None if pbp_row is None else pbp_row.get("period"),
        entry_seconds_remaining=trade.get("entry_seconds_remaining"),
        current_seconds_remaining=None if pbp_row is None else pbp_row.get("seconds_remaining"),
        time_since_entry_sec=t_sec,
        path_to_t=path,
        snapshot_kind="ncaab_reconstruct",
        availability_timestamp=when.isoformat(),
        query_mode=mode,
        query_source="HISTORICAL_RECONSTRUCT",
        entry_source=ENTRY_SOURCE,
        internal_game_id=gid or None,
        ticker=ticker,
        event_id=str(trade.get("event_id") or ""),
        clock_sport=CLOCK_SPORT,
    )
    status = "QUERY_PARTIAL" if price_bar is None or pbp_row is None else "OBSERVED"
    return {
        "status": status,
        "raw": raw,
        "when": when,
        "bars": bars,
        "pbp": pbp,
        "pbp_status": DEFAULT.pbp_status,
        "fill_status": DEFAULT.fill_status,
        "l2_status": DEFAULT.l2_status,
        "entry_source": ENTRY_SOURCE,
    }


def mutate_future_and_rebuild(
    trade: dict[str, Any],
    *,
    timestamp_utc: str,
    future_price: float,
    bars: list[tuple[datetime, float, float, float]] | None = None,
    pbp: list[dict[str, Any]] | None = None,
) -> tuple[RawState, RawState]:
    """Leakage helper: mutate bars/PBP after t; reconstruct at t must be unchanged."""
    first = build_ncaab_query_state(trade, timestamp_utc=timestamp_utc, bars=bars, pbp=pbp)
    when: datetime = first["when"]
    source_bars = bars if bars is not None else list(first.get("bars") or [])
    source_pbp = pbp if pbp is not None else list(first.get("pbp") or [])
    mutated_bars = list(source_bars)
    mutated_bars.append((when + timedelta(minutes=2), float(future_price), float(future_price), float(future_price)))
    mutated_pbp = list(source_pbp)
    mutated_pbp.append(
        {
            "ts": when + timedelta(minutes=2),
            "period": 2,
            "seconds_remaining": 0,
            "home_score": 99,
            "away_score": 1,
        }
    )
    second = build_ncaab_query_state(
        trade,
        timestamp_utc=timestamp_utc,
        bars=mutated_bars,
        pbp=mutated_pbp,
    )
    return first["raw"], second["raw"]
