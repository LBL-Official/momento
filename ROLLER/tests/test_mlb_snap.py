"""MLB PIT snap, YES batting, and inning slices."""

from datetime import datetime, timezone

from roller.mlb.snap import snap_mlb
from roller.mlb.state import slice_matches, yes_batting
from roller.research_query.entry_engine import TouchEvent, apply_period_clock, default_snap
from roller.research_query.models import ClockWindow, EntryCondition, PeriodWindow, TouchOrdinal

UTC = timezone.utc


def _ev(**kw):
    base = {
        "event_number": 1,
        "event_timestamp": "2026-06-18T23:10:00Z",
        "inning": 7,
        "half": "top",
        "outs": 2,
        "balls": 3,
        "strikes": 2,
        "runner_on_1": "0",
        "runner_on_2": "1",
        "runner_on_3": "0",
        "batting_team": "away",
        "home_score": 1,
        "away_score": 3,
    }
    base.update(kw)
    return base


def test_yes_batting_matrix():
    assert yes_batting(half="bottom", batting="home", team_side="home") is True
    assert yes_batting(half="top", batting="away", team_side="away") is True
    assert yes_batting(half="top", batting="away", team_side="home") is False
    assert yes_batting(half="bottom", batting="home", team_side="away") is False
    assert yes_batting(half=None, batting="home", team_side="home") is None


def test_snap_does_not_look_forward():
    events = [
        _ev(event_number=1, event_timestamp="2026-06-18T23:10:00Z", inning=6),
        _ev(event_number=2, event_timestamp="2026-06-18T23:20:00Z", inning=7),
    ]
    snap = snap_mlb(events, datetime(2026, 6, 18, 23, 12, tzinfo=UTC), team_side="away")
    assert snap["status"] == "REAL"
    assert snap["inning"] == 6
    assert snap["slice"] == "T6"


def test_missing_snap_unaligned():
    snap = snap_mlb([], datetime(2026, 6, 18, 23, 12, tzinfo=UTC))
    assert snap["status"] == "UNALIGNED"
    assert snap["exclusion_reason"] == "PIT_ALIGNMENT_FAILED"


def test_slices_t7_b7_i7():
    assert slice_matches("T7", "T7")
    assert slice_matches("B7", "B7")
    assert slice_matches("T7", "I7")
    assert slice_matches("B7", "I7")
    assert not slice_matches("T6", "I7")


def _touch(slice_name: str) -> TouchEvent:
    from roller.research_query.entry_engine import TradableBar

    bar = TradableBar(
        ts=datetime(2026, 6, 18, 23, 12, tzinfo=UTC),
        bid=8000,
        ask=None,
        volume=1,
        ticker="T",
        game_id="G",
        raw={},
    )
    return TouchEvent(
        ordinal=TouchOrdinal.FIRST_TOUCH,
        touch_index=1,
        price_e4=8000,
        bar=bar,
        snap={"status": "REAL", "slice": slice_name},
        alignment="aligned",
    )


def test_period_or_windows_mlb():
    cond = EntryCondition(
        id="e",
        ordinal=TouchOrdinal.FIRST_TOUCH,
        price_e4=8000,
        period_windows=(PeriodWindow(period="T7"), PeriodWindow(period="B7")),
    )
    assert apply_period_clock(_touch("T7"), cond, sport="MLB")
    assert apply_period_clock(_touch("B7"), cond, sport="MLB")
    assert not apply_period_clock(_touch("T6"), cond, sport="MLB")
    i7 = EntryCondition(id="e", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=8000, period="I7")
    assert apply_period_clock(_touch("T7"), i7, sport="MLB")
    clocked = EntryCondition(
        id="e",
        ordinal=TouchOrdinal.FIRST_TOUCH,
        price_e4=8000,
        period="T7",
        clock=ClockWindow(0, 60),
    )
    assert not apply_period_clock(_touch("T7"), clocked, sport="MLB")


def test_default_snap_routes_mlb():
    events = [_ev()]
    snap = default_snap(datetime(2026, 6, 18, 23, 12, tzinfo=UTC), events, "MLB")
    assert snap["slice"] == "T7"
    assert snap.get("outs") == 2
