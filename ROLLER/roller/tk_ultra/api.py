"""TK Ultra HTTP handlers. Austin + Choosin owned here. Ballhog is optional sibling."""

from __future__ import annotations

from typing import Any

from roller.austin.api import handle_health as austin_health
from roller.choosin_texas.api import handle_health as choosin_health
from roller.tk_ultra.adapters.austin import AUSTIN_ADAPTER
from roller.tk_ultra.adapters.ballhog import read_intent
from roller.tk_ultra.adapters.choosin import CHOOSIN_ADAPTER
from roller.tk_ultra.assessment import MATH_KEYS, assess_binary, attach_sibling
from roller.tk_ultra.context import compose, list_positions
from roller.tk_ultra.errors import TkUltraV0Error
from roller.tk_ultra.models import (
    AUSTIN_N,
    AUSTIN_UNIVERSE,
    CHOOSIN_N,
    CHOOSIN_UNIVERSE,
    LIVE_EXECUTION,
    MODEL_BINARY,
    PRODUCT,
    SYSTEM_ID,
    UNAVAILABLE,
)


def handle_health() -> dict[str, Any]:
    austin: dict[str, Any]
    choosin: dict[str, Any]
    try:
        austin = austin_health()
    except Exception as exc:  # noqa: BLE001
        austin = {"status": "UNAVAILABLE", "detail": f"{type(exc).__name__}: {exc}"}
    try:
        choosin = choosin_health()
    except Exception as exc:  # noqa: BLE001
        choosin = {"status": "UNAVAILABLE", "detail": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": True,
        "product": PRODUCT,
        "system_id": SYSTEM_ID,
        "role": "relative_value_hedging",
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "submits": False,
        "feed_mode": "HISTORICAL",
        "live_feed": "UNAVAILABLE",
        "model_modes": ["GENERIC_RV", MODEL_BINARY],
        "austin": {
            "availability": austin.get("status") or austin.get("live_feed") or "UNAVAILABLE",
            "universe": AUSTIN_UNIVERSE,
            "n": AUSTIN_N,
            "adapter": AUSTIN_ADAPTER,
            "payload": austin,
        },
        "choosin_texas": {
            "availability": choosin.get("status") or "UNAVAILABLE",
            "universe": CHOOSIN_UNIVERSE,
            "n": CHOOSIN_N,
            "adapter": CHOOSIN_ADAPTER,
            "payload": choosin,
        },
        "ballhog": _ballhog_health(),
        "position_management": "NOT_IMPLEMENTED",
        "note": (
            "TK Ultra determines relative-value route. Ballhog determines when/how much. "
            "Siblings. Candle path ≠ fill."
        ),
    }


def _ballhog_health() -> dict[str, Any]:
    try:
        from roller.ballhog.api import handle_intent  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "role": "optional_sibling",
            "detail": f"{type(exc).__name__}: {exc}",
        }
    return {
        "availability": "OBSERVED",
        "role": "optional_sibling",
        "contract": "ballhog.hedge_intent.v1",
        "callable": "roller.ballhog.api.handle_intent",
    }


def handle_sources() -> dict[str, Any]:
    return {
        "product": PRODUCT,
        "feed_mode": "HISTORICAL",
        "live_feed": "UNAVAILABLE",
        "execution_enabled": False,
        "austin": {
            "universe": AUSTIN_UNIVERSE,
            "n": AUSTIN_N,
            "adapter": AUSTIN_ADAPTER,
        },
        "choosin_texas": {
            "universe": CHOOSIN_UNIVERSE,
            "n": CHOOSIN_N,
            "pit_kind": "STATIC",
            "adapter": CHOOSIN_ADAPTER,
        },
        "ballhog": {
            "role": "optional_sibling",
            "contract": "ballhog.hedge_intent.v1",
            "callable": "roller.ballhog.api.handle_intent",
            "not_source_of": ["austin", "choosin_texas"],
        },
    }


def handle_positions() -> dict[str, Any]:
    return list_positions()


def handle_state(trade_id: str, as_of: str | None = None, include_sibling: bool = False) -> dict[str, Any]:
    return compose(trade_id, as_of=as_of, include_sibling=include_sibling)


def handle_assess_v0(body: dict[str, Any] | None) -> dict[str, Any]:
    payload = body if isinstance(body, dict) else {}
    trade_id = str(payload.get("trade_id") or "").strip()
    as_of = payload.get("as_of")
    include_sibling = bool(payload.get("include_sibling"))
    if trade_id:
        state = compose(trade_id, as_of=as_of, overlay=payload, include_sibling=include_sibling)
        return state["assessment"]
    assessment = assess_binary(payload, feed_mode=str(payload.get("feed_mode") or "MANUAL_INPUT"))
    if include_sibling and trade_id:
        assessment = attach_sibling(assessment, read_intent(trade_id, as_of=as_of))
    else:
        assessment = attach_sibling(assessment, None)
    return assessment


def handle_ballhog_context(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    return read_intent(trade_id, as_of=as_of)


def math_snapshot(assessment: dict[str, Any]) -> dict[str, Any]:
    return {key: assessment.get(key) for key in MATH_KEYS}
