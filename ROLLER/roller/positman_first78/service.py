"""Compose the 78/67 Ballhog intent with the 78/67 TK Ultra assessment."""

from __future__ import annotations

from typing import Any

from roller.positman.composer import compose_plan
from roller.positman.matching import match_siblings
from roller.positman.models import LIVE_EXECUTION, PRODUCT, SYSTEM_ID
from roller.positman.service import _audit


def _default_trade() -> str:
    from roller.ballhog_first78.api import handle_positions

    rows = handle_positions().get("positions") or []
    for row in rows:
        trade_id = str(row.get("trade_id") or "")
        if trade_id.startswith("f78-"):
            return trade_id
    return ""


def read_intent(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    from roller.ballhog.errors import BallhogError
    from roller.ballhog_first78.api import handle_intent

    try:
        body = handle_intent(trade_id, as_of=None if as_of in (None, "") else str(as_of))
    except BallhogError as exc:
        return {"availability": "UNAVAILABLE", "source_system": "ballhog", "error_code": exc.code, "detail": exc.message, "book": "FIRST78_67"}
    return {"availability": "OBSERVED", "source_system": "ballhog", "schema": body.get("schema"), "intent": body, "book": "FIRST78_67", "live_execution": LIVE_EXECUTION}


def read_assessment(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    from roller.tk_ultra.errors import TkUltraV0Error
    from roller.tk_ultra_first78.api import handle_assess_v0

    try:
        body = handle_assess_v0(
            {
                "trade_id": trade_id,
                "as_of": as_of,
                "include_sibling": False,
                "feed_mode": "HISTORICAL",
                "a_anchor_cents": 78,
                "b_anchor_cents": 22,
            }
        )
    except TkUltraV0Error as exc:
        return {"availability": "UNAVAILABLE", "source_system": "tk_ultra", "error_code": exc.code, "detail": exc.message, "book": "FIRST78_67"}
    return {
        "availability": body.get("availability") or "OBSERVED",
        "source_system": "tk_ultra",
        "schema": body.get("schema") or "tk_ultra.assessment.v0",
        "assessment": body,
        "book": "FIRST78_67",
        "live_execution": LIVE_EXECUTION,
    }


def plan(trade_id: str | None = None, as_of: str | None = None, record: bool = True) -> dict[str, Any]:
    wanted = str(trade_id or "").strip() or _default_trade()
    ballhog = read_intent(wanted, as_of) if wanted else {"availability": "UNAVAILABLE", "intent": {}}
    intent_stamp = None
    if not as_of:
        intent_body = ballhog.get("intent") if isinstance(ballhog.get("intent"), dict) else {}
        intent_stamp = intent_body.get("as_of")
    tk_ultra = read_assessment(wanted, as_of or intent_stamp) if wanted else {"availability": "UNAVAILABLE", "assessment": {}}
    intent = ballhog.get("intent") if isinstance(ballhog.get("intent"), dict) else {}
    assessment = tk_ultra.get("assessment") if isinstance(tk_ultra.get("assessment"), dict) else {}
    matched = match_siblings(intent or ballhog, assessment or tk_ultra)
    body = compose_plan(match=matched, ballhog=ballhog, tk_ultra=tk_ultra)
    body["trade_id"] = wanted
    body["book"] = "FIRST78_67"
    if record and wanted:
        _audit(body, intent, assessment)
    return body


def sources() -> dict[str, Any]:
    return {
        "product": PRODUCT,
        "system_id": SYSTEM_ID,
        "book": "FIRST78_67",
        "inputs": ["ballhog.hedge_intent.v1", "tk_ultra.assessment.v0"],
        "output": "positman.plan.v0",
        "execution_enabled": False,
        "live_execution": LIVE_EXECUTION,
        "write": "DENY",
        "adapters": {
            "ballhog": "roller.ballhog_first78.api.handle_intent",
            "tk_ultra": "roller.tk_ultra_first78.api.handle_assess_v0",
            "drevo": "roller.dre_first78.api.handle_decision",
        },
        "note": "Compositor only. Quantity from Ballhog 78/67. Route from TK Ultra 78/67.",
    }
