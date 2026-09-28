"""Phase 20: full NCAAB research desk acceptance.

Frontend draft → ResearchQuestion → compile → capability → ResearchContext
→ ConditionalBacktest (reference ≡ optimized) → Results contract.

Not FIRST80 P5. Not Confirm & Run CSV. Live warehouse is read-only.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from roller.config import RollerConfig
from roller.warehouse.conditional_backtest import compare_backtest_rows, run_conditional_backtest
from roller.warehouse.frontend_contract import (
    compile_frontend_research,
    execute_frontend_research,
    question_from_draft,
)
from roller.warehouse.research_compiler import compile_research

ROLLER_ROOT = Path(__file__).resolve().parents[1]
CFG = RollerConfig(ROLLER_ROOT)
LIVE = ROLLER_ROOT / "data" / "ncaab" / "2025_2026" / "derived" / "warehouse"
LIVE_SKIP = not (LIVE / "manifest.json").is_file()


def _acceptance_draft(**overrides) -> dict:
    uni = {
        "sports": ["basketball"],
        "leagues": ["NCAAB"],
        "seasons": ["2025-26"],
        "markets": ["kalshi"],
        "marketData": ["candles"],
        "dateFrom": "2025-11-03",
        "dateTo": "2025-11-30",
    }
    uni.update(overrides.pop("universe", {}))
    return {
        "universe": uni,
        "entryConditions": overrides.pop(
            "entryConditions",
            [{"id": "e1", "family": "cross", "priceCents": 65}],
        ),
        "exitConditions": overrides.pop(
            "exitConditions",
            [
                {"id": "win", "kind": "path", "family": "reach", "priceCents": 85, "outcome": "win"},
                {"id": "loss", "kind": "path", "family": "reach", "priceCents": 40, "outcome": "loss"},
            ],
        ),
        **overrides,
    }


@pytest.mark.skipif(LIVE_SKIP, reason="NCAAB Phase 8 warehouse absent")
def test_full_desk_frontend_question_to_results():
    question, errors = question_from_draft(_acceptance_draft())
    assert question is not None
    assert not errors
    assert question.universe.sports == ("NCAAB",)
    assert question.universe.leagues == ("NCAAB",)
    assert question.universe.sports != ("NBA",)
    assert question.entry_conditions[0].operation.value == "CROSS"
    assert question.entry_conditions[0].price_e4 == 6500
    assert "FIRST80" not in str(question.to_dict())

    compiled = compile_frontend_research({"question": question.to_dict()})
    assert compiled["status"] == "READY"
    assert compiled["source"] == "warehouse_research"
    assert compiled["observation_basis"] == "TRADABLE_YES_BID"
    assert compiled["capability"].get("unavailable_sport") != "NCAAB"

    executed = execute_frontend_research({"question": question.to_dict()}, include_reference=True)
    assert executed["status"] == "READY"
    assert executed["difference_count"] == 0
    contract = executed["results_contract"]
    assert contract["population"] > 0
    assert contract["statistics"]["basis"] == "observed_candle_path"
    assert "fill" in contract["statistics"]["not"]
    assert "live_trading_performance" in contract["statistics"]["not"]
    assert contract["audit_rows"]
    assert "price" not in contract["audit_rows"][0]


@pytest.mark.skipif(LIVE_SKIP, reason="NCAAB Phase 8 warehouse absent")
def test_reference_equals_optimized_row_by_row():
    question, _ = question_from_draft(_acceptance_draft())
    ref = run_conditional_backtest(question, CFG, engine_id="reference")
    opt = run_conditional_backtest(question, CFG, engine_id="optimized")
    diffs = compare_backtest_rows(ref, opt)
    assert ref.status.value == "READY"
    assert opt.status.value == "READY"
    assert ref.population == opt.population
    assert ref.result_hash == opt.result_hash
    assert len(diffs) == 0


@pytest.mark.skipif(LIVE_SKIP, reason="NCAAB Phase 8 warehouse absent")
def test_historical_l2_is_data_required():
    compiled = compile_frontend_research(
        {"draft": _acceptance_draft(universe={"marketData": ["historical_l2"]})}
    )
    assert compiled["status"] == "DATA_REQUIRED"
    assert "HISTORICAL_L2" in compiled["capability"]["missing_data"]


@pytest.mark.skipif(LIVE_SKIP, reason="NCAAB Phase 8 warehouse absent")
def test_pbp_candle_pit_is_operation_required():
    compiled = compile_frontend_research(
        {"draft": _acceptance_draft(requested_dimensions=["PBP_MARKET_PIT_ALIGNMENT"])}
    )
    assert compiled["status"] == "OPERATION_REQUIRED"
    assert "PBP_MARKET_PIT_ALIGNMENT" in compiled["capability"]["missing_operations"]


@pytest.mark.skipif(LIVE_SKIP, reason="NCAAB Phase 8 warehouse absent")
def test_zero_results_is_not_missing_data():
    executed = execute_frontend_research(
        {
            "draft": _acceptance_draft(
                universe={"dateFrom": "2024-01-01", "dateTo": "2024-01-02"},
            )
        }
    )
    assert executed["status"] == "ZERO_RESULTS"
    assert executed["results_contract"]["population"] == 0
    assert executed["status"] != "DATA_REQUIRED"


def test_source_has_no_confirm_and_run_imports():
    src = Path(__file__).resolve().parents[1] / "roller" / "warehouse" / "ncaab_desk.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any("research_query.execute" in m or m == "roller.research_query.execute" for m in imported)
    assert not any(m.endswith("load_dataset") for m in imported)
