"""BetOnline parser, dedup, and a blocked read. No live provider calls."""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from roller.ontologic_x.betonline.client import Client, CollectionBlocked, CollectionFailed
from roller.ontologic_x.betonline.collect import collect
from roller.ontologic_x.betonline.parse import parse_event
from roller.ontologic_x.math import american_implied
from roller.ontologic_x.store import Store

NOW = datetime(2026, 9, 27, 3, 0, tzinfo=timezone.utc)
GAME = {
    "GameId": 491101337,
    "AwayTeam": "Boston Celtics",
    "HomeTeam": "Detroit Pistons",
    "AwayRotation": 501,
    "HomeRotation": 502,
    "WagerCutOff": "2026-10-20T19:10:00",
    "GameDateTime": "0001-01-01T00:00:00",
    "AwayLine": {
        "SpreadLine": {
            "Line": -110,
            "DecimalLine": 1.91,
            "FractionalNumeratorLine": 10,
            "FractionalDenominatorLine": 11,
            "Point": 2,
        },
        "MoneyLine": {"Line": 0, "DecimalLine": 0, "FractionalNumeratorLine": 0, "FractionalDenominatorLine": 0},
    },
    "HomeLine": {
        "SpreadLine": {
            "Line": -110,
            "DecimalLine": 1.91,
            "FractionalNumeratorLine": 10,
            "FractionalDenominatorLine": 11,
            "Point": -2,
        },
        "MoneyLine": {"Line": 0, "DecimalLine": 0, "FractionalNumeratorLine": 0, "FractionalDenominatorLine": 0},
    },
    "TotalLine": {
        "TotalLine": {
            "Point": 220.5,
            "Over": {"Line": -110, "DecimalLine": 1.91, "FractionalNumeratorLine": 10, "FractionalDenominatorLine": 11},
            "Under": {"Line": -110, "DecimalLine": 1.91, "FractionalNumeratorLine": 10, "FractionalDenominatorLine": 11},
        }
    },
}
EVENT = {
    "EventStatus": "ACTIVE",
    "EventOffering": {
        "League": "NBA",
        "Sport": "Basketball",
        "Event": GAME,
        "PeriodEvents": [{"Name": "Game", "Number": 0, "HasGames": True, "Event": GAME}],
    },
}


def _games():
    return [
        {
            "nba_game_id": "0022600001",
            "season_type": "regular",
            "start_utc": "2026-10-20T19:00:00Z",
            "home_full_name": "Detroit Pistons",
            "away_full_name": "Boston Celtics",
            "home_tricode": "DET",
            "away_tricode": "BOS",
            "status": "upcoming",
        },
        {
            "nba_game_id": "0012600009",
            "season_type": "preseason",
            "start_utc": "2026-10-03T23:00:00Z",
            "home_full_name": "Toronto Raptors",
            "away_full_name": "Miami Heat",
            "home_tricode": "TOR",
            "away_tricode": "MIA",
            "status": "upcoming",
        },
    ]


class FixtureClient:
    def __init__(self, game=None, event=None, blocked=False):
        self.game = GAME if game is None else game
        self.event_payload = EVENT if event is None else event
        self.blocked = blocked
        self.event_calls = 0

    def league(self, period=0):
        if self.blocked:
            raise CollectionBlocked(403)
        return {"GameOffering": {"GamesDescription": [{"Game": self.game}]}}

    def event(self, game_id):
        self.event_calls += 1
        assert game_id == 491101337
        return self.event_payload

    def linked_events(self, game_id):
        assert game_id == 491101337
        return []


def _side(records, family, side):
    return next(row for row in records if row["market_family"] == family and row["side"] == side and row["period"] == "game")


def test_spread_total_and_moneyline_keep_their_sides_and_do_not_price_a_zero_sentinel():
    records = parse_event(GAME, EVENT)
    away = _side(records, "spread", "away")
    home = _side(records, "spread", "home")
    assert away["bookmaker"] == "betonline"
    assert away["line"] == "2"
    assert home["line"] == "-2"
    assert away["american"] == "-110"
    assert away["source_decimal"] == "1.91"
    assert away["decimal_odds"] == format(american_implied("-110")[0], "f")
    assert Decimal(away["implied"]) > 0
    assert away["wager_cutoff"] == "2026-10-20T19:10:00Z"
    assert away["source_updated_at"] is None
    assert away["decimal_discrepancy"] is not None
    assert away["source_decimal"] == "1.91"
    assert away["timezone"] == "UTC"
    total_over = _side(records, "total", "over")
    total_under = _side(records, "total", "under")
    assert total_over["line"] == "220.5"
    assert total_under["line"] == "220.5"
    assert total_over["no_vig_status"] == "OK"
    assert total_over["no_vig_method"] == "PROPORTIONAL_NO_VIG_V1"
    mass = Decimal(total_over["no_vig_probability"]) + Decimal(total_under["no_vig_probability"])
    assert abs(mass - Decimal(1)) < Decimal("0.0000001")
    money = _side(records, "moneyline", "away")
    assert money["status"] == "MARKET_NOT_OFFERED"
    assert money["american"] is None
    assert money["implied"] is None
    assert money.get("no_vig_probability") is None


