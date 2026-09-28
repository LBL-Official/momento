"""H2_1 clock-vs-wall alignment. Observes only. Does not repair timestamps."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.austin.clock import parse_utc
from roller.austin.experiments.persistence.events import primary_rows
from roller.austin.experiments.persistence.util import elapsed
from roller.austin.experiments.schedule import resolve_grid_timestamp
from roller.austin.reconstruct import last_bar_before
from roller.state.clock import elapsed_game_seconds


ALIGNED = "ALIGNED"
CLOCK_WALL_MISMATCH = "CLOCK_AFTER_ENTRY_BUT_WALL_BEFORE_ENTRY"
NO_NEARBY_PBP = "NO_NEARBY_PBP"
NO_NEARBY_BAR = "NO_NEARBY_BAR"
OTHER_MISMATCH = "OTHER_MISMATCH"


def _nearest_pbp(pbp: list[dict[str, Any]], period: int | None, remaining: int | None) -> dict[str, Any] | None:
    target = elapsed_game_seconds(period, remaining, sport="NCAAB")
    if target is None or not pbp:
        return None
    best = None
    best_d = None
    for row in pbp:
        used = elapsed_game_seconds(row.get("period"), row.get("seconds_remaining"), sport="NCAAB")
        if used is None:
            continue
        delta = abs(used - target)
        if best_d is None or delta < best_d:
            best = row
            best_d = delta
    return best


def _seconds_delta(later: datetime | None, earlier: datetime | None) -> float | None:
    if later is None or earlier is None:
        return None
    return (later - earlier).total_seconds()


def classify_trade(
    trade: dict[str, Any],
    queries: list[dict[str, Any]],
    *,
    bars: list,
    pbp: list[dict[str, Any]],
) -> dict[str, Any]:
    entry_ts = parse_utc(trade.get("entry_timestamp"))
    entry_period = trade.get("period")
    entry_clock = trade.get("entry_seconds_remaining")
    nearest_pbp = _nearest_pbp(pbp, entry_period, entry_clock)
    nearest_bar = None if entry_ts is None else last_bar_before(bars, entry_ts)
    if nearest_bar is None and bars:
        nearest_bar = min(bars, key=lambda row: abs((row[0] - entry_ts).total_seconds()) if entry_ts is not None else 10**12)
    pbp_ts = None if nearest_pbp is None else nearest_pbp.get("ts")
    bar_ts = None if nearest_bar is None else nearest_bar[0]
    primary = primary_rows(queries, trade["trade_id"])
    entry_elapsed = elapsed(entry_period, entry_clock)
    first_after = None
    for row in primary:
        used = elapsed(row.get("period"), row.get("game_clock_remaining"))
        if entry_elapsed is None or used is None:
            continue
        if used >= entry_elapsed:
            first_after = row
            break
    wall = None if first_after is None else parse_utc(first_after.get("timestamp_utc"))
    n_pre80 = sum(1 for r in primary if r.get("query_mode") == "PRE_80")
    n_valid = sum(1 for r in primary if r.get("conditional_ev_cents") is not None)
    if not pbp:
        status = NO_NEARBY_PBP
    elif not bars:
        status = NO_NEARBY_BAR
    elif first_after is not None and wall is not None and entry_ts is not None and wall < entry_ts:
        status = CLOCK_WALL_MISMATCH
    elif first_after is not None and wall is not None and entry_ts is not None and wall >= entry_ts:
        status = ALIGNED
    else:
        status = OTHER_MISMATCH
    return {
        "trade_id": trade["trade_id"],
        "game_date": trade.get("game_date"),
        "asked_six_entry_timestamp": trade.get("entry_timestamp"),
        "entry_period": entry_period,
        "entry_clock": entry_clock,
        "nearest_canonical_PBP_timestamp": None if pbp_ts is None else pbp_ts.isoformat(),
        "nearest_valid_bar_timestamp": None if bar_ts is None else bar_ts.isoformat(),
        "pbp_minus_entry_seconds": _seconds_delta(pbp_ts, entry_ts),
        "bar_minus_entry_seconds": _seconds_delta(bar_ts, entry_ts),
        "first_PRIMARY_GRID_clock_after_entry_period": None if first_after is None else first_after.get("period"),
        "first_PRIMARY_GRID_clock_after_entry_remaining": None if first_after is None else first_after.get("game_clock_remaining"),
        "wall_timestamp_for_that_grid": None if wall is None else wall.isoformat(),
        "wall_minus_entry_seconds": _seconds_delta(wall, entry_ts),
        "N_primary_rows": len(primary),
        "N_pre80_primary_rows": n_pre80,
        "N_valid_rows": n_valid,
        "alignment_status": status,
        "entry_timestamp": trade.get("entry_timestamp"),
    }


def example_rows(
    trade: dict[str, Any],
    queries: list[dict[str, Any]],
    *,
    bars: list,
    pbp: list[dict[str, Any]],
) -> dict[str, Any]:
    base = classify_trade(trade, queries, bars=bars, pbp=pbp)
    period = base.get("first_PRIMARY_GRID_clock_after_entry_period")
    remaining = base.get("first_PRIMARY_GRID_clock_after_entry_remaining")
    pbp_wall = resolve_grid_timestamp(pbp, int(period), int(remaining)) if period is not None and remaining is not None else None
    bar_wall = None
    if pbp_wall is not None:
        chosen = last_bar_before(bars, pbp_wall)
        bar_wall = None if chosen is None else chosen[0]
    primary = primary_rows(queries, trade["trade_id"])
    first_after = next(
        (
            r
            for r in primary
            if r.get("period") == period and r.get("game_clock_remaining") == remaining
        ),
        None,
    )
    return {
        **base,
        "entry_game_clock": trade.get("entry_seconds_remaining"),
        "entry_wall_timestamp": trade.get("entry_timestamp"),
        "next_2min_checkpoint_period": period,
        "next_2min_checkpoint_remaining": remaining,
        "checkpoint_PBP_wall_timestamp": None if pbp_wall is None else pbp_wall.isoformat(),
        "checkpoint_bar_wall_timestamp": None if bar_wall is None else bar_wall.isoformat(),
        "PRE_80_or_valid": None if first_after is None else (first_after.get("query_mode") or first_after.get("availability_status")),
    }


def alignment_verdict(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"status": "INSUFFICIENT_TO_DETERMINE", "defect": False}
    n = len(rows)
    mismatch = sum(1 for r in rows if r["alignment_status"] == CLOCK_WALL_MISMATCH)
    aligned = sum(1 for r in rows if r["alignment_status"] == ALIGNED)
    missing = sum(1 for r in rows if r["alignment_status"] in {NO_NEARBY_PBP, NO_NEARBY_BAR})
    pbp_deltas = [r["pbp_minus_entry_seconds"] for r in rows if r.get("pbp_minus_entry_seconds") is not None]
    wall_deltas = [r["wall_minus_entry_seconds"] for r in rows if r.get("wall_minus_entry_seconds") is not None]
    median_pbp = None if not pbp_deltas else float(sorted(pbp_deltas)[len(pbp_deltas) // 2])
    median_wall = None if not wall_deltas else float(sorted(wall_deltas)[len(wall_deltas) // 2])
    if missing == n:
        status = "INSUFFICIENT_TO_DETERMINE"
        defect = False
    elif mismatch / n >= 0.5 and (median_pbp is None or median_pbp < 0 or (median_wall is not None and median_wall < 0)):
        status = "EXPECTED_FROM_CANONICAL_TIMING"
        defect = False
    elif aligned / n >= 0.8:
        status = "EXPECTED_FROM_CANONICAL_TIMING"
        defect = False
    else:
        status = "INSUFFICIENT_TO_DETERMINE"
        defect = False
    return {
        "status": status,
        "defect": defect,
        "potential_data_alignment_defect": False,
        "n_trades": n,
        "n_clock_wall_mismatch": mismatch,
        "n_aligned": aligned,
        "n_missing_source": missing,
        "median_pbp_minus_entry_seconds": median_pbp,
        "median_wall_minus_entry_seconds": median_wall,
        "note": "Alignment is observed, not repaired. A reconstruction change would require a new experiment version.",
    }


ALIGNMENT_FIELDS = [
    "trade_id",
    "game_date",
    "asked_six_entry_timestamp",
    "entry_period",
    "entry_clock",
    "nearest_canonical_PBP_timestamp",
    "nearest_valid_bar_timestamp",
    "pbp_minus_entry_seconds",
    "bar_minus_entry_seconds",
    "first_PRIMARY_GRID_clock_after_entry_period",
    "first_PRIMARY_GRID_clock_after_entry_remaining",
    "wall_timestamp_for_that_grid",
    "wall_minus_entry_seconds",
    "N_primary_rows",
    "N_pre80_primary_rows",
    "N_valid_rows",
    "alignment_status",
]

EXAMPLE_FIELDS = ALIGNMENT_FIELDS + [
    "entry_game_clock",
    "entry_wall_timestamp",
    "next_2min_checkpoint_period",
    "next_2min_checkpoint_remaining",
    "checkpoint_PBP_wall_timestamp",
    "checkpoint_bar_wall_timestamp",
    "PRE_80_or_valid",
]
