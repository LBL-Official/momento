"""Regression: MLB generic_query must import sport_family.is_tennis.

The Confirm→Run crash was:

    cannot import name 'is_tennis' from 'roller.research_query.sport_family'

Compile of an MLB+league draft never entered the tennis branch, so READY
was honest for operations. Execute then lazy-imported is_tennis from
entry_engine / Base TE and raised ImportError.

This is an import contract test. It does not rewrite the question.
"""

from __future__ import annotations

from datetime import datetime, timezone

from roller.base_terminal_efficiency.builder import build_observation
from roller.research_query.compiler import compile_draft
from roller.research_query.entry_engine import TradableBar, default_snap
from roller.research_query.execute import execute_question
from roller.research_query.hashing import layer_hashes
from roller.research_query.models import (
    BASIS_LAST_TRADE,
    ExecutionPath,
    ResearchStatus,
    TouchOrdinal,
)
from roller.research_query.sport_family import is_baseball, is_tennis
from tests.mlb_golden import GOLDEN_DRAFT as EXACT_MLB_DRAFT

UTC = timezone.utc


def test_sport_family_exports_canonical_is_tennis():
    assert is_tennis("tennis") is True
    assert is_tennis("ATP") is True
    assert is_tennis("WTA") is True
    assert is_tennis("MLB") is False
    assert is_tennis("NBA") is False
    assert is_baseball("MLB") is True
    assert is_baseball("tennis") is False


def test_mlb_default_snap_lazy_imports_is_tennis():
    events = [
        {
            "event_number": 1,
            "event_timestamp": "2026-06-18T23:00:00Z",
            "inning": 7,
            "half": "top",
            "outs": 1,
            "balls": 0,
            "strikes": 0,
            "runner_on_1": "0",
            "runner_on_2": "0",
            "runner_on_3": "0",
            "batting_team": "away",
            "home_score": 1,
            "away_score": 2,
        }
    ]
    snap = default_snap(
        datetime(2026, 6, 18, 23, 1, tzinfo=UTC),
        events,
        "MLB",
        team_side="away",
    )
    assert snap["status"] == "REAL"
    assert snap.get("inning") == 7


def test_mlb_base_te_builder_lazy_imports_is_tennis():
    bar = TradableBar(
        ts=datetime(2026, 6, 18, 23, 1, tzinfo=UTC),
        bid=7500,
        ask=None,
        volume=1,
        ticker="KXMLBGAME-T-NYY",
        game_id="MLB_G1",
        raw={"team_side": "away", "last_close_e4": 7500},
        basis=BASIS_LAST_TRADE,
    )
    events = [
        {
            "event_number": 1,
            "event_timestamp": "2026-06-18T23:00:00Z",
            "inning": 7,
            "half": "top",
            "outs": 1,
            "balls": 0,
            "strikes": 0,
            "runner_on_1": "0",
            "runner_on_2": "0",
            "runner_on_3": "0",
            "batting_team": "away",
            "home_score": 1,
            "away_score": 2,
        }
    ]
    obs = build_observation([bar], pbp_events=events, sport="MLB")
    assert obs is not None
    assert obs.point_differential == 1


def test_exact_mlb_draft_compiles_last_trade_first_touch_75():
    compiled = compile_draft(EXACT_MLB_DRAFT)
    assert compiled.status in {ResearchStatus.READY, ResearchStatus.READY_WITH_LIMITATIONS}
    assert compiled.execution_path is ExecutionPath.GENERIC_QUERY
    q = compiled.question
    assert q.basis() == BASIS_LAST_TRADE
    assert len(q.entry_conditions) == 1
    entry = q.entry_conditions[0]
    assert entry.ordinal is TouchOrdinal.FIRST_TOUCH
    assert entry.price_e4 == 7500
    assert any(p.price_e4 == 4000 for p in q.path_conditions)
    assert q.win_hold
    assert q.universe.date_from == "2026-04-01"
    assert q.universe.date_to == "2026-09-08"
    assert "kalshi_1m_last_trade" in compiled.available
    assert "polymarket_1m_last_trade" not in compiled.available
    assert "tradable_yes_bid_close_cross" not in compiled.available
    hashes = layer_hashes(q, state=EXACT_MLB_DRAFT["teFilters"])
    assert hashes["question_hash"]
    assert hashes["entry_hash"]


def test_exact_mlb_draft_executes_without_is_tennis_import_error():
    out = execute_question(
        EXACT_MLB_DRAFT,
        ticker_payloads={
            "KXMLBGAME-T-NYY": [
                {
                    "available_at": "2026-06-18T23:00:00Z",
                    "last_close_e4": 7400,
                    "ticker": "KXMLBGAME-T-NYY",
                    "internal_game_id": "MLB_G1",
                    "team_side": "away",
                    "is_valid": "1",
                },
                {
                    "available_at": "2026-06-18T23:01:00Z",
                    "last_close_e4": 7500,
                    "ticker": "KXMLBGAME-T-NYY",
                    "internal_game_id": "MLB_G1",
                    "team_side": "away",
                    "is_valid": "1",
                },
                {
                    "available_at": "2026-06-18T23:02:00Z",
                    "last_close_e4": 4000,
                    "ticker": "KXMLBGAME-T-NYY",
                    "internal_game_id": "MLB_G1",
                    "team_side": "away",
                    "is_valid": "1",
                },
            ]
        },
        pbp_by_game={
            "MLB_G1": [
                {
                    "event_number": 1,
                    "event_timestamp": "2026-06-18T23:00:00Z",
                    "inning": 7,
                    "half": "top",
                    "outs": 1,
                    "balls": 0,
                    "strikes": 0,
                    "runner_on_1": "0",
                    "runner_on_2": "0",
                    "runner_on_3": "0",
                    "batting_team": "away",
                    "home_score": 1,
                    "away_score": 2,
                }
            ]
        },
        markets_by_ticker={
            "KXMLBGAME-T-NYY": {"result": "yes", "internal_game_id": "MLB_G1"}
        },
    )
    assert out["execution_status"] == "COMPLETE"
    assert out["observation_basis"] == BASIS_LAST_TRADE
    assert out["compile"]["execution_path"] == ExecutionPath.GENERIC_QUERY.value
    n = out["summary"]["population_n"]
    assert n == 1
    trade = out["population"]["trades"][0]
    te = trade["te"]
    assert te["point_differential"] == 1
    feat = datetime.fromisoformat(str(te["observation_ts"]).replace("Z", "+00:00"))
    entry = datetime.fromisoformat(str(trade["entry_ts"]).replace("Z", "+00:00"))
    assert feat <= entry
    assert te.get("entry_price_e4") == 7500
    prov = out["provenance"]
    assert prov["market_data"] == "kalshi_1m_last_trade"
    assert prov["market_data_type"] == "LAST_TRADE_PRINT"
    assert prov["price_rule"] == "last_trade_close_cross"
    assert "polymarket" not in str(prov["market_data"])
    assert "LAST TRADE ≠ YES BID" in " ".join(out["caveats"])
