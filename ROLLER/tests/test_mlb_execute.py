"""MLB generic execute on synthetic + one real fixture."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from roller.mlb.leakage import audit_snap
from roller.mlb.validate import validate_pbp_rows
from roller.research_query.compiler import compile_draft
from roller.research_query.execute import execute_compiled
from roller.research_query.models import BASIS_LAST_TRADE, ResearchStatus

UTC = timezone.utc


def _print_bar(i: int, last: int, *, ticker="KXMLBGAME-T-NYY", game="MLB_G1"):
    return {
        "available_at": f"2026-06-18T23:{i:02d}:00Z",
        "last_close_e4": last,
        "ticker": ticker,
        "internal_game_id": game,
        "team_side": "away",
        "is_valid": "1",
    }


def _pbp_row(ts: str, **kw):
    row = {
        "event_number": 1,
        "event_timestamp": ts,
        "inning": 7,
        "half": "top",
        "outs": 2,
        "balls": 1,
        "strikes": 2,
        "runner_on_1": "0",
        "runner_on_2": "1",
        "runner_on_3": "0",
        "runners": "2nd",
        "batting_team": "away",
        "home_score": 1,
        "away_score": 3,
    }
    row.update(kw)
    return row


def test_synthetic_mlb_execute_complete():
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["last_trade"],
            },
            "entryConditions": [
                {
                    "id": "e1",
                    "family": "cross",
                    "priceCents": 80,
                    "period": "T7",
                    "direction": "up",
                }
            ],
            "exitConditions": [
                {"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"},
                {"id": "p2", "kind": "path", "family": "drop_to", "priceCents": 40, "outcome": "loss"},
            ],
            "teFilters": {"scoreSide": "leading", "exactDiffs": [2], "outs": [2], "runners": "risp"},
        }
    )
    assert compiled.status in {ResearchStatus.READY, ResearchStatus.READY_WITH_LIMITATIONS, ResearchStatus.DATA_REQUIRED}
    compiled.question  # compiled even if DATA_REQUIRED when warehouse missing
    q = compiled.question.on_last_trade_basis() if compiled.question.basis() != BASIS_LAST_TRADE else compiled.question
    from roller.research_query.models import CompileResult, ExecutionPath

    forced = CompileResult(
        status=ResearchStatus.READY,
        execution_path=ExecutionPath.GENERIC_QUERY,
        reference_match=None,
        question=q,
        reasons=[],
        unavailable=[],
    )
    pbp = [_pbp_row("2026-06-18T23:01:00Z")]
    out = execute_compiled(
        forced,
        ticker_payloads={
            "KXMLBGAME-T-NYY": [_print_bar(0, 7900), _print_bar(1, 8000), _print_bar(2, 9000)],
        },
        pbp_by_game={"MLB_G1": pbp},
        markets_by_ticker={"KXMLBGAME-T-NYY": {"result": "yes", "internal_game_id": "MLB_G1"}},
        games=[{"internal_game_id": "MLB_G1", "league": "MLB", "sport": "MLB"}],
        te_filters={"scoreSide": "leading", "exactDiffs": [2], "outs": [2], "runners": "risp"},
    )
    assert out["execution_status"] == "COMPLETE"
    assert out["observation_basis"] == BASIS_LAST_TRADE
    assert out["mlb"]["funnel"]["entry_candidates"] >= 0
    assert "LAST TRADE ≠ YES BID" in " ".join(out["caveats"])
    trades = out["population"]["trades"]
    assert trades
    te = trades[0]["te"]
    assert te["outs"] == 2
    assert te["yes_batting"] is True
    assert te["point_differential"] == 2
    assert te.get("point_differential_unit") == "runs"


def test_missing_ticker_not_silent(monkeypatch):
    from roller.research_query.models import CompileResult, ExecutionPath
    from tests.test_mlb_te_hash import test_mixed_nba_mlb_operation_required  # noqa: F401

    compiled = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["last_trade"],
            },
            "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 80, "direction": "up"}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"}],
        }
    )
    q = compiled.question.on_last_trade_basis()
    forced = CompileResult(
        status=ResearchStatus.READY,
        execution_path=ExecutionPath.GENERIC_QUERY,
        reference_match=None,
        question=q,
        reasons=[],
        unavailable=[],
    )
    out = execute_compiled(
        forced,
        ticker_payloads={"": []},
        pbp_by_game={},
        markets_by_ticker={},
        games=[{"internal_game_id": "MLB_ORPHAN"}],
    )
    assert out["execution_status"] == "COMPLETE"
    assert out["mlb"]["exclusions"]["NO_MARKET"] >= 1


def test_real_pbp_fixture_parses():
    path = Path(
        "/Users/user/Desktop/Momento/Backtesting Suite/Foundation/Ingest/landing/mlb_statsapi/"
        "date=2026-06-18/gamePk=823448.envelope.json"
    )
    if not path.is_file():
        pytest.skip("real June 18 PBP envelope not on disk")
    from roller.mlb.pbp import parse_file

    rows = parse_file(path, internal_game_id="MLB_TEST", ingested_at="t", pipeline_version="t")
    assert rows
    rep = validate_pbp_rows(rows)
    assert rep["ok"], rep["issues"][:5]
    entry = datetime.fromisoformat(rows[10]["event_timestamp"].replace("Z", "+00:00"))
    audit = audit_snap(rows, entry)
    assert audit["ok"]
    if not audit["exclude"]:
        assert audit["snap"]["event_timestamp"]
        feat = datetime.fromisoformat(str(audit["snap"]["event_timestamp"]).replace("Z", "+00:00"))
        assert feat <= entry


def test_real_fixture_execute_if_warehouse_present():
    from roller.config import RollerConfig
    from roller.research_query.availability import baseball_warehouse_ready

    cfg = RollerConfig()
    if not baseball_warehouse_ready(cfg):
        pytest.skip("MLB canonical warehouse not ingested yet")
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["last_trade"],
                "dateFrom": "2026-06-18",
                "dateTo": "2026-06-18",
            },
            "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 80, "direction": "up"}],
            "exitConditions": [
                {"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"},
                {"id": "hold", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
            ],
        },
        cfg=cfg,
    )
    assert compiled.status in {ResearchStatus.READY, ResearchStatus.READY_WITH_LIMITATIONS}
    out = execute_compiled(compiled, cfg=cfg)
    assert out["execution_status"] == "COMPLETE"
    assert out["observation_basis"] == BASIS_LAST_TRADE
    assert out["mlb"]["funnel"]["games"] >= 1
    n = out["summary"]["population_n"]
    assert n is not None
    assert "LAST-TRADE PRINT OBSERVED" in (out["summary"]["population_description"] or "")
    te_scope = (out.get("identity") or {}).get("te_scope") or {}
    assert n == te_scope.get("n_scoped", n)
    assert out["mlb"]["funnel"]["universe"] == out["identity"]["universe_tickers"]
    assert out["mlb"]["funnel"]["games"] < 4315


def test_empty_volume_candles_are_data_required_not_silent_n0():
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
            },
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90}],
        }
    )
    assert compiled.status in {
        ResearchStatus.DATA_REQUIRED,
        ResearchStatus.READY,
        ResearchStatus.READY_WITH_LIMITATIONS,
    }
    if compiled.status is ResearchStatus.DATA_REQUIRED:
        assert any("volume" in r.lower() or "quality" in r.lower() or "candle" in r.lower() for r in compiled.reasons)
    from roller.research_query.models import CompileResult, ExecutionPath

    q = compiled.question
    forced = CompileResult(
        status=ResearchStatus.READY,
        execution_path=ExecutionPath.GENERIC_QUERY,
        reference_match=None,
        question=q,
        reasons=[],
        unavailable=[],
    )
    candles = [
        {
            "available_at": "2026-06-18T23:00:00Z",
            "yes_bid_close": 8000,
            "yes_ask_close": 8100,
            "volume": "",
            "ticker": "KXMLBGAME-T-NYY",
            "internal_game_id": "MLB_G1",
        },
        {
            "available_at": "2026-06-18T23:01:00Z",
            "yes_bid_close": 8100,
            "yes_ask_close": 8200,
            "volume": "",
            "ticker": "KXMLBGAME-T-NYY",
            "internal_game_id": "MLB_G1",
        },
    ]
    out = execute_compiled(
        forced,
        ticker_payloads={"KXMLBGAME-T-NYY": candles},
        pbp_by_game={"MLB_G1": [_pbp_row("2026-06-18T23:00:00Z")]},
        markets_by_ticker={"KXMLBGAME-T-NYY": {"result": "yes", "internal_game_id": "MLB_G1"}},
        games=[{"internal_game_id": "MLB_G1", "league": "MLB", "sport": "MLB"}],
    )
    assert out["execution_status"] == "DATA_REQUIRED"
    assert out["summary"]["population_n"] is None
    assert out["population"]["status"] != "COMPLETE" or out["population"]["count"] == 0
    text = " ".join([out["summary"]["population_description"] or "", *(out.get("caveats") or [])])
    assert "UNTRADABLE" in text
    assert out["mlb"]["exclusions"]["UNTRADABLE_CANDLES"] >= 1


def test_last_trade_first_touch_80_finds_crossing():
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["last_trade"],
            },
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90}],
        }
    )
    from roller.research_query.models import CompileResult, ExecutionPath

    q = compiled.question.on_last_trade_basis()
    forced = CompileResult(
        status=ResearchStatus.READY,
        execution_path=ExecutionPath.GENERIC_QUERY,
        reference_match=None,
        question=q,
        reasons=[],
        unavailable=[],
    )
    out = execute_compiled(
        forced,
        ticker_payloads={
            "KXMLBGAME-T-NYY": [_print_bar(0, 7900), _print_bar(1, 8000), _print_bar(2, 9000)],
        },
        pbp_by_game={"MLB_G1": [_pbp_row("2026-06-18T23:01:00Z")]},
        markets_by_ticker={"KXMLBGAME-T-NYY": {"result": "yes", "internal_game_id": "MLB_G1"}},
        games=[{"internal_game_id": "MLB_G1", "league": "MLB", "sport": "MLB"}],
    )
    assert out["execution_status"] == "COMPLETE"
    assert out["summary"]["population_n"] == 1
    assert out["observation_basis"] == BASIS_LAST_TRADE


def test_done_line_n_is_te_scoped():
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["last_trade"],
            },
            "entryConditions": [
                {
                    "id": "e1",
                    "family": "cross",
                    "priceCents": 80,
                    "periodWindows": [{"period": "T7"}, {"period": "B7"}],
                    "direction": "up",
                }
            ],
            "exitConditions": [
                {"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"},
                {"id": "hold", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
            ],
            "teFilters": {
                "scoreSide": "leading",
                "exactDiffs": [2],
                "outs": [2],
                "runners": "risp",
            },
        }
    )
    from roller.research_query.models import CompileResult, ExecutionPath

    q = compiled.question.on_last_trade_basis()
    forced = CompileResult(
        status=ResearchStatus.READY,
        execution_path=ExecutionPath.GENERIC_QUERY,
        reference_match=None,
        question=q,
        reasons=[],
        unavailable=[],
    )
    out = execute_compiled(
        forced,
        ticker_payloads={
            "KXMLBGAME-T-NYY": [_print_bar(0, 7900), _print_bar(1, 8000), _print_bar(2, 9000)],
        },
        pbp_by_game={"MLB_G1": [_pbp_row("2026-06-18T23:01:00Z")]},
        markets_by_ticker={"KXMLBGAME-T-NYY": {"result": "yes", "internal_game_id": "MLB_G1"}},
        games=[{"internal_game_id": "MLB_G1", "league": "MLB", "sport": "MLB"}],
        te_filters={"scoreSide": "leading", "exactDiffs": [2], "outs": [2], "runners": "risp"},
    )
    assert out["execution_status"] == "COMPLETE"
    n = out["summary"]["population_n"]
    te_scope = out["identity"]["te_scope"]
    assert n == te_scope["n_scoped"]
    assert te_scope["n_entry"] >= n
    assert n == 1
    assert "LAST-TRADE PRINT OBSERVED" in (out["summary"]["population_description"] or "")
