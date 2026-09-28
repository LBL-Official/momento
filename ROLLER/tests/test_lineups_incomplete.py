"""Lineups stay INCOMPLETE. Never fabricate a fifth player."""

from __future__ import annotations

from roller.state.lineup import lineup_state


def test_lineups_do_not_invent_opening_five():
    events = [
        {
            "available_at": "2025-12-20T20:01:00Z",
            "event_type": "substitution",
            "sub_type": "out",
            "person_id": "101",
            "team_tricode": "LAL",
        },
        {
            "available_at": "2025-12-20T20:01:01Z",
            "event_type": "substitution",
            "sub_type": "in",
            "person_id": "102",
            "team_tricode": "LAL",
        },
        {
            "available_at": "2025-12-20T20:02:00Z",
            "event_type": "substitution",
            "sub_type": "out",
            "person_id": "201",
            "team_tricode": "BOS",
        },
        {
            "available_at": "2025-12-20T20:02:01Z",
            "event_type": "substitution",
            "sub_type": "in",
            "person_id": "202",
            "team_tricode": "BOS",
        },
    ]
    out = lineup_state(events, sport="NBA", as_of="2025-12-20T20:03:00Z")
    assert out["status"] == "INCOMPLETE"
    on_court = out["data"]["on_court"]
    assert len(on_court) < 10
    for team_players in on_court.values():
        assert len(team_players) != 5 or "opening five unavailable" in str(out).lower()
    assert "fabricat" not in str(out).lower()


def test_future_substitution_is_hidden():
    events = [
        {
            "available_at": "2025-12-20T20:10:00Z",
            "event_type": "substitution",
            "sub_type": "in",
            "person_id": "999",
            "team_tricode": "LAL",
        }
    ]
    out = lineup_state(events, sport="NBA", as_of="2025-12-20T20:05:00Z")
    assert out["status"] == "INCOMPLETE"
    known = [p for players in (out["data"] or {}).get("on_court", {}).values() for p in players]
    assert "999" not in known
