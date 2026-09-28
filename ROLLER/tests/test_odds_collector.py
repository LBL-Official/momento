"""Odds collector budget, matching, and coverage. No live provider calls."""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from roller.ontologic_x.collector import (
    consider_moments,
    coverage_view,
    due_moments,
    match_event,
    merge_unquoted_schedule,
    observed_lines_from_odds,
    refresh_listing,
    rehearse,
)
from roller.ontologic_x.governor import active_policy, authorize, illustrative_costs, next_detailed_interval
from roller.ontologic_x.markets import scenario_cost
from roller.ontologic_x.store import Store

NOW = datetime(2026, 9, 23, 16, 0, tzinfo=timezone.utc)


class FakeTransport:
    def __init__(self, events, markets=None, odds=None, preseason_events=None):
        self.events_payload = events
        self.preseason_events = preseason_events or []
        self.markets_payload = markets or {}
        self.odds_payload = odds or {}
        self.market_calls = 0
        self.odds_calls = 0
        self.sports = []

    def events(self, sport):
        self.sports.append(sport)
        payload = self.preseason_events if sport == "basketball_nba_preseason" else self.events_payload
        if sport not in {"basketball_nba", "basketball_nba_preseason"}:
            raise AssertionError(sport)
        return payload, {"x-requests-last": "0", "x-requests-used": "5", "x-requests-remaining": "495"}

    def event_markets(self, sport, event_id):
        self.market_calls += 1
        return self.markets_payload.get(event_id, {"bookmakers": []}), {
            "x-requests-last": "1",
            "x-requests-used": str(5 + self.market_calls),
            "x-requests-remaining": str(495 - self.market_calls),
        }

    def event_odds(self, sport, event_id, markets):
        self.odds_calls += 1
        return self.odds_payload.get(event_id, {"bookmakers": []}), {
            "x-requests-last": "0",
            "x-requests-used": "6",
            "x-requests-remaining": "494",
        }


def _games():
    return [
        {
            "nba_game_id": "0012600001",
            "season_type": "preseason",
            "start_utc": "2026-10-04T23:00:00Z",
            "home_full_name": "Boston Celtics",
            "away_full_name": "New York Knicks",
            "home_tricode": "BOS",
            "away_tricode": "NYK",
            "status": "upcoming",
        },
        {
            "nba_game_id": "0022600001",
            "season_type": "regular",
            "start_utc": "2026-10-20T23:00:00Z",
            "home_full_name": "Detroit Pistons",
            "away_full_name": "Boston Celtics",
            "home_tricode": "DET",
            "away_tricode": "BOS",
            "status": "upcoming",
        },
    ]


def test_october_plan_does_not_raise_the_ceiling_by_date_alone():
    assert active_policy(date(2026, 9, 23), "starter")["name"] == "starter"
    assert active_policy(date(2026, 10, 20), "starter")["allowance"] == 500
    assert active_policy(date(2026, 10, 19), "october20")["active"] is False
    october = active_policy(date(2026, 10, 20), "october20")
    assert october["allowance"] == 20_000
    assert october["detailed_interval_seconds"] == 120
    assert october["buckets"]["detailed_markets"] == 10_000


def test_reserve_and_bucket_block_spend():
    policy = active_policy(date(2026, 9, 23), "starter")
    rows = [{"bucket": "coverage_debug", "credits_last": 5, "credits_remaining": 495, "credits_used": 5}]
    allowed, reason = authorize(rows, "coverage_debug", 1, policy)
    assert allowed and reason == "OK"
    blocked, why = authorize(rows, "coverage_debug", 46, policy)
    assert not blocked and why == "BUCKET_EXHAUSTED"
    reserve, why = authorize(rows, "reserve", 1, policy)
    assert not reserve and why == "BUCKET_CLOSED"
    tight = [{"bucket": "coverage_debug", "credits_last": 5, "credits_remaining": 100, "credits_used": 400}]
    held, why = authorize(tight, "preseason_snapshots", 1, policy)
    assert not held and why == "RESERVE_PROTECTION"
    assert next_detailed_interval(rows, policy, 1) is None
    funded = [{"bucket": "detailed_markets", "credits_last": 0, "credits_remaining": 15_000, "credits_used": 5_000}]
    assert next_detailed_interval(funded, active_policy(date(2026, 10, 20), "october20"), 1) == 120
    assert next_detailed_interval(rows, active_policy(date(2026, 10, 20), "october20"), 1) is None


