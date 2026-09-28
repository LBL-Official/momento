"""Entered chips must measure from I(t) PBP and the selected 1-minute basis.

Does not edit FIRST80. Does not invent L2. CANDLE ≠ FILL.
"""

from __future__ import annotations

from datetime import datetime, timezone

from roller.research_query.entry_engine import (
    default_snap,
    last_trade_sequence,
    nth_touch,
    observe_entry,
    order_pbp_events,
    tradable_sequence,
)
from roller.research_query.models import BASIS_LAST_TRADE, EntryCondition, TouchOrdinal

UTC = timezone.utc


def _ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _candle(minute: int, bid: int, *, last: int | None = None, ticker="T-HOME", game="G1"):
    row = {
        "available_at": f"2025-12-20T20:{minute:02d}:00Z",
        "candle_timestamp": f"2025-12-20T20:{minute:02d}:00Z",
        "event_timestamp": f"2025-12-20T20:{minute:02d}:00Z",
        "yes_bid_close": bid,
        "yes_ask_close": bid + 400,
        "volume": 10,
        "ticker": ticker,
        "internal_game_id": game,
        "is_valid": True,
        "team_side": "home",
    }
    if last is not None:
        row["last_close_e4"] = last
    return row


def _pbp(*, n: int, event_iso: str, avail_iso: str, period: int, clock: str = "08:00"):
    return {
        "internal_game_id": "G1",
        "event_number": n,
        "event_timestamp": event_iso,
        "event_time": event_iso,
        "available_at": avail_iso,
        "period": period,
        "clock": clock,
        "home_score": period * 10,
        "away_score": 0,
    }


def test_order_pbp_events_is_chronological():
    events = [
        _pbp(n=3, event_iso="2025-12-20T20:02:00Z", avail_iso="2025-12-20T20:02:00Z", period=1),
        _pbp(n=1, event_iso="2025-12-20T20:00:00Z", avail_iso="2025-12-20T20:00:00Z", period=1),
        _pbp(n=2, event_iso="2025-12-20T20:00:00Z", avail_iso="2025-12-20T20:00:00Z", period=1),
    ]
    ordered = order_pbp_events(events)
    assert [ev["event_number"] for ev in ordered] == [1, 2, 3]


def test_basketball_default_snap_excludes_available_at_equality():
    events = [
        _pbp(n=1, event_iso="2025-12-20T20:00:00Z", avail_iso="2025-12-20T20:00:00Z", period=2),
        _pbp(n=2, event_iso="2025-12-20T20:01:00Z", avail_iso="2025-12-20T20:01:00Z", period=3),
    ]
    snap = default_snap(_ts("2025-12-20T20:01:00Z"), events, "NBA")
    assert snap["status"] == "REAL"
    assert snap["slice"] == "Q2"
    assert int(snap["event_number"]) == 1


def test_basketball_default_snap_does_not_leak_delayed_available_at():
    """event_timestamp < t but available_at >= t must not classify the period."""
    events = [
        _pbp(n=1, event_iso="2025-12-20T20:00:00Z", avail_iso="2025-12-20T20:00:00Z", period=2),
        _pbp(n=2, event_iso="2025-12-20T20:00:50Z", avail_iso="2025-12-20T20:01:30Z", period=3),
    ]
    snap = default_snap(_ts("2025-12-20T20:01:00Z"), events, "NBA")
    assert snap["slice"] == "Q2"
    assert int(snap["event_number"]) == 1


def test_q3_first_touch_rejects_leaked_future_pbp():
    candles = [_candle(0, 7900), _candle(1, 8000)]
    leaked = [
        _pbp(n=1, event_iso="2025-12-20T20:00:00Z", avail_iso="2025-12-20T20:00:00Z", period=2),
        _pbp(n=2, event_iso="2025-12-20T20:00:50Z", avail_iso="2025-12-20T20:01:30Z", period=3),
    ]
    cond = EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000, period="Q3")
    ev, diag = nth_touch(candles, cond, sport="NBA", pbp_events=leaked)
    assert ev is None
    assert diag["reject_reason"] == "period_filter"


def test_q3_first_touch_accepts_visible_q3_pbp():
    candles = [_candle(0, 7900), _candle(1, 8000)]
    visible = [
        _pbp(n=1, event_iso="2025-12-20T20:00:00Z", avail_iso="2025-12-20T20:00:00Z", period=2),
        _pbp(n=2, event_iso="2025-12-20T20:00:50Z", avail_iso="2025-12-20T20:00:50Z", period=3),
    ]
    cond = EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000, period="Q3")
    ev, diag = nth_touch(candles, cond, sport="NBA", pbp_events=visible)
    assert ev is not None
    assert ev.snap["slice"] == "Q3"
    assert ev.bar.bid == 8000
    assert diag["reject_reason"] is None


