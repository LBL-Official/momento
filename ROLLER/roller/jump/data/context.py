"""JumpResearchContext. Independent sources. Missing is UNAVAILABLE, never $0."""

from __future__ import annotations

from typing import Any

from roller.jump.data.adapters import austin, ballhog, choosin, drevo, positman, roller, tk_ultra, vital
from roller.jump.data.lineage import for_result
from roller.jump.data.models import (
    AUSTIN_N,
    AUSTIN_UNIVERSE,
    CHOOSIN_N,
    CHOOSIN_UNIVERSE,
    CONTEXT_SCHEMA,
    DEFAULT_TRADE_ID,
    LIVE_EXECUTION,
    UNAVAILABLE,
    now_iso,
)


def _safe(fn, params: dict[str, Any]) -> dict[str, Any]:
    try:
        body = fn(params)
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "detail": f"{type(exc).__name__}: {exc}",
            "live_execution": LIVE_EXECUTION,
        }
    if not isinstance(body, dict):
        return {"availability": UNAVAILABLE, "detail": "non-dict source"}
    return body


def compose(trade_id: str | None = None, as_of: str | None = None) -> dict[str, Any]:
    wanted = str(trade_id or DEFAULT_TRADE_ID).strip()
    params = {"trade_id": wanted, "as_of": as_of}
    austin_q = _safe(austin.query_at_payload, params)
    if austin_q.get("availability") != UNAVAILABLE and not as_of:
        as_of = austin_q.get("as_of")
        params["as_of"] = as_of
    trade = _safe(austin.get_trade_payload, params)
    choosin_q = _safe(choosin.trade_context, params)
    ballhog_q = _safe(ballhog.intent, params)
    tk_q = _safe(tk_ultra.assess, params)
    positman_q = _safe(positman.plan, params)
    drevo_q = _safe(drevo.decision, params)
    ident = {
        "trade_id": wanted,
        "ticker": (trade.get("trade") or {}).get("ticker") or austin_q.get("ticker"),
        "event_id": (trade.get("trade") or {}).get("event_id") or austin_q.get("event_id"),
        "game_id": (trade.get("trade") or {}).get("game_id") or austin_q.get("game_id"),
    }
    roller_params = {
        "ticker": ident.get("ticker"),
        "as_of": as_of,
        "limit": 25,
    }
    roller_id = _safe(roller.game_identity, roller_params) if ident.get("ticker") else {
        "availability": UNAVAILABLE,
        "detail": "ticker unavailable",
        "source_system": "roller",
    }
    roller_obs = _safe(roller.observations, roller_params) if ident.get("ticker") else {
        "availability": UNAVAILABLE,
        "detail": "ticker unavailable",
        "source_system": "roller",
    }
    roller_pbp = _safe(roller.pbp, roller_params) if ident.get("ticker") else {
        "availability": UNAVAILABLE,
        "detail": "ticker unavailable",
        "source_system": "roller",
    }
    roller_settle = _safe(roller.settlement, roller_params) if ident.get("ticker") else {
        "availability": UNAVAILABLE,
        "detail": "ticker unavailable",
        "source_system": "roller",
    }
    vital_q = _safe(vital.status, {})
    health = {
        "austin": austin_q.get("availability"),
        "choosin_texas": choosin_q.get("availability"),
        "ballhog": ballhog_q.get("availability"),
        "tk_ultra": tk_q.get("availability"),
        "positman": positman_q.get("availability"),
        "drevo": drevo_q.get("availability"),
        "roller": roller_id.get("availability"),
        "roller_pbp": roller_pbp.get("availability"),
        "roller_settlement": roller_settle.get("availability"),
        "vital": vital_q.get("availability"),
    }
    lineage = for_result("JUMP_RESEARCH_CONTEXT", austin_q, params)
    lineage["parents"].extend(
        [
            {"system_id": "choosin_texas", "resource_id": "choosin.get_trade_context", "universe_id": CHOOSIN_UNIVERSE, "n": CHOOSIN_N},
            {"system_id": "ballhog", "resource_id": "ballhog.handle_intent"},
            {"system_id": "tk_ultra", "resource_id": "tk_ultra.assess_v0"},
            {"system_id": "position_management", "resource_id": "positman.plan"},
            {"system_id": "dre", "resource_id": "drevo.decision"},
            {"system_id": "roller", "resource_id": "warehouse.pointer"},
        ]
    )
    return {
        "schema": CONTEXT_SCHEMA,
        "identity": ident,
        "as_of": as_of,
        "game_state": {
            "source_system": "roller",
            "availability": roller_id.get("availability"),
            "result": roller_id,
        },
        "market_state": {
            "source_system": "roller",
            "availability": roller_obs.get("availability"),
            "result": roller_obs,
        },
        "pbp": {
            "source_system": "roller",
            "availability": roller_pbp.get("availability"),
            "result": roller_pbp,
        },
        "settlement": {
            "source_system": "roller",
            "availability": roller_settle.get("availability"),
            "result": roller_settle,
        },
        "Austin": {
            "source_system": "austin",
            "universe": AUSTIN_UNIVERSE,
            "n": AUSTIN_N,
            "availability": austin_q.get("availability"),
            "austin.conditional_ev_cents": austin_q.get("austin.conditional_ev_cents"),
            "result": austin_q,
        },
        "Choosin": {
            "source_system": "choosin_texas",
            "universe": CHOOSIN_UNIVERSE,
            "n": CHOOSIN_N,
            "availability": choosin_q.get("availability"),
            "choosin.population_survival": choosin_q.get("choosin.population_survival"),
            "pit_kind": "STATIC",
            "result": choosin_q,
        },
        "Ballhog": {
            "source_system": "ballhog",
            "availability": ballhog_q.get("availability"),
            "ballhog.rho_star": ballhog_q.get("ballhog.rho_star"),
            "result": ballhog_q,
        },
        "TKUltra": {
            "source_system": "tk_ultra",
            "availability": tk_q.get("availability"),
            "tk_ultra.gross_route_edge": tk_q.get("tk_ultra.gross_route_edge"),
            "result": tk_q,
        },
        "Positman": {
            "source_system": "position_management",
            "availability": positman_q.get("availability"),
            "position_route": positman_q.get("position_route"),
            "planned_qty": positman_q.get("planned_qty"),
            "result": positman_q,
        },
        "Drevo": {
            "source_system": "dre",
            "availability": drevo_q.get("availability"),
            "decision_status": drevo_q.get("decision_status"),
            "execution_authorized": False,
            "result": drevo_q,
        },
        "Vital": {
            "source_system": "vital",
            "availability": vital_q.get("availability"),
            "result": vital_q,
        },
        "lineage": lineage,
        "source_health": health,
        "universes": {
            "austin": {"id": AUSTIN_UNIVERSE, "n": AUSTIN_N},
            "choosin_texas": {"id": CHOOSIN_UNIVERSE, "n": CHOOSIN_N},
        },
        "note": "Universes are displayed together. They are not mixed.",
        "live_execution": LIVE_EXECUTION,
        "write": "DENY",
        "completed_at": now_iso(),
    }
