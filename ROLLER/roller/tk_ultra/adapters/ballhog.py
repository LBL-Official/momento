"""Read-only BallhogHedgeIntent sibling. Not Austin/Choosin evidence."""

from __future__ import annotations

from typing import Any

from roller.tk_ultra.models import UNAVAILABLE


def read_intent(trade_id: str, as_of: str | None = None, q_dir: object | None = None) -> dict[str, Any]:
    """In-process public Ballhog contract. No self-HTTP. No Ballhog adapters."""
    wanted = str(trade_id or "").strip()
    if not wanted:
        return {
            "availability": UNAVAILABLE,
            "schema": None,
            "detail": "trade_id missing",
            "reason_codes": ["BALLHOG_CONTEXT_UNAVAILABLE"],
        }
    try:
        from roller.ballhog.api import handle_intent
        from roller.ballhog.errors import BallhogError
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "schema": None,
            "detail": f"{type(exc).__name__}: {exc}",
            "reason_codes": ["BALLHOG_CONTEXT_UNAVAILABLE"],
        }
    try:
        intent = handle_intent(wanted, as_of=as_of, q_dir=q_dir)
    except BallhogError as exc:
        return {
            "availability": UNAVAILABLE,
            "schema": None,
            "detail": exc.message,
            "code": exc.code,
            "reason_codes": ["BALLHOG_CONTEXT_UNAVAILABLE"],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "schema": None,
            "detail": f"{type(exc).__name__}: {exc}",
            "reason_codes": ["BALLHOG_CONTEXT_UNAVAILABLE"],
        }
    if not isinstance(intent, dict):
        return {
            "availability": UNAVAILABLE,
            "schema": None,
            "detail": "Ballhog intent was not an object",
            "reason_codes": ["BALLHOG_CONTEXT_UNAVAILABLE"],
        }
    return {
        "availability": "OBSERVED",
        "schema": intent.get("schema"),
        "system_id": intent.get("system_id"),
        "product": intent.get("product"),
        "note": "SIBLING CONTEXT — NOT MODEL INPUT",
        "position_management": "NOT_IMPLEMENTED",
        "intent": intent,
        "reason_codes": [],
    }
