from terminal_efficiency.state.possession_builder import reconstruct_possessions


def test_made_fg_closes_confirmed():
    events = [
        {
            "game_id": "g1",
            "event_number": 1,
            "team_tricode": "AAA",
            "action_type": "2pt",
            "shot_result": "Made",
            "description": "AAA makes jump shot",
            "event_timestamp": "2024-11-01T01:00:00Z",
            "available_at": "2024-11-01T01:00:00Z",
            "period": 1,
            "seconds_remaining_game": 2800,
            "seconds_remaining_period": 700,
            "home_score": 2,
            "away_score": 0,
            "score_difference": 2,
        },
        {
            "game_id": "g1",
            "event_number": 2,
            "team_tricode": "BBB",
            "action_type": "turnover",
            "shot_result": "",
            "description": "BBB turnover",
            "event_timestamp": "2024-11-01T01:01:00Z",
            "available_at": "2024-11-01T01:01:00Z",
            "period": 1,
            "seconds_remaining_game": 2750,
            "seconds_remaining_period": 650,
            "home_score": 2,
            "away_score": 0,
            "score_difference": 2,
        },
    ]
    poss = reconstruct_possessions(events, sport="NBA")
    assert poss
    assert poss[0]["end_reason"] == "MADE_FIELD_GOAL"
    assert poss[0]["end_status"] == "CONFIRMED"
    assert poss[0]["start_event_number"] <= poss[0]["end_event_number"]


def test_unsupported_sport_empty():
    assert reconstruct_possessions([], sport="NFL") == []
