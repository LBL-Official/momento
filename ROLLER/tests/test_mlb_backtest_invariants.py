"""Adversarial MLB backtest invariants. False numbers must not compile as truth.

Does not invent settlement. Does not treat last trade as yes bid.
Does not claim path WIN is terminal YES. Does not touch FIRST80.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from roller.research_query.compiler import compile_draft
from roller.research_query.execute import _in_date_window, _settled_yes, execute_question
from roller.research_query.models import (
    BASIS_LAST_TRADE,
    ExecutionPath,
    ResearchStatus,
    TouchOrdinal,
)
from roller.research_query.official_settlement import merge_official_settlement
from roller.research_query.season_dates import collapse_full_season_dates
from tests.test_mlb_generic_query_is_tennis_import import EXACT_MLB_DRAFT

REPO = Path(__file__).resolve().parents[1]
JOB = REPO / "data/.cache/research_query/mlb-dated-2026-04-01-2026-09-08-job.json"
WINDOW_FROM = "2026-04-01"
WINDOW_TO = "2026-09-08"


def _bar(ticker: str, gid: str, ts: str, last: int) -> dict:
    return {
        "available_at": ts,
        "candle_timestamp": ts,
        "last_close_e4": last,
        "ticker": ticker,
        "internal_game_id": gid,
        "team_side": "away",
        "is_valid": "1",
    }


def _pbp(ts: str, *, away: int = 2, home: int = 1) -> dict:
    return {
        "event_number": 1,
        "event_timestamp": ts,
        "inning": 4,
        "half": "top",
        "outs": 0,
        "balls": 0,
        "strikes": 0,
        "runner_on_1": "0",
        "runner_on_2": "0",
        "runner_on_3": "0",
        "batting_team": "away",
        "home_score": home,
        "away_score": away,
    }


def test_compile_dated_mlb_is_kalshi_last_trade_not_yes_bid():
    compiled = compile_draft(EXACT_MLB_DRAFT)
    assert compiled.status in {ResearchStatus.READY, ResearchStatus.READY_WITH_LIMITATIONS}
    assert compiled.execution_path is ExecutionPath.GENERIC_QUERY
    assert compiled.reference_match is None
    q = compiled.question
    assert q.basis() == BASIS_LAST_TRADE
    assert q.universe.date_from == WINDOW_FROM
    assert q.universe.date_to == WINDOW_TO
    assert q.entry_conditions[0].ordinal is TouchOrdinal.FIRST_TOUCH
    assert q.entry_conditions[0].price_e4 == 7500
    assert "kalshi_1m_last_trade" in compiled.available
    assert "polymarket_1m_last_trade" not in compiled.available
    assert "tradable_yes_bid_close_cross" not in compiled.available


def test_mixed_family_is_operation_required_not_n0():
    compiled = compile_draft(
        {
            **EXACT_MLB_DRAFT,
            "universe": {
                **EXACT_MLB_DRAFT["universe"],
                "sports": ["baseball", "basketball"],
                "leagues": ["MLB", "NBA"],
            },
        }
    )
    assert compiled.status is ResearchStatus.OPERATION_REQUIRED
    assert compiled.execution_path is ExecutionPath.NONE


def test_box_score_is_not_settlement():
    assert _settled_yes({"home_win": True, "final_winner": "NYY", "away_win": False}) is None
    assert _settled_yes({"result": "yes"}) is True
    assert _settled_yes({}) is None


def test_post_entry_pbp_cannot_enter_te_state():
    out = execute_question(
        EXACT_MLB_DRAFT,
        ticker_payloads={
            "KXMLBGAME-26JUN18NYYBOS-NYY": [
                _bar("KXMLBGAME-26JUN18NYYBOS-NYY", "MLB_20260618_NYY_BOS_1", "2026-06-18T23:00:00Z", 7400),
                _bar("KXMLBGAME-26JUN18NYYBOS-NYY", "MLB_20260618_NYY_BOS_1", "2026-06-18T23:01:00Z", 7500),
            ]
        },
        pbp_by_game={
            "MLB_20260618_NYY_BOS_1": [
                _pbp("2026-06-18T23:00:00Z", away=2, home=1),
                _pbp("2026-06-18T23:40:00Z", away=9, home=0),
            ]
        },
        markets_by_ticker={
            "KXMLBGAME-26JUN18NYYBOS-NYY": {"result": "yes", "internal_game_id": "MLB_20260618_NYY_BOS_1"}
        },
    )
    assert out["execution_status"] == "COMPLETE"
    te = out["population"]["trades"][0]["te"]
    assert te["point_differential"] == 1
    assert te.get("point_differential") != 9
    feat = datetime.fromisoformat(str(te["observation_ts"]).replace("Z", "+00:00"))
    entry = datetime.fromisoformat(str(out["population"]["trades"][0]["entry_ts"]).replace("Z", "+00:00"))
    assert feat <= entry


def test_path_win_is_not_used_when_settlement_missing():
    out = execute_question(
        EXACT_MLB_DRAFT,
        ticker_payloads={
            "KXMLBGAME-26JUN18NYYBOS-NYY": [
                _bar("KXMLBGAME-26JUN18NYYBOS-NYY", "MLB_20260618_NYY_BOS_1", "2026-06-18T23:00:00Z", 7400),
                _bar("KXMLBGAME-26JUN18NYYBOS-NYY", "MLB_20260618_NYY_BOS_1", "2026-06-18T23:01:00Z", 7500),
                _bar("KXMLBGAME-26JUN18NYYBOS-NYY", "MLB_20260618_NYY_BOS_1", "2026-06-18T23:02:00Z", 9000),
            ]
        },
        pbp_by_game={"MLB_20260618_NYY_BOS_1": [_pbp("2026-06-18T23:00:00Z")]},
        markets_by_ticker={},
    )
    trade = out["population"]["trades"][0]
    assert trade["terminal_yes"] is None
    assert trade["path_true"] is False
    assert trade["exit_outcome"] is None


def test_yes_bid_on_a_print_bar_does_not_become_the_basis():
    out = execute_question(
        EXACT_MLB_DRAFT,
        ticker_payloads={
            "KXMLBGAME-26JUN18NYYBOS-NYY": [
                {
                    **_bar("KXMLBGAME-26JUN18NYYBOS-NYY", "MLB_20260618_NYY_BOS_1", "2026-06-18T23:00:00Z", 7400),
                    "yes_bid_close": 9900,
                },
                {
                    **_bar("KXMLBGAME-26JUN18NYYBOS-NYY", "MLB_20260618_NYY_BOS_1", "2026-06-18T23:01:00Z", 7500),
                    "yes_bid_close": 9900,
                },
            ]
        },
        pbp_by_game={"MLB_20260618_NYY_BOS_1": [_pbp("2026-06-18T23:00:00Z")]},
        markets_by_ticker={
            "KXMLBGAME-26JUN18NYYBOS-NYY": {"result": "yes"}
        },
    )
    trade = out["population"]["trades"][0]
    assert trade["price_basis"] == BASIS_LAST_TRADE
    assert trade["entry_price_e4"] == 7500
    assert out["observation_basis"] == BASIS_LAST_TRADE
    assert out["provenance"]["market_data"] == "kalshi_1m_last_trade"
    assert out["provenance"]["market_data_type"] == "LAST_TRADE_PRINT"


def test_leading_exact_2_does_not_keep_lead_1():
    out = execute_question(
        {
            **EXACT_MLB_DRAFT,
            "teFilters": {"scoreSide": "leading", "exactDiffs": [2]},
        },
        ticker_payloads={
            "KXMLBGAME-26JUN18NYYBOS-NYY": [
                _bar("KXMLBGAME-26JUN18NYYBOS-NYY", "MLB_20260618_NYY_BOS_1", "2026-06-18T23:00:00Z", 7400),
                _bar("KXMLBGAME-26JUN18NYYBOS-NYY", "MLB_20260618_NYY_BOS_1", "2026-06-18T23:01:00Z", 7500),
            ]
        },
        pbp_by_game={"MLB_20260618_NYY_BOS_1": [_pbp("2026-06-18T23:00:00Z", away=2, home=1)]},
        markets_by_ticker={"KXMLBGAME-26JUN18NYYBOS-NYY": {"result": "yes"}},
    )
    assert out["summary"]["population_n"] == 0
    assert out["identity"]["te_scope"]["n_entry"] == 1
    assert out["identity"]["te_scope"]["n_dropped"] == 1


def test_june_stub_and_custom_window_stay_bound():
    assert collapse_full_season_dates(("MLB",), ("2025-26",), "2026-06-18", "2026-06-30") == (
        "2026-06-18",
        "2026-06-30",
    )
    assert collapse_full_season_dates(("MLB",), ("2025-26",), WINDOW_FROM, WINDOW_TO) == (
        WINDOW_FROM,
        WINDOW_TO,
    )


def test_ingest_timestamp_cannot_admit_2025_game():
    rec = {
        "internal_game_id": "MLB_20250416_ATH_CWS_1",
        "ticker": "KXMLBGAME-25APR16ATHCWS-ATH",
        "available_at": "2026-09-11T15:02:15Z",
        "ingested_at": "2026-09-11T15:02:15Z",
    }
    assert _in_date_window(rec, WINDOW_FROM, WINDOW_TO) is False


def test_official_w_does_not_invent_kxmlb_settlement():
    _, status = merge_official_settlement({}, tickers=["KXMLBGAME-26JUN18NYYBOS-NYY"])
    assert status["n_direct"] == 0
    assert status["n_complement"] == 0
    assert status["overlay_applied"] is False


def test_dated_job_artifact_matches_golden_fixture():
    from tests.mlb_golden import assert_golden_result

    if not JOB.is_file():
        return
    rec = json.loads(JOB.read_text(encoding="utf-8"))
    assert_golden_result(rec.get("result") or rec)
