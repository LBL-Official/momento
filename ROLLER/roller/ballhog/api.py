"""Ballhog HTTP handlers. Austin + Choosin Texas only. Does not submit."""

from __future__ import annotations

from typing import Any

from roller.austin.api import handle_health as austin_health
from roller.ballhog.context import compose, list_positions
from roller.ballhog.errors import BallhogError
from roller.ballhog.models import (
    AUSTIN_N,
    AUSTIN_UNIVERSE,
    CHOOSIN_N,
    CHOOSIN_UNIVERSE,
    LIVE_EXECUTION,
    PRODUCT,
    RESEARCH_UNIT_QTY,
)
from roller.ballhog.policy import load_policy
from roller.choosin_texas.api import handle_health as choosin_health


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
        "system_id": "hedging_analysis",
        "role": "exposure_removal_optimizer",
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "submits": False,
        "feed_mode": "HISTORICAL",
        "live_feed": "UNAVAILABLE",
        "austin": {
            "availability": austin.get("status") or austin.get("live_feed") or "UNAVAILABLE",
            "universe": AUSTIN_UNIVERSE,
            "n": AUSTIN_N,
            "payload": austin,
        },
        "choosin_texas": {
            "availability": choosin.get("status") or "UNAVAILABLE",
            "universe": CHOOSIN_UNIVERSE,
            "n": CHOOSIN_N,
            "payload": choosin,
        },
        "note": (
            "Ballhog decides WHEN / q* / rho* / Δ*. TK Ultra expresses economically. "
            "Candle path ≠ fill. Dual-leg lock is theoretical."
        ),
    }


def handle_sources() -> dict[str, Any]:
    policy = load_policy()
    return {
        "product": PRODUCT,
        "feed_mode": "HISTORICAL",
        "live_feed": "UNAVAILABLE",
        "execution_enabled": False,
        "research_unit_qty": RESEARCH_UNIT_QTY,
        "default_q_dir": policy.default_q_dir,
        "max_q_dir": policy.max_q_dir,
        "austin": {
            "universe": AUSTIN_UNIVERSE,
            "n": AUSTIN_N,
            "model_version": "austin_v2",
            "dataset_version": AUSTIN_UNIVERSE,
            "adapter": "roller.dre.adapters.austin.query_at persist=False",
        },
        "choosin_texas": {
            "universe": CHOOSIN_UNIVERSE,
            "n": CHOOSIN_N,
            "pit_kind": "STATIC",
            "adapter": "roller.dre.adapters.choosin.get_trade_context",
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
    as_of_s = None if as_of in (None, "") else str(as_of)
    q_raw = payload.get("q_dir")
    q_dir = None if q_raw in (None, "") else q_raw
    return trade_id, as_of_s, q_dir


def handle_surface(body: dict[str, Any] | None) -> dict[str, Any]:
    trade_id, as_of, q_dir = _from_body(body)
    state = compose(trade_id, as_of=as_of, q_dir=q_dir)
    decision = state.get("decision") or {}
    return {
        "schema": (decision.get("surface") or {}).get("schema"),
        "trade_id": trade_id,
        "as_of": state.get("as_of"),
        "feed_mode": state.get("feed_mode"),
        "research_unit_qty": state.get("research_unit_qty"),
        "q_dir": state.get("q_dir"),
        "q_hedge": state.get("q_hedge"),
        "rho": state.get("rho"),
        "austin": state.get("austin"),
        "surface": decision.get("surface"),
        "execution_enabled": False,
    }


def handle_frontier(body: dict[str, Any] | None) -> dict[str, Any]:
    trade_id, as_of, q_dir = _from_body(body)
    state = compose(trade_id, as_of=as_of, q_dir=q_dir)
    decision = state.get("decision") or {}
    return {
        "trade_id": trade_id,
        "as_of": state.get("as_of"),
        "feed_mode": state.get("feed_mode"),
        "research_unit_qty": state.get("research_unit_qty"),
        "q_dir": state.get("q_dir"),
        "decision_status": decision.get("decision_status"),
        "risk_intent": decision.get("risk_intent"),
        "hedge_feasibility": decision.get("hedge_feasibility"),
        "explanation": decision.get("explanation"),
        "frontier": decision.get("frontier"),
        "execution_enabled": False,
    }


def handle_decision(body: dict[str, Any] | None) -> dict[str, Any]:
    trade_id, as_of, q_dir = _from_body(body)
    state = compose(trade_id, as_of=as_of, q_dir=q_dir)
    decision = dict(state.get("decision") or {})
    decision["trade_id"] = trade_id
    decision["as_of"] = state.get("as_of")
    decision["feed_mode"] = state.get("feed_mode")
    decision["intent"] = state.get("intent")
    decision["austin"] = state.get("austin")
    decision["choosin_texas"] = {k: state.get("choosin_texas", {}).get(k) for k in ("universe", "n", "availability")}
    return decision


def handle_transitions(body: dict[str, Any] | None = None, trade_id: str | None = None, as_of: str | None = None) -> dict[str, Any]:
    if trade_id:
        tid, ts, q_dir = str(trade_id), as_of, None
    else:
        tid, ts, q_dir = _from_body(body)
    state = compose(tid, as_of=ts, q_dir=q_dir)
    return {
        "trade_id": tid,
        "as_of": state.get("as_of"),
        "transitions": state.get("transitions"),
        "execution_enabled": False,
    }


def handle_intent(trade_id: str, as_of: str | None = None, q_dir: object | None = None) -> dict[str, Any]:
    state = compose(trade_id, as_of=as_of, q_dir=q_dir)
    return state["intent"]


def handle_desk() -> dict[str, Any]:
    policy = load_policy()
    return {
        "product": PRODUCT,
        "system_id": "hedging_analysis",
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "feed_mode": "HISTORICAL",
        "live_feed": "UNAVAILABLE",
        "policy": policy.as_dict(),
        "sources": handle_sources(),
        "note": "Exposure removal optimizer. Does not submit.",
    }
