"""Ballhog read adapter. Does not recompute rho* / q* / Delta*."""

from __future__ import annotations

from typing import Any

from roller.jump.data.models import AUSTIN_N, AUSTIN_UNIVERSE, LIVE_EXECUTION, UNAVAILABLE


def intent(params: dict[str, Any]) -> dict[str, Any]:
    from roller.ballhog.api import handle_intent
    from roller.ballhog.errors import BallhogError

    trade_id = str(params.get("trade_id") or "").strip()
    as_of = params.get("as_of")
    try:
        body = handle_intent(trade_id, as_of=None if as_of in (None, "") else str(as_of))
    except BallhogError as exc:
        return {
            "availability": UNAVAILABLE,
            "source_system": "ballhog",
            "error_code": exc.code,
            "detail": exc.message,
            "trade_id": trade_id or None,
            "live_execution": LIVE_EXECUTION,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "source_system": "ballhog",
            "detail": f"{type(exc).__name__}: {exc}",
            "trade_id": trade_id or None,
            "live_execution": LIVE_EXECUTION,
        }
    return {
        "availability": body.get("availability") or "OBSERVED",
        "source_system": "ballhog",
        "permission": "QUERY",
        "write": "DENY",
        "trade_id": trade_id,
        "as_of": as_of or body.get("as_of"),
        "data_mode": "HISTORICAL_QUERY",
        "austin_universe": AUSTIN_UNIVERSE,
        "austin_n": AUSTIN_N,
        "ballhog.rho_star": body.get("rho_star"),
        "q_star": body.get("q_star"),
        "delta_star": body.get("delta_star"),
        "risk_intent": body.get("risk_intent"),
        "live_execution": LIVE_EXECUTION,
        "raw": body,
    }
