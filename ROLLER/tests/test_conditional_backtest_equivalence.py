"""Phase 13 reference ≡ optimized. Exact row equality. Not a speed project."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.research_query.models import (
    ClockWindow,
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
from roller.warehouse.conditional_backtest import (
    compare_backtest_rows,
    run_conditional_backtest,
    run_plan_optimized,
    run_plan_reference,
)
from roller.warehouse.entities import (
    Game,
    GameMarketLink,
    LinkStatus,
    MarketObservation,
    ObservationBasis,
    PBPEvent,
    Settlement,
    SettlementResult,
)
from roller.warehouse.query_context import ResearchContext
from roller.warehouse.research_compiler import compile_research

ROLLER_ROOT = Path(__file__).resolve().parents[1]
CFG = RollerConfig(ROLLER_ROOT)
GID = "NBA_20251010_BOS_TOR"
TICKER = "KX-BOS"


def _universe(**kwargs) -> Universe:
    base = dict(
        sports=("NBA",),
        leagues=("NBA",),
        seasons=("2025-2026",),
        markets=("kalshi",),
        market_data=("candles",),
        game_data=(),
        date_from="2025-10-10",
        date_to="2025-10-10",
    )
    base.update(kwargs)
    return Universe(**base)


def _question(*, entries=None, paths=None, requested_dimensions=("HOLD_TO_SETTLEMENT",), **kw) -> ResearchQuestion:
    return ResearchQuestion(
        universe=_universe(**kw),
        entry_conditions=entries
        or (
            EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, operation=EntryOp.CROSS),
        ),
        path_conditions=paths
        if paths is not None
        else (
            PathCondition(id="win", op=PathOp.REACH, price_e4=8700, outcome=ExitOutcome.WIN),
            PathCondition(id="loss", op=PathOp.REACH, price_e4=4100, outcome=ExitOutcome.LOSS),
        ),
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=requested_dimensions,
    )


def _obs(ts: str, close: int) -> MarketObservation:
    return MarketObservation(
        ticker=TICKER,
        basis=ObservationBasis.TRADABLE_YES_BID,
        available_at=ts,
        internal_game_id=GID,
        yes_bid_close=close,
    )


def _ctx(closes, *, settlement=SettlementResult.YES, pbp=(), extra_links=(), extra_obs=()) -> ResearchContext:
    settle = ()
    if settlement is not None:
        settle = (Settlement(ticker=TICKER, result=settlement, settlement_value_e4=10000 if settlement is SettlementResult.YES else 0),)
    return ResearchContext(
        games=(Game(internal_game_id=GID, sport="NBA", season="2025-2026", league="NBA", game_date="2025-10-10"),),
        links=(
            GameMarketLink(status=LinkStatus.LINKED, internal_game_id=GID, ticker=TICKER, identity_rule_version="1.0.0"),
            *extra_links,
        ),
        observations=tuple(_obs(ts, px) for ts, px in closes) + extra_obs,
        settlements=settle,
        pbp_events=pbp,
        warehouse_version="eq",
    )


def _eq(question, ctx):
    plan = compile_research(question, CFG)
    ref = run_plan_reference(plan, ctx)
    opt = run_plan_optimized(plan, ctx)
    diffs = compare_backtest_rows(ref, opt)
    assert diffs == [], diffs
    assert ref.result_hash == opt.result_hash
    assert ref.population == opt.population
    return ref


def test_simple_cross_touch_and_ordinal():
    closes = [("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 6000), ("2025-10-10T01:03:00Z", 6300), ("2025-10-10T01:04:00Z", 8700)]
    _eq(_question(), _ctx(closes))
    _eq(_question(entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300),), paths=()), _ctx(closes, settlement=None))
    _eq(_question(entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.SECOND_TOUCH, price_e4=6300),), paths=()), _ctx(closes, settlement=None))


def test_all_entry_ops_equivalent():
    seqs = {
        EntryOp.CROSS: [(6000, "01:00"), (6300, "01:01")],
        EntryOp.BREAK: [(6000, "01:00"), (6400, "01:01")],
        EntryOp.REVERSION: [(6000, "01:00"), (6400, "01:01"), (6200, "01:02")],
        EntryOp.BOUNCE: [(6000, "01:00"), (6300, "01:01"), (6200, "01:02")],
        EntryOp.RECOVERY: [(6400, "01:00"), (6000, "01:01"), (6300, "01:02")],
        EntryOp.ABOVE: [(6400, "01:00")],
        EntryOp.BELOW: [(6200, "01:00")],
        EntryOp.MAXIMUM_TOUCH: [(6000, "01:00"), (6300, "01:01")],
        EntryOp.MINIMUM_TOUCH: [(7000, "01:00"), (6300, "01:01")],
    }
    for op, seq in seqs.items():
        closes = [(f"2025-10-10T{t}:00Z", px) for px, t in seq]
        q = _question(
            entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, operation=op, direction="up" if op is EntryOp.RECOVERY else None),),
            paths=(),
            requested_dimensions=("NO_TERMINAL_RESULT",),
        )
        _eq(q, _ctx(closes, settlement=None))


def test_period_clock_and_and_exits():
    pbp = (
        PBPEvent(internal_game_id=GID, event_timestamp="2025-10-10T01:00:30Z", available_at="2025-10-10T01:00:30Z", period="2", clock="8:00"),
    )
    q = _question(
        entries=(
            EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, period="Q2", operation=EntryOp.CROSS),
        ),
        paths=(),
        requested_dimensions=("NO_TERMINAL_RESULT",),
    )
    _eq(q, _ctx([("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)], settlement=None, pbp=pbp))
    clock_q = _question(
        entries=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=6300,
                period="Q2",
                clock=ClockWindow(360, 480),
                operation=EntryOp.CROSS,
            ),
        ),
        paths=(),
        requested_dimensions=("NO_TERMINAL_RESULT",),
    )
    _eq(clock_q, _ctx([("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)], settlement=None, pbp=pbp))
    and_q = _question(
        entries=(
            EntryCondition(id="a", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, operation=EntryOp.CROSS),
            EntryCondition(id="b", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=7000, operation=EntryOp.ABOVE),
        ),
        paths=(),
        requested_dimensions=("NO_TERMINAL_RESULT",),
    )
    _eq(and_q, _ctx([("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 7100)], settlement=None))
    _eq(
        _question(paths=(PathCondition(id="w", op=PathOp.REACH, price_e4=8700, outcome=ExitOutcome.WIN),)),
        _ctx([("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 8700)]),
    )
    _eq(
        _question(paths=(PathCondition(id="l", op=PathOp.DROP_TO, price_e4=4100, outcome=ExitOutcome.LOSS),)),
        _ctx([("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 4100)]),
    )
    _eq(_question(paths=(), requested_dimensions=("HOLD_TO_SETTLEMENT",)), _ctx([("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)]))
    _eq(_question(paths=(), requested_dimensions=("HOLD_TO_SETTLEMENT",)), _ctx([("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)], settlement=None))
    _eq(_question(paths=(), requested_dimensions=("HOLD_TO_SETTLEMENT",)), _ctx([("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)], settlement=SettlementResult.INVALID))


def test_jump_through_boundary_ot_repeat():
    _eq(
        _question(),
        _ctx([("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 3700)]),
    )
    ot = (
        PBPEvent(internal_game_id=GID, event_timestamp="2025-10-10T01:00:30Z", available_at="2025-10-10T01:00:30Z", period="5", clock="4:00"),
    )
    q_ot = _question(
        entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, period="OT", operation=EntryOp.CROSS),),
        paths=(),
        requested_dimensions=("NO_TERMINAL_RESULT",),
    )
    _eq(q_ot, _ctx([("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)], settlement=None, pbp=ot))
    q4 = _question(
        entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, period="Q4", operation=EntryOp.CROSS),),
        paths=(),
        requested_dimensions=("NO_TERMINAL_RESULT",),
    )
    ref = _eq(q4, _ctx([("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)], settlement=None, pbp=ot))
    assert ref.population == 0
    plan = compile_research(_question(), CFG)
    ctx = _ctx([("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 8700)])
    a = run_plan_reference(plan, ctx)
    b = run_plan_reference(plan, ctx)
    assert a.result_hash == b.result_hash
    assert a.to_dict()["rows"] == b.to_dict()["rows"]


def test_duplicate_game_records_one_row():
    closes = [("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 8700)]
    ctx = _ctx(closes)
    dup = ResearchContext(
        games=ctx.games + ctx.games,
        links=ctx.links + ctx.links,
        observations=ctx.observations,
        settlements=ctx.settlements,
        pbp_events=ctx.pbp_events,
        warehouse_version="eq",
    )
    ref = _eq(_question(), dup)
    assert ref.population == 1


def test_live_warehouse_reference_equals_optimized():
    q = _question(
        entries=(
            EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, period="Q2", operation=EntryOp.CROSS),
        ),
        game_data=("pbp",),
    )
    ref = run_conditional_backtest(q, CFG, engine_id="reference")
    opt = run_conditional_backtest(q, CFG, engine_id="optimized")
    assert ref.plan_hash == "4547787d8dfdb8c40717d7321e399179e868a67f0b069cadabc3f7964f9ffa67"
    assert compare_backtest_rows(ref, opt) == []
    assert ref.population == opt.population
    assert ref.result_hash == opt.result_hash
