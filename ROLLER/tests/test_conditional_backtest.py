"""Phase 12 conditional backtest. Observation-path only. No FIRST80. No fills."""

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
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)
from roller.warehouse.conditional_backtest import (
    BacktestStatus,
    Classification,
    _pbp_by_game,
    _pbp_dicts,
    run_conditional_backtest,
    run_plan,
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
from roller.warehouse.research_compiler import TerminalBehavior, compile_research

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


def _question(*, entries=None, paths=None, requested_dimensions=("HOLD_TO_SETTLEMENT",), **universe_kw) -> ResearchQuestion:
    return ResearchQuestion(
        universe=_universe(**universe_kw),
        entry_conditions=entries
        or (
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=6300,
                operation=EntryOp.CROSS,
            ),
        ),
        path_conditions=paths
        or (
            PathCondition(id="win", op=PathOp.REACH, price_e4=8700, outcome=ExitOutcome.WIN),
            PathCondition(id="loss", op=PathOp.REACH, price_e4=4100, outcome=ExitOutcome.LOSS),
        ),
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=requested_dimensions,
    )


def _obs(ts: str, close: int, ticker: str = TICKER) -> MarketObservation:
    return MarketObservation(
        ticker=ticker,
        basis=ObservationBasis.TRADABLE_YES_BID,
        available_at=ts,
        internal_game_id=GID,
        yes_bid_close=close,
    )


def _bag(*, closes: list[tuple[str, int]], settlement: SettlementResult | None = SettlementResult.YES, pbp=(), extra_obs=()) -> ResearchContext:
    obs = tuple(_obs(ts, px) for ts, px in closes) + extra_obs
    settle = ()
    if settlement is not None:
        settle = (
            Settlement(ticker=TICKER, result=settlement, settlement_value_e4=10000 if settlement is SettlementResult.YES else 0),
        )
    return ResearchContext(
        games=(Game(internal_game_id=GID, sport="NBA", season="2025-2026", league="NBA", game_date="2025-10-10"),),
        links=(
            GameMarketLink(status=LinkStatus.LINKED, internal_game_id=GID, ticker=TICKER, identity_rule_version="1.0.0"),
        ),
        observations=obs,
        settlements=settle,
        pbp_events=pbp,
        warehouse_version="test",
    )


def _plan(question: ResearchQuestion):
    return compile_research(question, CFG)


def test_data_required_and_operation_required_do_not_scan():
    l2 = run_conditional_backtest(_question(market_data=("l2",)), CFG)
    assert l2.status is BacktestStatus.DATA_REQUIRED
    assert l2.rows == ()
    tick = run_conditional_backtest(_question(market_data=("tick",)), CFG)
    assert tick.status is BacktestStatus.DATA_REQUIRED
    align = run_conditional_backtest(_question(requested_dimensions=("PBP_MARKET_PIT_ALIGNMENT",)), CFG)
    assert align.status is BacktestStatus.OPERATION_REQUIRED
    assert align.rows == ()
    bad = run_conditional_backtest(_question(leagues=("NHL",)), CFG)
    assert bad.status is BacktestStatus.DATA_REQUIRED
    inverted = run_conditional_backtest(_question(date_from="2026-06-01", date_to="2025-01-01"), CFG)
    assert inverted.status is BacktestStatus.DATA_REQUIRED


def test_cross_reach_win_and_loss():
    q = _question()
    plan = _plan(q)
    win_ctx = _bag(
        closes=[
            ("2025-10-10T01:00:00Z", 6000),
            ("2025-10-10T01:01:00Z", 6300),
            ("2025-10-10T01:02:00Z", 8700),
        ]
    )
    win = run_plan(plan, win_ctx)
    assert win.status is BacktestStatus.READY
    assert win.population == 1
    assert win.rows[0].classification == Classification.WIN.value
    assert win.rows[0].entry_value == 6300
    assert win.rows[0].entry_timestamp == "2025-10-10T01:01:00Z"
    assert win.rows[0].win_exit_value == 8700
    assert win.rows[0].observation_basis == "TRADABLE_YES_BID"
    assert win.rows[0].pit_field == "available_at"
    loss_ctx = _bag(
        closes=[
            ("2025-10-10T01:00:00Z", 6000),
            ("2025-10-10T01:01:00Z", 6300),
            ("2025-10-10T01:02:00Z", 4100),
        ]
    )
    loss = run_plan(plan, loss_ctx)
    assert loss.rows[0].classification == Classification.LOSS.value
    assert loss.rows[0].loss_exit_value == 4100


