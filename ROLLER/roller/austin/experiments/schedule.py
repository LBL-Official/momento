"""Predetermined 2-minute game-clock grid. Slice is eligibility, not horizon."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.austin.clock import parse_utc
from roller.austin.pbp_join import load_pbp, state_at
from roller.austin.reconstruct import last_bar_before
from roller.nba_8040_reverse_features.bars import load_ticker_bars

REG_REMAINING = tuple(range(1200, -1, -120))
OT_REMAINING = (300, 180, 60)
DIAGNOSTIC_PRINTS = (80, 70, 60, 50, 42, 41, 40)


def _clock_tuple(period: int | None, remaining: int | None) -> tuple[int, int] | None:
    if period is None or remaining is None:
        return None
    return (int(period), int(remaining))


def _after_entry(point: tuple[int, int], entry: tuple[int, int]) -> bool:
    if point[0] != entry[0]:
        return point[0] > entry[0]
    return point[1] < entry[1]


def _on_grid(period: int, remaining: int) -> bool:
    if period <= 2:
        return remaining in REG_REMAINING
    return remaining in OT_REMAINING


def grid_points(*, max_period: int) -> list[tuple[int, int]]:
    points = [(1, rem) for rem in REG_REMAINING] + [(2, rem) for rem in REG_REMAINING]
    for period in range(3, max(3, max_period + 1)):
        points.extend((period, rem) for rem in OT_REMAINING)
    return points


def resolve_grid_timestamp(events: list[dict[str, Any]], period: int, remaining: int) -> datetime | None:
    exact = None
    fallback = None
    for row in events:
        if row.get("period") != period or row.get("seconds_remaining") is None:
            continue
        sec = int(row["seconds_remaining"])
        if sec == remaining:
            exact = row["ts"]
        elif fallback is None and sec >= remaining:
            fallback = row["ts"]
    return exact or fallback


def build_observation_grid(
    trade: dict[str, Any],
    *,
    bars: list[tuple] | None = None,
    pbp: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    ticker = trade["ticker"]
    gid = str(trade.get("internal_game_id") or "")
    if bars is None:
        bars = load_ticker_bars({ticker}, sport="NCAAB").get(ticker, [])
    if pbp is None:
        pbp = load_pbp({gid}, sport="NCAAB").get(gid, []) if gid else []
    max_period = 2
    for row in pbp:
        if row.get("period"):
            max_period = max(max_period, int(row["period"]))
    entry = _clock_tuple(trade.get("period"), trade.get("entry_seconds_remaining"))
    entry_ts = parse_utc(trade.get("entry_timestamp"))
    settle_ts = parse_utc(trade.get("last_tradable_timestamp"))
    rows: list[dict[str, Any]] = []
    for period, remaining in grid_points(max_period=max_period):
        when = resolve_grid_timestamp(pbp, period, remaining)
        skip = None
        role = "PRIMARY_GRID"
        if entry is not None and not _after_entry((period, remaining), entry):
            if entry == (period, remaining) and _on_grid(period, remaining):
                role = "PRIMARY_GRID"
            else:
                skip = "PRE_ENTRY"
                role = "PRE_ENTRY"
        if when is None:
            skip = skip or "NO_PBP"
        if settle_ts is not None and when is not None and when > settle_ts:
            skip = "AFTER_SETTLEMENT"
            role = "AFTER_SETTLEMENT"
        pbp_row = None if when is None else state_at(pbp, when)
        price = None if when is None else last_bar_before(bars, when)
        rows.append(
            {
                "trade_id": trade["trade_id"],
                "internal_game_id": gid,
                "ticker": ticker,
                "period": period,
                "game_clock_remaining": remaining,
                "timestamp_utc": None if when is None else when.isoformat(),
                "role": role if skip is None else skip,
                "skip_reason": skip,
                "primary": skip is None and role == "PRIMARY_GRID",
                "on_grid": True,
                "current_price_cents": None if price is None else int(round(price[1])),
                "home_score": None if pbp_row is None else pbp_row.get("home_score"),
                "away_score": None if pbp_row is None else pbp_row.get("away_score"),
                "entry_equals_grid": entry == (period, remaining),
            }
        )
    for label in DIAGNOSTIC_PRINTS:
        live = [row for row in bars if row[1] > 0]
        if entry_ts is None:
            continue
        pool = [row for row in live if row[0] >= entry_ts] if label != 80 else live
        pred = (lambda c, c0=label: c >= c0) if label == 80 else (lambda c, c0=label: c <= c0)
        hit = next((row for row in pool if pred(row[1])), None)
        if hit is None:
            continue
        pbp_row = state_at(pbp, hit[0])
        period = None if pbp_row is None else pbp_row.get("period")
        remaining = None if pbp_row is None else pbp_row.get("seconds_remaining")
        rows.append(
            {
                "trade_id": trade["trade_id"],
                "internal_game_id": gid,
                "ticker": ticker,
                "period": period,
                "game_clock_remaining": remaining,
                "timestamp_utc": hit[0].isoformat(),
                "role": "DIAGNOSTIC_EVENT",
                "skip_reason": None,
                "primary": False,
                "on_grid": bool(period is not None and remaining is not None and _on_grid(int(period), int(remaining))),
                "diagnostic_print": label,
                "current_price_cents": int(round(hit[1])),
                "home_score": None if pbp_row is None else pbp_row.get("home_score"),
                "away_score": None if pbp_row is None else pbp_row.get("away_score"),
                "entry_equals_grid": False,
            }
        )
    return rows


def primary_rows(grid: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in grid if row.get("primary")]
