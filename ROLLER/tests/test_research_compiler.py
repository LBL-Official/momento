"""Phase 11 isolated research compiler. Plans only. No execute. No FIRST80."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from roller.admin import load_dataset
from roller.config import RollerConfig
from roller.research_query.models import (
    ClockWindow,
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
from roller.warehouse.catalog import get_catalog
from roller.warehouse.coverage import CapabilityName
from roller.warehouse.query_context import get_research_context
from roller.warehouse.research_compiler import (
    COMPILER_VERSION,
    TerminalBehavior,
    compile_research,
)

ROLLER_ROOT = Path(__file__).resolve().parents[1]
CFG = RollerConfig(ROLLER_ROOT)


def _universe(**kwargs) -> Universe:
    base = dict(
        sports=("NBA",),
        leagues=("NBA",),
        seasons=("2025-2026",),
        markets=("kalshi",),
        market_data=("candles",),
        game_data=("pbp",),
        date_from="2025-10-10",
        date_to="2025-10-10",
    )
    base.update(kwargs)
    return Universe(**base)


def _entry(op: EntryOp | None = EntryOp.CROSS, *, ordinal: TouchOrdinal = TouchOrdinal.FIRST_TOUCH, **kwargs) -> EntryCondition:
    fields = dict(
        id=kwargs.pop("id", "e1"),
        ordinal=ordinal,
        price_e4=kwargs.pop("price_e4", 6300),
        period=kwargs.pop("period", "Q2"),
        operation=op,
    )
    fields.update(kwargs)
    return EntryCondition(**fields)


def _question(*, entries=None, paths=None, requested_dimensions=("HOLD_TO_SETTLEMENT",), **universe_kw) -> ResearchQuestion:
    return ResearchQuestion(
        universe=_universe(**universe_kw),
        entry_conditions=entries
        or (
            _entry(),
        ),
        path_conditions=paths
        or (
            PathCondition(id="win", op=PathOp.REACH, price_e4=8700, outcome=ExitOutcome.WIN),
            PathCondition(id="loss", op=PathOp.REACH, price_e4=4100, outcome=ExitOutcome.LOSS),
        ),
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=requested_dimensions,
    )


def test_universe_nba_season_and_date_range():
    plan = compile_research(_question(), CFG)
    assert plan.status is ResearchStatus.READY
    assert plan.universe["sports"] == ["NBA"]
    assert plan.universe["seasons"] == ["2025-2026"]
    assert plan.universe["date_from"] == "2025-10-10"
    assert plan.observation_basis == "TRADABLE_YES_BID"
    assert plan.resolution == "1_MINUTE_CANDLE"
    assert plan.pit_requirement == "available_at"
    assert plan.terminal is TerminalBehavior.HOLD_TO_SETTLEMENT
    assert plan.compiler_version == COMPILER_VERSION
    assert "ZERO_RESULTS" not in plan.to_dict()
    assert plan.to_dict()["status"] != "ZERO_RESULTS"


def test_invalid_league_and_date_range_fail_closed():
    nhl = compile_research(_question(leagues=("NHL",)), CFG)
    assert nhl.status is ResearchStatus.DATA_REQUIRED
    assert "UNIVERSE" in nhl.missing_data
    inverted = compile_research(_question(date_from="2026-06-01", date_to="2025-01-01"), CFG)
    assert inverted.status is ResearchStatus.DATA_REQUIRED
    assert "DATE_RANGE" in inverted.missing_data
    mlb = compile_research(_question(sports=("MLB",), leagues=("MLB",)), CFG)
    assert mlb.status in {ResearchStatus.DATA_REQUIRED, ResearchStatus.OPERATION_REQUIRED}
    if mlb.status is ResearchStatus.OPERATION_REQUIRED:
        assert "MLB_BASKETBALL_PERIOD" in mlb.missing_operations
    else:
        assert "WAREHOUSE" in mlb.missing_data or "UNIVERSE" in mlb.missing_data


def test_observation_tick_and_l2_are_data_required():
    candles = compile_research(_question(market_data=("candles",)), CFG)
    assert candles.status is ResearchStatus.READY
    tick = compile_research(_question(market_data=("tick",)), CFG)
    assert tick.status is ResearchStatus.DATA_REQUIRED
    assert "TICK" in tick.missing_data
    l2 = compile_research(_question(market_data=("orderbook",)), CFG)
    assert l2.status is ResearchStatus.DATA_REQUIRED
    tape = compile_research(_question(market_data=("trade_tape",)), CFG)
    assert tape.status is ResearchStatus.DATA_REQUIRED


def test_all_entry_ops_compile_without_scan():
    ops = [
        EntryOp.CROSS,
        EntryOp.BREAK,
        EntryOp.REVERSION,
        EntryOp.BOUNCE,
        EntryOp.RECOVERY,
        EntryOp.ABOVE,
        EntryOp.BELOW,
        EntryOp.MAXIMUM_TOUCH,
        EntryOp.MINIMUM_TOUCH,
    ]
    for op in ops:
        plan = compile_research(_question(entries=(_entry(op),)), CFG)
        assert plan.status is ResearchStatus.READY
        assert plan.entries[0].op == op.value
        assert plan.entries[0].price_e4 == 6300
        assert plan.entries[0].period == "Q2"
    touch = compile_research(_question(entries=(_entry(None, ordinal=TouchOrdinal.FIRST_TOUCH),)), CFG)
    assert touch.entries[0].op == EntryOp.FIRST_TOUCH.value
    assert touch.entries[0].source_vocabulary == "TOUCH"
    second = compile_research(
        _question(entries=(_entry(None, ordinal=TouchOrdinal.SECOND_TOUCH, id="e2"),)),
        CFG,
    )
    assert second.entries[0].op == EntryOp.SECOND_TOUCH.value


def test_entry_parameters_range_ordinal_clock_and():
    clock = ClockWindow(remaining_from_s=60, remaining_to_s=120)
    a = _entry(EntryOp.CROSS, id="a", price_e4=6300, period="Q2", clock=clock)
    b = _entry(
        EntryOp.ABOVE,
        id="b",
        price_e4=5000,
        price_to_e4=7000,
        period="Q3",
        ordinal=TouchOrdinal.FIRST_TOUCH,
    )
    plan = compile_research(_question(entries=(a, b)), CFG)
    assert plan.entries[0].conjunction is None
    assert plan.entries[1].conjunction == "AND"
    assert plan.entries[1].price_to_e4 == 7000
    assert plan.entries[0].clock == {"remaining_from_s": 60, "remaining_to_s": 120}
    assert [e.id for e in plan.entries] == ["a", "b"]


def test_independent_win_loss_exits():
    paths = (
        PathCondition(id="win", op=PathOp.REACH, price_e4=8700, outcome=ExitOutcome.WIN),
        PathCondition(id="loss", op=PathOp.DROP_TO, price_e4=4100, outcome=ExitOutcome.LOSS),
        PathCondition(id="rise", op=PathOp.RISE_TO, price_e4=9000, outcome=ExitOutcome.WIN),
        PathCondition(id="rec", op=PathOp.RECOVER, price_e4=6000, outcome=ExitOutcome.WIN),
        PathCondition(
            id="clk",
            op=PathOp.REACH,
            price_e4=0,
            outcome=ExitOutcome.LOSS,
            horizon_kind="clock",
            horizon_minutes=5,
        ),
    )
    q = ResearchQuestion(
        universe=_universe(),
        entry_conditions=(_entry(),),
        path_conditions=paths,
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=("HOLD_TO_SETTLEMENT",),
        win_hold=True,
        loss_hold=True,
    )
    plan = compile_research(q, CFG)
    ops = {(x.outcome, x.op) for x in plan.exits}
    assert ("win", "HOLD") in ops
    assert ("loss", "HOLD") in ops
    assert ("win", "REACH") in ops
    assert ("loss", "DROP") in ops
    assert ("win", "RISE") in ops
    assert ("win", "RECOVER") in ops
    assert ("loss", "CLOCK") in ops
    none = compile_research(
        ResearchQuestion(
            universe=_universe(),
            entry_conditions=(_entry(),),
            path_conditions=(),
            terminal=TerminalOutcome.BOTH,
            requested_dimensions=("NO_TERMINAL_RESULT",),
        ),
        CFG,
    )
    assert none.terminal is TerminalBehavior.NO_TERMINAL_RESULT


def test_capability_trio_and_no_zero_results():
    ready = compile_research(_question(), CFG)
    assert ready.status is ResearchStatus.READY
    data = compile_research(_question(market_data=("l2",)), CFG)
    assert data.status is ResearchStatus.DATA_REQUIRED
    align = compile_research(
        _question(requested_dimensions=("PBP_MARKET_PIT_ALIGNMENT",)),
        CFG,
    )
    assert align.status is ResearchStatus.OPERATION_REQUIRED
    assert "ZERO_RESULTS" not in data.to_dict()
    assert "ZERO_RESULTS" not in align.to_dict()


def test_no_first80_w9_fills_l2_csv_or_execute():
    fn_src = inspect.getsource(compile_research)
    assert "official_settlement" not in fn_src
    assert "compile_question" not in fn_src
    assert "kalshi_markets.csv" not in fn_src
    module_src = Path(__file__).resolve().parents[1] / "roller" / "warehouse" / "research_compiler.py"
    text = module_src.read_text(encoding="utf-8")
    assert "from roller.research_query.compiler" not in text
    assert "from roller.research_query.execute" not in text
    load_src = inspect.getsource(load_dataset)
    assert "compile_research" not in load_src
    tree = ast.parse((ROLLER_ROOT / "roller" / "research_query" / "compiler.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "roller.warehouse.research_compiler" not in imported


def test_determinism_same_question_same_plan():
    q = _question()
    a = compile_research(q, CFG)
    b = compile_research(q, CFG)
    assert a.to_dict() == b.to_dict()
    assert a.plan_hash == b.plan_hash
    assert a.plan_hash == a.digest()
    assert "current_time" not in a.to_dict()


def test_ready_chain_catalog_context_plan_without_backtest():
    q = _question()
    catalog = get_catalog(CFG)
    cov = catalog.resolve(
        [
            CapabilityName.GAME,
            CapabilityName.TRADABLE_YES_BID_1M,
            CapabilityName.CANDLE_PIT,
            CapabilityName.SETTLEMENT,
            CapabilityName.PBP,
        ]
    )
    assert cov.status is ResearchStatus.READY
    ctx = get_research_context(q, CFG)
    assert ctx.status is ResearchStatus.READY
    assert ctx.context is not None
    assert ctx.context.observation_basis == "TRADABLE_YES_BID"
    plan = compile_research(q, CFG)
    assert plan.status is ResearchStatus.READY
    assert plan.entries[0].op == EntryOp.CROSS.value
    assert plan.entries[0].price_e4 == 6300
    assert {x.op for x in plan.exits} == {"REACH"}
    l2 = get_research_context(_question(market_data=("l2",)), CFG)
    assert l2.status is ResearchStatus.DATA_REQUIRED
    assert l2.context is None
    l2_plan = compile_research(_question(market_data=("l2",)), CFG)
    assert l2_plan.status is ResearchStatus.DATA_REQUIRED
    align = catalog.resolve([CapabilityName.PBP_MARKET_PIT_ALIGNMENT])
    assert align.status is ResearchStatus.OPERATION_REQUIRED
    src = inspect.getsource(compile_research)
    assert "win_rate" not in src
    assert "expected_value" not in src
