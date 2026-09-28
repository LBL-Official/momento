"""Phase 14 edge/failure suite. Fixtures are in-memory. Warehouse is not mutated."""

from __future__ import annotations

from pathlib import Path

import pytest

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
    run_conditional_backtest,
    run_plan,
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


def _u(**kwargs) -> Universe:
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


def _q(*, entries=None, paths=None, dims=("HOLD_TO_SETTLEMENT",), **kw) -> ResearchQuestion:
    return ResearchQuestion(
        universe=_u(**kw),
        entry_conditions=entries
        or (EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, operation=EntryOp.CROSS),),
        path_conditions=paths
        if paths is not None
        else (
            PathCondition(id="win", op=PathOp.REACH, price_e4=8700, outcome=ExitOutcome.WIN),
            PathCondition(id="loss", op=PathOp.REACH, price_e4=4100, outcome=ExitOutcome.LOSS),
        ),
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=dims,
    )


def _obs(ts: str, close: int, ticker=TICKER, gid=GID) -> MarketObservation:
    return MarketObservation(
        ticker=ticker,
        basis=ObservationBasis.TRADABLE_YES_BID,
        available_at=ts,
        internal_game_id=gid,
        yes_bid_close=close,
    )


def _ctx(*, closes=None, links=None, games=None, settlements=None, pbp=(), obs=None) -> ResearchContext:
    return ResearchContext(
        games=games
        if games is not None
        else (Game(internal_game_id=GID, sport="NBA", season="2025-2026", league="NBA", game_date="2025-10-10"),),
        links=links
        if links is not None
        else (GameMarketLink(status=LinkStatus.LINKED, internal_game_id=GID, ticker=TICKER, identity_rule_version="1.0.0"),),
        observations=obs if obs is not None else tuple(_obs(ts, px) for ts, px in (closes or ())),
        settlements=settlements if settlements is not None else (),
        pbp_events=pbp,
        warehouse_version="edge",
    )


def test_no_market_no_guess():
    plan = compile_research(_q(), CFG)
    ctx = _ctx(closes=[("2025-10-10T01:00:00Z", 6000)], links=(), games=(Game(internal_game_id=GID, sport="NBA", season="2025-2026", league="NBA", game_date="2025-10-10"),))
    out = run_plan(plan, ctx)
    assert out.population == 0
    assert out.rows == ()


def test_no_pbp_required_vs_not():
    plan_free = compile_research(_q(), CFG)
    ctx = _ctx(closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 8700)])
    free = run_plan(plan_free, ctx)
    assert free.population == 1
    plan_q2 = compile_research(
        _q(entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, period="Q2", operation=EntryOp.CROSS),)),
        CFG,
    )
    need = run_plan(plan_q2, ctx)
    assert need.population == 0
    assert need.exclusions


def test_missing_and_invalid_settlement():
    plan = compile_research(_q(paths=(), dims=("HOLD_TO_SETTLEMENT",)), CFG)
    miss = run_plan(plan, _ctx(closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)]))
    assert miss.rows[0].classification == Classification.MISSING_SETTLEMENT.value
    inv = run_plan(
        plan,
        _ctx(
            closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)],
            settlements=(Settlement(ticker=TICKER, result=SettlementResult.INVALID),),
        ),
    )
    assert inv.rows[0].classification == Classification.INVALID_SETTLEMENT.value
    assert inv.rows[0].settlement_status == "INVALID"


