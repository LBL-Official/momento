"""Player in-game state is backward-only and uses personId when present."""

from __future__ import annotations

from roller.state.player import player_state


def test_player_points_ignore_future_events():
    events = [
        {
            "available_at": "2025-12-20T20:00:00Z",
            "person_id": "2544",
            "player_name": "James",
            "event_type": "shot",
            "sub_type": "3pt",
            "shot_result": "Made",
            "team_tricode": "LAL",
        },
        {
            "available_at": "2025-12-20T20:10:00Z",
            "person_id": "2544",
            "player_name": "James",
            "event_type": "shot",
            "sub_type": "2pt",
            "shot_result": "Made",
            "team_tricode": "LAL",
        },
    ]
    out = player_state(events, sport="NBA", as_of="2025-12-20T20:01:00Z")
    assert out["status"] == "REAL"
    james = out["data"]["players"]["2544"]
    assert james["points"] == 3
    assert james["made_fg"] == 1


def test_wnba_player_state_not_supported():
    out = player_state(
        [{"available_at": "2025-06-10T19:00:00Z", "event_type": "shot", "person_id": ""}],
        sport="WNBA",
        as_of="2025-06-10T20:00:00Z",
    )
    assert out["status"] == "NOT_SUPPORTED"
    assert out["data"] is None
