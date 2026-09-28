"""OrchestraContext. Read-only. Queries Systimo; does not own product data."""

from __future__ import annotations

from typing import Any

from roller.systimo.models import LIVE_EXECUTION, UNAVAILABLE, now_iso
from roller.systimo.transitions import get_trace, latest_for_trade
from roller.systimo.transitions.types import ORCHESTRA_NAMESPACES


def _safe(fn, *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        body = fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "detail": f"{type(exc).__name__}: {exc}",
            "live_execution": LIVE_EXECUTION,
        }
    if not isinstance(body, dict):
        return {"availability": UNAVAILABLE, "detail": "non-dict source"}
    if body.get("availability"):
        return body
    return {**body, "availability": body.get("availability") or "OBSERVED"}


def handle_orchestra_context(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    wanted = str(trade_id or "").strip()
    austin = _safe(_austin, wanted, as_of)
    choosin = _safe(_choosin, wanted)
    ballhog = _safe(_ballhog, wanted, as_of)
    tk_ultra = _safe(_tk_ultra, wanted, as_of)
    positman = _safe(_positman, wanted, as_of)
    drevo = _safe(_drevo, wanted, as_of)
    vital = _safe(_vital)
    jump = _safe(_jump, wanted, as_of)
    boundary = drevo.get("execution_boundary") if isinstance(drevo.get("execution_boundary"), dict) else {
        "availability": UNAVAILABLE,
        "status": "NOT_SUBMITTED",
        "execution_enabled": False,
    }
    trace = latest_for_trade(wanted, as_of)
    integrity = (trace.get("integrity") if isinstance(trace, dict) else None) or {
        "integrity_status": UNAVAILABLE
    }
    namespaces = {
        "austin": austin,
        "choosin_texas": choosin,
        "ballhog": ballhog,
        "tk_ultra": tk_ultra,
        "positman": positman,
        "drevo": drevo,
        "execution_boundary": boundary,
        "vital": vital,
        "jump": jump,
    }
    health = {name: (namespaces[name].get("availability") if isinstance(namespaces[name], dict) else UNAVAILABLE) for name in ORCHESTRA_NAMESPACES}
    return {
        "schema": "systimo.orchestra_context.v0",
        "product": "Orchestra",
        "query_only": True,
        "write": "DENY",
        "control": "DENY",
        "trade_id": wanted,
        "as_of": as_of or positman.get("as_of") or austin.get("as_of"),
        "trace": trace if trace.get("availability") != UNAVAILABLE else {"availability": UNAVAILABLE},
        "integrity": integrity,
        "namespaces": namespaces,
        "source_health": health,
        "execution_enabled": False,
        "live_execution": LIVE_EXECUTION,
        "note": "Orchestra queries Systimo. Partial source failure is UNAVAILABLE, never $0.",
        "completed_at": now_iso(),
    }


def _austin(trade_id: str, as_of: str | None) -> dict[str, Any]:
    from roller.jump.data.adapters.austin import query_at_payload

    return query_at_payload({"trade_id": trade_id, "as_of": as_of})


def _choosin(trade_id: str) -> dict[str, Any]:
    from roller.jump.data.adapters.choosin import trade_context

    return trade_context({"trade_id": trade_id})


def _ballhog(trade_id: str, as_of: str | None) -> dict[str, Any]:
    from roller.positman.adapters.ballhog import read_intent

    return read_intent(trade_id, as_of)


def _tk_ultra(trade_id: str, as_of: str | None) -> dict[str, Any]:
    from roller.positman.adapters.tk_ultra import read_assessment

    return read_assessment(trade_id, as_of)


def _positman(trade_id: str, as_of: str | None) -> dict[str, Any]:
    from roller.positman.service import plan

    return plan(trade_id, as_of, record=False)


def _drevo(trade_id: str, as_of: str | None) -> dict[str, Any]:
    from roller.dre.decision import decide_for_trade

    return decide_for_trade(trade_id, as_of, record=False)


def _vital() -> dict[str, Any]:
    from roller.jump.data.adapters.vital import status

    return status({})


def _jump(trade_id: str, as_of: str | None) -> dict[str, Any]:
    from roller.jump.data.context import compose

    return compose(trade_id, as_of)
