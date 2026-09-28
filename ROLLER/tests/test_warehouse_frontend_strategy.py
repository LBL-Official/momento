"""Phase 19: frontend constructs ResearchQuestion; backend compiles/executes.

No Confirm & Run rewrite. No FIRST80 primitive. No detector math in the UI contract.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from roller.config import RollerConfig
from roller.research_query.models import (
    EntryCondition,
    EntryOp,
    ExitOutcome,
    PathCondition,
    PathOp,
    ResearchQuestion,
    ResearchStatus,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)
from roller.warehouse.coverage import OBS_BASIS, PIT_FIELD
from roller.warehouse.frontend_contract import (
    compile_frontend_research,
    execute_frontend_research,
    question_from_draft,
    question_from_payload,
    syntactic_errors,
)
from roller.warehouse.research_compiler import compile_research

ROLLER_ROOT = Path(__file__).resolve().parents[1]
CFG = RollerConfig(ROLLER_ROOT)
LIVE = ROLLER_ROOT / "data" / "nba" / "2025_2026" / "derived" / "warehouse"
LIVE_SKIP = not (LIVE / "manifest.json").is_file()


def _draft(**kwargs) -> dict:
    uni = {
        "sports": ["NBA"],
        "leagues": ["NBA"],
        "seasons": ["2025-26"],
        "markets": ["kalshi"],
        "marketData": ["candles"],
        "dateFrom": "2025-10-10",
        "dateTo": "2025-10-10",
    }
    uni.update(kwargs.pop("universe", {}))
    return {
        "universe": uni,
        "entryConditions": kwargs.pop(
            "entryConditions",
            [{"id": "e1", "family": "cross", "priceCents": 63, "period": "Q2"}],
        ),
        "exitConditions": kwargs.pop(
            "exitConditions",
            [
                {"id": "win", "kind": "path", "family": "reach", "priceCents": 87, "outcome": "win"},
                {"id": "loss", "kind": "path", "family": "reach", "priceCents": 41, "outcome": "loss"},
                {"id": "term", "kind": "terminal", "family": "both"},
            ],
        ),
        **kwargs,
    }


def test_ui_basketball_sport_nba_league_maps_universe():
    """Quick Start stores sport=basketball + league=NBA. Warehouse identity is NBA."""
    question, errors = question_from_draft(
        _draft(universe={"sports": ["basketball"], "leagues": ["NBA"]})
    )
    assert question is not None
    assert "missing_threshold" not in errors
    assert question.universe.sports == ("NBA",)
    assert question.universe.leagues == ("NBA",)
    ncaab, _ = question_from_draft(
        _draft(universe={"sports": ["basketball"], "leagues": ["NCAAB"]})
    )
    assert ncaab is not None
    assert ncaab.universe.sports == ("NCAAB",)
    assert ncaab.universe.leagues == ("NCAAB",)
    assert ncaab.universe.sports != ("NBA",)


def test_strategy_construction_from_draft():
    question, errors = question_from_draft(_draft())
    assert question is not None
    assert "missing_threshold" not in errors
    assert question.universe.seasons == ("2025-2026",)
    assert question.universe.market_data == ("candles",)
    assert question.entry_conditions[0].operation is EntryOp.CROSS
    assert question.entry_conditions[0].price_e4 == 6300
    assert question.entry_conditions[0].period == "Q2"
    assert question.path_conditions[0].op is PathOp.REACH
    assert question.path_conditions[0].outcome is ExitOutcome.WIN
    assert question.path_conditions[1].price_e4 == 4100
    assert "HOLD_TO_SETTLEMENT" in question.requested_dimensions


def test_research_question_serialization_roundtrip():
    question, _ = question_from_draft(_draft())
    again = ResearchQuestion.from_dict(question.to_dict())
    assert again.to_dict() == question.to_dict()
    payload_q, errors = question_from_payload({"question": question.to_dict()})
    assert errors == []
    assert payload_q is not None
    assert payload_q.to_dict() == question.to_dict()


def test_invalid_strategy_validation():
    missing, errors = question_from_draft(_draft(entryConditions=[{"id": "e1", "family": "cross"}]))
    assert "missing_threshold" in errors
    bad_dates, date_errors = question_from_draft(
        _draft(universe={"dateFrom": "2025-11-01", "dateTo": "2025-10-01"})
    )
    assert "malformed_date_range" in date_errors
    no_exit, exit_errors = question_from_draft(_draft(exitConditions=[]))
    assert "missing_win_exit" in exit_errors
    assert "missing_loss_exit" in exit_errors
    period, period_errors = question_from_draft(
        _draft(entryConditions=[{"id": "e1", "family": "cross", "priceCents": 63, "period": "QX"}])
    )
    assert "invalid_period" in period_errors
    ncaab_slices, ncaab_errors = question_from_draft(
        _draft(
            universe={
                "sports": ["basketball"],
                "leagues": ["NCAAB"],
                "seasons": ["2025-26"],
                "dateFrom": "2025-03-18",
                "dateTo": "2026-09-01",
            },
            entryConditions=[
                {
                    "id": "e1",
                    "family": "first_touch",
                    "priceCents": 85,
                    "maxEntryCents": 90,
                    "periodWindows": [{"period": "H2_1"}, {"period": "H1_2"}],
                }
            ],
            exitConditions=[
                {"id": "loss", "kind": "path", "family": "reach", "priceCents": 40, "outcome": "loss"},
                {"id": "win", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
            ],
        )
    )
    assert "invalid_period" not in ncaab_errors
    assert ncaab_slices is not None
    assert [w.period for w in ncaab_slices.entry_conditions[0].period_windows] == ["H2_1", "H1_2"]
    assert ncaab_slices.entry_conditions[0].max_entry_e4 == 9000
    assert ncaab_slices.win_hold is True
    compiled = compile_frontend_research({"question": ncaab_slices.to_dict()})
    assert "invalid_period" not in compiled.get("syntactic_errors", [])
    assert compiled["status"] != "INVALID"
    clock, clock_errors = question_from_draft(
        _draft(
            entryConditions=[
                {
                    "id": "e1",
                    "family": "cross",
                    "priceCents": 63,
                    "clockFrom": "xx",
                    "clockTo": "yy",
                }
            ]
        )
    )
    assert "invalid_clock" in clock_errors
    bare = syntactic_errors(
        ResearchQuestion(
            universe=Universe(
                sports=("NBA",),
                leagues=("NBA",),
                seasons=("2025-2026",),
                markets=("kalshi",),
                market_data=("candles",),
            ),
            entry_conditions=(),
            path_conditions=(),
            terminal=TerminalOutcome.BOTH,
        )
    )
    assert "missing_entry" in bare
    assert "missing_win_exit" in bare


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_capability_ready_display():
    compiled = compile_frontend_research({"draft": _draft(entryConditions=[{"id": "e1", "family": "cross", "priceCents": 63}])})
    assert compiled["status"] == ResearchStatus.READY.value
    assert compiled["capability"]["status"] == ResearchStatus.READY.value
    assert compiled["observation_basis"] == OBS_BASIS
    assert compiled["pit_field"] == PIT_FIELD
    assert compiled["source"] == "warehouse_research"


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_capability_data_required_display():
    compiled = compile_frontend_research(
        {
            "draft": _draft(
                universe={"marketData": ["historical_l2"]},
                entryConditions=[{"id": "e1", "family": "cross", "priceCents": 63}],
            )
        }
    )
    assert compiled["status"] == ResearchStatus.DATA_REQUIRED.value
    assert "HISTORICAL_L2" in compiled["capability"]["missing_data"]
    executed = execute_frontend_research(
        {
            "draft": _draft(
                universe={"marketData": ["historical_l2"]},
                entryConditions=[{"id": "e1", "family": "cross", "priceCents": 63}],
            )
        }
    )
    assert executed["status"] == "DATA_REQUIRED"
    assert executed["result"] is None


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_capability_operation_required_display():
    compiled = compile_frontend_research(
        {
            "draft": _draft(
                entryConditions=[{"id": "e1", "family": "cross", "priceCents": 63}],
                requested_dimensions=["PBP_MARKET_PIT_ALIGNMENT"],
            )
        }
    )
    assert compiled["status"] == ResearchStatus.OPERATION_REQUIRED.value
    assert "PBP_MARKET_PIT_ALIGNMENT" in compiled["capability"]["missing_operations"]


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_zero_results_state():
    """Valid Q2 CROSS on 2025-10-10 is executable and population 0."""
    executed = execute_frontend_research({"draft": _draft()})
    assert executed["status"] == "ZERO_RESULTS"
    assert executed["result"]["population"] == 0
    assert executed["results_contract"]["population"] == 0
    assert executed["plan_hash"]
    assert executed["status"] != "DATA_REQUIRED"
    assert executed["status"] != "OPERATION_REQUIRED"


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_backend_submission_and_result_rendering():
    executed = execute_frontend_research(
        {"draft": _draft(entryConditions=[{"id": "e1", "family": "cross", "priceCents": 63}])}
    )
    assert executed["status"] == "READY"
    contract = executed["results_contract"]
    assert contract["population"] == 7
    assert contract["classification"]["WIN"] == 1
    assert contract["classification"]["LOSS"] == 6
    assert contract["statistics"]["W"] == 1
    assert contract["statistics"]["L"] == 6
    assert contract["statistics"]["win_rate"] == pytest.approx(1 / 7)
    assert contract["statistics"]["loss_rate"] == pytest.approx(6 / 7)
    assert contract["statistics"]["rr"] == pytest.approx(24 / 22)
    assert contract["statistics"]["basis"] == "observed_candle_path"
    assert "fill" in contract["statistics"]["not"]
    assert contract["observation_basis"] == OBS_BASIS
    assert contract["pit_field"] == PIT_FIELD
    assert contract["coverage"]["executed_population"] == 7
    assert "exclusions" in contract
    assert contract["audit_rows"]
    row = contract["audit_rows"][0]
    for key in (
        "internal_game_id",
        "market_id",
        "entry_timestamp",
        "entry_value",
        "entry_operation",
        "classification",
        "settlement_status",
        "observation_basis",
        "pit_field",
    ):
        assert key in row
    assert "price" not in row
    assert contract["reproducibility"]["result_hash"]
    assert contract["reproducibility"]["plan_hash"] == executed["plan_hash"]


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_row_level_audit_and_coverage():
    executed = execute_frontend_research(
        {"draft": _draft(entryConditions=[{"id": "e1", "family": "cross", "priceCents": 63}])}
    )
    rows = executed["results_contract"]["audit_rows"]
    assert len(rows) == 7
    assert {r["classification"] for r in rows} == {"WIN", "LOSS"}
    cov = executed["results_contract"]["coverage"]
    assert cov["nominal_universe"]["games"] == 1362
    assert cov["nominal_universe"]["markets"] == 2724
    assert isinstance(cov["exclusions"], dict)


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_previously_unseen_generic_strategy():
    """BREAK 71¢ / REACH 90 / DROP 35 — not a frozen historical primitive."""
    draft = _draft(
        entryConditions=[{"id": "e1", "family": "break", "priceCents": 71}],
        exitConditions=[
            {"id": "win", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"},
            {"id": "loss", "kind": "path", "family": "drop_to", "priceCents": 35, "outcome": "loss"},
            {"id": "term", "kind": "terminal", "family": "both"},
        ],
    )
    question, errors = question_from_draft(draft)
    assert question is not None
    assert not [e for e in errors if e in {"missing_threshold", "missing_entry"}]
    assert question.entry_conditions[0].operation is EntryOp.BREAK
    assert question.entry_conditions[0].price_e4 == 7100
    assert question.path_conditions[1].op is PathOp.DROP_TO
    plan = compile_research(question, CFG)
    compiled = compile_frontend_research({"question": question.to_dict()})
    assert compiled["status"] == plan.status.value
    assert compiled["plan_hash"] == plan.plan_hash
    assert "FIRST80" not in str(question.to_dict())
    executed = execute_frontend_research({"question": question.to_dict()})
    assert executed["status"] in {"READY", "ZERO_RESULTS"}
    assert executed["source"] == "warehouse_research"
    assert executed["results_contract"]["entry"][0]["op"] == "BREAK"


def test_no_first80_or_confirm_and_run_in_contract():
    src = Path(__file__).resolve().parents[1] / "roller" / "warehouse" / "frontend_contract.py"
    text = src.read_text(encoding="utf-8")
    for token in ("FIRST80", "FIRST75", "FIRST01", "T40", "Lebronner", "PADE"):
        assert token not in text
    tree = ast.parse(text)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "roller.research_query.execute" not in imported
    assert "roller.research_query.compiler" not in imported
    assert "roller.admin" not in imported


def test_frontend_constructor_has_no_hardcoded_primitives():
    src = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "roller-terminal"
        / "src"
        / "v2"
        / "warehouse"
        / "researchQuestionFromDraft.ts"
    )
    text = src.read_text(encoding="utf-8")
    for token in ("FIRST80", "FIRST75", "FIRST01", "T40", "Lebronner", "PADE", "DRE"):
        assert token not in text
    assert "CROSS" in text
    assert "BREAK" in text
