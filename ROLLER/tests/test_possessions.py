"""Possession rules. WNBA/NCAAB use ESPN grammar when team is present."""

from __future__ import annotations

from roller.state.possessions import reconstruct_possessions


def ev(**kwargs) -> dict:
    row = {
        "internal_game_id": "NBA_20251220_LAL_BOS",
        "event_number": 1,
        "event_time": "2025-12-20T20:00:00Z",
        "available_at": "2025-12-20T20:00:00Z",
        "event_type": "shot",
        "sub_type": "",
        "shot_result": "",
        "team_tricode": "LAL",
        "team_id": "",
        "possession": "",
        "home_score": 0,
        "away_score": 0,
        "event_description": "",
    }
    row.update(kwargs)
    return row


def test_made_field_goal_ends_confirmed():
    events = [
        ev(event_number=1, event_type="shot", shot_result="Made", team_tricode="LAL"),
        ev(event_number=2, event_type="shot", shot_result="Missed", team_tricode="BOS", event_time="2025-12-20T20:00:20Z", available_at="2025-12-20T20:00:20Z"),
    ]
    out = reconstruct_possessions(events, sport="NBA", home_team_id="BOS", away_team_id="LAL")
    assert out["status"] == "REAL"
    first = out["possessions"][0]
    assert first["end_reason"] == "MADE_FIELD_GOAL"
    assert first["end_status"] == "CONFIRMED"
    assert first["offensive_team_id"] == "LAL"


def test_and_one_free_throws_stay_on_same_possession():
    events = [
        ev(event_number=1, event_type="shot", shot_result="Made", team_tricode="LAL"),
        ev(event_number=2, event_type="freethrow", shot_result="Made", team_tricode="LAL", event_time="2025-12-20T20:00:05Z", available_at="2025-12-20T20:00:05Z"),
        ev(event_number=3, event_type="shot", shot_result="Missed", team_tricode="BOS", event_time="2025-12-20T20:00:25Z", available_at="2025-12-20T20:00:25Z"),
    ]
    out = reconstruct_possessions(events, sport="NBA", home_team_id="BOS", away_team_id="LAL")
    first = out["possessions"][0]
    assert first["start_event_number"] == 1
    assert first["end_event_number"] == 2
    assert first["end_reason"] == "MADE_FIELD_GOAL"


def test_defensive_rebound_ends_confirmed():
    events = [
        ev(event_number=1, event_type="shot", shot_result="Missed", team_tricode="LAL"),
        ev(event_number=2, event_type="rebound", sub_type="defensive", team_tricode="BOS", event_time="2025-12-20T20:00:08Z", available_at="2025-12-20T20:00:08Z"),
    ]
    out = reconstruct_possessions(events, sport="NBA", home_team_id="BOS", away_team_id="LAL")
    first = out["possessions"][0]
    assert first["end_reason"] == "DEFENSIVE_REBOUND"
    assert first["end_status"] == "CONFIRMED"
    assert first["offensive_team_id"] == "LAL"


def test_turnover_ends_confirmed():
    events = [
        ev(event_number=1, event_type="turnover", team_tricode="LAL"),
        ev(event_number=2, event_type="shot", team_tricode="BOS", event_time="2025-12-20T20:00:10Z", available_at="2025-12-20T20:00:10Z"),
    ]
    out = reconstruct_possessions(events, sport="NBA", home_team_id="BOS", away_team_id="LAL")
    assert out["possessions"][0]["end_reason"] == "TURNOVER"
    assert out["possessions"][0]["end_status"] == "CONFIRMED"


def test_steal_ends_confirmed():
    events = [
        ev(event_number=1, event_type="steal", team_tricode="BOS"),
        ev(event_number=2, event_type="shot", team_tricode="BOS", event_time="2025-12-20T20:00:10Z", available_at="2025-12-20T20:00:10Z"),
    ]
    out = reconstruct_possessions(events, sport="NBA", home_team_id="BOS", away_team_id="LAL")
    assert out["possessions"][0]["end_reason"] == "STEAL"
    assert out["possessions"][0]["end_status"] == "CONFIRMED"


