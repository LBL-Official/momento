"""WNBA/NCAAB persist observed wall as time_actual. Never invent from tip+clock."""

from __future__ import annotations

from roller.ingest.pbp import parse_espn_plays


def test_prefers_time_actual_then_wallclock():
    plays = {
        "plays": [
            {
                "sequenceNumber": 1,
                "period": {"number": 1},
                "clock": {"displayValue": "10:00"},
                "timeActual": "2026-06-01T19:00:05Z",
                "wallclock": "2026-06-01T19:00:01Z",
                "homeScore": 0,
                "awayScore": 0,
                "type_text": "Start Period",
                "team": {"id": "16", "abbreviation": "NY"},
                "homeAway": "away",
            },
            {
                "sequenceNumber": 2,
                "period": 1,
                "clock": "9:40",
                "wallclock": "2026-06-01T19:00:25Z",
                "homeScore": 2,
                "awayScore": 0,
                "type_text": "Made Shot",
                "home_away": "home",
                "team": {"abbreviation": "DAL"},
            },
        ]
    }
    rows = parse_espn_plays(plays)
    assert rows[0]["time_actual"] == "2026-06-01T19:00:05Z"
    assert rows[0]["event_timestamp"] == "2026-06-01T19:00:05Z"
    assert rows[0]["clock"] == "10:00"
    assert rows[0]["home_away"] == "away"
    assert rows[0]["team_tricode"] == "NY"
    assert rows[1]["time_actual"] == "2026-06-01T19:00:25Z"
    assert rows[1]["clock"] == "9:40"
