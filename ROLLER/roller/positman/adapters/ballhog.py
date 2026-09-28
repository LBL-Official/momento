"""Public Ballhog intent reader. Does not import roller.ballhog.adapters."""

from __future__ import annotations

from typing import Any

from roller.positman.models import LIVE_EXECUTION, UNAVAILABLE


def read_intent(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    from roller.ballhog.api import handle_intent
    from roller.ballhog.errors import BallhogError

    try:
        body = handle_intent(trade_id, as_of=None if as_of in (None, "") else str(as_of))
    except BallhogError as exc:
        return {
            "availability": UNAVAILABLE,
            "source_system": "ballhog",
            "error_code": exc.code,
            "detail": exc.message,
            "live_execution": LIVE_EXECUTION,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "source_system": "ballhog",
            "detail": f"{type(exc).__name__}: {exc}",
            "live_execution": LIVE_EXECUTION,
        }
    return {
        "availability": "OBSERVED",
        "source_system": "ballhog",
        "schema": body.get("schema") or "ballhog.hedge_intent.v1",
        "intent": body,
        "live_execution": LIVE_EXECUTION,
    }
