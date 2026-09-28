"""Accept-through ceiling and one-trade-per-game enforcement.

First Touch is still prior < P and current >= P. The recorded entry is the
observed close, never rewritten to P. max_entry_e4 is not crossings_band.
GAME / 1 keeps the first chronological market First Touch and drops later
sides of the same game only when strategy_enforced is requested.
CANDLE PATH ≠ FILL.
"""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.exposure_contract import MODE_STRATEGY_ENFORCED, MODE_VERIFY_ONLY
from roller.research_query.models import (
    EntryCondition,
    EntryOp,
    PathCondition,
    PathOp,
    ResearchQuestion,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)
from roller.research_query.validation import validate_question
from roller.warehouse.conditional_backtest import compare_backtest_rows, run_plan
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
from roller.warehouse.frontend_contract import (
    exposure_from_body,
    question_from_draft,
    results_contract,
)
from roller.warehouse.query_context import ResearchContext
from roller.warehouse.research_compiler import compile_research

ROLLER_ROOT = Path(__file__).resolve().parents[1]
CFG = RollerConfig(ROLLER_ROOT)
GID = "NBA_20251010_BOS_TOR"
HOME = "KX-BOS"
AWAY = "KX-TOR"


def _universe() -> Universe:
    return Universe(
        sports=("NBA",),
        leagues=("NBA",),
        seasons=("2025-2026",),
        markets=("kalshi",),
        market_data=("candles",),
        game_data=("pbp",),
        date_from="2025-10-10",
        date_to="2025-10-10",
    )


def _question(*, max_entry_e4: int | None = None) -> ResearchQuestion:
    return ResearchQuestion(
        universe=_universe(),
        entry_conditions=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=8000,
                operation=EntryOp.FIRST_TOUCH,
                max_entry_e4=max_entry_e4,
            ),
        ),
        path_conditions=(PathCondition(id="loss", op=PathOp.REACH, price_e4=3500),),
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=("HOLD_TO_SETTLEMENT",),
        win_hold=True,
    )


def _obs(ts: str, close: int, ticker: str) -> MarketObservation:
    return MarketObservation(
        ticker=ticker,
        basis=ObservationBasis.TRADABLE_YES_BID,
        available_at=ts,
        internal_game_id=GID,
        yes_bid_close=close,
    )


def _pbp() -> PBPEvent:
    return PBPEvent(
        internal_game_id=GID,
        event_timestamp="2025-10-10T01:00:30Z",
        available_at="2025-10-10T01:00:30Z",
        period="2",
        clock="8:00",
        event_number="1",
        home_score=70,
        away_score=60,
    )


def _ctx(closes_by_ticker: dict[str, list[tuple[str, int]]]) -> ResearchContext:
    tickers = tuple(closes_by_ticker)
    return ResearchContext(
        games=(Game(internal_game_id=GID, sport="NBA", season="2025-2026", league="NBA", game_date="2025-10-10"),),
        links=tuple(
            GameMarketLink(
                status=LinkStatus.LINKED,
                internal_game_id=GID,
                ticker=ticker,
                identity_rule_version="1.0.0",
            )
            for ticker in tickers
        ),
        observations=tuple(
            _obs(ts, px, ticker) for ticker, closes in closes_by_ticker.items() for ts, px in closes
        ),
        settlements=tuple(
            Settlement(
                ticker=ticker,
                result=SettlementResult.YES,
                settlement_value_e4=10000,
            )
            for ticker in tickers
        ),
        pbp_events=(_pbp(),),
        warehouse_version="test",
    )


GAME_ENFORCE = {
    "enforcement_mode": MODE_STRATEGY_ENFORCED,
    "exposure_unit": "GAME",
    "max_entries_per_unit": 1,
}


def test_warehouse_records_jump_through_close():
    plan = compile_research(_question(), CFG)
    assert plan.entries[0].max_entry_e4 is None
    result = run_plan(
        plan,
        _ctx({HOME: [("2025-10-10T01:00:00Z", 7900), ("2025-10-10T01:01:00Z", 8100)]}),
    )
    assert result.population == 1
    assert result.rows[0].entry_value == 8100


