"""Post-Phase-20 production capability and NBA sport lock.

Does not change Phase 0–20 warehouse semantics. Does not call Confirm & Run.
"""

from __future__ import annotations

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
from roller.warehouse.frontend_contract import compile_frontend_research, question_from_draft
from roller.warehouse.production import (
    PRODUCTION_SPORT,
    PRODUCTION_SPORTS,
    UNAVAILABLE_SPORTS,
    production_capabilities,
    unavailable_production_sport,
)


def _nba_question(**universe: object) -> ResearchQuestion:
    return ResearchQuestion(
        universe=Universe(
            sports=universe.get("sports", ("NBA",)),
            leagues=universe.get("leagues", ("NBA",)),
            seasons=("2025-2026",),
            markets=("kalshi",),
            market_data=("candles",),
            date_from="2025-10-10",
            date_to="2025-10-10",
        ),
        entry_conditions=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=6500,
                operation=EntryOp.CROSS,
            ),
        ),
        path_conditions=(
            PathCondition(id="win", op=PathOp.REACH, price_e4=8500, outcome=ExitOutcome.WIN),
            PathCondition(id="loss", op=PathOp.REACH, price_e4=4000, outcome=ExitOutcome.LOSS),
        ),
        terminal=TerminalOutcome.BOTH,
    )


def test_capabilities_nba_and_mlb():
    cap = production_capabilities()
    assert cap["available_sports"] == list(PRODUCTION_SPORTS)
    assert PRODUCTION_SPORT in cap["available_sports"]
    assert "MLB" in cap["available_sports"]
    assert "NCAAB" in cap["available_sports"]
    assert "ATP" in cap["available_sports"]
    assert "WTA" in cap["available_sports"]
    names = [row["sport"] for row in cap["unavailable_sports"]]
    assert names == list(UNAVAILABLE_SPORTS)
    assert "MLB" not in names
    assert "NCAAB" not in names
    assert all(row["status"] == "NOT_AVAILABLE" for row in cap["unavailable_sports"])
    assert cap["available_observation_bases"] == ["TRADABLE_YES_BID", "LAST_TRADE_PRINT"]
    assert cap["available_resolutions"] == ["1_MINUTE_CANDLE"]
    assert cap["available_PIT_fields"] == ["available_at"]
    assert "HISTORICAL_L2" in cap["unsupported_capabilities"]
    assert "HISTORICAL_TICK" in cap["unsupported_capabilities"]
    assert "PBP_MARKET_PIT_ALIGNMENT" in cap["unsupported_capabilities"]


def test_basketball_nba_universe_is_available():
    question, errors = question_from_draft(
        {
            "universe": {
                "sports": ["basketball"],
                "leagues": ["NBA"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
                "dateFrom": "2025-10-10",
                "dateTo": "2025-10-10",
            },
            "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 65}],
            "exitConditions": [
                {"id": "win", "kind": "path", "family": "reach", "priceCents": 85, "outcome": "win"},
                {"id": "loss", "kind": "path", "family": "reach", "priceCents": 40, "outcome": "loss"},
            ],
        }
    )
    assert question is not None
    assert "missing_threshold" not in errors
    assert question.universe.sports == ("NBA",)
    assert question.universe.leagues == ("NBA",)
    assert unavailable_production_sport(question) is None


def test_ncaab_is_available_and_not_nba():
    question, errors = question_from_draft(
        {
            "universe": {
                "sports": ["basketball"],
                "leagues": ["NCAAB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
                "dateFrom": "2025-11-03",
                "dateTo": "2025-11-03",
            },
            "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 65}],
            "exitConditions": [
                {"id": "win", "kind": "path", "family": "reach", "priceCents": 85, "outcome": "win"},
                {"id": "loss", "kind": "path", "family": "reach", "priceCents": 40, "outcome": "loss"},
            ],
        }
    )
    assert question is not None
    assert "missing_threshold" not in errors
    assert question.universe.sports == ("NCAAB",)
    assert question.universe.leagues == ("NCAAB",)
    assert unavailable_production_sport(question) is None
    compiled = compile_frontend_research({"question": question.to_dict()})
    assert compiled.get("capability", {}).get("unavailable_sport") != "NCAAB"
    assert compiled["status"] != "INVALID"


def test_mlb_and_isolated_tennis_tours_are_available():
    assert unavailable_production_sport(_nba_question(sports=("MLB",), leagues=("MLB",))) is None
    assert unavailable_production_sport(_nba_question(sports=("ATP",), leagues=("ATP",))) is None
    assert unavailable_production_sport(_nba_question(sports=("WTA",), leagues=("WTA",))) is None


def test_tennis_without_tour_and_mixed_tours_fail_closed():
    for sports, leagues in (
        (("TENNIS",), ()),
        (("TENNIS",), ("ATP", "WTA")),
        (("ATP", "WTA"), ("ATP", "WTA")),
    ):
        blocked = unavailable_production_sport(_nba_question(sports=sports, leagues=leagues))
        assert blocked == "UNIVERSE"
        compiled = compile_frontend_research({"question": _nba_question(sports=sports, leagues=leagues).to_dict()})
        assert compiled["status"] == "DATA_REQUIRED"
        assert compiled["capability"]["missing_data"] == ["UNIVERSE"]
        assert compiled.get("result") is None


def test_wnba_still_unavailable():
    blocked = unavailable_production_sport(_nba_question(sports=("WNBA",), leagues=("WNBA",)))
    assert blocked == "WNBA"
    compiled = compile_frontend_research({"question": _nba_question(sports=("WNBA",), leagues=("WNBA",)).to_dict()})
    assert compiled["status"] == "DATA_REQUIRED"
    assert compiled["capability"]["missing_data"] == ["UNIVERSE"]
    assert compiled.get("result") is None