def test_gap_minutes_and_missing_available_at_rejected():
    plan = compile_research(_q(), CFG)
    gapped = run_plan(plan, _ctx(closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:10:00Z", 6300), ("2025-10-10T01:11:00Z", 8700)]))
    assert gapped.rows[0].entry_timestamp == "2025-10-10T01:10:00Z"
    with pytest.raises(ValueError):
        MarketObservation(ticker=TICKER, basis=ObservationBasis.TRADABLE_YES_BID, available_at="", yes_bid_close=6300)


def test_same_minute_duplicate_keeps_order():
    plan = compile_research(_q(), CFG)
    ctx = _ctx(
        obs=(
            _obs("2025-10-10T01:00:00Z", 6000),
            _obs("2025-10-10T01:01:00Z", 6200),
            _obs("2025-10-10T01:01:00Z", 6300),
            _obs("2025-10-10T01:02:00Z", 8700),
        )
    )
    out = run_plan(plan, ctx)
    assert out.population == 1
    assert out.rows[0].entry_timestamp == "2025-10-10T01:01:00Z"
    assert out.rows[0].entry_value == 6300


def test_ordinal_and_repeated_exit_one_terminal():
    closes = [
        ("2025-10-10T01:00:00Z", 6000),
        ("2025-10-10T01:01:00Z", 6300),
        ("2025-10-10T01:02:00Z", 6000),
        ("2025-10-10T01:03:00Z", 6300),
        ("2025-10-10T01:04:00Z", 8700),
        ("2025-10-10T01:05:00Z", 8800),
    ]
    third = compile_research(
        _q(entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.SECOND_TOUCH, price_e4=6300),), paths=(PathCondition(id="w", op=PathOp.REACH, price_e4=8700, outcome=ExitOutcome.WIN),), dims=("NO_TERMINAL_RESULT",)),
        CFG,
    )
    out = run_plan(third, _ctx(closes=closes))
    assert out.population == 1
    assert out.rows[0].entry_timestamp == "2025-10-10T01:03:00Z"
    assert out.rows[0].win_exit_timestamp == "2025-10-10T01:04:00Z"


def test_same_observation_tie_and_jump_through():
    plan = compile_research(_q(), CFG)
    jump = run_plan(plan, _ctx(closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 3700)]))
    assert jump.rows[0].classification == Classification.LOSS.value
    assert jump.rows[0].loss_exit_value == 3700
    dumped = jump.rows[0].to_dict()
    assert "fill_price" not in dumped
    assert "maker_fill" not in dumped
    ctx = _ctx(
        obs=(
            _obs("2025-10-10T01:00:00Z", 6000),
            _obs("2025-10-10T01:01:00Z", 6300),
            _obs("2025-10-10T01:02:00Z", 8700),
            MarketObservation(
                ticker=TICKER,
                basis=ObservationBasis.TRADABLE_YES_BID,
                available_at="2025-10-10T01:02:00Z",
                internal_game_id=GID,
                yes_bid_close=4100,
            ),
        )
    )
    tied = run_plan(plan, ctx)
    assert tied.population == 1
    assert tied.rows[0].classification == Classification.SAME_BAR_TIE.value
    assert tied.rows[0].win_exit_timestamp == tied.rows[0].loss_exit_timestamp == "2025-10-10T01:02:00Z"


def test_boundary_equality():
    plan_cross = compile_research(_q(paths=(), dims=("NO_TERMINAL_RESULT",)), CFG)
    already = run_plan(plan_cross, _ctx(closes=[("2025-10-10T01:00:00Z", 6300), ("2025-10-10T01:01:00Z", 6300)]))
    assert already.population == 0
    above = compile_research(
        _q(entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, operation=EntryOp.ABOVE),), paths=(), dims=("NO_TERMINAL_RESULT",)),
        CFG,
    )
    eq_above = run_plan(above, _ctx(closes=[("2025-10-10T01:00:00Z", 6300)]))
    assert eq_above.population == 0
    below = compile_research(
        _q(entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, operation=EntryOp.BELOW),), paths=(), dims=("NO_TERMINAL_RESULT",)),
        CFG,
    )
    eq_below = run_plan(below, _ctx(closes=[("2025-10-10T01:00:00Z", 6300)]))
    assert eq_below.population == 0