def test_warehouse_max_entry_rejects_94_and_does_not_take_later_82():
    plan = compile_research(_question(max_entry_e4=8900), CFG)
    assert plan.entries[0].max_entry_e4 == 8900
    result = run_plan(
        plan,
        _ctx(
            {
                HOME: [
                    ("2025-10-10T01:00:00Z", 7900),
                    ("2025-10-10T01:01:00Z", 9400),
                    ("2025-10-10T01:02:00Z", 7000),
                    ("2025-10-10T01:03:00Z", 8200),
                ]
            }
        ),
    )
    assert result.population == 0
    assert result.exclusions.get("max_entry_exceeded", 0) >= 1


def test_warehouse_max_entry_accepts_81_through_89():
    plan = compile_research(_question(max_entry_e4=8900), CFG)
    result = run_plan(
        plan,
        _ctx({HOME: [("2025-10-10T01:00:00Z", 7900), ("2025-10-10T01:01:00Z", 8100)]}),
    )
    assert result.population == 1
    assert result.rows[0].entry_value == 8100


def test_draft_max_entry_survives_warehouse_question():
    question, errors = question_from_draft(
        {
            "universe": {
                "sports": ["NBA"],
                "leagues": ["NBA"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
            },
            "entryConditions": [
                {"id": "e1", "family": "first_touch", "priceCents": 80, "maxEntryCents": 89}
            ],
            "exitConditions": [
                {"id": "loss", "kind": "path", "family": "reach", "priceCents": 35, "outcome": "loss"},
                {"id": "term", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
            ],
        }
    )
    assert "invalid_max_entry" not in errors
    assert question is not None
    assert question.entry_conditions[0].price_e4 == 8000
    assert question.entry_conditions[0].price_to_e4 is None
    assert question.entry_conditions[0].max_entry_e4 == 8900


def test_max_entry_below_trigger_is_invalid():
    errors = validate_question(_question(max_entry_e4=7000))
    assert any("max_entry_e4" in e for e in errors)


def test_one_trade_per_game_keeps_first_chronological_side():
    ctx = _ctx(
        {
            HOME: [("2025-10-10T01:00:00Z", 7900), ("2025-10-10T01:01:00Z", 8100)],
            AWAY: [("2025-10-10T01:00:00Z", 7900), ("2025-10-10T01:03:00Z", 8000)],
        }
    )
    plan = compile_research(_question(), CFG)
    both = run_plan(plan, ctx)
    one = run_plan(plan, ctx, exposure=GAME_ENFORCE)
    verify = run_plan(
        plan,
        ctx,
        exposure={"enforcement_mode": MODE_VERIFY_ONLY, "exposure_unit": "GAME", "max_entries_per_unit": 1},
    )
    assert both.population == 2
    assert verify.population == 2
    assert one.population == 1
    assert one.rows[0].market_id == HOME
    assert one.rows[0].entry_value == 8100
    assert one.exclusions.get("exposure_game", 0) == 1


def test_exposure_from_body_requires_explicit_enforcement():
    assert exposure_from_body({"exposure_unit": "GAME", "max_entries_per_unit": 1})[
        "enforcement_mode"
    ] == MODE_VERIFY_ONLY
    requested = exposure_from_body(
        {
            "exposure_enforcement_mode": "strategy_enforced",
            "exposure_unit": "GAME",
            "max_entries_per_unit": 1,
        }
    )
    assert requested is not None
    assert requested["enforcement_mode"] == MODE_STRATEGY_ENFORCED


def test_reference_matches_optimized_with_ceiling_and_game_cap():
    plan = compile_research(_question(max_entry_e4=8900), CFG)
    ctx = _ctx(
        {
            HOME: [("2025-10-10T01:00:00Z", 7900), ("2025-10-10T01:01:00Z", 8100)],
            AWAY: [("2025-10-10T01:00:00Z", 7900), ("2025-10-10T01:03:00Z", 9400)],
        }
    )
    ref = run_plan(plan, ctx, engine_id="reference", exposure=GAME_ENFORCE)
    opt = run_plan(plan, ctx, engine_id="optimized", exposure=GAME_ENFORCE)
    assert ref.population == 1
    assert opt.population == 1
    assert compare_backtest_rows(ref, opt) == []
    contract = results_contract(
        _question(max_entry_e4=8900),
        plan,
        opt,
        body={"exposure_enforcement_mode": "strategy_enforced", "exposure_unit": "GAME", "max_entries_per_unit": 1},
    )
    assert contract["exposure"]["execution_enforced"] is True
    assert contract["population"] == 1
    assert contract["entry"][0]["max_entry_e4"] == 8900
