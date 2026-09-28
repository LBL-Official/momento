"""Ontologic X baseline. Fixture mode is not a live-feed pass."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from roller.ontologic_x.identity import game_id_text, match_game, preseason_start, season_type_from_game_id
from roller.ontologic_x.math import InvalidPrice, american_implied, analytical_partition, percent_text, proportional_no_vig
from roller.ontologic_x.pairing import classify_book, pair_quotes
from roller.ontologic_x.service import Service
from roller.ontologic_x.sources import FixtureSource, PollGate, load_fixture_document, parse_odds_api
from roller.ontologic_x.store import Store

FIXTURE = Path(__file__).resolve().parents[2] / "research" / "ontologic_x" / "fixtures" / "baseline.json"
SENTINEL = "sk_test_do_not_emit_9f3a"
T0 = datetime(2026, 9, 23, 16, 0, tzinfo=timezone.utc)


def _money(home: int, away: int, **extra) -> list[dict]:
    base = {
        "provider": "fixture",
        "bookmaker": "williamhill",
        "provider_event_id": "evt",
        "market_family": "moneyline",
        "period": "game",
        "main": True,
        "status": "open",
        "phase": "pregame",
        "settlement": "including_overtime",
        "line": None,
        "source_updated_at": "2026-10-04T18:00:00Z",
    }
    return [
        {**base, "side": "home", "american": home, **extra},
        {**base, "side": "away", "american": away},
    ]


def _service(tmp_path: Path) -> Service:
    document = load_fixture_document(FIXTURE)
    return Service(Store(tmp_path / "ontologic_x.sqlite"), FixtureSource(document), owner="worker-a")


def _game(body: dict, game_id: str) -> dict:
    return next(game for game in body["games"] if game["id"] == game_id)


def test_american_conversion_and_locked_no_vig():
    decimal, implied = american_implied(-150)
    assert decimal == Decimal("1.666666666666666666666666667") or decimal == Decimal(1) + Decimal(100) / Decimal(150)
    assert implied == Decimal("0.6")
    assert percent_text(implied) == "60.0000%"
    _decimal, plus = american_implied(130)
    assert percent_text(plus) == "43.4783%"
    result = proportional_no_vig([implied, plus])
    assert result["status"] == "OK"
    assert result["overround_points"] == "3.4783"
    assert result["normalized"][0]["display_percent"] == "57.9832%"
    assert result["normalized"][1]["display_percent"] == "42.0168%"
    assert result["mass"] == 1
    with pytest.raises(InvalidPrice):
        american_implied(0)
    with pytest.raises(InvalidPrice):
        american_implied("NaN")
    with pytest.raises(InvalidPrice):
        american_implied(None)


def test_incomplete_period_settlement_skew_orientation_and_books():
    assert pair_quotes(_money(-150, 130)[:1])[0]["status"] == "INCOMPLETE"
    home = _money(-150, 130)[0]
    away = _money(-150, 130)[1]
    away["period"] = "Q1"
    assert pair_quotes([home, away])[0]["status"] == "INCOMPLETE"
    away = _money(-150, 130)[1]
    away["settlement"] = "regulation"
    statuses = {pair["status"] for pair in pair_quotes([home, away])}
    assert "OK" not in statuses
    skewed = _money(-150, 130)
    skewed[1]["source_updated_at"] = "2026-10-04T18:05:00Z"
    assert pair_quotes(skewed)[0]["status"] == "TIMESTAMP_SKEW"
    flipped = [
        {**home, "market_family": "spread", "line": "-3.5"},
        {**away, "market_family": "spread", "line": "-3.5", "settlement": "including_overtime", "period": "game"},
    ]
    assert pair_quotes(flipped)[0]["status"] == "ORIENTATION_INVALID"
    assert classify_book("williamhill_us") == "caesars_key"
    assert classify_book("William Hill") == "williamhill"
    assert classify_book("draftkings") == "other"


def test_push_label_tails_and_monotonicity_failure():
    home = _money(-110, -110)[0]
    away = _money(-110, -110)[1]
    integer = pair_quotes(
        [
            {**home, "market_family": "spread", "line": "-3", "side": "home"},
            {**away, "market_family": "spread", "line": "3", "side": "away"},
        ]
    )[0]
    assert integer["status"] == "CONDITIONAL_ON_NO_PUSH"
    assert integer["push_probability"] == "UNAVAILABLE"
    points = [(Decimal("3.5"), Decimal(69) / Decimal(119)), (Decimal("7.5"), Decimal(50) / Decimal(119))]
    part = analytical_partition(points, "M")
    assert part["status"] == "OK"
    assert part["buckets"][0]["unbounded_below"] is True
    assert part["buckets"][-1]["unbounded_above"] is True
    assert part["buckets"][0]["label"] == "M ≤ 3.5"
    assert part["buckets"][-1]["label"] == "M > 7.5"
    assert "max_score" not in part
    assert sum(Decimal(bucket["probability"]) for bucket in part["buckets"]) == 1
    broken = analytical_partition(
        [(Decimal("3.5"), Decimal("0.40")), (Decimal("7.5"), Decimal("0.55"))],
        "M",
    )
    assert broken["status"] == "SUPPRESSED"
    assert broken["reason"] == "INCONSISTENT_LADDER"
    assert broken["buckets"] == []


def test_fixture_snapshot_identity_dedupe_suspension_and_secret(tmp_path: Path):
    raw = FIXTURE.read_text()
    assert SENTINEL in raw
    service = _service(tmp_path)
    first = service.tick(T0)
    assert first["polled"] is True
    body = service.board()
    encoded = json.dumps(body)
    assert SENTINEL not in encoded
    assert "0012600001" in encoded
    assert body["preseason_start"] == "2026-10-01T23:00:00Z"
    assert body["preseason_start_source"] == "FIXTURE"
    assert body["canonical_source"] == "CANONICAL_FIXTURE"
    assert body["live_execution"] is False
    bos = _game(body, "0012600001")
    assert bos["internal_game_id"] == "NBA_20261004_NYK_BOS"
    assert bos["mapping"] == "MATCHED"
    home = next(side for side in bos["moneyline"]["normalized"] if side["side"] == "home")
    away = next(side for side in bos["moneyline"]["normalized"] if side["side"] == "away")
    assert home["raw_display_percent"] == "60.0000%"
    assert away["raw_display_percent"] == "43.4783%"
    assert bos["moneyline"]["overround_points"] == "3.4783"
    assert home["display_percent"] == "57.9832%"
    assert away["display_percent"] == "42.0168%"
    assert away["source_updated_at"] == "2026-10-04T18:00:00Z"
    assert bos["margin_partition"]["status"] == "OK"
    assert bos["margin_partition"]["buckets"][0]["unbounded_below"] is True
    assert bos["total_partition"]["status"] == "OK"
    assert bos["quarters"]["Q1"]["status"] == "OK"
    assert bos["quarters"]["Q2"]["status"] == "UNAVAILABLE"
    integer = next(market for market in bos["markets"] if market.get("conditional_on_no_push"))
    assert integer["push_probability"] == "UNAVAILABLE"
    assert all(market.get("line") != "-10.5" for market in bos["markets"])
    assert any(quote.get("status") == "suspended" for quote in bos["history"])
    reasons = {row["reason"] for row in body["rejected_books"]}
    assert "NOT_WILLIAM_HILL" in reasons
    assert "BOOK_KEY_IS_CAESARS" in reasons
    assert "-140" not in json.dumps(bos["moneyline"])
    assert "-160" not in json.dumps(bos["moneyline"])
    assert _game(body, "0012600004")["empty_state"] == "NO_POSTED_ODDS"
    assert _game(body, "0012600003")["empty_state"] == "INCONSISTENT_LADDER"
    assert _game(body, "0012600003")["margin_partition"]["buckets"] == []
    assert _game(body, "0012600009")["empty_state"] == "INCOMPLETE"
    assert any(game["id"] == "unmatched-fix-ambiguous" and game["mapping"] == "AMBIGUOUS" for game in body["games"])
    assert any(game["id"] == "unmatched-fix-unmatched" and game["mapping"] == "UNMATCHED" for game in body["games"])
    assert [game["status"] for game in body["games"] if game["status"] in {"live", "upcoming"}][0] == "live"
    second = service.tick(T0 + timedelta(seconds=5))
    assert second["snapshot_id"] != first["snapshot_id"]
    changed = _game(service.board(), "0012600001")
    changed_away = next(side for side in changed["moneyline"]["normalized"] if side["side"] == "away")
    changed_home = next(side for side in changed["moneyline"]["normalized"] if side["side"] == "home")
    assert changed_away["source_updated_at"] is None
    assert changed_away["last_quote_change_at"] == "2026-09-23T16:00:05Z"
    assert changed_home["source_updated_at"] == "2026-10-04T18:00:00Z"
    assert changed_home["last_quote_change_at"] == "2026-09-23T16:00:00Z"
    assert changed["freshness"]["source_time_label"] == "SOURCE_TIME_UNAVAILABLE"
    third = service.tick(T0 + timedelta(seconds=10))
    assert third["ok"] is True
    stable = _game(service.board(), "0012600001")
    stable_away = next(side for side in stable["moneyline"]["normalized"] if side["side"] == "away")
    assert stable_away["last_quote_change_at"] == "2026-09-23T16:00:05Z"
    assert service.store.successful_polls() == 3
    assert SENTINEL not in json.dumps(service.health())


def test_lease_blocks_second_worker_and_backoff_skips_transport(tmp_path: Path):
    store = Store(tmp_path / "lease.sqlite")
    calls = {"n": 0}

    def transport(_revision: int) -> dict:
        calls["n"] += 1
        return {
            "mode": "FIXTURE",
            "label": "FIXTURE",
            "quotes": [],
            "nba_games": [],
            "canonical_games": [],
            "cadence_label": "FIXTURE",
        }

    owner = Service(store, transport, owner="worker-a")
    other = Service(store, transport, owner="worker-b")
    assert owner.tick(T0)["polled"] is True
    held = other.tick(T0 + timedelta(seconds=1))
    assert held["reason"] == "LEASE_HELD"
    assert held["polled"] is False
    assert calls["n"] == 1

    def failing(_revision: int) -> dict:
        calls["n"] += 1
        raise TimeoutError("slow book")

    gated = Service(Store(tmp_path / "backoff.sqlite"), failing, owner="worker-a")
    assert gated.tick(T0)["reason"] == "TRANSPORT"
    skipped = gated.tick(T0 + timedelta(seconds=1))
    assert skipped["reason"] == "BACKOFF"
    assert calls["n"] == 2
    gate = PollGate()
    assert gate.failure(T0) == 2
    assert gate.allowed(T0 + timedelta(seconds=1)) is False
    assert gate.allowed(T0 + timedelta(seconds=2)) is True


def test_odds_api_parser_keeps_william_hill_only():
    payload = [
        {
            "id": "evt-1",
            "home_team": "Celtics",
            "away_team": "Knicks",
            "commence_time": "2026-10-04T23:30:00Z",
            "bookmakers": [
                {
                    "key": "williamhill_us",
                    "title": "Caesars",
                    "markets": [{"key": "h2h", "outcomes": [{"name": "Celtics", "price": "-160"}]}],
                },
                {
                    "key": "williamhill",
                    "markets": [
                        {
                            "key": "h2h",
                            "last_update": "2026-10-04T18:00:00Z",
                            "outcomes": [
                                {"name": "Celtics", "price": "-150"},
                                {"name": "Knicks", "price": "130"},
                            ],
                        }
                    ],
                },
            ],
        }
    ]
    quotes, rejected = parse_odds_api(payload)
    assert rejected == ["BOOK_KEY_IS_CAESARS"]
    assert {quote["side"] for quote in quotes} == {"home", "away"}
    assert quotes[0]["source_updated_at"] == "2026-10-04T18:00:00Z"
    assert quotes[0]["settlement"] == "UNKNOWN"


def test_nba_game_id_keeps_leading_zeros_and_preseason_comes_from_rows():
    assert game_id_text(12600001) == "0012600001"
    assert season_type_from_game_id("0012600001") == "preseason"
    games = [
        {"season_type": "preseason", "start_utc": "2026-10-08T00:00:00Z"},
        {"season_type": "regular", "start_utc": "2026-10-03T00:00:00Z"},
        {"season_type": "preseason", "start_utc": "2026-10-06T00:00:00Z"},
    ]
    assert preseason_start(games) == "2026-10-06T00:00:00Z"
    event = {"home_team_id": 1, "away_team_id": 2, "start_utc": "2026-10-07T01:15:00Z"}
    catalog = [
        {"home_team_id": 1, "away_team_id": 2, "start_utc": "2026-10-07T01:00:00Z", "neutral": False, "nba_game_id": "a"},
        {"home_team_id": 1, "away_team_id": 2, "start_utc": "2026-10-07T01:30:00Z", "neutral": False, "nba_game_id": "b"},
    ]
    found, status = match_game(event, catalog)
    assert found is None
    assert status == "AMBIGUOUS"


def test_health_does_not_claim_live_connectivity(tmp_path: Path):
    service = _service(tmp_path)
    service.tick(T0)
    health = service.health()
    assert health["provider_configured"] is False
    assert health["live_connectivity"] == "BLOCKED"
    assert health["five_second_book_freshness"] == "NOT_CLAIMED"
    assert health["source_freshness_measured"] is False
    assert health["cadence_label"] == "FIXTURE"
    assert health["lease_owner"] == "worker-a"
    assert health["submits"] is False
