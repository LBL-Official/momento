"""Phase 16: new warehouse-backed execution is parquet-only.

Confirm & Run remains CSV. This file does not delete live CSV.
Isolation tests for execute / load_dataset stay in test_warehouse_entities.py.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from roller.admin import load_dataset
from roller.config import RollerConfig
from roller.research_query.models import (
    EntryCondition,
    EntryOp,
    ExitOutcome,
    PathCondition,
    PathOp,
    ResearchQuestion,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)
from roller.warehouse.conditional_backtest import compare_backtest_rows, run_conditional_backtest
from roller.warehouse.query_context import clear_context_cache, get_research_context
from roller.warehouse.research_compiler import compile_research

ROLLER_ROOT = Path(__file__).resolve().parents[1]
CFG = RollerConfig(ROLLER_ROOT)
WAREHOUSE = ROLLER_ROOT / "data" / "nba" / "2025_2026" / "derived" / "warehouse"
Q2_PLAN_HASH = "4547787d8dfdb8c40717d7321e399179e868a67f0b069cadabc3f7964f9ffa67"
DATE_PLAN_HASH = "d8c10b912b20a45b0f9909cb759f2dee8a23298cd55df21ab94feb9e2432a35a"


def _question(*, period=None, game_data=()) -> ResearchQuestion:
    return ResearchQuestion(
        universe=Universe(
            sports=("NBA",),
            leagues=("NBA",),
            seasons=("2025-2026",),
            markets=("kalshi",),
            market_data=("candles",),
            game_data=game_data,
            date_from="2025-10-10",
            date_to="2025-10-10",
        ),
        entry_conditions=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=6300,
                period=period,
                operation=EntryOp.CROSS,
            ),
        ),
        path_conditions=(
            PathCondition(id="win", op=PathOp.REACH, price_e4=8700, outcome=ExitOutcome.WIN),
            PathCondition(id="loss", op=PathOp.REACH, price_e4=4100, outcome=ExitOutcome.LOSS),
        ),
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=("HOLD_TO_SETTLEMENT",),
    )


def _boom(*_args, **_kwargs):
    raise AssertionError("warehouse-backed path touched CSV / rq_index / FIRST80")


@pytest.mark.skipif(not (WAREHOUSE / "manifest.json").is_file(), reason="Phase 8 warehouse absent")
def test_warehouse_path_runs_when_csv_rq_index_first80_unavailable(monkeypatch):
    monkeypatch.setattr("roller.admin.load_dataset", _boom)
    monkeypatch.setattr("roller.warehouse.loader.load_dataset", _boom)
    monkeypatch.setattr("roller.warehouse.catalog.catalog", _boom)
    monkeypatch.setattr("roller.research.first80.run_first80", _boom, raising=False)
    import roller.research_query as rq

    if hasattr(rq, "first80"):
        monkeypatch.setattr(rq, "first80", type("X", (), {"run_first80": staticmethod(_boom)}))

    clear_context_cache()
    q = _question()
    plan = compile_research(q, CFG)
    loaded = get_research_context(q, CFG, plan=plan)
    result = run_conditional_backtest(q, CFG, engine_id="optimized")
    assert plan.status.value == "READY"
    assert loaded.status.value == "READY"
    assert loaded.context is not None
    assert loaded.context.observations
    assert result.population == 7
    assert plan.plan_hash == DATE_PLAN_HASH


@pytest.mark.skipif(not (WAREHOUSE / "manifest.json").is_file(), reason="Phase 8 warehouse absent")
def test_live_q2_reference_equals_optimized():
    clear_context_cache()
    q = _question(period="Q2", game_data=("pbp",))
    plan = compile_research(q, CFG)
    ref = run_conditional_backtest(q, CFG, engine_id="reference")
    opt = run_conditional_backtest(q, CFG, engine_id="optimized")
    assert plan.plan_hash == Q2_PLAN_HASH
    assert compare_backtest_rows(ref, opt) == []
    assert ref.population == opt.population == 0
    assert ref.result_hash == opt.result_hash == "1b0ce3dc4fb863a2c9b7517669ca1e5936a02d07dab4905d896ab2dc8894a0f6"
    man = __import__("json").loads((WAREHOUSE / "manifest.json").read_text(encoding="utf-8"))
    assert man["updated_at"]
    assert man.get("pbp_pit_aligned_to_candles") is False


def test_query_context_source_is_parquet_only():
    src = inspect.getsource(get_research_context)
    assert "read_csv" not in src
    assert "load_dataset" not in src
    assert "rq_index" not in src
    assert "first80" not in src
    qc = (ROLLER_ROOT / "roller" / "warehouse" / "query_context.py").read_text(encoding="utf-8")
    assert "read_parquet" in qc
    assert "FIRST80" not in qc
    assert "rq_index" not in qc


def test_load_dataset_still_csv():
    src = inspect.getsource(load_dataset)
    assert "read_parquet" not in src
    assert "ResearchContext" not in src
    assert "GameMarketLink" not in src


def test_live_execute_paths_do_not_import_entities():
    root = ROLLER_ROOT / "roller"
    forbidden = {
        "roller.warehouse.entities",
        "roller.warehouse.query_context",
        "roller.warehouse.conditional_backtest",
        "roller.warehouse.research_compiler",
        "roller.warehouse.coverage",
        "roller.warehouse.auto_ingest",
        "roller.warehouse.auto_verify",
        "roller.warehouse.frontend_contract",
        "roller.warehouse.layout",
    }
    for rel in (
        "admin.py",
        "research_query/execute.py",
        "research_query/compiler.py",
        "research_query/planner.py",
        "research_query/official_settlement.py",
        "research/first80.py",
    ):
        tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        assert imported.isdisjoint(forbidden), rel
