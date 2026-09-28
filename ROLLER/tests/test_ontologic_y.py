"""Ontologic Y contracts. No training and no unpickle."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from roller.ontologic_x.identity import match_game
from roller.ontologic_x.math import analytical_partition, is_integer_line
from roller.ontologic_y.capability import capability_matrix, live_partitions
from roller.ontologic_y.features import aggregate
from roller.ontologic_y.math import american_from_probability, complement, fair_decimal, percent_text
from roller.ontologic_y.model import assess_xib
from roller.ontologic_y.service import Service
from roller.ontologic_y.store import Store
from roller.ontologic_y.windows import descriptive_windows

NOW = datetime(2026, 10, 20, 23, 0, tzinfo=timezone.utc)


def _game(game_id: str, start: datetime, season_type: str, team: str = "1") -> dict:
    return {
        "nba_game_id": game_id,
        "start_utc": start.isoformat(),
        "season_type": season_type,
        "season": "2026-27",
        "team_id": team,
        "completed": True,
        "FGM": 40,
        "FGA": 80,
        "FG3M": 10,
        "FG3A": 30,
        "FTM": 10,
        "FTA": 12,
        "OREB": 8,
        "DREB": 30,
        "REB": 38,
        "AST": 20,
        "TOV": 12,
        "PTS": 100,
    }


def test_windows_stay_separate_and_exclude_the_target_and_the_future():
    tipoff = NOW
    history = [
        _game(f"00226000{index:02d}", tipoff - timedelta(days=index), "regular")
        for index in range(1, 13)
    ]
    history.append(_game("0012600001", tipoff - timedelta(days=2), "preseason"))
    history.append(_game("0022600099", tipoff, "regular"))
    history.append(_game("0022600098", tipoff + timedelta(days=1), "regular"))
    body = descriptive_windows(history, tipoff, "0022600001")
    regular = body["windows"]["regular"]
    assert regular["count"] == 10
    assert regular["label"] == "DESCRIPTIVE_ONLY"
    assert regular["model_input"] is False
    assert "0022600001" not in regular["game_ids"]
    assert "0022600099" not in regular["game_ids"]
    assert "0022600098" not in regular["game_ids"]
    assert body["windows"]["preseason"]["count"] == 1
    assert set(body["windows"]) == {"regular", "preseason"}


def test_short_window_reports_its_count_and_a_long_gap():
    history = [
        _game("0022500001", NOW - timedelta(days=80), "regular"),
        _game("0022600002", NOW - timedelta(days=3), "regular"),
    ]
    history[0]["season"] = "2025-26"
    window = descriptive_windows(history, NOW, "0022600099")["windows"]["regular"]
    assert window["count"] == 2
    assert window["long_gap"] is True
    assert window["cross_season"] is True


def test_missing_advanced_fields_stay_unavailable():
    body = aggregate([_game("0022600001", NOW, "regular")])
    assert "pace" in body["missing"]
    assert body["status"] == "FEATURE_UNAVAILABLE"
    assert body["derived"][0]["formula"] == "(FGM + 0.5*FG3M) / FGA"
    assert body["model_input"] is False


def test_xib_is_incompatible_without_unpickle_or_fit():
    source = Path(assess_xib.__code__.co_filename).read_text()
    assert "import joblib" not in source
    assert ".fit(" not in source
    record = assess_xib()
    assert record["artifact_found"] is True
    assert record["model_status"] == "MODEL_INCOMPATIBLE"
    assert record["joblib_unpickled"] is False
    assert record["trained_in_process"] is False
    assert record["probabilities"] == "unavailable"
    assert "NOT_XGBOOST" in record["reasons"]


def test_no_probability_is_minted_when_the_score_changes():
    store = Store(Path("/tmp/ontologic-y-score.sqlite"))
    service = Service(store, owner="score")
    catalog = {
        "status": "OK",
        "preseason_start": "2026-10-03T23:00:00+00:00",
        "games": [
            {
                "nba_game_id": "0012600009",
                "start_utc": NOW.isoformat(),
                "status": "live",
                "season_type": "preseason",
                "home_tricode": "TOR",
                "away_tricode": "MIA",
                "home_team_id": 1610612761,
                "away_team_id": 1610612748,
                "home_score": 10,
                "away_score": 8,
                "period": 1,
                "clock": "8:00",
            }
        ],
    }
    first = service._snapshot(catalog, None, NOW)
    catalog["games"][0]["home_score"] = 12
    second = service._snapshot(catalog, {"rows": [], "retrieved_at": NOW.isoformat()}, NOW + timedelta(seconds=30))
    assert first["prediction_generated_at"] is None
    assert second["prediction_generated_at"] is None
    assert second["games"][0]["basis"] is None
    assert second["games"][0]["moneyline"] == "MARKET_MODEL_UNAVAILABLE"
    assert second["earliest_preseason_game_returned"] == "2026-10-03T23:00:00+00:00"
    assert second["schedule_completeness"] == "UNVERIFIED"
    store.close()


def test_market_matrix_and_fair_odds():
    assert all(row["status"] == "MARKET_MODEL_UNAVAILABLE" for row in capability_matrix())
    assert live_partitions()["margin"]["status"] == "MARKET_MODEL_UNAVAILABLE"
    pair = complement("0.6")
    assert pair["away"] == Decimal("0.4")
    assert pair["vig_removal"] == "NOT_APPLICABLE"
    assert fair_decimal("0.5") == "2"
    assert american_from_probability("0.6").startswith("-")
    assert american_from_probability(0) is None
    assert american_from_probability(1) is None
    assert fair_decimal(0) is None
    assert percent_text(Decimal("0.6")) == "60.0000%"


def test_partition_tails_monotonicity_mass_and_push():
    points = [(Decimal("-3.5"), Decimal("0.60")), (Decimal("3.5"), Decimal("0.40"))]
    body = analytical_partition(points, "M")
    assert body["status"] == "OK"
    assert body["buckets"][0]["unbounded_below"] is True
    assert body["buckets"][-1]["unbounded_above"] is True
    assert body["mass"] == "1"
    broken = analytical_partition(
        [(Decimal("-3.5"), Decimal("0.40")), (Decimal("3.5"), Decimal("0.60"))],
        "M",
    )
    assert broken["status"] == "SUPPRESSED"
    assert is_integer_line(3) is True
    assert live_partitions()["total"]["buckets"] == []


def test_unmatched_identity_and_lease_backoff():
    game, status = match_game(
        {"start_utc": NOW.isoformat(), "home_team_id": 1, "away_team_id": 2},
        [{"nba_game_id": "0022600001", "start_utc": NOW.isoformat(), "home_team_id": 9, "away_team_id": 2}],
    )
    assert game is None and status == "UNMATCHED"
    path = Path("/tmp/ontologic-y-lease.sqlite")
    if path.exists():
        path.unlink()
    store = Store(path)
    assert store.try_lease("a", NOW) is True
    assert store.try_lease("b", NOW) is False
    store.release("a")
    for _ in range(3):
        store.record_poll(NOW, "a", False, "NBA", "down")
    service = Service(store, owner="a")
    body = service.refresh(NOW)
    assert body["schedule_status"] == "BACKOFF"
    store.close()