def test_illustrative_quarter_load_exceeds_the_october_allowance():
    assert scenario_cost(10, 30, 1) == 300
    assert scenario_cost(10, 30, 40) == 12_000
    assert scenario_cost(25, 30, 40) == 30_000
    costs = {row["credits"]: row for row in illustrative_costs()}
    assert costs[12_000]["exceeds_october20_detailed"] is True
    assert costs[30_000]["exceeds_october20_allowance"] is True


def test_match_uses_full_name_and_quarter_moments_need_a_clock():
    game, status = match_event(
        {"home_team": "Boston Celtics", "away_team": "New York Knicks", "commence_time": "2026-10-04T23:10:00Z"},
        _games(),
    )
    assert status == "MATCHED"
    assert game["nba_game_id"] == "0012600001"
    missed, missed_status = match_event(
        {"home_team": "Boston Celtics", "away_team": "Knicks", "commence_time": "2026-10-04T23:10:00Z"},
        _games(),
    )
    assert missed is None and missed_status == "UNMATCHED"
    assert due_moments({"status": "upcoming", "commence_time": "2026-10-04T23:00:00Z"}) == ["pregame"]
    assert "q2_open" in due_moments({"status": "live", "period": 2, "clock": "12:00"})
    assert due_moments({"status": "live", "period": None, "clock": None}) == []


def test_preseason_absence_is_labeled_separately_and_spends_one_regular_discovery(tmp_path: Path):
    transport = FakeTransport(
        events=[
            {
                "id": "reg-1",
                "home_team": "Detroit Pistons",
                "away_team": "Boston Celtics",
                "commence_time": "2026-10-20T23:00:00Z",
            }
        ],
        markets={"reg-1": {"bookmakers": [{"key": "draftkings", "markets": [{"key": "h2h"}]}]}},
    )
    report = rehearse(Store(tmp_path / "odds.sqlite"), transport, _games(), NOW)
    assert transport.market_calls == 1
    assert transport.odds_calls == 0
    assert report["preseason_listed"] is False
    assert report["coverage"]["preseason"]["h2h"] == "UNAVAILABLE"
    assert report["coverage"]["regular"]["h2h"] == "UNAVAILABLE"
    assert report["buckets"]["reserve"]["spent"] == 0
    assert report["buckets"]["coverage_debug"]["spent"] == 6
    assert report["snapshot_collection"] == "HELD"
    assert transport.sports == ["basketball_nba_preseason", "basketball_nba"]
    games = {row["id"]: row for row in Store(tmp_path / "odds.sqlite").current_body()["games"]}
    assert set(games) == {"0012600001", "0022600001"}
    assert games["0012600001"]["empty_state"] == "NO_POSTED_ODDS"
    assert games["0012600001"]["bookmaker"] is None
    assert games["0012600001"]["moneyline"] is None
    assert games["0022600001"]["empty_state"] == "NO_POSTED_ODDS"
    assert games["0022600001"]["mapping"] == "MATCHED"
    text = Path(tmp_path / "odds.sqlite").read_bytes()
    assert b"sk_" not in text


def test_modeled_prices_are_rejected_and_observed_lines_keep_the_source_time(tmp_path: Path):
    store = Store(tmp_path / "lines.sqlite")
    with pytest.raises(ValueError, match="MODELED_NOT_A_QUOTE"):
        store.add_observed_line({"recorded_at": "2026-09-23T16:00:00Z", "derivation": "MODELED", "market_key": "h2h"})
    payload = {
        "bookmakers": [
            {
                "key": "williamhill",
                "markets": [
                    {
                        "key": "h2h",
                        "last_update": "2026-10-04T18:00:00Z",
                        "outcomes": [{"name": "Boston Celtics", "price": "-150"}, {"name": "New York Knicks", "price": "130"}],
                    }
                ],
            }
        ]
    }
    lines = observed_lines_from_odds(payload, event_id="e", nba_game_id="0012600001", season_phase="preseason", retrieved_at="2026-09-23T16:00:00Z")
    assert len(lines) == 2
    assert lines[0]["source_updated_at"] == "2026-10-04T18:00:00Z"
    assert lines[0]["derivation"] == "OBSERVED"
    for line in lines:
        store.add_observed_line(line)
    assert store.observed_lines()[0]["american"] == "-150"