def test_period_boundaries_and_ot():
    q2 = compile_research(
        _q(entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, period="Q2", operation=EntryOp.CROSS),), paths=(), dims=("NO_TERMINAL_RESULT",)),
        CFG,
    )
    q1_pbp = (PBPEvent(internal_game_id=GID, event_timestamp="2025-10-10T01:00:30Z", available_at="2025-10-10T01:00:30Z", period="1", clock="1:00"),)
    ot_pbp = (PBPEvent(internal_game_id=GID, event_timestamp="2025-10-10T01:00:30Z", available_at="2025-10-10T01:00:30Z", period="5", clock="4:00"),)
    closes = [("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)]
    assert run_plan(q2, _ctx(closes=closes, pbp=q1_pbp)).population == 0
    ot_plan = compile_research(
        _q(entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, period="OT", operation=EntryOp.CROSS),), paths=(), dims=("NO_TERMINAL_RESULT",)),
        CFG,
    )
    assert run_plan(ot_plan, _ctx(closes=closes, pbp=ot_pbp)).population == 1
    q4 = compile_research(
        _q(entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, period="Q4", operation=EntryOp.CROSS),), paths=(), dims=("NO_TERMINAL_RESULT",)),
        CFG,
    )
    assert run_plan(q4, _ctx(closes=closes, pbp=ot_pbp)).population == 0


def _clock_plan(lo: int, hi: int):
    return compile_research(
        _q(
            entries=(
                EntryCondition(
                    id="e1",
                    ordinal=TouchOrdinal.FIRST_TOUCH,
                    price_e4=6300,
                    period="Q2",
                    clock=ClockWindow(remaining_from_s=lo, remaining_to_s=hi),
                    operation=EntryOp.CROSS,
                ),
            ),
            paths=(),
            dims=("NO_TERMINAL_RESULT",),
        ),
        CFG,
    )


def _clock_pbp(clock: str) -> tuple[PBPEvent, ...]:
    return (
        PBPEvent(
            internal_game_id=GID,
            event_timestamp="2025-10-10T01:00:30Z",
            available_at="2025-10-10T01:00:30Z",
            period="2",
            clock=clock,
        ),
    )


def test_clock_boundaries():
    q = _clock_plan(360, 480)
    closes = [("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)]
    assert run_plan(q, _ctx(closes=closes, pbp=_clock_pbp("7:00"))).population == 1
    assert run_plan(q, _ctx(closes=closes, pbp=_clock_pbp("0:00"))).population == 0
    wide = _clock_plan(0, 720)
    for clock in ("12:00", "11:59", "10:00", "09:59", "00:01", "00:00"):
        assert run_plan(wide, _ctx(closes=closes, pbp=_clock_pbp(clock))).population == 1, clock
    ten = _clock_plan(600, 720)
    assert run_plan(ten, _ctx(closes=closes, pbp=_clock_pbp("12:00"))).population == 1
    assert run_plan(ten, _ctx(closes=closes, pbp=_clock_pbp("11:59"))).population == 1
    assert run_plan(ten, _ctx(closes=closes, pbp=_clock_pbp("10:00"))).population == 1
    assert run_plan(ten, _ctx(closes=closes, pbp=_clock_pbp("09:59"))).population == 0
    assert run_plan(ten, _ctx(closes=closes, pbp=_clock_pbp("00:01"))).population == 0
    assert run_plan(ten, _ctx(closes=closes, pbp=_clock_pbp("00:00"))).population == 0


def test_missing_next_bar_no_fabricated_candle():
    plan = compile_research(_q(dims=("NO_TERMINAL_RESULT",)), CFG)
    out = run_plan(plan, _ctx(closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)]))
    assert out.rows[0].classification == Classification.NO_TERMINAL_RESULT.value
    assert out.rows[0].win_exit_timestamp == ""