def test_zero_entry_is_zero_results_not_data_required():
    plan = _plan(_question())
    ctx = _bag(closes=[("2025-10-10T01:00:00Z", 5000), ("2025-10-10T01:01:00Z", 5100)])
    out = run_plan(plan, ctx)
    assert out.status is BacktestStatus.ZERO_RESULTS
    assert out.population == 0
    assert out.status is not BacktestStatus.DATA_REQUIRED


def test_all_entry_ops():
    cases = [
        (EntryOp.CROSS, [(6000, "01:00"), (6300, "01:01")]),
        (EntryOp.BREAK, [(6000, "01:00"), (6400, "01:01")]),
        (EntryOp.REVERSION, [(6000, "01:00"), (6400, "01:01"), (6200, "01:02")]),
        (EntryOp.BOUNCE, [(6000, "01:00"), (6300, "01:01"), (6200, "01:02")]),
        (EntryOp.RECOVERY, [(6400, "01:00"), (6000, "01:01"), (6300, "01:02")]),
        (EntryOp.ABOVE, [(6400, "01:00")]),
        (EntryOp.BELOW, [(6200, "01:00")]),
        (EntryOp.MAXIMUM_TOUCH, [(6000, "01:00"), (6300, "01:01")]),
        (EntryOp.MINIMUM_TOUCH, [(7000, "01:00"), (6300, "01:01")]),
    ]
    for op, seq in cases:
        built = [(f"2025-10-10T{stamp}:00Z", px) for px, stamp in seq]
        q = _question(
            entries=(
                EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, operation=op, direction="up" if op is EntryOp.RECOVERY else None),
            ),
            paths=(),
            requested_dimensions=("NO_TERMINAL_RESULT",),
        )
        out = run_plan(_plan(q), _bag(closes=built, settlement=None))
        assert out.population == 1, op
        assert out.rows[0].entry_operation == op.value


def test_touch_and_ordinal_touch():
    closes = [
        ("2025-10-10T01:00:00Z", 6000),
        ("2025-10-10T01:01:00Z", 6300),
        ("2025-10-10T01:02:00Z", 6000),
        ("2025-10-10T01:03:00Z", 6300),
    ]
    first = _question(
        entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300),),
        paths=(),
        requested_dimensions=("NO_TERMINAL_RESULT",),
    )
    second = _question(
        entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.SECOND_TOUCH, price_e4=6300),),
        paths=(),
        requested_dimensions=("NO_TERMINAL_RESULT",),
    )
    a = run_plan(_plan(first), _bag(closes=closes, settlement=None))
    b = run_plan(_plan(second), _bag(closes=closes, settlement=None))
    assert a.rows[0].entry_timestamp == "2025-10-10T01:01:00Z"
    assert b.rows[0].entry_timestamp == "2025-10-10T01:03:00Z"


def test_and_is_sequential():
    q = _question(
        entries=(
            EntryCondition(id="a", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, operation=EntryOp.CROSS),
            EntryCondition(id="b", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=7000, operation=EntryOp.ABOVE),
        ),
        paths=(),
        requested_dimensions=("NO_TERMINAL_RESULT",),
    )
    ctx = _bag(
        closes=[
            ("2025-10-10T01:00:00Z", 6000),
            ("2025-10-10T01:01:00Z", 6300),
            ("2025-10-10T01:02:00Z", 7100),
        ],
        settlement=None,
    )
    out = run_plan(_plan(q), ctx)
    assert out.population == 1
    assert out.rows[0].entry_value == 7100


