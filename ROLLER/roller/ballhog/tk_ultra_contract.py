"""BallhogHedgeIntent. TK Ultra assess is not modified."""

from __future__ import annotations

from typing import Any

from roller.ballhog.models import INTENT_SCHEMA, LIVE_EXECUTION


def _intent_status(q_star: object) -> str:
    if q_star is None:
        return "UNRESOLVED"
    if int(q_star) == 0:
        return "NO_HEDGE"
    return "HEDGE_REQUESTED"


def build_intent(
    *,
    trade_id: str,
    as_of: str | None,
    decision: dict[str, Any],
    austin_universe: str,
    choosin_universe: str,
) -> dict[str, Any]:
    timing = decision.get("timing") if isinstance(decision.get("timing"), dict) else {}
    q_star = decision.get("q_star")
    status = _intent_status(q_star)
    return {
        "schema": INTENT_SCHEMA,
        "system_id": "hedging_analysis",
        "product": "Ballhog",
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "position_id": trade_id,
        "as_of": as_of,
        "source_side": "A1_FAVORITE_YES",
        "research_unit_qty": decision.get("research_unit_qty"),
        "q_dir": decision.get("q_dir"),
        "q_hedge": decision.get("q_hedge"),
        "rho": decision.get("rho"),
        "rho_star": decision.get("rho_star"),
        "q_star": q_star,
        "quantity_to_neutralize": q_star,
        "residual_exposure_target": decision.get("delta_star"),
        "target_exposure": decision.get("target_exposure_qty"),
        "target_residual_qty": decision.get("target_residual_qty"),
        "current_exposure": decision.get("q_dir"),
        "risk_intent": decision.get("risk_intent") or timing.get("timing_state"),
        "hedge_feasibility": decision.get("hedge_feasibility"),
        "timing_state": timing.get("timing_state"),
        "urgency": timing.get("timing_state"),
        "intent_status": status,
        "alpha_before": decision.get("austin_alpha_cents"),
        "minimum_alpha_to_preserve": 0,
        "alpha_ci": decision.get("alpha_ci"),
        "decision_status": decision.get("decision_status"),
        "reason_codes": decision.get("reason_codes") or [],
        "explanation": decision.get("explanation"),
        "acceptable_hedge_price_region": decision.get("acceptable_hedge_price_region"),
        "economic_constraints": {
            "positive_robust_portfolio_ev": True,
            "execution_assumption": "THEORETICAL",
            "not_an_order": True,
        },
        "provenance": {
            "austin_universe": austin_universe,
            "choosin_universe": choosin_universe,
            "policy_version": decision.get("policy_version"),
        },
        "note": (
            "Desired risk transformation only. TK Ultra chooses economic expression "
            "with its own wing/base/beta/anchors. Position Management is NOT_IMPLEMENTED."
        ),
    }