def test_period_end_closes_open_possession():
    events = [
        ev(event_number=1, event_type="shot", shot_result="Missed", team_tricode="LAL"),
        ev(event_number=2, event_type="period", event_description="end", team_tricode="", event_time="2025-12-20T20:12:00Z", available_at="2025-12-20T20:12:00Z"),
    ]
    out = reconstruct_possessions(events, sport="NBA", home_team_id="BOS", away_team_id="LAL")
    assert out["possessions"][0]["end_reason"] == "PERIOD_END"
    assert out["possessions"][0]["end_status"] in {"CONFIRMED", "RECONSTRUCTED"}


def test_team_change_without_end_type_is_reconstructed():
    events = [
        ev(event_number=1, event_type="pass", team_tricode="LAL"),
        ev(event_number=2, event_type="pass", team_tricode="BOS", event_time="2025-12-20T20:00:12Z", available_at="2025-12-20T20:00:12Z"),
    ]
    out = reconstruct_possessions(events, sport="NBA", home_team_id="BOS", away_team_id="LAL")
    assert out["possessions"][0]["end_status"] == "RECONSTRUCTED"
    assert out["possessions"][0]["end_reason"] == "TEAM_CHANGE"


def test_conflicting_jumpball_is_ambiguous():
    events = [
        ev(event_number=1, event_type="jumpball", team_tricode="LAL", possession="BOS"),
    ]
    out = reconstruct_possessions(events, sport="NBA", home_team_id="BOS", away_team_id="LAL")
    assert out["possessions"]
    assert out["possessions"][0]["start_status"] == "AMBIGUOUS"


def test_no_team_is_unresolved():
    events = [
        ev(event_number=1, event_type="period", event_description="start", team_tricode="", possession=""),
    ]
    out = reconstruct_possessions(events, sport="NBA", home_team_id="BOS", away_team_id="LAL")
    assert out["possessions"][0]["start_status"] == "UNRESOLVED"


def test_wnba_espn_made_shot_ends_possession():
    events = [
        ev(event_number=1, event_type="Made Shot", team_tricode="NY", shot_result=""),
        ev(event_number=2, event_type="Made Shot", team_tricode="DAL", event_time="2025-12-20T20:00:20Z", available_at="2025-12-20T20:00:20Z"),
    ]
    out = reconstruct_possessions(events, sport="WNBA", home_team_id="DAL", away_team_id="NY")
    assert out["status"] in {"REAL", "PARTIAL"}
    assert out["possessions"][0]["end_reason"] == "MADE_FIELD_GOAL"
    assert out["possessions"][0]["sport"] == "WNBA"


def test_ncaab_defensive_rebound_type_text():
    events = [
        ev(event_number=1, event_type="Missed Shot", team_tricode="DUKE", shot_result=""),
        ev(
            event_number=2,
            event_type="Defensive Rebound",
            team_tricode="UNC",
            event_time="2025-12-20T20:00:08Z",
            available_at="2025-12-20T20:00:08Z",
        ),
    ]
    out = reconstruct_possessions(events, sport="NCAAB", home_team_id="UNC", away_team_id="DUKE")
    assert out["possessions"][0]["end_reason"] == "DEFENSIVE_REBOUND"


def test_start_and_end_status_may_differ():
    events = [
        ev(event_number=1, event_type="period", event_description="start", team_tricode="", possession=""),
        ev(event_number=2, event_type="shot", shot_result="Made", team_tricode="LAL", event_time="2025-12-20T20:00:20Z", available_at="2025-12-20T20:00:20Z"),
    ]
    out = reconstruct_possessions(events, sport="NBA", home_team_id="BOS", away_team_id="LAL")
    first = out["possessions"][0]
    assert first["start_status"] == "UNRESOLVED"
    assert first["end_status"] == "CONFIRMED"
    assert first["end_reason"] == "MADE_FIELD_GOAL"
