"""Austin 78/67 query and the derived-four static prior."""

from __future__ import annotations

from typing import Any

from roller.austin_first78.config import EV_DEFINITION, EV_FORMULA
from roller.austin_first78.store import load_json
from roller.austin_first78.paths import summary_path
from roller.ballhog_first78.context import (
    choosin_prior,
    get_trade,
    last_observed_by_trade,
    list_trades,
    query_at,
    replay,
)
from roller.choosin_texas.first78.artifact import load_derived
from roller.choosin_texas.first78.desk import present_derived
from roller.dre.pit import Stamped, iso, to_utc

AUSTIN_UNIVERSE = "choosin_nba_2q3q_first78_67"
CHOOSIN_UNIVERSE = "DERIVED_FOUR_FIRST78"


def austin_n() -> int | None:
    summary = load_json(summary_path()) or {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    value = coverage.get("n_trades")
    return None if value is None else int(value)


def trade_context() -> dict[str, Any]:
    body = load_derived()
    if body.get("status") != "OBSERVED":
        return {
            "source": "CHOOSIN_TEXAS",
            "availability": "UNAVAILABLE",
            "universe": CHOOSIN_UNIVERSE,
            "historical_n": None,
            "detail": body.get("message"),
            "note": "Derived-four FIRST78 prior is unavailable.",
        }
    desk = present_derived(body)
    universe = desk["universe"]
    official = universe["trade"] if isinstance(universe.get("trade"), dict) else {}
    prior = choosin_prior()
    generated = to_utc(body.get("built_at") or body.get("generated_at"))
    return {
        "source": "CHOOSIN_TEXAS",
        "availability": "STATIC",
        "status": "OBSERVED",
        "product": "Choosin Texas",
        "pit_kind": "STATIC",
        "source_timestamp": iso(generated),
        "articulation": "FIRST78 78→67",
        "population": "DERIVED_FOUR_FIRST78",
        "cohort": "derived_four",
        "historical_n": universe.get("n"),
        "W": universe.get("W"),
        "L": universe.get("L"),
        "entry_definition": {
            "rule": "FIRST78_67",
            "entry_cents": 78,
            "loss_barrier_cents": 67,
            "gain_cents": 22,
        },
        "historical_win_rate": (universe.get("terminal") or {}).get("p_display"),
        "historical_survival_rate": official.get("S_display") or prior.get("historical_survival_rate"),
        "historical_ev": {
            "label": "HISTORICAL TRADE PRIOR",
            "estimand": "CHOOSIN_TEXAS_POPULATION_EV",
            "definition": "derived-four FIRST78_67 population",
            "formula": EV_FORMULA,
            "ev_display": official.get("ev_per_trade_display"),
            "ev_per_trade_display": official.get("ev_per_trade_display"),
            "note": "Candle-path theoretical population EV. Not Austin conditional EV. Not a fill.",
        },
        "baseline_path_profile": universe.get("paths") or [],
        "trade_classification": "FIRST78 derived-four 78/67",
        "source_object_id": "first78_derived_four",
        "source_version": "first78_derived_v1",
        "universe": CHOOSIN_UNIVERSE,
        "austin_universe": AUSTIN_UNIVERSE,
        "note": "Qualified 78¢ count. Not the Austin training N and not the FIRST80 936 book.",
        "per_ticker_path_economics": {"value": None, "availability": "UNAVAILABLE"},
        "stamp": Stamped(
            field="trade_context",
            value=True,
            source="choosin_texas",
            source_timestamp=generated,
            pit_kind="STATIC",
        ),
        "ev_definition": EV_DEFINITION,
    }
