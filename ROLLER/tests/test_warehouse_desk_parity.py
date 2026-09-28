"""NBA / MLB / NCAAB warehouse desks share the same compile/execute bar.

Does not rewrite FIRST80_Q3, NCAAB_FIRST80_P5, or MLB 554/1661.
Does not call Confirm & Run load_dataset.
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
    ResearchQuestion,
    ResearchStatus,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)
from roller.warehouse.coverage import CapabilityName, get_catalog
from roller.warehouse.desk import desk_lab_folder, desk_sport
from roller.warehouse.frontend_contract import (
    compile_frontend_research,
    execute_frontend_research,
    question_from_draft,
)
from roller.warehouse.layout import warehouse_root
from roller.warehouse.production import unavailable_production_sport
from roller.warehouse.research_compiler import compile_research

ROLLER_ROOT = Path(__file__).resolve().parents[1]
CFG = RollerConfig(ROLLER_ROOT)

SPECS = {
    "NBA": {
        "sports": ("NBA",),
        "leagues": ("NBA",),
        "draft_sports": ["basketball"],
        "draft_leagues": ["NBA"],
        "date_from": "2025-10-10",
        "date_to": "2025-10-10",
        "empty_from": "2024-01-01",
        "empty_to": "2024-01-02",
    },
    "MLB": {
        "sports": ("MLB",),
        "leagues": ("MLB",),
        "draft_sports": ["baseball"],
        "draft_leagues": ["MLB"],
        "date_from": "2025-04-01",
        "date_to": "2025-04-30",
        "empty_from": "2024-01-01",
        "empty_to": "2024-01-02",
    },
    "NCAAB": {
        "sports": ("NCAAB",),
        "leagues": ("NCAAB",),
        "draft_sports": ["basketball"],
        "draft_leagues": ["NCAAB"],
        "date_from": "2025-11-03",
        "date_to": "2025-11-30",
        "empty_from": "2024-01-01",
        "empty_to": "2024-01-02",
    },
    "ATP": {
        "sports": ("ATP",),
        "leagues": ("ATP",),
        "draft_sports": ["tennis"],
        "draft_leagues": ["ATP"],
        "date_from": "2025-07-01",
        "date_to": "2025-07-31",
        "empty_from": "2024-01-01",
        "empty_to": "2024-01-02",
    },
    "WTA": {
        "sports": ("WTA",),
        "leagues": ("WTA",),
        "draft_sports": ["tennis"],
        "draft_leagues": ["WTA"],
        "date_from": "2025-07-01",
        "date_to": "2025-07-31",
        "empty_from": "2024-01-01",
        "empty_to": "2024-01-02",
    },
}


def _live(sport: str) -> bool:
    return (warehouse_root(CFG, sport, "2025-2026") / "manifest.json").is_file()


def _question(sport: str, **universe: object) -> ResearchQuestion:
    spec = SPECS[sport]
    return ResearchQuestion(
        universe=Universe(
            sports=universe.get("sports", spec["sports"]),
            leagues=universe.get("leagues", spec["leagues"]),
            seasons=("2025-2026",),
            markets=("kalshi",),
            market_data=universe.get("market_data", ("candles",)),
            date_from=universe.get("date_from", spec["date_from"]),
            date_to=universe.get("date_to", spec["date_to"]),
        ),
        entry_conditions=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=6500,
                operation=EntryOp.CROSS,
                period=universe.get("period"),
            ),
        ),
        path_conditions=(
            PathCondition(id="win", op=PathOp.REACH, price_e4=8500, outcome=ExitOutcome.WIN),
            PathCondition(id="loss", op=PathOp.REACH, price_e4=4000, outcome=ExitOutcome.LOSS),
        ),
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=universe.get("requested_dimensions", ("HOLD_TO_SETTLEMENT",)),
    )


def _draft(sport: str, **universe) -> dict:
    spec = SPECS[sport]
    uni = {
        "sports": spec["draft_sports"],
        "leagues": spec["draft_leagues"],
        "seasons": ["2025-26"],
        "markets": ["kalshi"],
        "marketData": ["candles"],
        "dateFrom": spec["date_from"],
        "dateTo": spec["date_to"],
    }
    uni.update(universe)
    return {
        "universe": uni,
        "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 65}],
        "exitConditions": [
            {"id": "win", "kind": "path", "family": "reach", "priceCents": 85, "outcome": "win"},
            {"id": "loss", "kind": "path", "family": "reach", "priceCents": 40, "outcome": "loss"},
        ],
    }


@pytest.mark.parametrize("sport", ["NBA", "MLB", "NCAAB", "ATP", "WTA"])
def test_desk_sport_resolves(sport: str):
    q = _question(sport)
    assert desk_sport(q) == sport
    assert unavailable_production_sport(q) is None
    question, errors = question_from_draft(_draft(sport))
    assert question is not None
    assert "missing_threshold" not in errors
    assert question.universe.sports == (sport,)
    assert question.universe.leagues == (sport,)
    if sport == "NCAAB":
        assert question.universe.sports != ("NBA",)
    if sport in {"ATP", "WTA"}:
        assert question.universe.sports != ("NBA",)
        assert question.universe.sports != ("ATP", "WTA")
    assert desk_lab_folder(q) == sport
    if sport != "NBA":
        assert desk_lab_folder(q, "NBA") == sport


@pytest.mark.parametrize("sport", ["NBA", "MLB", "NCAAB", "ATP", "WTA"])
def test_catalog_capability_matrix(sport: str):
    if not _live(sport):
        pytest.skip(f"{sport} Phase 8 warehouse absent")
    cat = get_catalog(CFG, sport=sport)
    assert cat.sport == sport
    assert cat.resolve([CapabilityName.TRADABLE_YES_BID_1M]).status is ResearchStatus.READY
    assert cat.resolve([CapabilityName.TICK]).status is ResearchStatus.DATA_REQUIRED
    assert cat.resolve([CapabilityName.HISTORICAL_L2]).status is ResearchStatus.DATA_REQUIRED
    assert cat.resolve([CapabilityName.PBP_MARKET_PIT_ALIGNMENT]).status is ResearchStatus.OPERATION_REQUIRED
    if sport == "NCAAB":
        assert cat.observations["last_trade_print_count"] == 0
    if sport in {"ATP", "WTA"}:
        assert cat.observations["last_trade_print_count"] > 0


@pytest.mark.parametrize("sport", ["NBA", "MLB", "NCAAB", "ATP", "WTA"])
def test_compile_and_execute_ref_equals_opt(sport: str, monkeypatch):
    if not _live(sport):
        pytest.skip(f"{sport} Phase 8 warehouse absent")
    called = {"load_dataset": False}

    def _banned(*_a, **_k):
        called["load_dataset"] = True
        raise AssertionError("warehouse desk must not call load_dataset")

    monkeypatch.setattr("roller.admin.load_dataset", _banned)
    compiled = compile_frontend_research({"draft": _draft(sport)})
    assert compiled["status"] == "READY"
    assert compiled["observation_basis"] == "TRADABLE_YES_BID"
    assert compiled["source"] == "warehouse_research"
    plan = compile_research(_question(sport), CFG)
    assert plan.status is ResearchStatus.READY
    executed = execute_frontend_research({"draft": _draft(sport)}, include_reference=True)
    assert executed["status"] == "READY"
    assert executed["difference_count"] == 0
    contract = executed["results_contract"]
    assert contract["population"] > 0
    assert contract["statistics"]["W"] + contract["statistics"]["L"] >= 0
    assert contract["statistics"]["rr"] is not None
    assert contract["statistics"]["basis"] == "observed_candle_path"
    assert "fill" in contract["statistics"]["not"]
    assert called["load_dataset"] is False


@pytest.mark.parametrize("sport", ["NBA", "MLB", "NCAAB", "ATP", "WTA"])
def test_zero_results_is_not_data_required(sport: str):
    if not _live(sport):
        pytest.skip(f"{sport} Phase 8 warehouse absent")
    spec = SPECS[sport]
    q = _question(sport, date_from=spec["empty_from"], date_to=spec["empty_to"])
    plan = compile_research(q, CFG)
    assert plan.status is ResearchStatus.READY
    executed = execute_frontend_research({"question": q.to_dict()})
    assert executed["status"] == "ZERO_RESULTS"
    assert executed["status"] != "DATA_REQUIRED"


def test_mlb_q4_is_operation_required():
    if not _live("MLB"):
        pytest.skip("MLB Phase 8 warehouse absent")
    q = _question("MLB", period="Q4")
    plan = compile_research(q, CFG)
    assert plan.status in {ResearchStatus.OPERATION_REQUIRED, ResearchStatus.DATA_REQUIRED}
    if plan.status is ResearchStatus.OPERATION_REQUIRED:
        assert "MLB_BASKETBALL_PERIOD" in plan.missing_operations


def test_mixed_atp_wta_has_no_desk():
    q = _question("ATP", sports=("ATP", "WTA"), leagues=("ATP", "WTA"))
    assert desk_sport(q) is None
    assert unavailable_production_sport(q) == "UNIVERSE"
    assert desk_sport(_question("ATP", sports=("TENNIS",), leagues=())) is None


def test_atp_q4_is_operation_required():
    if not _live("ATP"):
        pytest.skip("ATP Phase 8 warehouse absent")
    q = _question("ATP", period="Q4")
    plan = compile_research(q, CFG)
    assert plan.status is ResearchStatus.OPERATION_REQUIRED
    assert "TENNIS_FOREIGN_PERIOD" in plan.missing_operations


def test_wta_does_not_remap_to_atp_or_nba():
    q = _question("WTA")
    assert desk_sport(q) == "WTA"
    assert desk_sport(q) != "ATP"
    assert desk_sport(q) != "NBA"
    assert desk_lab_folder(q, "NBA") == "WTA"