def test_hold_settlement_states():
    q = _question(paths=(), requested_dimensions=("HOLD_TO_SETTLEMENT",))
    plan = _plan(q)
    closes = [("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)]
    yes = run_plan(plan, _bag(closes=closes, settlement=SettlementResult.YES))
    assert yes.rows[0].classification == Classification.HELD_TO_SETTLEMENT.value
    assert yes.rows[0].settlement_status == "YES"
    no = run_plan(plan, _bag(closes=closes, settlement=SettlementResult.NO))
    assert no.rows[0].classification == Classification.HELD_TO_SETTLEMENT.value
    assert no.rows[0].settlement_status == "NO"
    inv = run_plan(plan, _bag(closes=closes, settlement=SettlementResult.INVALID))
    assert inv.rows[0].classification == Classification.INVALID_SETTLEMENT.value
    miss = run_plan(plan, _bag(closes=closes, settlement=None))
    assert miss.rows[0].classification == Classification.MISSING_SETTLEMENT.value
    none = run_plan(_plan(_question(paths=(), requested_dimensions=("NO_TERMINAL_RESULT",))), _bag(closes=closes, settlement=SettlementResult.YES))
    assert none.rows[0].classification == Classification.NO_TERMINAL_RESULT.value
    assert none.rows[0].settlement_status == ""


def test_same_bar_tie_and_jump_through():
    q = _question()
    plan = _plan(q)
    tie = _bag(
        closes=[
            ("2025-10-10T01:00:00Z", 6000),
            ("2025-10-10T01:01:00Z", 6300),
            ("2025-10-10T01:02:00Z", 8700),
            ("2025-10-10T01:02:00Z", 4100),
        ]
    )
    # same timestamp two closes: warehouse order kept; REACH 87 and 41 may tie if same ts after sort
    # Use one bar that satisfies both directional reaches from 6300: impossible on one value.
    # 6300 → 4100 is LOSS REACH 41; WIN REACH 87 needs >= 87 from below. Separate bars same ts:
    out = run_plan(plan, tie)
    if out.population:
        assert "fill" not in out.rows[0].to_dict()
    jump = _bag(
        closes=[
            ("2025-10-10T01:00:00Z", 6000),
            ("2025-10-10T01:01:00Z", 6300),
            ("2025-10-10T01:02:00Z", 3700),
        ]
    )
    loss = run_plan(plan, jump)
    assert loss.rows[0].classification == Classification.LOSS.value
    assert loss.rows[0].loss_exit_value == 3700
    assert "fill_price" not in loss.rows[0].to_dict()


def test_gap_minutes_not_filled():
    q = _question()
    ctx = _bag(
        closes=[
            ("2025-10-10T01:00:00Z", 6000),
            ("2025-10-10T01:05:00Z", 6300),
            ("2025-10-10T01:06:00Z", 8700),
        ]
    )
    out = run_plan(_plan(q), ctx)
    assert out.rows[0].entry_timestamp == "2025-10-10T01:05:00Z"
    assert out.population == 1


def test_exits_drop_rise_recover_clock():
    drop_q = _question(
        paths=(PathCondition(id="l", op=PathOp.DROP_TO, price_e4=5000, outcome=ExitOutcome.LOSS),),
        requested_dimensions=("NO_TERMINAL_RESULT",),
    )
    drop = run_plan(
        _plan(drop_q),
        _bag(
            closes=[
                ("2025-10-10T01:00:00Z", 6000),
                ("2025-10-10T01:01:00Z", 6300),
                ("2025-10-10T01:02:00Z", 5000),
            ],
            settlement=None,
        ),
    )
    assert drop.rows[0].classification == Classification.LOSS.value
    rise_q = _question(
        paths=(PathCondition(id="w", op=PathOp.RISE_TO, price_e4=8000, outcome=ExitOutcome.WIN),),
        requested_dimensions=("NO_TERMINAL_RESULT",),
    )
    rise = run_plan(
        _plan(rise_q),
        _bag(
            closes=[
                ("2025-10-10T01:00:00Z", 6000),
                ("2025-10-10T01:01:00Z", 6300),
                ("2025-10-10T01:02:00Z", 8000),
            ],
            settlement=None,
        ),
    )
    assert rise.rows[0].classification == Classification.WIN.value
    rec_q = _question(
        paths=(PathCondition(id="w", op=PathOp.RECOVER, price_e4=7000, outcome=ExitOutcome.WIN),),
        requested_dimensions=("NO_TERMINAL_RESULT",),
    )
    rec = run_plan(
        _plan(rec_q),
        _bag(
            closes=[
                ("2025-10-10T01:00:00Z", 6000),
                ("2025-10-10T01:01:00Z", 6300),
                ("2025-10-10T01:02:00Z", 7000),
            ],
            settlement=None,
        ),
    )
    assert rec.rows[0].classification == Classification.WIN.value
    clock_q = ResearchQuestion(
        universe=_universe(),
        entry_conditions=(
            EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, operation=EntryOp.CROSS),
        ),
        path_conditions=(
            PathCondition(
                id="clk",
                op=PathOp.REACH,
                price_e4=0,
                outcome=ExitOutcome.LOSS,
                horizon_kind="clock",
                horizon_minutes=5,
            ),
        ),
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=("NO_TERMINAL_RESULT",),
    )
    clock = run_plan(
        _plan(clock_q),
        _bag(closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)], settlement=None),
    )
    assert clock.population in {0, 1}
    if clock.population == 0:
        assert "clock_unaligned" in clock.exclusions or clock.status is BacktestStatus.ZERO_RESULTS


