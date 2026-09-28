from datetime import datetime, timedelta, timezone

import pandas as pd

from terminal_efficiency.clocks import parse_utc
from terminal_efficiency.features.pregame import build_pregame_features
from terminal_efficiency.validation.leakage_audit import run_leakage_audit
from terminal_efficiency.validation.temporal_split import add_split, assert_no_test_in_fit


def _game(gid, date, start, end, home, away, hw, **extra):
    row = {
        "game_id": gid,
        "league": "NBA",
        "season": "2024-2025",
        "game_date": date,
        "scheduled_start": start,
        "result_available_at": end,
        "home_team_id": home,
        "away_team_id": away,
        "final_home_win": hw,
        "final_home_score": 100 if hw else 90,
        "final_away_score": 90 if hw else 100,
        "home_ortg": 110,
        "away_ortg": 105,
        "home_drtg": 105,
        "away_drtg": 110,
        "home_pace": 100,
        "away_pace": 100,
    }
    row.update(extra)
    return row


def test_pregame_excludes_target_and_future():
    t0 = datetime(2024, 11, 1, 0, 0, tzinfo=timezone.utc)
    games = pd.DataFrame(
        [
            _game("g1", "2024-11-01", t0.isoformat(), (t0 + timedelta(hours=3)).isoformat(), "AAA", "BBB", True),
            _game(
                "g2",
                "2024-11-03",
                (t0 + timedelta(days=2)).isoformat(),
                (t0 + timedelta(days=2, hours=3)).isoformat(),
                "AAA",
                "CCC",
                True,
            ),
            _game(
                "g3",
                "2024-11-05",
                (t0 + timedelta(days=4)).isoformat(),
                (t0 + timedelta(days=4, hours=3)).isoformat(),
                "AAA",
                "DDD",
                False,
            ),
        ]
    )
    pre = build_pregame_features(games)
    g3 = pre[pre.game_id == "g3"].iloc[0]
    assert g3["home_games_played_pre"] == 2
    assert g3["home_win_pct_pre"] == 1.0
    as_of = parse_utc(g3["feature_as_of_timestamp"])
    start = parse_utc(g3["scheduled_start"])
    assert as_of < start


def test_audit_fails_future_event():
    obs = pd.DataFrame(
        [
            {
                "game_id": "g1",
                "prediction_timestamp": "2024-11-01T01:00:00Z",
                "feature_as_of_timestamp": "2024-11-01T01:00:00Z",
                "game_event_timestamp": "2024-11-01T01:05:00Z",
                "event_number": 1,
                "split": "TRAIN",
            }
        ]
    )
    report = run_leakage_audit(league="NBA", season="1999-2000", observations=obs)
    assert report["status"] == "FAIL"
    assert any(f["feature"] == "game_event_timestamp" for f in report["failures"])


def test_forbidden_market_column():
    obs = pd.DataFrame(
        [
            {
                "game_id": "g1",
                "prediction_timestamp": "2024-11-01T01:00:00Z",
                "feature_as_of_timestamp": "2024-11-01T00:59:00Z",
                "game_event_timestamp": "2024-11-01T00:59:00Z",
                "event_number": 1,
                "yes_bid_close_e4": 8000,
                "split": "TRAIN",
            }
        ]
    )
    report = run_leakage_audit(
        league="NBA", season="1999-2000", observations=obs, feature_columns=["yes_bid_close_e4"]
    )
    assert report["status"] == "FAIL"


def test_test_frozen_cannot_fit():
    df = add_split(pd.DataFrame({"game_date": ["2025-11-01"], "season": ["2025-2026"]}))
    assert df.iloc[0]["split"] == "TEST_FROZEN"
    try:
        assert_no_test_in_fit(df)
        raise AssertionError("should have failed")
    except RuntimeError:
        pass
