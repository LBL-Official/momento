"""Tennis PIT snap: asof-backward, no future leakage, sequence-only fail-closed."""

from datetime import datetime, timezone

from roller.research_query.entry_engine import apply_period_clock, default_snap
from roller.research_query.models import ClockWindow, EntryCondition, PeriodWindow, TouchOrdinal
from roller.tennis.snap import NO_POINT_DATA, choose_pit_row, pit_visible, snap_tennis
from roller.tennis.windows import window_matches

UTC = timezone.utc


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _point(ts: str | None, **kw):
    row = {
        "point_number": 1,
        "set_number": 1,
        "game_number": 3,
        "sets_p1": 0,
        "sets_p2": 0,
        "games_p1": 2,
        "games_p2": 1,
        "points_p1_raw": "30",
        "points_p2_raw": "15",
        "point_score_raw": "30-15",
        "server": 1,
        "receiver": 2,
        "is_tiebreak": False,
        "best_of": 3,
        "pbp_basis": "TIMESTAMPED_OBSERVED",
        "pit_joinable": True,
        "event_timestamp": ts,
    }
    row.update(kw)
    return row


def test_asof_equal_and_between():
    events = [
        _point("2026-06-18T12:00:00Z", point_number=1),
        _point("2026-06-18T12:02:00Z", point_number=2, points_p1_raw="40", point_score_raw="40-15"),
        _point("2026-06-18T12:05:00Z", point_number=3, points_p1_raw="AD", point_score_raw="AD-15"),
    ]
    exact = snap_tennis(events, _ts("2026-06-18T12:02:00Z"), yes_player=1)
    assert exact["status"] == "REAL"
    assert exact["point_number"] == 2
    assert exact["snapshot_age_seconds"] == 0
    between = snap_tennis(events, _ts("2026-06-18T12:03:30Z"), yes_player=1)
    assert between["point_number"] == 2
    assert between["snapshot_age_seconds"] == 90


def test_future_point_never_attached():
    events = [
        _point("2026-06-18T12:00:00Z", point_number=1),
        _point("2026-06-18T12:05:00Z", point_number=2, points_p1_raw="AD"),
    ]
    snap = snap_tennis(events, _ts("2026-06-18T12:01:00Z"), yes_player=1)
    assert snap["point_number"] == 1
    assert choose_pit_row(events, _ts("2026-06-18T12:01:00Z"))["point_number"] == 1
    assert all(ev["point_number"] == 1 for ev in pit_visible(events, _ts("2026-06-18T12:01:00Z")))


def test_before_first_point_is_no_point_data():
    events = [_point("2026-06-18T12:00:00Z")]
    snap = snap_tennis(events, _ts("2026-06-18T11:59:59Z"), yes_player=1)
    assert snap["status"] == NO_POINT_DATA
    assert snap["exclusion_reason"] == "NO_PRIOR_POINT"
    assert snap["pit_joinable"] is False


def test_sequence_only_cannot_become_pit():
    events = [
        _point(None, pbp_basis="SEQUENCE_ONLY", pit_joinable=False, event_timestamp=None),
        _point("2026-06-18T12:00:00Z", pbp_basis="SEQUENCE_ONLY", pit_joinable=False),
    ]
    snap = snap_tennis(events, _ts("2026-06-18T12:01:00Z"), yes_player=1)
    assert snap["status"] == NO_POINT_DATA
    assert snap["exclusion_reason"] == "SEQUENCE_ONLY"
    assert snap["point_snapshot_available"] is False


def test_sequence_row_ignored_when_timestamped_exists():
    events = [
        _point(None, pbp_basis="SEQUENCE_ONLY", pit_joinable=False, point_number=99),
        _point("2026-06-18T12:00:00Z", point_number=1),
    ]
    snap = snap_tennis(events, _ts("2026-06-18T12:01:00Z"), yes_player=1)
    assert snap["status"] == "REAL"
    assert snap["point_number"] == 1


def test_default_snap_routes_tennis():
    events = [_point("2026-06-18T12:00:00Z")]
    snap = default_snap(_ts("2026-06-18T12:01:00Z"), events, "ATP", team_side="1")
    assert snap["status"] == "REAL"
    assert snap["slice"] == "S1"
    assert snap["yes_serving"] is True


