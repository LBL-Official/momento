"""Drevo read adapter. Does not invent ACCEPT."""

from __future__ import annotations

from typing import Any

from roller.jump.data.models import LIVE_EXECUTION, UNAVAILABLE


def decision(params: dict[str, Any]) -> dict[str, Any]:
    from roller.dre.decision import decide_for_trade

    trade_id = str(params.get("trade_id") or "").strip()
    as_of = params.get("as_of")
    try:
        body = decide_for_trade(trade_id, None if as_of in (None, "") else str(as_of), record=False)
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "source_system": "dre",
            "detail": f"{type(exc).__name__}: {exc}",
            "trade_id": trade_id or None,
            "live_execution": LIVE_EXECUTION,
        }
    return {
        "availability": body.get("availability") or "OBSERVED",
        "source_system": "dre",
        "permission": "QUERY",
        "write": "DENY",
        "trade_id": trade_id,
        "as_of": as_of or body.get("as_of"),
        "schema": body.get("schema"),
        "decision_status": body.get("decision_status"),
        "structural_status": body.get("structural_status"),
        "execution_authorized": False,
        "live_execution": LIVE_EXECUTION,
        "raw": body,
    }
