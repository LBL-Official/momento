"""HTTP handlers for the 78/67 Ballhog desk. Does not submit."""

from __future__ import annotations

from typing import Any

from roller.austin_first78.api import handle_health as austin_health
from roller.ballhog.errors import BallhogError
from roller.ballhog.models import LIVE_EXECUTION, PRODUCT, RESEARCH_UNIT_QTY
from roller.ballhog_first78.compose import AUSTIN_UNIVERSE, CHOOSIN_UNIVERSE, austin_n, choosin_n, compose, list_positions
from roller.ballhog_first78.context import choosin_prior
from roller.ballhog_first78.policy import load_policy


def handle_health() -> dict[str, Any]:
    try:
        austin = austin_health()
    except Exception as exc:  # noqa: BLE001
        austin = {"status": "UNAVAILABLE", "detail": f"{type(exc).__name__}: {exc}"}
    prior = choosin_prior()
    return {
        "ok": True,
        "product": PRODUCT,
        "book": "FIRST78_67",
        "system_id": "hedging_analysis",
        "role": "exposure_removal_optimizer",
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "submits": False,
        "feed_mode": "HISTORICAL",
        "live_feed": "UNAVAILABLE",
        "lock": "22-p",
        "price_grid": list(range(62, 73)),
        "austin": {
            "availability": "OBSERVED" if austin.get("ok") else "UNAVAILABLE",
            "universe": AUSTIN_UNIVERSE,
            "n": austin_n(),
            "payload": austin,
        },
        "choosin_texas": {
            "availability": prior.get("availability") or "UNAVAILABLE",
            "universe": CHOOSIN_UNIVERSE,
            "n": prior.get("n"),
            "entry_cents": 78,
            "stop_cents": 67,
            "payload": prior,
        },
        "note": "78/67 exposure-removal desk. Lock is 22 − p. Candle path is not a fill.",
    }


def handle_sources() -> dict[str, Any]:
    policy = load_policy()
    return {
        "product": PRODUCT,
        "book": "FIRST78_67",
        "feed_mode": "HISTORICAL",
        "live_feed": "UNAVAILABLE",
        "execution_enabled": False,
        "research_unit_qty": RESEARCH_UNIT_QTY,
        "default_q_dir": policy.default_q_dir,
        "max_q_dir": policy.max_q_dir,
        "austin": {
            "universe": AUSTIN_UNIVERSE,
            "n": austin_n(),
            "adapter": "roller.austin_first78 query persist=False",
        },
        "choosin_texas": {
            "universe": CHOOSIN_UNIVERSE,
            "n": choosin_n(),
            "pit_kind": "STATIC",
            "adapter": "derived-four FIRST78_67",
        },
        "policy": policy.as_dict(),
    }


def handle_positions() -> dict[str, Any]:
    return list_positions()


def handle_state(trade_id: str, as_of: str | None = None, q_dir: object | None = None) -> dict[str, Any]:
    return compose(trade_id, as_of=as_of, q_dir=q_dir)


def _from_body(body: dict[str, Any] | None) -> tuple[str, str | None, object | None]:
    payload = body if isinstance(body, dict) else {}
    trade_id = str(payload.get("trade_id") or payload.get("position_id") or "").strip()
    if not trade_id:
        raise BallhogError("INVALID_INPUT", "trade_id is required")
    as_of = payload.get("as_of")
    q_raw = payload.get("q_dir")
    return trade_id, None if as_of in (None, "") else str(as_of), None if q_raw in (None, "") else q_raw


def handle_surface(body: dict[str, Any] | None) -> dict[str, Any]:
    trade_id, as_of, q_dir = _from_body(body)
    state = compose(trade_id, as_of=as_of, q_dir=q_dir)
    decision = state.get("decision") or {}
    return {"trade_id": trade_id, "as_of": state.get("as_of"), "surface": decision.get("surface"), "execution_enabled": False}


def handle_frontier(body: dict[str, Any] | None) -> dict[str, Any]:
    trade_id, as_of, q_dir = _from_body(body)
    state = compose(trade_id, as_of=as_of, q_dir=q_dir)
    decision = state.get("decision") or {}
    return {
        "trade_id": trade_id,
        "as_of": state.get("as_of"),
        "decision_status": decision.get("decision_status"),
        "frontier": decision.get("frontier"),
        "execution_enabled": False,
    }


def handle_decision(body: dict[str, Any] | None) -> dict[str, Any]:
    trade_id, as_of, q_dir = _from_body(body)
    state = compose(trade_id, as_of=as_of, q_dir=q_dir)
    decision = dict(state.get("decision") or {})
    decision["trade_id"] = trade_id
    decision["as_of"] = state.get("as_of")
    decision["intent"] = state.get("intent")
    decision["austin"] = state.get("austin")
    decision["choosin_texas"] = state.get("choosin_texas")
    return decision


def handle_transitions(body: dict[str, Any] | None = None, trade_id: str | None = None, as_of: str | None = None) -> dict[str, Any]:
    if trade_id:
        tid, ts = str(trade_id), as_of
    else:
        tid, ts, _q = _from_body(body)
    state = compose(tid, as_of=ts)
    return {"trade_id": tid, "as_of": state.get("as_of"), "transitions": state.get("transitions"), "execution_enabled": False}


def handle_intent(trade_id: str, as_of: str | None = None, q_dir: object | None = None) -> dict[str, Any]:
    return compose(trade_id, as_of=as_of, q_dir=q_dir)["intent"]


def handle_desk() -> dict[str, Any]:
    policy = load_policy()
    return {
        "product": PRODUCT,
        "book": "FIRST78_67",
        "system_id": "hedging_analysis",
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "feed_mode": "HISTORICAL",
        "live_feed": "UNAVAILABLE",
        "policy": policy.as_dict(),
        "sources": handle_sources(),
        "note": "78/67 exposure removal. Does not submit.",
    }