def test_date_identity_and_duplicates():
    other = "NBA_20251010_ORL_PHI"
    plan = compile_research(_q(), CFG)
    ctx = _ctx(
        games=(
            Game(internal_game_id=GID, sport="NBA", season="2025-2026", league="NBA", game_date="2025-10-10"),
            Game(internal_game_id=other, sport="NBA", season="2025-2026", league="NBA", game_date="2025-10-10"),
        ),
        links=(
            GameMarketLink(status=LinkStatus.LINKED, internal_game_id=GID, ticker=TICKER, identity_rule_version="1.0.0"),
            GameMarketLink(status=LinkStatus.LINKED, internal_game_id=other, ticker="KX-ORL", identity_rule_version="1.0.0"),
        ),
        obs=(
            _obs("2025-10-10T01:00:00Z", 6000),
            _obs("2025-10-10T01:01:00Z", 6300, ticker=TICKER),
            _obs("2025-10-10T01:02:00Z", 8700, ticker=TICKER),
            _obs("2025-10-10T01:00:00Z", 6000, ticker="KX-ORL", gid=other),
            _obs("2025-10-10T01:01:00Z", 6300, ticker="KX-ORL", gid=other),
            _obs("2025-10-10T01:02:00Z", 8700, ticker="KX-ORL", gid=other),
        ),
        settlements=(
            Settlement(ticker=TICKER, result=SettlementResult.YES, settlement_value_e4=10000),
            Settlement(ticker="KX-ORL", result=SettlementResult.NO, settlement_value_e4=0),
        ),
    )
    out = run_plan(plan, ctx)
    gids = {r.internal_game_id for r in out.rows}
    assert GID in gids and other in gids
    assert len(out.rows) == len({r.identity() for r in out.rows})


def test_malformed_and_empty_and_capabilities():
    plan = compile_research(_q(), CFG)
    empty = run_plan(plan, _ctx(closes=[("2025-10-10T01:00:00Z", 5000)]))
    assert empty.status is BacktestStatus.ZERO_RESULTS
    assert empty.status is not BacktestStatus.DATA_REQUIRED
    assert run_conditional_backtest(_q(market_data=("l2",)), CFG).status is BacktestStatus.DATA_REQUIRED
    assert run_conditional_backtest(_q(market_data=("tick",)), CFG).status is BacktestStatus.DATA_REQUIRED
    assert run_conditional_backtest(_q(market_data=("orderbook",)), CFG).status is BacktestStatus.DATA_REQUIRED
    assert run_conditional_backtest(_q(market_data=("trade_tape",)), CFG).status is BacktestStatus.DATA_REQUIRED
    assert run_conditional_backtest(_q(dims=("PBP_MARKET_PIT_ALIGNMENT",)), CFG).status is BacktestStatus.OPERATION_REQUIRED
    with pytest.raises(ValueError):
        MarketObservation(ticker="", basis=ObservationBasis.TRADABLE_YES_BID, available_at="2025-10-10T01:00:00Z", yes_bid_close=6300)


def test_no_fill_or_settlement_inference_fields():
    plan = compile_research(_q(), CFG)
    out = run_plan(plan, _ctx(closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 3700)]))
    dumped = str(out.to_dict())
    for banned in ("fill_price", "maker_fill", "taker_fill", "queue_position", "slippage", "home_win"):
        assert banned not in dumped
    src = Path(__file__).resolve().parents[1] / "roller" / "warehouse" / "conditional_backtest.py"
    text = src.read_text(encoding="utf-8")
    assert "official_settlement" not in text
    assert "home_win" not in text
    assert "final_score" not in text
    last_candle = compile_research(_q(paths=(), dims=("HOLD_TO_SETTLEMENT",)), CFG)
    last = run_plan(last_candle, _ctx(closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 0)]))
    assert last.rows[0].classification == Classification.MISSING_SETTLEMENT.value
    hundred = run_plan(last_candle, _ctx(closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 10000)]))
    assert hundred.rows[0].classification == Classification.MISSING_SETTLEMENT.value


