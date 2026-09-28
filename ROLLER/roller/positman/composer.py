"""Deterministic quantity × route merge. No λ. No recomputation."""

from __future__ import annotations

from typing import Any

from roller.positman.models import BOUNDARY_SCHEMA, LIVE_EXECUTION, PLAN_SCHEMA, PRODUCT, SYSTEM_ID, now_iso


def _qty(value: Any) -> int | None:
    if value is None or value == "" or value == "UNAVAILABLE":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def compose_plan(
    *,
    match: dict[str, Any],
    ballhog: dict[str, Any],
    tk_ultra: dict[str, Any],
) -> dict[str, Any]:
    ident = match.get("identity") or {}
    intent = ballhog.get("intent") if isinstance(ballhog.get("intent"), dict) else {}
    assessment = tk_ultra.get("assessment") if isinstance(tk_ultra.get("assessment"), dict) else {}
    q_star = _qty(intent.get("q_star"))
    rho_star = intent.get("rho_star")
    risk_intent = intent.get("risk_intent")
    feasibility = intent.get("hedge_feasibility")
    decision_status = str(intent.get("decision_status") or "")
    route_pref = assessment.get("route_preference")
    current_a = _qty(assessment.get("current_a_qty"))
    current_exp = _qty(intent.get("current_exposure"))
    reasons: list[str] = []
    plan_status = "PLAN_RESOLVED"
    position_route = "PLAN_UNRESOLVED"
    planned_qty: int | None = None

    if match.get("match_status") in {"IDENTITY_MISMATCH", "STATE_TIME_MISMATCH"}:
        position_route = "IDENTITY_MISMATCH" if match["match_status"] == "IDENTITY_MISMATCH" else "PLAN_UNRESOLVED"
        plan_status = match["match_status"]
        reasons.append(match["match_status"])
        planned_qty = None
    elif ballhog.get("availability") == "UNAVAILABLE":
        plan_status = "SOURCE_UNAVAILABLE"
        position_route = "SOURCE_UNAVAILABLE"
        reasons.append("BALLHOG_UNAVAILABLE")
    elif q_star is None or decision_status == "POLICY_UNRESOLVED" or intent.get("intent_status") == "UNRESOLVED":
        plan_status = "PLAN_UNRESOLVED"
        position_route = "PLAN_UNRESOLVED"
        reasons.append("BALLHOG_POLICY_UNRESOLVED")
        planned_qty = None
    elif q_star == 0:
        position_route = "NO_CHANGE"
        planned_qty = 0
        reasons.append("BALLHOG_NO_CHANGE")
        if feasibility == "NO_ADMISSIBLE_HEDGE":
            reasons.append("NO_ADMISSIBLE_HEDGE")
    elif tk_ultra.get("availability") == "UNAVAILABLE" or not route_pref or route_pref == "UNAVAILABLE":
        plan_status = "SOURCE_UNAVAILABLE"
        position_route = "WAIT_FOR_ROUTE"
        planned_qty = q_star
        reasons.append("TK_ROUTE_UNAVAILABLE")
    elif route_pref == "BUY_B_BETTER":
        position_route = "ACQUIRE_B"
        planned_qty = q_star
        reasons.append("TK_ROUTE_BUY_B_BETTER")
        reasons.append("PLAN_RESOLVED")
    elif route_pref == "SELL_A_BETTER":
        if current_a is not None and q_star > current_a:
            plan_status = "PLAN_UNRESOLVED"
            position_route = "PLAN_UNRESOLVED"
            planned_qty = None
            reasons.append("PLAN_QUANTITY_INVALID")
        else:
            position_route = "REDUCE_A"
            planned_qty = q_star
            reasons.append("TK_ROUTE_SELL_A_BETTER")
            reasons.append("PLAN_RESOLVED")
    elif route_pref == "PARITY":
        plan_status = "PLAN_UNRESOLVED"
        position_route = "ROUTE_PARITY_UNRESOLVED"
        planned_qty = None
        reasons.append("TK_ROUTE_PARITY")
    else:
        plan_status = "PLAN_UNRESOLVED"
        position_route = "PLAN_UNRESOLVED"
        reasons.append("TK_ROUTE_UNAVAILABLE")

    target_residual = intent.get("target_residual_qty")
    target_exposure = intent.get("target_exposure")
    route_ctx = {
        "route_preference": route_pref,
        "gross_route_edge": assessment.get("gross_route_edge"),
        "rv_state": assessment.get("rv_state"),
        "expected_wing": assessment.get("expected_wing"),
        "tk_residual": assessment.get("tk_residual"),
        "stop_equivalent_b_avg": assessment.get("stop_equivalent_b_avg"),
        "max_remaining_avg_price": assessment.get("max_remaining_avg_price"),
        "hedge_runway": assessment.get("hedge_runway_vs_ask"),
        "fill": "UNAVAILABLE",
        "candle_path_not_fill": True,
    }
    if position_route == "ACQUIRE_B":
        route_ctx["b_ask"] = assessment.get("synthetic_exit_price") or assessment.get("direct_exit_price")
    if position_route == "REDUCE_A":
        route_ctx["a_bid"] = assessment.get("direct_exit_price")

    return {
        "schema": PLAN_SCHEMA,
        "product": PRODUCT,
        "system_id": SYSTEM_ID,
        "trace_id": match.get("trace_id"),
        "identity": ident,
        "as_of": ident.get("as_of"),
        "match_status": match.get("match_status"),
        "ballhog_ref": {
            "schema": ballhog.get("schema"),
            "availability": ballhog.get("availability"),
            "object_id": intent.get("position_id") or ident.get("trade_id"),
        },
        "tk_ultra_ref": {
            "schema": tk_ultra.get("schema"),
            "availability": tk_ultra.get("availability"),
            "object_id": (assessment.get("identity") or {}).get("trade_id") if isinstance(assessment.get("identity"), dict) else ident.get("trade_id"),
        },
        "risk_intent": risk_intent,
        "requested_reduction_qty": q_star,
        "requested_rho": rho_star,
        "current_exposure": current_exp,
        "target_exposure": target_exposure,
        "target_residual_qty": target_residual,
        "route_preference": route_pref,
        "position_route": position_route,
        "planned_qty": planned_qty,
        "A_contract": ident.get("a_contract"),
        "B_contract": ident.get("b_contract"),
        "route_economic_context": route_ctx,
        "plan_status": plan_status,
        "reason_codes": reasons,
        "quantity_source": "BALLHOG",
        "route_source": "TK_ULTRA",
        "execution_enabled": False,
        "live_execution": LIVE_EXECUTION,
        "source_provenance": {
            "ballhog": "roller.ballhog.api.handle_intent",
            "tk_ultra": "roller.tk_ultra.api.handle_assess_v0",
            "copy": False,
        },
        "created_at": now_iso(),
    }


def execution_boundary(plan: dict[str, Any], decision: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema": BOUNDARY_SCHEMA,
        "trace_id": plan.get("trace_id") or (decision or {}).get("trace_id"),
        "route": plan.get("position_route"),
        "quantity": plan.get("planned_qty"),
        "A_contract": plan.get("A_contract"),
        "B_contract": plan.get("B_contract"),
        "decision_ref": (decision or {}).get("schema"),
        "decision_status": (decision or {}).get("decision_status"),
        "risk_approved": False,
        "execution_enabled": False,
        "status": "NOT_SUBMITTED",
        "execution": "EXECUTION_DISABLED",
        "live_execution": LIVE_EXECUTION,
        "created_at": now_iso(),
    }