def test_preseason_event_without_a_william_hill_price_stays_scheduled(tmp_path: Path):
    transport = FakeTransport(
        events=[],
        preseason_events=[
            {
                "id": "pre-empty",
                "home_team": "Boston Celtics",
                "away_team": "New York Knicks",
                "commence_time": "2026-10-04T23:00:00Z",
            }
        ],
        markets={"pre-empty": {"bookmakers": []}},
    )
    store = Store(tmp_path / "scheduled.sqlite")
    rehearse(store, transport, _games(), NOW)
    row = next(game for game in store.current_body()["games"] if game["id"] == "0012600001")
    assert row["empty_state"] == "NO_POSTED_ODDS"
    assert row["bookmaker"] is None
    assert row["moneyline"] is None
    assert row["season_phase"] == "preseason"
    assert transport.odds_calls == 0
    assert transport.market_calls == 1


def test_later_schedule_merge_keeps_an_unquoted_preseason_game(tmp_path: Path):
    store = Store(tmp_path / "merge.sqlite")
    store.save_snapshot("coverage-prior", NOW, {"snapshot_id": "coverage-prior", "games": []}, {})
    merge_unquoted_schedule(store, _games(), NOW)
    games = store.current_body()["games"]
    assert [game["id"] for game in games] == ["0012600001"]
    assert games[0]["empty_state"] == "NO_POSTED_ODDS"
    merge_unquoted_schedule(store, _games(), NOW)
    assert [game["id"] for game in store.current_body()["games"]] == ["0012600001"]


def test_later_preseason_listing_is_discovered_without_repeating_a_covered_event(tmp_path: Path):
    store = Store(tmp_path / "later.sqlite")
    store.meta_set("preseason_listed", "false")
    store.add_credit(
        {
            "recorded_at": "2026-09-23T16:00:00Z",
            "bucket": "coverage_debug",
            "purpose": "prior_manual_probe",
            "endpoint": "bulk_odds",
            "credits_last": 5,
            "credits_used": 5,
            "credits_remaining": 495,
            "season_phase": "unscoped",
        }
    )
    transport = FakeTransport(
        events=[
            {
                "id": "pre-1",
                "home_team": "Boston Celtics",
                "away_team": "New York Knicks",
                "commence_time": "2026-10-04T23:00:00Z",
            }
        ],
        markets={"pre-1": {"bookmakers": []}},
    )
    first = refresh_listing(store, transport, _games(), NOW)
    second = refresh_listing(store, transport, _games(), NOW)
    assert first["found"] == 1
    assert second["checked"] is False
    assert transport.market_calls == 1
    assert store.meta_get("preseason_listed") == "true"


def test_quarter_snapshot_does_not_run_without_the_arm_flag(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ONTOLOGIC_COLLECT_SNAPSHOTS", raising=False)
    store = Store(tmp_path / "moments.sqlite")
    store.save_plan(
        {"event_id": "pre-1", "moment": "q2_open", "nba_game_id": "0012600001", "season_phase": "preseason", "status": "PLANNED"}
    )
    transport = FakeTransport(events=[])
    result = consider_moments(
        store,
        [{"event_id": "pre-1", "nba_game_id": "0012600001", "season_phase": "preseason", "status": "live", "period": 2, "clock": "12:00"}],
        transport,
        NOW,
    )
    assert result["reason"] == "SNAPSHOTS_HELD"
    assert transport.odds_calls == 0
    view = coverage_view(store, NOW)
    assert "ab6ab7" not in str(view)
