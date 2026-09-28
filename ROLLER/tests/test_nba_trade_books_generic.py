"""NBA warehouse → Labs → SuperASI A trade books are generic.

Any NBA entry shape uses the same W/L / R:R / EV books as Results.
Hold-YES is 100¢ settlement, not a fill. Path LOSS stays LOSS.
Does not change live FIRST01 / 80/81/83/89. Candle path ≠ fill.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from roller.config import RollerConfig
from roller.labs.schema import strategy_fields
from roller.labs.store import _canonical_csv
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
from roller.superasi.base.ingest import parse_labs_csv
from roller.superasi.base.observed import summarize_observed
from roller.warehouse.conditional_backtest import Classification, run_plan
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
    _is_win_hold,
    _plan_trade_prices,
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

HOLD_EXITS = [
    {"id": "loss", "kind": "path", "family": "reach", "priceCents": 35, "outcome": "loss"},
    {"id": "term", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
]

NBA_HOLD_ENTRIES = (
    (
        "first_touch_80_q2_or_q3",
        {
            "family": "first_touch",
            "priceCents": 80,
            "periodWindows": [{"period": "Q2"}, {"period": "Q3"}],
        },
        8000,
        3500,
    ),
    ("first_touch_80_q1", {"family": "first_touch", "priceCents": 80, "period": "Q1"}, 8000, 3500),
    ("first_touch_80_q4", {"family": "first_touch", "priceCents": 80, "period": "Q4"}, 8000, 3500),
    ("first_touch_83", {"family": "first_touch", "priceCents": 83}, 8300, 3500),
    ("cross_65_q2", {"family": "cross", "priceCents": 65, "period": "Q2"}, 6500, 3500),
    ("break_71", {"family": "break", "priceCents": 71}, 7100, 3500),
)

NBA_PATH_ENTRIES = (
    ("cross_63_reach_87_41", {"family": "cross", "priceCents": 63}, 6300, 8700, 4100),
    ("first_touch_80_reach_90_35", {"family": "first_touch", "priceCents": 80}, 8000, 9000, 3500),
)

TOUCH_CLOSES = [
    ("2025-10-10T01:00:00Z", 7900),
    ("2025-10-10T01:01:00Z", 8100),
]
CROSS_CLOSES = [
    ("2025-10-10T01:00:00Z", 6400),
    ("2025-10-10T01:01:00Z", 6600),
]
BREAK_CLOSES = [
    ("2025-10-10T01:00:00Z", 7000),
    ("2025-10-10T01:01:00Z", 7200),
]


def _nba_draft(entry: dict, exits: list[dict]) -> dict:
    return {
        "universe": {
            "sports": ["NBA"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
            "dateFrom": "2025-10-10",
            "dateTo": "2025-10-10",
        },
        "entryConditions": [{"id": "e1", **entry}],
        "exitConditions": exits,
    }


def _compile(entry: dict, exits: list[dict]):
    question, errors = question_from_draft(_nba_draft(entry, exits))
    assert question is not None
    assert "missing_entry" not in errors
    assert "missing_win_exit" not in errors
    return question, compile_research(question, CFG)


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


def _question(*, entries, paths, win_hold=True) -> ResearchQuestion:
    return ResearchQuestion(
        universe=_universe(),
        entry_conditions=entries,
        path_conditions=paths,
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=("HOLD_TO_SETTLEMENT",),
        win_hold=win_hold,
    )


def _obs(ts: str, close: int) -> MarketObservation:
    return MarketObservation(
        ticker=TICKER,
        basis=ObservationBasis.TRADABLE_YES_BID,
        available_at=ts,
        internal_game_id=GID,
        yes_bid_close=close,
    )


def _pbp(period: str) -> PBPEvent:
    return PBPEvent(
        internal_game_id=GID,
        event_timestamp="2025-10-10T01:00:30Z",
        available_at="2025-10-10T01:00:30Z",
        period=period,
        clock="8:00",
        event_number="1",
        home_score=70,
        away_score=60,
    )


def _bag(*, closes, settlement=SettlementResult.YES, period: str | None = "2"):
    settle = ()
    if settlement is not None:
        settle = (
            Settlement(
                ticker=TICKER,
                result=settlement,
                settlement_value_e4=10000 if settlement is SettlementResult.YES else 0,
            ),
        )
    return ResearchContext(
        games=(Game(internal_game_id=GID, sport="NBA", season="2025-2026", league="NBA", game_date="2025-10-10"),),
        links=(
            GameMarketLink(status=LinkStatus.LINKED, internal_game_id=GID, ticker=TICKER, identity_rule_version="1.0.0"),
        ),
        observations=tuple(_obs(ts, px) for ts, px in closes),
        settlements=settle,
        pbp_events=(_pbp(period),) if period else (),
        warehouse_version="test",
    )


@pytest.mark.parametrize("label,entry,entry_e4,loss_e4", NBA_HOLD_ENTRIES)
def test_any_nba_hold_yes_compiles_to_settlement_prices(label, entry, entry_e4, loss_e4):
    question, plan = _compile(entry, HOLD_EXITS)
    assert question.win_hold is True
    assert _is_win_hold(question, plan) is True
    got_entry, win_exit, loss_exit = _plan_trade_prices(plan, question)
    assert got_entry == entry_e4
    assert win_exit == 10000
    assert loss_exit == loss_e4
    reward = win_exit - got_entry
    risk = got_entry - loss_exit
    assert reward == 10000 - entry_e4
    assert risk == entry_e4 - loss_e4


@pytest.mark.parametrize("label,entry,entry_e4,win_e4,loss_e4", NBA_PATH_ENTRIES)
def test_any_nba_path_exits_keep_path_prices(label, entry, entry_e4, win_e4, loss_e4):
    exits = [
        {"id": "win", "kind": "path", "family": "reach", "priceCents": win_e4 // 100, "outcome": "win"},
        {"id": "loss", "kind": "path", "family": "reach", "priceCents": loss_e4 // 100, "outcome": "loss"},
    ]
    question, plan = _compile(entry, exits)
    assert question.win_hold is False
    assert _is_win_hold(question, plan) is False
    got_entry, win_exit, loss_exit = _plan_trade_prices(plan, question)
    assert got_entry == entry_e4
    assert win_exit == win_e4
    assert loss_exit == loss_e4


def test_compiled_hold_does_not_need_question_flag():
    q = _question(
        entries=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=8000,
                operation=EntryOp.FIRST_TOUCH,
                period_windows=(PeriodWindow(period="Q2"), PeriodWindow(period="Q3")),
            ),
        ),
        paths=(PathCondition(id="loss", op=PathOp.REACH, price_e4=3500, outcome=ExitOutcome.LOSS),),
    )
    plan = compile_research(q, CFG)
    held = run_plan(plan, _bag(closes=TOUCH_CLOSES, settlement=SettlementResult.YES))
    assert held.population == 1
    stripped = replace(q, win_hold=False)
    contract = results_contract(stripped, plan, held)
    stats = contract["statistics"]
    assert contract["win_hold"] is True
    assert stats["W"] == 1
    assert stats["L"] == 0
    assert stats["terminal_win_n"] == 1
    assert stats["reward_e4"] == 2000
    assert stats["risk_e4"] == 4500
    assert stats["ev_e4"] == pytest.approx(2000)


def test_path_loss_then_official_yes_stays_loss_for_any_entry():
    q = _question(
        entries=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=8000,
                operation=EntryOp.FIRST_TOUCH,
                period_windows=(PeriodWindow(period="Q2"),),
            ),
        ),
        paths=(PathCondition(id="loss", op=PathOp.REACH, price_e4=3500, outcome=ExitOutcome.LOSS),),
    )
    plan = compile_research(q, CFG)
    loss = run_plan(
        plan,
        _bag(
            closes=[*TOUCH_CLOSES, ("2025-10-10T01:02:00Z", 3500)],
            settlement=SettlementResult.YES,
        ),
    )
    assert loss.rows[0].classification == Classification.LOSS.value
    stats = results_contract(q, plan, loss)["statistics"]
    assert stats["L"] == 1
    assert stats["W"] == 0
    assert stats["path_loss_n"] == 1
    assert stats["terminal_win_n"] == 0
    assert stats["official_w_n"] == 1
    assert stats["ev_e4"] == pytest.approx(-4500)


@pytest.mark.parametrize(
    "label,entry,closes,entry_e4",
    [
        (
            "first_touch_80",
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=8000,
                operation=EntryOp.FIRST_TOUCH,
                period_windows=(PeriodWindow(period="Q2"), PeriodWindow(period="Q3")),
            ),
            TOUCH_CLOSES,
            8000,
        ),
        (
            "cross_65",
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=6500,
                operation=EntryOp.CROSS,
                period=None,
            ),
            CROSS_CLOSES,
            6500,
        ),
        (
            "break_71",
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=7100,
                operation=EntryOp.BREAK,
                period=None,
            ),
            BREAK_CLOSES,
            7100,
        ),
    ],
)
def test_hold_yes_books_match_labs_and_superasi(label, entry, closes, entry_e4):
    q = _question(
        entries=(entry,),
        paths=(PathCondition(id="loss", op=PathOp.REACH, price_e4=3500, outcome=ExitOutcome.LOSS),),
    )
    plan = compile_research(q, CFG)
    held_yes = run_plan(plan, _bag(closes=closes, settlement=SettlementResult.YES, period="2"))
    held_no = run_plan(plan, _bag(closes=closes, settlement=SettlementResult.NO, period="2"))
    assert held_yes.population == 1
    assert held_no.population == 1
    yes_c = results_contract(q, plan, held_yes)
    no_c = results_contract(q, plan, held_no)
    reward = 10000 - entry_e4
    risk = entry_e4 - 3500
    assert yes_c["statistics"]["W"] == 1
    assert yes_c["statistics"]["reward_e4"] == reward
    assert yes_c["statistics"]["risk_e4"] == risk
    assert yes_c["statistics"]["ev_e4"] == pytest.approx(reward)
    assert no_c["statistics"]["L"] == 1
    assert no_c["statistics"]["ev_e4"] == pytest.approx(-entry_e4)

    stale = dict(yes_c)
    stale["statistics"] = {"population": 1}
    stale["classification"] = {"WIN": 0, "LOSS": 0, "HELD_TO_SETTLEMENT": 1}
    fields = strategy_fields(f"nba {label}", {"status": "READY", "results_contract": stale})
    assert fields["wins"] == "1"
    assert fields["losses"] == "0"
    assert fields["average_win"] == str(reward)
    assert fields["average_loss"] == str(risk)
    assert float(fields["gross_ev"]) == pytest.approx(reward)

    parsed = parse_labs_csv(_canonical_csv(f"nba {label}", {"status": "READY", "results_contract": stale}))
    observed = summarize_observed(parsed)
    assert observed["wins"] == 1
    assert observed["losses"] == 0
    assert observed["average_win"] == pytest.approx(reward)
    assert observed["average_loss"] == pytest.approx(risk)
    assert observed["gross_ev"] == pytest.approx(reward)


def test_labs_header_path_only_does_not_count_held_yes():
    payload = {
        "status": "READY",
        "results_contract": {
            "win_hold": False,
            "population": 2,
            "classification": {"WIN": 1, "HELD_TO_SETTLEMENT": 1},
            "statistics": {"population": 2, "W": 1, "L": 0},
            "entry": [{"op": "CROSS", "price_e4": 6300}],
            "win_exit": [{"op": "REACH", "price_e4": 8700}],
            "loss_exit": [{"op": "REACH", "price_e4": 4100}],
            "audit_rows": [
                {"classification": "WIN", "settlement_status": "YES", "entry_value": 6300},
                {"classification": "HELD_TO_SETTLEMENT", "settlement_status": "YES", "entry_value": 6300},
            ],
        },
    }
    fields = strategy_fields("nba path only", payload)
    assert fields["wins"] == "1"
    assert fields["losses"] == "0"
    observed = summarize_observed(parse_labs_csv(_canonical_csv("nba path only", payload)))
    assert observed["wins"] == 1
    assert observed["losses"] == 0


def test_labs_header_ignores_classification_win_for_hold_yes():
    payload = {
        "status": "READY",
        "results_contract": {
            "win_hold": True,
            "population": 10,
            "classification": {"WIN": 0, "LOSS": 2, "HELD_TO_SETTLEMENT": 8},
            "statistics": {"population": 10},
            "entry": [{"op": "FIRST_TOUCH", "price_e4": 8000}],
            "win_exit": [{"id": "win_hold", "op": "HOLD", "outcome": "win"}],
            "loss_exit": [{"op": "REACH", "price_e4": 3500}],
            "audit_rows": (
                [{"classification": "HELD_TO_SETTLEMENT", "settlement_status": "YES", "entry_value": 8000}] * 8
                + [{"classification": "HELD_TO_SETTLEMENT", "settlement_status": "NO", "entry_value": 8000}]
                + [{"classification": "LOSS", "settlement_status": "YES", "entry_value": 8000}]
            ),
        },
    }
    fields = strategy_fields("any nba hold", payload)
    assert fields["wins"] == "8"
    assert fields["losses"] == "2"
    assert fields["average_win"] == "2000"
    assert fields["average_loss"] == "4500"
    assert float(fields["win_rate"]) == pytest.approx(0.8)
    assert float(fields["gross_ev"]) == pytest.approx((8 * 2000 - 4500 - 8000) / 10)
    observed = summarize_observed(parse_labs_csv(_canonical_csv("any nba hold", payload)))
    assert observed["wins"] == 8
    assert observed["losses"] == 2
    assert observed["gross_ev"] == pytest.approx((8 * 2000 - 4500 - 8000) / 10)


@pytest.mark.skipif(not (LIVE / "manifest.json").is_file(), reason="NBA warehouse absent")
@pytest.mark.parametrize(
    "label,entry,exits",
    [
        ("live_first_touch_hold", {"family": "first_touch", "priceCents": 80, "period": "Q2"}, HOLD_EXITS),
        (
            "live_cross_path",
            {"family": "cross", "priceCents": 63},
            [
                {"id": "win", "kind": "path", "family": "reach", "priceCents": 87, "outcome": "win"},
                {"id": "loss", "kind": "path", "family": "reach", "priceCents": 41, "outcome": "loss"},
            ],
        ),
    ],
)
def test_live_one_day_nba_superasi_matches_warehouse(label, entry, exits):
    from roller.warehouse.frontend_contract import execute_frontend_research

    question, errors = question_from_draft(_nba_draft(entry, exits))
    assert question is not None
    assert not [e for e in errors if e.startswith("missing_")]
    executed = execute_frontend_research({"question": question.to_dict()}, CFG)
    assert executed["status"] in {"READY", "ZERO_RESULTS"}
    contract = executed["results_contract"]
    if executed["status"] == "ZERO_RESULTS" or not contract:
        return
    stats = contract["statistics"]
    assert stats["W"] == stats["path_win_n"] + stats["terminal_win_n"]
    assert stats["L"] == stats["path_loss_n"] + stats["terminal_loss_n"]
    parsed = parse_labs_csv(_canonical_csv(label, {"status": executed["status"], "results_contract": contract}))
    observed = summarize_observed(parsed)
    assert observed["wins"] == stats["W"]
    assert observed["losses"] == stats["L"]
    if stats.get("ev_e4") is not None:
        assert observed["gross_ev"] == pytest.approx(stats["ev_e4"])
