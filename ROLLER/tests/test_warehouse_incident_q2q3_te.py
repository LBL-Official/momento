"""Warehouse incident: Q2∨Q3, TE 6–20, hold settlement books, exposure verify.

Does not change First Touch crossing math. Does not import first80 or execute.py
from the warehouse contract. CANDLE PATH ≠ FILL.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from roller.config import RollerConfig
from roller.research_query.models import (
    EntryCondition,
    EntryOp,
    ExitOutcome,
    PathCondition,
    PathOp,
    PeriodWindow,
    ResearchQuestion,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)
from roller.warehouse.conditional_backtest import (
    Classification,
    _compiled_to_condition,
    compare_backtest_rows,
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
from roller.warehouse.frontend_contract import (
    execute_frontend_research,
    question_from_draft,
    results_contract,
)
from roller.warehouse.query_context import ResearchContext
from roller.warehouse.research_compiler import compile_research

ROLLER_ROOT = Path(__file__).resolve().parents[1]
CFG = RollerConfig(ROLLER_ROOT)
GID = "NBA_20251010_BOS_TOR"
TICKER = "KX-BOS"
LIVE = ROLLER_ROOT / "data" / "nba" / "2025_2026" / "derived" / "warehouse"


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


def _q2q3_entry() -> EntryCondition:
    return EntryCondition(
        id="e1",
        ordinal=TouchOrdinal.FIRST_TOUCH,
        price_e4=8000,
        operation=EntryOp.FIRST_TOUCH,
        period_windows=(PeriodWindow(period="Q2"), PeriodWindow(period="Q3")),
    )


def _question(*, entries=None, paths=None, win_hold=True, **universe_kw) -> ResearchQuestion:
    return ResearchQuestion(
        universe=_universe(**universe_kw),
        entry_conditions=entries or (_q2q3_entry(),),
        path_conditions=paths
        or (PathCondition(id="loss", op=PathOp.REACH, price_e4=3500, outcome=ExitOutcome.LOSS),),
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=("HOLD_TO_SETTLEMENT",),
        win_hold=win_hold,
    )


def _obs(ts: str, close: int, ticker: str = TICKER) -> MarketObservation:
    return MarketObservation(
        ticker=ticker,
        basis=ObservationBasis.TRADABLE_YES_BID,
        available_at=ts,
        internal_game_id=GID,
        yes_bid_close=close,
    )


def _pbp(*, period: str, home: int | None = 70, away: int | None = 60, ts: str = "2025-10-10T01:00:30Z") -> PBPEvent:
    return PBPEvent(
        internal_game_id=GID,
        event_timestamp=ts,
        available_at=ts,
        period=period,
        clock="8:00",
        event_number="1",
        home_score=home,
        away_score=away,
    )


def _bag(*, closes, settlement=SettlementResult.YES, pbp=(), ticker=TICKER):
    settle = ()
    if settlement is not None:
        settle = (
            Settlement(
                ticker=ticker,
                result=settlement,
                settlement_value_e4=10000 if settlement is SettlementResult.YES else 0,
            ),
        )
    return ResearchContext(
        games=(Game(internal_game_id=GID, sport="NBA", season="2025-2026", league="NBA", game_date="2025-10-10"),),
        links=(
            GameMarketLink(status=LinkStatus.LINKED, internal_game_id=GID, ticker=ticker, identity_rule_version="1.0.0"),
        ),
        observations=tuple(_obs(ts, px, ticker) for ts, px in closes),
        settlements=settle,
        pbp_events=pbp,
        warehouse_version="test",
    )


TOUCH_CLOSES = [
    ("2025-10-10T01:00:00Z", 7900),
    ("2025-10-10T01:01:00Z", 8100),
]


def test_period_windows_survive_draft_or():
    question, errors = question_from_draft(
        {
            "universe": {
                "sports": ["NBA"],
                "leagues": ["NBA"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
                "dateFrom": "2025-10-10",
                "dateTo": "2025-10-10",
            },
            "entryConditions": [
                {
                    "id": "e1",
                    "family": "first_touch",
                    "priceCents": 80,
                    "periodWindows": [{"period": "Q2"}, {"period": "Q3"}],
                }
            ],
            "exitConditions": [
                {"id": "loss", "kind": "path", "family": "reach", "priceCents": 35, "outcome": "loss"},
                {"id": "term", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
            ],
            "teFilters": {"customRange": {"min": 6, "max": 20}},
        }
    )
    assert "missing_entry" not in errors
    assert question is not None
    entry = question.entry_conditions[0]
    assert entry.period is None
    assert [w.period for w in entry.period_windows] == ["Q2", "Q3"]
    assert "pbp" in question.universe.game_data
    assert question.win_hold is True


def test_single_period_chip_stays_flat():
    question, _ = question_from_draft(
        {
            "universe": {
                "sports": ["NBA"],
                "leagues": ["NBA"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
            },
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q2"}],
            "exitConditions": [
                {"id": "loss", "kind": "path", "family": "reach", "priceCents": 35, "outcome": "loss"},
                {"id": "term", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
            ],
        }
    )
    assert question is not None
    assert question.entry_conditions[0].period == "Q2"
    assert question.entry_conditions[0].period_windows == ()


def test_compiled_to_condition_keeps_period_windows():
    plan = compile_research(_question(), CFG)
    cond = _compiled_to_condition(plan.entries[0])
    assert [w.period for w in cond.period_windows] == ["Q2", "Q3"]
    assert cond.has_period_or_clock()


def test_q2_or_q3_keeps_aligned_and_excludes_unaligned():
    q = _question(paths=(), win_hold=False)
    plan = compile_research(q, CFG)
    q2 = run_plan(plan, _bag(closes=TOUCH_CLOSES, settlement=None, pbp=(_pbp(period="2"),)))
    q3 = run_plan(plan, _bag(closes=TOUCH_CLOSES, settlement=None, pbp=(_pbp(period="3"),)))
    q1 = run_plan(plan, _bag(closes=TOUCH_CLOSES, settlement=None, pbp=(_pbp(period="1"),)))
    none = run_plan(plan, _bag(closes=TOUCH_CLOSES, settlement=None, pbp=()))
    assert q2.population == 1
    assert q2.rows[0].entry_period == "Q2"
    assert q3.population == 1
    assert q3.rows[0].entry_period == "Q3"
    assert q1.population == 0
    assert none.population == 0
    assert "period_unaligned" in none.exclusions or "period_filter" in none.exclusions
    assert q2.rows[0].entry_period != "UNALIGNED"
    assert q3.rows[0].entry_period != "UNALIGNED"


def test_te_custom_6_20_keeps_and_drops():
    q = _question(paths=(), win_hold=False)
    plan = compile_research(q, CFG)
    filters = {"customRange": {"min": 6, "max": 20}}
    keep = run_plan(
        plan,
        _bag(closes=TOUCH_CLOSES, settlement=None, pbp=(_pbp(period="2", home=70, away=60),)),
        te_filters=filters,
    )
    drop_small = run_plan(
        plan,
        _bag(closes=TOUCH_CLOSES, settlement=None, pbp=(_pbp(period="2", home=53, away=50),)),
        te_filters=filters,
    )
    drop_missing = run_plan(
        plan,
        _bag(closes=TOUCH_CLOSES, settlement=None, pbp=(_pbp(period="2", home=None, away=None),)),
        te_filters=filters,
    )
    assert keep.population == 1
    assert drop_small.population == 0
    assert drop_missing.population == 0
    assert drop_small.exclusions.get("te_scope", 0) >= 1
    assert drop_missing.exclusions.get("te_scope", 0) >= 1


def test_hold_settlement_books_do_not_rewrite_row_class():
    q = _question()
    plan = compile_research(q, CFG)
    held_yes = run_plan(plan, _bag(closes=TOUCH_CLOSES, settlement=SettlementResult.YES, pbp=(_pbp(period="2"),)))
    held_no = run_plan(plan, _bag(closes=TOUCH_CLOSES, settlement=SettlementResult.NO, pbp=(_pbp(period="2"),)))
    missing = run_plan(plan, _bag(closes=TOUCH_CLOSES, settlement=None, pbp=(_pbp(period="2"),)))
    loss = run_plan(
        plan,
        _bag(
            closes=[*TOUCH_CLOSES, ("2025-10-10T01:02:00Z", 3500)],
            settlement=SettlementResult.YES,
            pbp=(_pbp(period="2"),),
        ),
    )
    assert held_yes.rows[0].classification == Classification.HELD_TO_SETTLEMENT.value
    assert held_yes.rows[0].settlement_status == "YES"
    assert held_no.rows[0].classification == Classification.HELD_TO_SETTLEMENT.value
    assert missing.rows[0].classification == Classification.MISSING_SETTLEMENT.value
    assert loss.rows[0].classification == Classification.LOSS.value
    yes_c = results_contract(q, plan, held_yes)
    no_c = results_contract(q, plan, held_no)
    miss_c = results_contract(q, plan, missing)
    loss_c = results_contract(q, plan, loss)
    assert yes_c["statistics"]["terminal_win_n"] == 1
    assert yes_c["statistics"]["W"] == 1
    assert yes_c["statistics"]["L"] == 0
    assert no_c["statistics"]["terminal_loss_n"] == 1
    assert no_c["statistics"]["L"] == 1
    assert no_c["statistics"]["W"] == 0
    assert miss_c["statistics"]["unresolved_n"] == 1
    assert miss_c["statistics"]["L"] == 0
    assert miss_c["statistics"]["W"] == 0
    assert loss_c["statistics"]["path_loss_n"] == 1
    assert loss_c["statistics"]["L"] == 1
    assert loss_c["statistics"]["terminal_win_n"] == 0
    assert loss_c["statistics"]["official_w_n"] == 1
    assert yes_c["statistics"]["official_w_n"] == 1
    assert no_c["statistics"]["official_l_n"] == 1
    assert yes_c["statistics"]["reward_e4"] == 2000
    assert yes_c["statistics"]["risk_e4"] == 4500
    assert yes_c["statistics"]["rr"] == pytest.approx(2000 / 4500)
    assert yes_c["statistics"]["ev_e4"] == pytest.approx(2000)
    assert loss_c["statistics"]["rr"] == pytest.approx(2000 / 4500)
    assert loss_c["statistics"]["ev_e4"] == pytest.approx(-4500)
    assert no_c["statistics"]["rr"] == pytest.approx(2000 / 4500)
    assert no_c["statistics"]["ev_e4"] == pytest.approx(-8000)
    assert loss_c["exposure"]["status"] in {"OBSERVED", "UNVERIFIED", "CARDINALITY_VIOLATION"}
    assert loss_c["te_scope"]["n_scoped"] == 1


def test_zero_close_is_not_loss_reach():
    q = _question()
    plan = compile_research(q, CFG)
    held = run_plan(
        plan,
        _bag(
            closes=[*TOUCH_CLOSES, ("2025-10-10T01:02:00Z", 0), ("2025-10-10T01:03:00Z", 8200)],
            settlement=SettlementResult.YES,
            pbp=(_pbp(period="2"),),
        ),
    )
    later_35 = run_plan(
        plan,
        _bag(
            closes=[
                *TOUCH_CLOSES,
                ("2025-10-10T01:02:00Z", 0),
                ("2025-10-10T01:03:00Z", 3400),
            ],
            settlement=SettlementResult.YES,
            pbp=(_pbp(period="2"),),
        ),
    )
    assert held.population == 1
    assert held.rows[0].classification == Classification.HELD_TO_SETTLEMENT.value
    assert held.rows[0].loss_exit_value is None
    assert later_35.rows[0].classification == Classification.LOSS.value
    assert later_35.rows[0].loss_exit_value == 3400


def test_reference_matches_optimized_for_incident_fixture():
    q = _question()
    plan = compile_research(q, CFG)
    ctx = _bag(
        closes=[*TOUCH_CLOSES, ("2025-10-10T01:02:00Z", 3500)],
        settlement=SettlementResult.YES,
        pbp=(_pbp(period="2", home=70, away=60),),
    )
    filters = {"customRange": {"min": 6, "max": 20}}
    ref = run_plan_reference(plan, ctx, te_filters=filters)
    opt = run_plan_optimized(plan, ctx, te_filters=filters)
    assert compare_backtest_rows(ref, opt) == []
    assert [r.to_dict() for r in ref.rows] == [r.to_dict() for r in opt.rows]


def test_frontend_constructor_serializes_period_windows():
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
    assert "period_windows" in text
    assert "periodWindows" in text
    assert "teFiltersActive" in text


@pytest.mark.skipif(not (LIVE / "manifest.json").is_file(), reason="NBA warehouse absent")
def test_live_exact_question_applies_constraints():
    question = ResearchQuestion(
        universe=Universe(
            sports=("NBA",),
            leagues=("NBA",),
            seasons=("2025-2026",),
            markets=("kalshi",),
            market_data=("candles",),
            game_data=("pbp",),
            date_from="2025-03-18",
            date_to="2026-09-01",
        ),
        entry_conditions=(_q2q3_entry(),),
        path_conditions=(PathCondition(id="loss", op=PathOp.REACH, price_e4=3500, outcome=ExitOutcome.LOSS),),
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=("HOLD_TO_SETTLEMENT",),
        win_hold=True,
    )
    te = {"customRange": {"min": 6, "max": 20}}
    executed = execute_frontend_research(
        {"question": question.to_dict(), "te_filters": te},
        CFG,
        include_reference=True,
    )
    assert executed["status"] in {"READY", "ZERO_RESULTS"}
    contract = executed["results_contract"]
    assert contract is not None
    assert [w["period"] for w in contract["entry"][0].get("period_windows") or []] == ["Q2", "Q3"]
    assert contract["te_scope"]["requested"]["custom_range"] == {"min": 6, "max": 20}
    for row in contract["audit_rows"]:
        assert row["entry_period"] in {"Q2", "Q3"}
        assert row["entry_period"] != "UNALIGNED"
    assert executed.get("difference_count", 0) == 0
    stats = contract["statistics"]
    assert stats["W"] == stats["path_win_n"] + stats["terminal_win_n"]
    assert stats["L"] == stats["path_loss_n"] + stats["terminal_loss_n"]
    assert stats["unresolved_n"] >= 0
    assert contract["exposure"]["exposure_unit"] == "GAME"
    assert contract["population"] == executed["result"]["population"]
