"""Phase 15: pruning, projection, cache. Not a speed-threshold suite."""

from __future__ import annotations

from pathlib import Path

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


def _q(*, date_from="2025-10-10", date_to="2025-10-10", period=None, game_data=()) -> ResearchQuestion:
    return ResearchQuestion(
        universe=Universe(
            sports=("NBA",),
            leagues=("NBA",),
            seasons=("2025-2026",),
            markets=("kalshi",),
            market_data=("candles",),
            game_data=game_data,
            date_from=date_from,
            date_to=date_to,
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


def test_date_query_does_not_open_far_months():
    clear_context_cache()
    loaded = get_research_context(_q(), CFG)
    assert loaded.context is not None
    months = set(loaded.load_stats.observation_months)
    assert "2025-10" in months
    assert "2026-06" not in months
    assert "2026-03" not in months
    assert loaded.load_stats.observation_rows_read >= 5125
    assert loaded.load_stats.pbp_rows_read == 0


def test_period_query_loads_pbp_plain_query_does_not():
    clear_context_cache()
    plain = get_research_context(_q(), CFG)
    q2 = get_research_context(_q(period="Q2", game_data=("pbp",)), CFG)
    assert plain.load_stats.pbp_rows_read == 0
    assert q2.load_stats.pbp_rows_read > 0
    assert plain.context is not None and q2.context is not None
    assert len(plain.context.pbp_events) == 0
    assert len(q2.context.pbp_events) == 3176


def test_projection_drops_last_trade_fields():
    clear_context_cache()
    loaded = get_research_context(_q(), CFG)
    assert loaded.context is not None
    assert loaded.context.observations
    assert all(o.last_close_e4 is None for o in loaded.context.observations)
    assert all(o.yes_bid_close is not None for o in loaded.context.observations)
    assert all(o.available_at for o in loaded.context.observations)


def test_cache_hit_and_invalidation():
    clear_context_cache()
    a = get_research_context(_q(), CFG)
    b = get_research_context(_q(), CFG)
    assert a.load_stats.cache_hit is False
    assert b.load_stats.cache_hit is True
    assert b.context is a.context
    clear_context_cache()
    c = get_research_context(_q(), CFG)
    assert c.load_stats.cache_hit is False
    assert c.context is not None
    assert len(c.context.observations) == len(a.context.observations)


def test_repeated_query_hashes_match():
    clear_context_cache()
    q = _q(period="Q2", game_data=("pbp",))
    first = run_conditional_backtest(q, CFG, engine_id="optimized")
    second = run_conditional_backtest(q, CFG, engine_id="optimized")
    assert first.result_hash == second.result_hash
    assert first.population == second.population
    assert first.plan_hash == "4547787d8dfdb8c40717d7321e399179e868a67f0b069cadabc3f7964f9ffa67"


def test_reference_equals_optimized_after_optimization():
    clear_context_cache()
    q = _q()
    ref = run_conditional_backtest(q, CFG, engine_id="reference")
    opt = run_conditional_backtest(q, CFG, engine_id="optimized")
    assert compare_backtest_rows(ref, opt) == []
    assert ref.population == 7
    assert opt.population == 7