def test_full_game_period_stays_apart_from_an_unpublished_quarter():
    records = parse_event(GAME, EVENT, [])
    assert _side(records, "spread", "away")["period"] == "game"
    quarter = next(row for row in records if row["period"] == "Q1")
    assert quarter["status"] == "MARKET_NOT_OFFERED"
    assert quarter["american"] is None


def test_duplicate_observation_does_not_append_and_a_new_price_does(tmp_path: Path):
    store = Store(tmp_path / "betonline.sqlite")
    client = FixtureClient()
    first = collect(store, client, _games(), NOW)
    second = collect(store, client, _games(), NOW)
    assert first["inserted"] > 0
    assert second["inserted"] == 0
    assert len(store.book_quotes("betonline")) == first["inserted"]
    changed = {
        **GAME,
        "AwayLine": {
            **GAME["AwayLine"],
            "SpreadLine": {**GAME["AwayLine"]["SpreadLine"], "Line": -105, "DecimalLine": 1.95},
        },
    }
    event = {**EVENT, "EventOffering": {**EVENT["EventOffering"], "Event": changed, "PeriodEvents": [{"Name": "Game", "Number": 0, "Event": changed}]}}
    third = collect(store, FixtureClient(game=changed, event=event), _games(), NOW)
    assert third["inserted"] >= 1
    away = [
        row
        for row in store.book_quotes("betonline")
        if row["market_family"] == "spread" and row["side"] == "away" and row["period"] == "game"
    ]
    assert [row["american"] for row in away] == ["-110", "-105"]
    body = store.current_body()
    pistons = next(game for game in body["games"] if game["id"] == "0022600001")
    assert pistons["bookmaker"] == "betonline"
    assert pistons["matchup"] == "BOS @ DET"
    assert pistons["main_spread"]["status"] == "CONDITIONAL_ON_NO_PUSH"
    october3 = next(game for game in body["games"] if game["id"] == "0012600009")
    assert october3["bookmaker"] is None
    assert october3["empty_state"] == "NO_POSTED_ODDS"
    assert october3["moneyline"] is None
    assert october3["event_coverage"]["status"] == "NO_BETONLINE_EVENT"
    assert october3["outcomes"] == []


def test_blocked_read_keeps_the_scheduled_game(tmp_path: Path):
    store = Store(tmp_path / "blocked.sqlite")
    collect(store, FixtureClient(), _games(), NOW)
    before = store.current_body()["snapshot_id"]
    result = collect(store, FixtureClient(blocked=True), _games(), NOW)
    assert result["status"] == "COLLECTION_BLOCKED"
    assert result["kept_snapshot"] is True
    assert store.current_body()["snapshot_id"] == before
    assert any(game["id"] == "0012600009" for game in store.current_body()["games"])


def test_public_page_refusal_is_not_retried():
    calls = []

    class Once(Client):
        def _once(self, method, url, body, headers):
            calls.append(method)
            return 403, ""

    client = Once(retries=5, sleep=lambda _seconds: None)
    with pytest.raises(CollectionBlocked):
        client.league()
    assert calls == ["GET"]


def test_suspended_event_does_not_become_an_implied_price():
    event = {**EVENT, "EventStatus": "SUSPENDED"}
    records = parse_event(GAME, event, [])
    spread = _side(records, "spread", "away")
    assert spread["status"] == "MARKET_SUSPENDED"
    assert spread["american"] is None
    assert spread["implied"] is None


def test_linked_quarter_stays_apart_from_the_full_game_spread():
    quarter = {
        **GAME,
        "AwayLine": {
            "SpreadLine": {"Line": -115, "DecimalLine": 1.87, "Point": 1.5},
            "MoneyLine": {"Line": 0, "DecimalLine": 0},
        },
        "HomeLine": {
            "SpreadLine": {"Line": -105, "DecimalLine": 1.95, "Point": -1.5},
            "MoneyLine": {"Line": 0, "DecimalLine": 0},
        },
    }
    linked = [{"PeriodEvents": [{"Name": "1st Quarter", "Number": 1, "Event": quarter}]}]
    records = parse_event(GAME, EVENT, linked)
    assert _side(records, "spread", "away")["line"] == "2"
    quarter_row = next(row for row in records if row["period"] == "Q1" and row["market_family"] == "spread" and row["side"] == "away")
    assert quarter_row["line"] == "1.5"
    assert quarter_row["american"] == "-115"
    assert not any(row["period"] == "Q1" and row["status"] == "MARKET_NOT_OFFERED" and row["market_family"] == "period" for row in records)