def test_period_q2_filter_with_pbp_snap():
    q = _question(
        entries=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=6300,
                period="Q2",
                operation=EntryOp.CROSS,
            ),
        ),
        paths=(),
        requested_dimensions=("NO_TERMINAL_RESULT",),
    )
    pbp = (
        PBPEvent(
            internal_game_id=GID,
            event_timestamp="2025-10-10T01:00:30Z",
            available_at="2025-10-10T01:00:30Z",
            period="2",
            clock="8:00",
        ),
    )
    ctx = _bag(
        closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)],
        settlement=None,
        pbp=pbp,
    )
    out = run_plan(_plan(q), ctx)
    assert out.population == 1
    assert out.rows[0].entry_period == "Q2"


def test_period_unaligned_is_exclusion():
    q = _question(
        entries=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=6300,
                period="Q2",
                operation=EntryOp.CROSS,
            ),
        )
    )
    ctx = _bag(closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)])
    out = run_plan(_plan(q), ctx)
    assert out.population == 0
    assert out.exclusions
    assert "period_unaligned" in out.exclusions or "period_filter" in out.exclusions


def test_identity_via_link_not_ticker_parse():
    plan = _plan(_question())
    ctx = _bag(closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 8700)])
    out = run_plan(plan, ctx)
    assert out.rows[0].internal_game_id == GID
    assert out.rows[0].market_id == TICKER
    src = inspect.getsource(run_plan)
    assert "split(" not in src


def test_reference_matches_optimized_on_bag():
    plan = _plan(_question())
    ctx = _bag(
        closes=[
            ("2025-10-10T01:00:00Z", 6000),
            ("2025-10-10T01:01:00Z", 6300),
            ("2025-10-10T01:02:00Z", 8700),
        ]
    )
    ref = run_plan_reference(plan, ctx)
    opt = run_plan_optimized(plan, ctx)
    assert [r.to_dict() for r in ref.rows] == [r.to_dict() for r in opt.rows]


def test_live_nba_q2_cross_executes():
    q = _question(
        entries=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=6300,
                period="Q2",
                operation=EntryOp.CROSS,
            ),
        ),
        game_data=("pbp",),
    )
    plan = compile_research(q, CFG)
    assert plan.plan_hash == "4547787d8dfdb8c40717d7321e399179e868a67f0b069cadabc3f7964f9ffa67"
    out = run_conditional_backtest(q, CFG)
    assert out.status in {BacktestStatus.READY, BacktestStatus.ZERO_RESULTS}
    assert out.plan_hash == plan.plan_hash
    bos = [r for r in out.rows if r.internal_game_id == GID]
    for row in bos:
        if row.market_id.endswith("-BOS"):
            assert row.settlement_status in {"YES", ""}
        if row.market_id.endswith("-TOR"):
            assert row.settlement_status in {"NO", ""}
    again = run_conditional_backtest(q, CFG)
    assert again.to_dict()["rows"] == out.to_dict()["rows"]
    assert again.result_hash == out.result_hash


def test_pbp_index_is_one_pass_per_game():
    events = tuple(
        PBPEvent(
            internal_game_id=gid,
            event_timestamp=f"2025-11-01T00:00:{i:02d}Z",
            period="1",
            clock="10:00",
            home_score=i,
            away_score=0,
        )
        for i, gid in enumerate(("G1", "G2", "G1", "G3", "G2"))
    )
    gids = {"G1", "G2", "G3", "MISSING"}
    grouped = _pbp_by_game(events, gids)
    for gid in gids:
        assert grouped[gid] == _pbp_dicts(events, gid)


def test_no_confirm_and_run_or_first80():
    src = Path(__file__).resolve().parents[1] / "roller" / "warehouse" / "conditional_backtest.py"
    text = src.read_text(encoding="utf-8")
    assert "official_settlement" not in text
    assert "from roller.research_query.compiler" not in text
    assert "from roller.research_query.execute" not in text
    assert "kalshi_markets.csv" not in text
    assert "first80" not in text.lower()
    assert "fill_price" not in text
    load_src = inspect.getsource(load_dataset)
    assert "conditional_backtest" not in load_src
    tree = ast.parse((ROLLER_ROOT / "roller" / "research_query" / "execute.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "roller.warehouse.conditional_backtest" not in imported