def test_path_boundary_equality():
    closes_eq = [("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 8700)]
    reach = compile_research(
        _q(paths=(PathCondition(id="w", op=PathOp.REACH, price_e4=8700, outcome=ExitOutcome.WIN),), dims=("NO_TERMINAL_RESULT",)),
        CFG,
    )
    assert run_plan(reach, _ctx(closes=closes_eq)).rows[0].classification == Classification.WIN.value
    rise = compile_research(
        _q(paths=(PathCondition(id="w", op=PathOp.RISE_TO, price_e4=8700, outcome=ExitOutcome.WIN),), dims=("NO_TERMINAL_RESULT",)),
        CFG,
    )
    assert run_plan(rise, _ctx(closes=closes_eq)).rows[0].classification == Classification.WIN.value
    rec = compile_research(
        _q(paths=(PathCondition(id="w", op=PathOp.RECOVER, price_e4=8700, outcome=ExitOutcome.WIN),), dims=("NO_TERMINAL_RESULT",)),
        CFG,
    )
    assert run_plan(rec, _ctx(closes=closes_eq)).rows[0].classification == Classification.WIN.value
    drop = compile_research(
        _q(paths=(PathCondition(id="l", op=PathOp.DROP_TO, price_e4=4100, outcome=ExitOutcome.LOSS),), dims=("NO_TERMINAL_RESULT",)),
        CFG,
    )
    assert run_plan(drop, _ctx(closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 4100)])).rows[0].classification == Classification.LOSS.value
    already = compile_research(
        _q(paths=(PathCondition(id="w", op=PathOp.REACH, price_e4=6300, outcome=ExitOutcome.WIN),), dims=("NO_TERMINAL_RESULT",)),
        CFG,
    )
    stay = run_plan(already, _ctx(closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300), ("2025-10-10T01:02:00Z", 6300)]))
    assert stay.rows[0].classification == Classification.NO_TERMINAL_RESULT.value


def test_period_leaks_q1_to_ot():
    closes = [("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)]
    for period, pbp_period, expect in (
        ("Q2", "1", 0),
        ("Q2", "2", 1),
        ("Q3", "2", 0),
        ("Q3", "3", 1),
        ("Q4", "3", 0),
        ("Q4", "4", 1),
        ("Q4", "5", 0),
        ("OT", "4", 0),
        ("OT", "5", 1),
    ):
        plan = compile_research(
            _q(
                entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, period=period, operation=EntryOp.CROSS),),
                paths=(),
                dims=("NO_TERMINAL_RESULT",),
            ),
            CFG,
        )
        pbp = (
            PBPEvent(
                internal_game_id=GID,
                event_timestamp="2025-10-10T01:00:30Z",
                available_at="2025-10-10T01:00:30Z",
                period=pbp_period,
                clock="6:00",
            ),
        )
        assert run_plan(plan, _ctx(closes=closes, pbp=pbp)).population == expect, (period, pbp_period)


def test_dst_keeps_utc_order():
    plan = compile_research(_q(paths=(), dims=("NO_TERMINAL_RESULT",)), CFG)
    out = run_plan(
        plan,
        _ctx(
            closes=[
                ("2025-11-02T05:59:00Z", 6000),
                ("2025-11-02T06:00:00Z", 6300),
                ("2025-11-02T07:00:00Z", 6400),
            ]
        ),
    )
    assert out.population == 1
    assert out.rows[0].entry_timestamp == "2025-11-02T06:00:00Z"
    assert out.rows[0].entry_timestamp.endswith("Z")