def test_alternate_lines_do_not_share_a_no_vig_group():
    game = {
        **GAME,
        "AwayLine": {
            **GAME["AwayLine"],
            "BuyPointLineRule": [
                {
                    "Point": 3.5,
                    "Away": {"Line": -120, "DecimalLine": 1.83, "Point": 3.5},
                    "Home": {"Line": 100, "DecimalLine": 2.0, "Point": -3.5},
                }
            ],
        },
    }
    records = parse_event(game, EVENT, [])
    main = _side(records, "spread", "away")
    alternate = next(row for row in records if row["market_family"] == "alternate_spread" and row["side"] == "away")
    assert main["line"] == "2"
    assert alternate["line"] == "3.5"
    assert main["no_vig_status"] == "OK"
    assert alternate["no_vig_status"] == "OK"
    assert main["no_vig_probability"] != alternate["no_vig_probability"]


def test_unmapped_and_malformed_markets_keep_their_status():
    offering = {
        **EVENT["EventOffering"],
        "Markets": [
            {
                "MarketName": "Series Price",
                "MarketId": "99",
                "Outcomes": [
                    {"Name": "yes", "Line": -150, "DecimalLine": 1.67, "Participant": "Celtics"},
                    {"Name": "no", "Line": 130, "DecimalLine": 2.3, "Participant": "Pistons"},
                ],
            }
        ],
    }
    records = parse_event(GAME, {**EVENT, "EventOffering": offering}, [])
    unmapped = [row for row in records if row["market_family"] == "unmapped"]
    assert unmapped
    assert {row["status"] for row in unmapped} == {"UNMAPPED_MARKET"}
    assert all(row["specialty"] for row in unmapped)
    broken = {**GAME, "AwayLine": {**GAME["AwayLine"], "SpreadLine": "not-a-price"}}
    failed = parse_event(broken, EVENT, [])
    assert _side(failed, "spread", "away")["status"] == "PARSE_FAILED"
    assert _side(failed, "spread", "away")["implied"] is None


def test_unchanged_price_updates_last_seen_without_a_new_row(tmp_path: Path):
    store = Store(tmp_path / "seen.sqlite")
    collect(store, FixtureClient(), _games(), NOW)
    later = datetime(2026, 9, 27, 3, 5, tzinfo=timezone.utc)
    second = collect(store, FixtureClient(), _games(), later)
    assert second["inserted"] == 0
    row = next(
        item
        for item in store.book_quotes("betonline")
        if item["market_family"] == "spread" and item["side"] == "away" and item["period"] == "game"
    )
    assert row["american"] == "-110"
    assert row["last_seen_at"] == "2026-09-27T03:05:00Z"
    assert row["source_updated_at"] is None


def test_a_failed_event_does_not_erase_a_stored_price(tmp_path: Path):
    store = Store(tmp_path / "partial.sqlite")
    collect(store, FixtureClient(), _games(), NOW)
    before = len(store.book_quotes("betonline"))

    class OneFails(FixtureClient):
        def event(self, game_id):
            raise CollectionFailed("HTTP_500")

    result = collect(store, OneFails(), _games(), NOW)
    assert result["status"] == "PARTIAL"
    assert len(store.book_quotes("betonline")) == before
    body = store.current_body()
    kept = next(game for game in body["games"] if game["id"] == "0022600001")
    assert kept["main_spread"]["line"] == "-2"
    assert kept["event_coverage"]["status"] == "FETCH_FAILED"
    october3 = next(game for game in body["games"] if game["id"] == "0012600009")
    assert october3["bookmaker"] is None
    assert october3["moneyline"] is None


def test_a_second_collector_does_not_write(tmp_path: Path):
    store = Store(tmp_path / "lease.sqlite")
    collect(store, FixtureClient(), _games(), NOW)
    snapshot = store.current_body()["snapshot_id"]
    assert store.try_acquire("other-process", NOW, ttl_seconds=180)
    result = collect(store, FixtureClient(), _games(), NOW)
    assert result["status"] == "ALREADY_RUNNING"
    assert store.current_body()["snapshot_id"] == snapshot
