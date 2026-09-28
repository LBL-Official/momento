"""HTTP handlers for Drevo 78/67. Does not submit."""

from __future__ import annotations

from typing import Any

from roller.austin_first78.api import handle_health as austin_health
from roller.dre.models import LIVE_EXECUTION
from roller.dre_first78.composer import compose_position, list_positions
from roller.dre_first78.context import AUSTIN_UNIVERSE, CHOOSIN_UNIVERSE, austin_n, trade_context

PRODUCT = "DRE"
OBJECTIVE = {
    "id": "DRE_PORTFOLIO_OBJECTIVE_V1",
    "status": "RESEARCH_MEMO",
    "calculus": "NOT_IMPLEMENTED",
    "preserve_alpha_first": True,
    "first_form": "ΔP → 0 | αP > 0",
    "eventual_form": "ΔP → ΔP*(Xt)",
    "ssot": "research/dre/PORTFOLIO_OBJECTIVE_V1.md",
    "forward_feed": ["trade_breakdown_first78", "position_stratification_first78"],
    "note": "Preserve αP > 0, then move exposure toward ΔP*(Xt). Do not invent Λα.",
}


def handle_health() -> dict[str, Any]:
    try:
        austin = austin_health()
    except Exception as exc:  # noqa: BLE001
        austin = {"status": "UNAVAILABLE", "detail": f"{type(exc).__name__}: {exc}"}
    prior = trade_context()
    return {
        "ok": True,
        "product": PRODUCT,
        "product_canonical": "Drevo",
        "book": "FIRST78_67",
        "role": "dynamic_risk_engine",
        "live_execution": LIVE_EXECUTION,
        "submits": False,
        "phase3_is_execution_policy": False,
        "live_feed": "UNAVAILABLE",
        "objective": OBJECTIVE,
        "upstream": {
            "position_stratification": {"universe": AUSTIN_UNIVERSE, "n": austin_n(), "availability": "OBSERVED" if austin.get("ok") else "UNAVAILABLE"},
            "trade_breakdown": {"universe": CHOOSIN_UNIVERSE, "n": prior.get("historical_n"), "availability": prior.get("availability")},
        },
        "note": "78/67 hold-reason desk. Reads the Austin 78/67 fit and the derived-four prior.",
    }


def handle_trade_breakdown() -> dict[str, Any]:
    prior = trade_context()
    return {
        "status": prior.get("availability") or "UNAVAILABLE",
        "source": "choosin_texas",
        "book": "FIRST78_67",
        "n": prior.get("historical_n"),
        "universe": CHOOSIN_UNIVERSE,
        "S_display": prior.get("historical_survival_rate"),
        "historical_ev": prior.get("historical_ev"),
        "note": prior.get("note"),
    }


def handle_stratum() -> dict[str, Any]:
    return {
        "status": "OBSERVED" if austin_n() else "UNAVAILABLE",
        "source": "austin",
        "book": "FIRST78_67",
        "book_n": austin_n(),
        "universe": AUSTIN_UNIVERSE,
        "live_feed": "UNAVAILABLE",
        "note": "Position stratification on the 78/67 fit. Never BUY/SKIP.",
    }


def handle_experiments() -> dict[str, Any]:
    return {
        "status": "UNAVAILABLE",
        "source": "austin_first78",
        "book": "FIRST78_67",
        "experiments": [],
        "detail": "The 604 experiment index is not mounted on the 78/67 desk.",
        "live_execution": LIVE_EXECUTION,
        "phase3_is_execution_policy": False,
    }


def handle_experiment(experiment_id: str) -> dict[str, Any]:
    return {**handle_experiments(), "experiment_id": experiment_id}


def handle_positions(slice_name: str | None = None, q: str | None = None, dataset_split: str | None = None) -> dict[str, Any]:
    return list_positions(slice_name=slice_name, q=q, dataset_split=dataset_split)


def handle_position(position_id: str, as_of: str | None = None) -> dict[str, Any]:
    return compose_position(position_id, as_of=as_of, mode="HISTORICAL")


def handle_replay_position(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    return compose_position(trade_id, as_of=as_of, mode="REPLAY")


def handle_desk() -> dict[str, Any]:
    return {
        "product": PRODUCT,
        "product_canonical": "Drevo",
        "book": "FIRST78_67",
        "live_execution": LIVE_EXECUTION,
        "submits": False,
        "phase3_is_execution_policy": False,
        "live_feed": "UNAVAILABLE",
        "objective": OBJECTIVE,
        "trade_breakdown": handle_trade_breakdown(),
        "stratum": handle_stratum(),
        "experiments": handle_experiments(),
        "note": "Hold-reason research on FIRST78→67. Calculus is NOT_IMPLEMENTED.",
    }


def handle_decision(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    from roller.dre.decision import decide
    from roller.positman_first78.service import plan

    body_plan = plan(trade_id, as_of, record=False)
    decision = decide(body_plan)
    decision["trade_id"] = trade_id
    decision["book"] = "FIRST78_67"
    return decision
