"""Quick Start chips must compile onto the measured question.

Full-season dates stay on the AST. Lock matching may collapse a copy.
Do not unbind the window the operator entered.
"""

from __future__ import annotations

from roller.research_query.compiler import compile_draft, question_from_draft, reference_match
from roller.research_query.models import ResearchQuestion, Universe
from roller.research_query.season_dates import bounds_for_season


def _first80_draft(**universe_extra):
    universe = {
        "sports": ["basketball"],
        "leagues": ["NBA"],
        "seasons": ["2025-26"],
        "markets": ["kalshi"],
        "marketData": ["candles"],
        **universe_extra,
    }
    return {
        "universe": universe,
        "entryConditions": [
            {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}
        ],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40},
            {"id": "t", "kind": "terminal", "family": "both"},
        ],
    }


def test_full_season_dates_stay_on_question_and_still_lock(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    lo, hi = bounds_for_season("NBA", "2025-26")
    assert lo and hi
    draft = _first80_draft(dateFrom=lo, dateTo=hi)
    q = question_from_draft(draft)
    assert q.universe.date_from == lo
    assert q.universe.date_to == hi
    compiled = compile_draft(draft)
    assert compiled.question.universe.date_from == lo
    assert compiled.question.universe.date_to == hi
    assert compiled.reference_match == "FIRST80_Q3"
    assert reference_match(q) == "FIRST80_Q3"


def test_custom_dates_stay_and_do_not_lock(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = _first80_draft(dateFrom="2025-11-01", dateTo="2026-02-01")
    q = question_from_draft(draft)
    assert q.universe.date_from == "2025-11-01"
    assert q.universe.date_to == "2026-02-01"
    compiled = compile_draft(draft)
    assert compiled.reference_match is None
    assert compiled.question.universe.date_from == "2025-11-01"


def test_mlb_season_dates_are_measured_not_unbound():
    lo, hi = bounds_for_season("MLB", "2025-26")
    draft = {
        "universe": {
            "sports": ["baseball"],
            "leagues": ["MLB"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["last_trade"],
            "dateFrom": lo,
            "dateTo": hi,
        },
        "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80}],
        "exitConditions": [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40, "outcome": "loss"},
            {"id": "t", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
        ],
    }
    compiled = compile_draft(draft)
    assert compiled.question.universe.date_from == lo
    assert compiled.question.universe.date_to == hi
    assert compiled.question.universe.leagues == ("MLB",)
    assert compiled.question.universe.market_data == ("last_trade",)
    assert compiled.reference_match is None


def test_dropped_dates_fail_closed(monkeypatch):
    from roller.research_query import compiler as compiler_mod

    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = _first80_draft(dateFrom="2026-04-01", dateTo="2026-09-08")
    real = compiler_mod.question_from_draft

    def stripped(raw, *a, **k):
        q = real(raw)
        uni = q.universe
        return ResearchQuestion(
            universe=Universe(
                sports=uni.sports,
                leagues=uni.leagues,
                seasons=uni.seasons,
                markets=uni.markets,
                market_data=uni.market_data,
                game_data=uni.game_data,
                date_from=None,
                date_to=None,
            ),
            entry_conditions=q.entry_conditions,
            path_conditions=q.path_conditions,
            terminal=q.terminal,
            requested_dimensions=q.requested_dimensions,
            accept_limitations=q.accept_limitations,
            win_hold=q.win_hold,
            loss_hold=q.loss_hold,
        )

    monkeypatch.setattr(compiler_mod, "question_from_draft", stripped)
    compiled = compiler_mod.compile_draft(draft)
    assert compiled.status.value == "OPERATION_REQUIRED"
    assert "universe_identity" in compiled.unavailable
    assert any("dateFrom" in r for r in compiled.reasons)


def test_league_and_market_survive_compile():
    draft = {
        "universe": {
            "sports": ["tennis"],
            "leagues": ["ATP"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["last_trade"],
            "dateFrom": "2025-06-18",
            "dateTo": "2026-09-12",
        },
        "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 60}],
        "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 40}],
    }
    compiled = compile_draft(draft)
    assert compiled.question.universe.leagues == ("ATP",)
    assert compiled.question.universe.markets == ("kalshi",)
    assert compiled.question.universe.market_data == ("last_trade",)
    assert compiled.question.universe.date_from == "2025-06-18"
    assert compiled.question.entry_conditions[0].price_e4 == 6000
    assert compiled.question.path_conditions[0].price_e4 == 4000


def test_rewritten_entry_price_fails_closed(monkeypatch):
    from roller.research_query import compiler as compiler_mod
    from roller.research_query.models import EntryCondition, TouchOrdinal

    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = _first80_draft(dateFrom="2025-11-01", dateTo="2026-02-01")
    real = compiler_mod.question_from_draft

    def rewritten(raw, *a, **k):
        q = real(raw)
        e = q.entry_conditions[0]
        return type(q)(
            universe=q.universe,
            entry_conditions=(
                EntryCondition(
                    id=e.id,
                    ordinal=TouchOrdinal.FIRST_TOUCH,
                    price_e4=7500,
                    period=e.period,
                ),
            ),
            path_conditions=q.path_conditions,
            terminal=q.terminal,
            requested_dimensions=q.requested_dimensions,
            accept_limitations=q.accept_limitations,
            win_hold=q.win_hold,
            loss_hold=q.loss_hold,
        )

    monkeypatch.setattr(compiler_mod, "question_from_draft", rewritten)
    compiled = compiler_mod.compile_draft(draft)
    assert compiled.status.value == "OPERATION_REQUIRED"
    assert "entry_identity" in compiled.unavailable


def test_rewritten_path_price_fails_closed(monkeypatch):
    from roller.research_query import compiler as compiler_mod
    from roller.research_query.models import PathCondition, PathOp

    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = _first80_draft(dateFrom="2025-11-01", dateTo="2026-02-01")
    real = compiler_mod.question_from_draft

    def rewritten(raw, *a, **k):
        q = real(raw)
        p = q.path_conditions[0]
        return type(q)(
            universe=q.universe,
            entry_conditions=q.entry_conditions,
            path_conditions=(PathCondition(id=p.id, op=PathOp.REACH, price_e4=5000),),
            terminal=q.terminal,
            requested_dimensions=q.requested_dimensions,
            accept_limitations=q.accept_limitations,
            win_hold=q.win_hold,
            loss_hold=q.loss_hold,
        )

    monkeypatch.setattr(compiler_mod, "question_from_draft", rewritten)
    compiled = compiler_mod.compile_draft(draft)
    assert compiled.status.value == "OPERATION_REQUIRED"
    assert "path_identity" in compiled.unavailable


def test_q3_clock_chip_stays_on_ast(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = _first80_draft(dateFrom="2025-11-01", dateTo="2026-02-01")
    draft["entryConditions"][0]["clockFrom"] = "08:00"
    draft["entryConditions"][0]["clockTo"] = "04:00"
    compiled = compile_draft(draft)
    cond = compiled.question.entry_conditions[0]
    assert cond.period == "Q3"
    assert cond.clock is not None
    bounds = {int(cond.clock.remaining_from_s), int(cond.clock.remaining_to_s)}
    assert bounds == {480, 240}
    assert compiled.reference_match is None


def test_dropped_clock_chip_fails_closed(monkeypatch):
    from roller.research_query import compiler as compiler_mod
    from roller.research_query.models import EntryCondition, TouchOrdinal

    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = _first80_draft(dateFrom="2025-11-01", dateTo="2026-02-01")
    draft["entryConditions"][0]["clockFrom"] = "08:00"
    draft["entryConditions"][0]["clockTo"] = "04:00"
    real = compiler_mod.question_from_draft

    def stripped(raw, *a, **k):
        q = real(raw)
        e = q.entry_conditions[0]
        return type(q)(
            universe=q.universe,
            entry_conditions=(
                EntryCondition(
                    id=e.id,
                    ordinal=TouchOrdinal.FIRST_TOUCH,
                    price_e4=e.price_e4,
                    period=e.period,
                ),
            ),
            path_conditions=q.path_conditions,
            terminal=q.terminal,
            requested_dimensions=q.requested_dimensions,
            accept_limitations=q.accept_limitations,
            win_hold=q.win_hold,
            loss_hold=q.loss_hold,
        )

    monkeypatch.setattr(compiler_mod, "question_from_draft", stripped)
    compiled = compiler_mod.compile_draft(draft)
    assert compiled.status.value == "OPERATION_REQUIRED"
    assert "entry_identity" in compiled.unavailable
    assert any("clock" in r for r in compiled.reasons)


def test_direction_chip_stays_on_ast(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
            "dateFrom": "2025-11-01",
            "dateTo": "2026-02-01",
        },
        "entryConditions": [
            {"id": "e1", "family": "cross", "priceCents": 80, "direction": "up"}
        ],
        "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90}],
    }
    compiled = compile_draft(draft)
    assert compiled.question.entry_conditions[0].direction == "up"


def test_mlb_clock_chip_fails_closed(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": {
            "sports": ["baseball"],
            "leagues": ["MLB"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["last_trade"],
        },
        "entryConditions": [
            {
                "id": "e1",
                "family": "first_touch",
                "priceCents": 80,
                "period": "T7",
                "clockFrom": "08:00",
                "clockTo": "04:00",
            }
        ],
        "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90}],
    }
    compiled = compile_draft(draft)
    assert compiled.status.value == "OPERATION_REQUIRED"
    assert "family_chip" in compiled.unavailable


def test_unknown_te_chip_fails_closed(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
            "dateFrom": "2025-11-01",
            "dateTo": "2026-02-01",
        },
        "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80}],
        "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90}],
        "teFilters": {"notARealChip": "yes"},
    }
    compiled = compile_draft(draft)
    assert compiled.status.value == "OPERATION_REQUIRED"
    assert "te_identity" in compiled.unavailable


def test_foreign_period_on_mlb_fails_closed(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": {
            "sports": ["baseball"],
            "leagues": ["MLB"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["last_trade"],
        },
        "entryConditions": [
            {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}
        ],
        "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90}],
    }
    compiled = compile_draft(draft)
    assert compiled.status.value == "OPERATION_REQUIRED"
    assert any("Q3" in r for r in compiled.reasons)


def test_rewritten_period_fails_closed(monkeypatch):
    from roller.research_query import compiler as compiler_mod
    from roller.research_query.models import EntryCondition, TouchOrdinal

    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = _first80_draft(dateFrom="2025-11-01", dateTo="2026-02-01")
    real = compiler_mod.question_from_draft

    def rewritten(raw, *a, **k):
        q = real(raw)
        e = q.entry_conditions[0]
        return type(q)(
            universe=q.universe,
            entry_conditions=(
                EntryCondition(
                    id=e.id,
                    ordinal=TouchOrdinal.FIRST_TOUCH,
                    price_e4=e.price_e4,
                    period="Q2",
                ),
            ),
            path_conditions=q.path_conditions,
            terminal=q.terminal,
            requested_dimensions=q.requested_dimensions,
            accept_limitations=q.accept_limitations,
            win_hold=q.win_hold,
            loss_hold=q.loss_hold,
        )

    monkeypatch.setattr(compiler_mod, "question_from_draft", rewritten)
    compiled = compiler_mod.compile_draft(draft)
    assert compiled.status.value == "OPERATION_REQUIRED"
    assert "entry_identity" in compiled.unavailable