def test_snap_uses_player_indexed_score_not_server_first_pts():
    """P2 serving at 30-15 server-first is 15-30 player-indexed. Do not invert."""
    events = [
        _point(
            "2026-06-18T12:00:00Z",
            server=2,
            receiver=1,
            points_p1_raw="15",
            points_p2_raw="30",
            point_score_raw="30-15",
            source_tb_set=True,
            is_tiebreak=False,
        )
    ]
    snap = snap_tennis(events, _ts("2026-06-18T12:01:00Z"), yes_player=1)
    assert snap["status"] == "REAL"
    assert snap["yes_serving"] is False
    assert snap["yes_returning"] is True
    assert snap["yes_point_lead"] == -1
    assert snap["is_tiebreak"] is False
    assert snap.get("source_tb_set") is not True


def test_source_time_raw_never_becomes_a_timestamp():
    events = [
        _point(
            None,
            pbp_basis="SEQUENCE_ONLY",
            pit_joinable=False,
            event_timestamp=None,
            source_time_raw="11:10 AM",
        )
    ]
    snap = snap_tennis(events, _ts("2026-06-18T12:01:00Z"), yes_player=1)
    assert snap["status"] == NO_POINT_DATA
    assert snap["point_snapshot_ts"] is None


def test_set_and_game_windows():
    snap = {"set_number": 2, "game_number": 5, "status": "REAL", "slice": "S2"}
    assert window_matches(snap, "S2")
    assert not window_matches(snap, "S1")
    assert window_matches(snap, "G4-6")
    assert not window_matches(snap, "G1-3")
    assert not window_matches({"set_number": None, "game_number": None}, "S1")
    late = {"set_number": 3, "game_number": 12, "status": "REAL", "slice": "S3"}
    assert window_matches(late, "G10+")
    assert not window_matches(late, "G7-9")
    assert not window_matches({"set_number": 3, "game_number": 9}, "G10+")


def test_same_timestamp_uses_later_point_number():
    events = [
        _point("2026-06-18T12:00:00Z", point_number=4, points_p1_raw="30"),
        _point("2026-06-18T12:00:00Z", point_number=5, points_p1_raw="40", point_score_raw="40-15"),
    ]
    snap = snap_tennis(events, _ts("2026-06-18T12:00:00Z"), yes_player=1)
    assert snap["point_number"] == 5
    assert snap["points_p1_raw"] == "40"


def test_period_clock_s1_passes_and_clock_fails():
    from roller.research_query.entry_engine import TouchEvent, TradableBar
    from roller.research_query.models import EntryOp

    bar = TradableBar(
        ts=_ts("2026-06-18T12:01:00Z"),
        bid=8000,
        ask=8100,
        volume=10,
        ticker="KXATPMATCH-T-ZVE",
        game_id="TENNIS_G1",
        raw={},
        basis="TRADABLE_YES_BID",
    )
    ev = TouchEvent(
        ordinal=TouchOrdinal.FIRST_TOUCH,
        touch_index=1,
        price_e4=8000,
        bar=bar,
        snap={"status": "REAL", "slice": "S1", "set_number": 1, "game_number": 2},
        alignment="aligned",
        operation=EntryOp.FIRST_TOUCH,
    )
    cond = EntryCondition(
        id="e1",
        ordinal=TouchOrdinal.FIRST_TOUCH,
        price_e4=8000,
        period="S1",
    )
    assert apply_period_clock(ev, cond, sport="ATP") is True
    clocked = EntryCondition(
        id="e1",
        ordinal=TouchOrdinal.FIRST_TOUCH,
        price_e4=8000,
        period="S1",
        clock=ClockWindow(remaining_from_s=60, remaining_to_s=0),
    )
    assert apply_period_clock(ev, clocked, sport="ATP") is False
    other = EntryCondition(
        id="e1",
        ordinal=TouchOrdinal.FIRST_TOUCH,
        price_e4=8000,
        period_windows=(PeriodWindow(period="S3"),),
    )
    assert apply_period_clock(ev, other, sport="ATP") is False