def test_last_trade_reads_print_not_yes_bid():
    candles = [
        _candle(0, bid=8000, last=5900),
        _candle(1, bid=8100, last=6000),
        _candle(2, bid=4000, last=4000),
    ]
    tradable, _ = tradable_sequence(candles)
    prints, skipped = last_trade_sequence(candles)
    assert [b.bid for b in tradable] == [8000, 8100, 4000]
    assert [b.bid for b in prints] == [5900, 6000, 4000]
    assert skipped == 0
    cond = EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6000)
    ev, _ = observe_entry(candles, cond, sport="NBA", basis=BASIS_LAST_TRADE, pbp_events=[])
    assert ev is not None
    assert ev.bar.bid == 6000
    assert ev.bar.basis == BASIS_LAST_TRADE


def test_last_trade_does_not_fall_back_to_yes_bid():
    candles = [_candle(0, bid=7900), _candle(1, bid=8000), _candle(2, bid=4000)]
    prints, skipped = last_trade_sequence(candles)
    assert prints == []
    assert skipped == 3
    cond = EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000)
    ev, diag = observe_entry(candles, cond, sport="NBA", basis=BASIS_LAST_TRADE, pbp_events=[])
    assert ev is None
    assert diag["reject_reason"] in ("no_nth_touch", "untradable_only")


def test_mlb_default_snap_keeps_event_timestamp_equality():
    """MLB: event_timestamp <= snap is visible. Do not apply basketball available_at < t."""
    events = [
        {
            "internal_game_id": "G1",
            "event_number": 1,
            "event_timestamp": "2026-06-18T23:12:00Z",
            "event_time": "2026-06-18T23:12:00Z",
            "available_at": "2026-06-18T23:12:00Z",
            "inning": 7,
            "half": "top",
            "outs": 1,
            "balls": 0,
            "strikes": 0,
            "runner_on_1": "0",
            "runner_on_2": "0",
            "runner_on_3": "0",
            "batting_team": "away",
            "home_score": 1,
            "away_score": 3,
        }
    ]
    snap = default_snap(_ts("2026-06-18T23:12:00Z"), events, "MLB")
    assert snap["status"] == "REAL"
    assert snap["slice"] == "T7"


def test_read_snaps_orders_pbp_events(tmp_path):
    from roller.research_query.indexes.snaps import read_snaps, write_snaps

    write_snaps(
        tmp_path / "pbp_events.parquet",
        {
            "G1": [
                _pbp(n=3, event_iso="2025-12-20T20:02:00Z", avail_iso="2025-12-20T20:02:00Z", period=1),
                _pbp(n=1, event_iso="2025-12-20T20:00:00Z", avail_iso="2025-12-20T20:00:00Z", period=1),
                _pbp(n=2, event_iso="2025-12-20T20:00:00Z", avail_iso="2025-12-20T20:00:00Z", period=1),
            ]
        },
    )
    got = read_snaps(tmp_path / "pbp_events.parquet")
    assert [ev["event_number"] for ev in got["G1"]] == [1, 2, 3]


def test_warehouse_groups_then_sorts_pbp():
    import pandas as pd

    from roller.research_query.availability import LeagueScope
    from roller.research_query.execute import _load_one_scope
    from roller.research_query.models import ResearchQuestion, TerminalOutcome, Universe

    candles = pd.DataFrame(
        [
            {
                "ticker": "T-HOME",
                "internal_game_id": "G1",
                "available_at": "2025-12-20T20:00:00Z",
                "yes_bid_close": 7900,
                "is_valid": True,
            }
        ]
    )
    pbp = pd.DataFrame(
        [
            _pbp(n=3, event_iso="2025-12-20T20:02:00Z", avail_iso="2025-12-20T20:02:00Z", period=1),
            _pbp(n=1, event_iso="2025-12-20T20:00:00Z", avail_iso="2025-12-20T20:00:00Z", period=1),
            _pbp(n=2, event_iso="2025-12-20T20:00:00Z", avail_iso="2025-12-20T20:00:00Z", period=1),
        ]
    )
    q = ResearchQuestion(
        universe=Universe(
            sports=("basketball",),
            leagues=("NBA",),
            seasons=("2025-26",),
            markets=("kalshi",),
            market_data=("candles",),
        ),
        entry_conditions=(
            EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000),
        ),
        path_conditions=(),
        terminal=TerminalOutcome.BOTH,
    )
    _tickers, pbp_by, _markets, _games = _load_one_scope(
        None,
        q,
        LeagueScope(league="NBA", sport="NBA", season="2025-2026"),
        tables={"candles": candles, "pbp": pbp, "markets": None, "games": None},
    )
    assert [ev["event_number"] for ev in pbp_by["G1"]] == [1, 2, 3]
