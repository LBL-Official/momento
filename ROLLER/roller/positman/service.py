"""Positman service. Compose Ballhog × TK Ultra. Record Systimo audit."""

from __future__ import annotations

from typing import Any

from roller.positman.adapters.ballhog import read_intent
from roller.positman.adapters.tk_ultra import read_assessment
from roller.positman.composer import compose_plan
from roller.positman.matching import match_siblings
from roller.positman.models import DEFAULT_TRADE_ID, LIVE_EXECUTION, PRODUCT, SYSTEM_ID


def plan(trade_id: str | None = None, as_of: str | None = None, record: bool = True) -> dict[str, Any]:
    wanted = str(trade_id or DEFAULT_TRADE_ID).strip()
    ballhog = read_intent(wanted, as_of)
    tk_ultra = read_assessment(wanted, as_of)
    intent = ballhog.get("intent") if isinstance(ballhog.get("intent"), dict) else {}
    assessment = tk_ultra.get("assessment") if isinstance(tk_ultra.get("assessment"), dict) else {}
    matched = match_siblings(intent or ballhog, assessment or tk_ultra)
    body = compose_plan(match=matched, ballhog=ballhog, tk_ultra=tk_ultra)
    body["trade_id"] = wanted
    if record:
        _audit(body, intent, assessment)
    return body


def sources() -> dict[str, Any]:
    return {
        "product": PRODUCT,
        "system_id": SYSTEM_ID,
        "inputs": ["ballhog.hedge_intent.v1", "tk_ultra.assessment.v0"],
        "output": "positman.plan.v0",
        "execution_enabled": False,
        "live_execution": LIVE_EXECUTION,
        "write": "DENY",
        "note": "Compositor only. Quantity from Ballhog. Route from TK Ultra.",
    }


def _audit(plan_body: dict[str, Any], intent: dict[str, Any], assessment: dict[str, Any]) -> None:
    from roller.systimo.transitions import record_event
    from roller.systimo.transitions.identity import extract_identity

    ident = extract_identity({**plan_body, "identity": plan_body.get("identity")})
    ident["trace_id"] = plan_body.get("trace_id")
    try:
        record_event(
            stage="SOURCE_STATE",
            system_id="systimo",
            object_type="TransitionIdentity",
            object_id=str(ident.get("trade_id") or plan_body.get("trade_id") or ""),
            schema_name="systimo.transition_trace.v0",
            payload={"identity": ident, "match_status": plan_body.get("match_status")},
            identity=ident,
            event_status=str(plan_body.get("match_status") or "OBSERVED"),
        )
        if intent:
            record_event(
                stage="BALLHOG_INTENT",
                system_id="ballhog",
                object_type="BallhogHedgeIntent",
                object_id=str(intent.get("position_id") or plan_body.get("trade_id") or ""),
                schema_name="ballhog.hedge_intent.v1",
                payload=intent,
                identity=ident,
            )
        if assessment:
            record_event(
                stage="TK_ULTRA_ASSESSMENT",
                system_id="tk_ultra",
                object_type="TKUltraRVAssessment",
                object_id=str((assessment.get("identity") or {}).get("trade_id") or plan_body.get("trade_id") or ""),
                schema_name="tk_ultra.assessment.v0",
                payload=assessment,
                identity=ident,
            )
        record_event(
            stage="POSITMAN_PLAN",
            system_id="position_management",
            object_type="PositmanPositionPlan",
            object_id=str(plan_body.get("trace_id") or ""),
            schema_name="positman.plan.v0",
            payload=plan_body,
            identity=ident,
            event_status=str(plan_body.get("plan_status") or "OBSERVED"),
        )
    except Exception:
        # Audit must not block the plan. Missing Systimo tables surface in tests.
        return
