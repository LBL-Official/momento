"""DrevoDecision. Structural VALID/INVALID. Policy is NO_POLICY_FROZEN."""

from __future__ import annotations

from typing import Any

from roller.dre.models import LIVE_EXECUTION
from roller.positman.composer import execution_boundary
from roller.positman.models import ROUTES, now_iso

DECISION_SCHEMA = "drevo.decision.v0"
PRODUCT = "Drevo"
SYSTEM_ID = "dynamic_risk_engine"
UNAVAILABLE = "UNAVAILABLE"


def decide(plan: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    structural = "VALID"
    ident = plan.get("identity") if isinstance(plan.get("identity"), dict) else {}
    schema = plan.get("schema")
    route = plan.get("position_route")
    qty = plan.get("planned_qty")
    current = plan.get("current_exposure")
    current_a = None
    ctx = plan.get("route_economic_context") if isinstance(plan.get("route_economic_context"), dict) else {}
    if plan.get("availability") == UNAVAILABLE or not plan:
        structural = "INVALID"
        reasons.append("POSITMAN_UNAVAILABLE")
    if schema and schema != "positman.plan.v0":
        structural = "INVALID"
        reasons.append("SCHEMA_INVALID")
    if not plan.get("trace_id"):
        structural = "INVALID"
        reasons.append("TRACE_ID_MISSING")
    if not ident.get("trade_id") and not plan.get("trade_id"):
        structural = "INVALID"
        reasons.append("IDENTITY_INCOMPLETE")
    if route and route not in ROUTES:
        structural = "INVALID"
        reasons.append("ROUTE_INVALID")
    if plan.get("match_status") in {"IDENTITY_MISMATCH", "STATE_TIME_MISMATCH"}:
        structural = "INVALID"
        reasons.append(str(plan.get("match_status")))
    if plan.get("plan_status") == "SOURCE_UNAVAILABLE":
        reasons.append("SOURCE_UNAVAILABLE")
    if route == "REDUCE_A":
        try:
            current_a = int(current) if current is not None else None
        except (TypeError, ValueError):
            current_a = None
        if qty is not None and current_a is not None and int(qty) > current_a:
            structural = "INVALID"
            reasons.append("PLAN_QUANTITY_INVALID")
    if plan.get("plan_status") in {"IDENTITY_MISMATCH", "STATE_TIME_MISMATCH"}:
        decision_status = str(plan.get("plan_status"))
    elif structural == "INVALID":
        decision_status = "REJECT"
    elif plan.get("plan_status") == "SOURCE_UNAVAILABLE":
        decision_status = "SOURCE_UNAVAILABLE"
    else:
        decision_status = "POLICY_UNRESOLVED"
        reasons.append("NO_POLICY_FROZEN")
    body = {
        "schema": DECISION_SCHEMA,
        "product": PRODUCT,
        "product_alias": "DRE",
        "system_id": SYSTEM_ID,
        "trace_id": plan.get("trace_id"),
        "identity": ident or {"trade_id": plan.get("trade_id")},
        "as_of": plan.get("as_of") or ident.get("as_of"),
        "positman_ref": {
            "schema": plan.get("schema"),
            "plan_status": plan.get("plan_status"),
            "position_route": route,
            "planned_qty": qty,
        },
        "structural_status": structural,
        "decision_status": decision_status,
        "execution_authorized": False,
        "execution_enabled": False,
        "live_execution": LIVE_EXECUTION,
        "policy_id": "NONE",
        "policy_status": "NO_POLICY_FROZEN",
        "reason_codes": reasons,
        "route_economic_context": ctx,
        "note": "V0 has no frozen ACCEPT policy. Structural VALID does not authorize execution.",
        "created_at": now_iso(),
    }
    boundary = execution_boundary(plan, body)
    body["execution_boundary"] = boundary
    return body


def decide_for_trade(trade_id: str, as_of: str | None = None, record: bool = True) -> dict[str, Any]:
    from roller.dre.positman_adapter import read_plan

    plan = read_plan(trade_id, as_of)
    body = decide(plan)
    body["trade_id"] = trade_id
    if record:
        _audit(body, plan)
    return body


def _audit(decision: dict[str, Any], plan: dict[str, Any]) -> None:
    from roller.systimo.transitions import record_event
    from roller.systimo.transitions.identity import extract_identity

    ident = extract_identity({**plan, **decision, "identity": decision.get("identity") or plan.get("identity")})
    ident["trace_id"] = decision.get("trace_id")
    try:
        record_event(
            stage="DREVO_DECISION",
            system_id="dre",
            object_type="DrevoDecision",
            object_id=str(decision.get("trace_id") or ""),
            schema_name=DECISION_SCHEMA,
            payload=decision,
            identity=ident,
            event_status=str(decision.get("decision_status") or "OBSERVED"),
        )
        boundary = decision.get("execution_boundary") if isinstance(decision.get("execution_boundary"), dict) else {}
        record_event(
            stage="EXECUTION_BOUNDARY",
            system_id="dre",
            object_type="ApprovedPositionTransition",
            object_id=str(decision.get("trace_id") or ""),
            schema_name="positman.execution_boundary.v0",
            payload=boundary,
            identity=ident,
            event_status="NOT_SUBMITTED",
        )
    except Exception:
        return
