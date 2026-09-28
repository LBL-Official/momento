"""Sport clocks, MM:SS parse, entry slices, and snap-at-timestamp."""

from __future__ import annotations

from datetime import datetime, timezone

from roller.state.clock import clock_remaining_seconds, elapsed_game_seconds, entry_slice
from roller.state.clock_snap import snap_events


def test_mmss_and_iso_clocks():
    assert clock_remaining_seconds("PT12M00.00S") == 720
    assert clock_remaining_seconds("10:00") == 600
    assert clock_remaining_seconds("6:32") == 6 * 60 + 32


def test_sport_elapsed_clocks():
    assert elapsed_game_seconds(1, "PT12M00S", sport="NBA") == 0
    assert elapsed_game_seconds(1, "PT10M00S", sport="WNBA") == 0
    assert elapsed_game_seconds(1, "PT20M00S", sport="NCAAB") == 0
    assert elapsed_game_seconds(2, "10:00", sport="WNBA") == 600
    assert elapsed_game_seconds(2, "10:00", sport="NCAAB") == 1200 + 600


def test_entry_slices_asked_six():
    assert entry_slice("NBA", 2, 400) == "Q2"
    assert entry_slice("WNBA", 3, 120) == "Q3"
    assert entry_slice("NCAAB", 1, 601) == "H1_1"
    assert entry_slice("NCAAB", 1, 600) == "H1_2"
    assert entry_slice("NCAAB", 2, 601) == "H2_1"
    assert entry_slice("NCAAB", 2, 600) == "H2_2"
    assert entry_slice("NBA", None, 100) == "UNALIGNED"
    assert entry_slice("NCAAB", 1, None) == "UNALIGNED"


def test_snap_last_event_at_or_before_timestamp():
    events = [
        {
            "event_number": 1,
            "event_timestamp": "2025-12-20T20:00:00Z",
            "available_at": "2025-12-20T20:00:00Z",
            "period": 2,
            "clock": "PT06M00.00S",
            "time_actual": "2025-12-20T20:00:00Z",
        },
        {
            "event_number": 2,
            "event_timestamp": "2025-12-20T20:13:02Z",
            "available_at": "2025-12-20T20:13:02Z",
            "period": 3,
            "clock": "PT06M32.00S",
            "time_actual": "2025-12-20T20:13:02Z",
        },
        {
            "event_number": 3,
            "event_timestamp": "2025-12-20T20:14:00Z",
            "available_at": "2025-12-20T20:14:00Z",
            "period": 3,
            "clock": "PT06M00.00S",
            "time_actual": "2025-12-20T20:14:00Z",
        },
    ]
    snap = snap_events(events, datetime(2025, 12, 20, 20, 13, 30, tzinfo=timezone.utc), sport="NBA")
    assert snap["status"] == "REAL"
    assert snap["slice"] == "Q3"
    assert int(snap["event_number"]) == 2


def test_event_timestamp_wins_when_event_time_disagrees():
    from roller.state.clock_snap import pbp_event_ts, snap_events

    events = [
        {
            "event_number": 1,
            "event_timestamp": "2025-12-20T20:00:00Z",
            "event_time": "2025-12-20T20:13:02Z",
            "available_at": "2025-12-20T20:00:00Z",
            "period": 2,
            "clock": "PT06M00.00S",
        },
        {
            "event_number": 2,
            "event_timestamp": "2025-12-20T20:13:02Z",
            "event_time": "2025-12-20T20:00:00Z",
            "available_at": "2025-12-20T20:13:02Z",
            "period": 3,
            "clock": "PT06M32.00S",
        },
    ]
    assert pbp_event_ts(events[0]) == datetime(2025, 12, 20, 20, 0, tzinfo=timezone.utc)
    snap = snap_events(events, datetime(2025, 12, 20, 20, 13, 30, tzinfo=timezone.utc), sport="NBA")
    assert int(snap["event_number"]) == 2
    assert snap["slice"] == "Q3"


def test_clock_snap_api_requires_as_of(roller_env):
    from pathlib import Path

    from roller import Roller
    from roller.config import RollerConfig
    from roller.maintenance.update import update_sport
    from roller.point_in_time.filters import AsOfRequiredError

    cfg = RollerConfig(Path(roller_env))
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    try:
        db.clock_snap("NBA_20251220_LAL_BOS", "2025-12-20T20:13:30Z")
        raise AssertionError("expected AsOfRequiredError")
    except AsOfRequiredError:
        pass
    snap = db.clock_snap(
        "NBA_20251220_LAL_BOS",
        "2025-12-20T20:13:30Z",
        as_of="2025-12-20T20:13:30Z",
    )
    assert snap["slice"] == "Q3"
