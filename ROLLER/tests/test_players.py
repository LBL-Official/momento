"""Player identity: pass-through personId, no silent merges."""

from __future__ import annotations

import pandas as pd

from roller.canonical.players import collect_player_rows
from roller.ingest.pbp import parse_nba_actions


def test_nba_person_fields_passthrough():
    actions = parse_nba_actions(
        {
            "game": {
                "actions": [
                    {
                        "actionNumber": 1,
                        "timeActual": "2025-12-20T20:13:02Z",
                        "period": 3,
                        "clock": "PT06M32.00S",
                        "scoreHome": "10",
                        "scoreAway": "8",
                        "actionType": "shot",
                        "description": "make",
                        "teamTricode": "LAL",
                        "possession": 1610612747,
                        "personId": 2544,
                        "subType": "jumpshot",
                        "shotResult": "Made",
                        "teamId": 1610612747,
                        "playerName": "James",
                    }
                ]
            }
        }
    )
    assert actions[0]["person_id"] == "2544"
    assert actions[0]["sub_type"] == "jumpshot"
    assert actions[0]["shot_result"] == "Made"
    assert actions[0]["team_id"] == "1610612747"
    assert actions[0]["event_timestamp"] == "2025-12-20T20:13:02Z"
    assert actions[0]["available_at"] == "2025-12-20T20:13:02Z"


def test_ambiguous_names_are_review_required_not_merged():
    events = pd.DataFrame(
        [
            {"person_id": "1", "player_name": "Smith"},
            {"person_id": "2", "player_name": "Smith"},
        ]
    )
    rows = collect_player_rows(events, "NBA")
    ids = {r["player_id"] for r in rows}
    assert ids == {"1", "2"}
    assert all(r["status"] == "REVIEW_REQUIRED" for r in rows)