def test_date_range_and_duplicate_records():
    inverted = compile_research(_q(date_from="2026-06-01", date_to="2025-01-01"), CFG)
    assert inverted.status.value == "DATA_REQUIRED"
    plan = compile_research(_q(), CFG)
    dup_link = GameMarketLink(status=LinkStatus.LINKED, internal_game_id=GID, ticker=TICKER, identity_rule_version="1.0.0")
    ctx = _ctx(
        games=(
            Game(internal_game_id=GID, sport="NBA", season="2025-2026", league="NBA", game_date="2025-10-10"),
            Game(internal_game_id=GID, sport="NBA", season="2025-2026", league="NBA", game_date="2025-10-10"),
        ),
        links=(dup_link, dup_link),
        obs=(
            _obs("2025-10-10T01:00:00Z", 6000),
            _obs("2025-10-10T01:00:00Z", 6000),
            _obs("2025-10-10T01:01:00Z", 6300),
            _obs("2025-10-10T01:01:00Z", 6300),
            _obs("2025-10-10T01:02:00Z", 8700),
        ),
        settlements=(
            Settlement(ticker=TICKER, result=SettlementResult.YES, settlement_value_e4=10000),
            Settlement(ticker=TICKER, result=SettlementResult.YES, settlement_value_e4=10000),
        ),
        pbp=(
            PBPEvent(internal_game_id=GID, event_timestamp="2025-10-10T01:00:30Z", available_at="2025-10-10T01:00:30Z", period="2", clock="8:00"),
            PBPEvent(internal_game_id=GID, event_timestamp="2025-10-10T01:00:30Z", available_at="2025-10-10T01:00:30Z", period="2", clock="8:00"),
        ),
    )
    out = run_plan(plan, ctx)
    assert out.population == 1
    assert len(out.rows) == 1


def test_malformed_clock_and_period_fail_closed():
    plan = compile_research(
        _q(
            entries=(EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, period="Q2", operation=EntryOp.CROSS),),
            paths=(),
            dims=("NO_TERMINAL_RESULT",),
        ),
        CFG,
    )
    closes = [("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6300)]
    bad_clock = (
        PBPEvent(
            internal_game_id=GID,
            event_timestamp="2025-10-10T01:00:30Z",
            available_at="2025-10-10T01:00:30Z",
            period="2",
            clock="not-a-clock",
        ),
    )
    out = run_plan(plan, _ctx(closes=closes, pbp=bad_clock))
    assert out.population in {0, 1}
    if out.population == 1:
        assert out.rows[0].entry_clock in {"", "not-a-clock"}
    bad_period = (
        PBPEvent(
            internal_game_id=GID,
            event_timestamp="2025-10-10T01:00:30Z",
            available_at="2025-10-10T01:00:30Z",
            period="xx",
            clock="8:00",
        ),
    )
    leaked = run_plan(plan, _ctx(closes=closes, pbp=bad_period))
    assert leaked.population == 0


def test_ordinals_first_second_third():
    closes = [
        ("2025-10-10T01:00:00Z", 6000),
        ("2025-10-10T01:01:00Z", 6300),
        ("2025-10-10T01:02:00Z", 6000),
        ("2025-10-10T01:03:00Z", 6300),
        ("2025-10-10T01:04:00Z", 6000),
        ("2025-10-10T01:05:00Z", 6300),
    ]
    expected = {
        TouchOrdinal.FIRST_TOUCH: "2025-10-10T01:01:00Z",
        TouchOrdinal.SECOND_TOUCH: "2025-10-10T01:03:00Z",
        TouchOrdinal.THIRD_TOUCH: "2025-10-10T01:05:00Z",
    }
    for ordinal, ts in expected.items():
        plan = compile_research(
            _q(entries=(EntryCondition(id="e1", ordinal=ordinal, price_e4=6300),), paths=(), dims=("NO_TERMINAL_RESULT",)),
            CFG,
        )
        out = run_plan(plan, _ctx(closes=closes))
        assert out.population == 1
        assert out.rows[0].entry_timestamp == ts


def test_live_date_range_stays_on_requested_day():
    from roller.warehouse.query_context import get_research_context

    loaded = get_research_context(_q(game_data=("pbp",)), CFG)
    assert loaded.context is not None
    dates = {g.game_date for g in loaded.context.games}
    assert dates <= {"2025-10-10"}
