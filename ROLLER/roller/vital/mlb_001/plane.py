"""MLB 001 Bot Standard control plane. Observe + fail-closed control. No submit."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.vital.bots import get_bot, get_bot_boundary
from roller.vital.control import CONTROL_ENV, DISPATCH_ENV, control_enabled, dispatch_mode
from roller.vital.honesty import observation_unavailable, unavailable
from roller.vital.mlb_001.identity import (
    BOT_ID,
    CONFIG_POINTER,
    ENGINE_POINTER,
    FACTORY,
    HOST_RUNTIME,
    STRATEGY_POINTER,
)
from roller.vital.observe import observe_bot
from roller.vital.store import config_identity_path, read_json
from roller.vital.versions import (
    CONTROL_ACTIONS,
    CONTROL_CONFIRMATION,
    HONESTY,
    LIVE_CONFIRMATION,
    LIVE_EXECUTION,
)

# Phase 3 required surfaces. Worker / pipeline are Phases 4–5.
REQUIRED_SURFACES = (
    "status",
    "configuration",
    "strategy",
    "positions",
    "orders",
    "risk",
    "heartbeat",
    "logs",
    "events",
    "controls",
)

ROUTES = {
    "plane": "GET /vital/bots/{id}/plane",
    "status": "GET /vital/bots/{id}/status",
    "health": "GET /vital/bots/{id}/health",
    "configuration": "GET /vital/bots/{id}/configuration",
    "strategy": "GET /vital/bots/{id}/strategy",
    "positions": "GET /vital/bots/{id}/positions",
    "orders": "GET /vital/bots/{id}/orders",
    "risk": "GET /vital/bots/{id}/risk",
    "heartbeat": "GET /vital/bots/{id}/heartbeat",
    "logs": "GET /vital/bots/{id}/logs",
    "events": "GET /vital/bots/{id}/events",
    "controls": "GET /vital/bots/{id}/controls",
    "commands": "POST /vital/bots/{id}/commands",
    "boundary": "GET /vital/bots/{id}/boundary",
    "worker": "GET /vital/bots/{id}/worker",
    "pipeline": "GET /vital/bots/{id}/pipeline",
    "runtime": "GET /vital/bots/{id}/runtime",
    "deployment": "GET /vital/bots/{id}/deployment",
    "kalshi": "GET /vital/bots/{id}/kalshi",
    "kalshi_observe": "POST /vital/bots/{id}/kalshi/observe",
    "host_observe": "POST /vital/bots/{id}/host/observe",
    "parameters": "GET /vital/bots/{id}/parameters",
    "parameters_patch": "PATCH /vital/bots/{id}/parameters",
    "kalshi_health": "GET /vital/bots/{id}/kalshi-health",
    "integration": "GET /vital/bots/{id}/integration",
    "integration_demo_lifecycle": "POST /vital/bots/{id}/integration/demo-lifecycle",
    "integration_handshake": "POST /vital/bots/{id}/integration/handshake",
}


def _runtime(bot_id: str, *, root: Path | None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    return observe_bot(bot_id, root=root, persist=False)["runtime"]


def plane_catalog(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    return {
        "bot_id": BOT_ID,
        "phase": 3,
        "layer": "control_plane",
        "surfaces": list(REQUIRED_SURFACES),
        "routes": dict(ROUTES),
        "frontend_owns_trading_logic": False,
        "live_execution": LIVE_EXECUTION,
        "http_200_not_running": True,
        "start_is_not_live_arm": True,
        "auth_fail_closed": True,
        "honesty": {
            "browser_is_not_engine": HONESTY["browser_is_not_engine"],
            "http_200_not_running": HONESTY["http_200_not_running"],
            "start_not_live_arm": HONESTY["start_not_live_arm"],
            "secrets_in_api": HONESTY["secrets_in_api"],
        },
    }


def configuration_view(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    identity = read_json(config_identity_path(BOT_ID, root=root))
    return {
        "bot_id": BOT_ID,
        "layer": "configuration",
        "pointer": CONFIG_POINTER,
        "editable": False,
        "secrets": False,
        "live_arm_is_not_vital_start": True,
        "identity": identity if identity is not None else observation_unavailable("config identity unread"),
        "factory": dict(FACTORY),
        "live_gates": {
            "mode": "live",
            "live.enabled": True,
            "confirmation": LIVE_CONFIRMATION,
            "note": "Triple gate stays in crates/core. Vital start does not arm live.",
        },
    }


def strategy_view(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    runtime = _runtime(bot_id, root=root)
    return {
        "bot_id": BOT_ID,
        "layer": "strategy",
        "pointer": STRATEGY_POINTER,
        "signal": FACTORY["signal"],
        "proposes": True,
        "submits": False,
        "locked": True,
        "does_not_retune": True,
        "constants": {
            "min_entry_cents": FACTORY["min_entry_cents"],
            "preferred_entry_cents": FACTORY["preferred_entry_cents"],
            "max_entry_cents": FACTORY["max_entry_cents"],
            "confirm_cents": FACTORY["confirm_cents"],
            "lock_cents": FACTORY["lock_cents"],
            "order_type": FACTORY["order_type"],
        },
        "looking_for": "YES bid First 80, then 81 confirm, then maker-only entry in 80–83",
        "entry_rules": {
            "observation": "YES_BID",
            "first_touch_cents": FACTORY["min_entry_cents"],
            "confirm_cents": FACTORY["confirm_cents"],
            "band_cents": [FACTORY["min_entry_cents"], FACTORY["max_entry_cents"]],
            "limit": "observed YES bid",
            "order_type": FACTORY["order_type"],
        },
        "exit_rules": {
            "lock_cents": FACTORY["lock_cents"],
            "stop": "50% VWAP on the position YES bid",
            "not_iti_reach": True,
        },
        "order_rules": {
            "entry": "post-only maker",
            "exit": "reduce-only IOC liquidation",
            "risk": "Risk Decision Engine",
            "submitter": ENGINE_POINTER,
        },
        "spec_status": "CONFIRMED",
        "state": observation_unavailable("host strategy dump unread"),
        "open_mlb_positions": runtime.get("open_mlb_positions"),
        "note": "MlbStrategy proposes TradeIntent. It does not submit to Kalshi.",
    }


def risk_view(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    runtime = _runtime(bot_id, root=root)
    return {
        "bot_id": BOT_ID,
        "layer": "risk",
        "pointer": "crates/risk",
        "engine": "Risk Decision Engine",
        "second_engine": False,
        "submits": False,
        "limits": {
            "bankroll_cents": FACTORY["bankroll_cents"],
            "allocation_bps": FACTORY["allocation_bps"],
            "per_game_cents": FACTORY["per_game_cents"],
            "max_open_mlb_positions": FACTORY["max_open_mlb_positions"],
            "max_entry_cents": FACTORY["max_entry_cents"],
        },
        "occupancy": runtime.get("open_mlb_positions"),
        "kill_switch": runtime.get("kill_switch"),
        "live_armed": runtime.get("live_armed"),
        "state": observation_unavailable("host risk persist unread"),
        "note": "Strategy cannot bypass Risk. Vital does not implement a second Risk.",
    }


def heartbeat_view(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    runtime = _runtime(bot_id, root=root)
    beat = runtime.get("heartbeat")
    if not isinstance(beat, dict):
        beat = observation_unavailable("host heartbeat unread")
    return {
        "bot_id": BOT_ID,
        "layer": "heartbeat",
        "source_pointer": HOST_RUNTIME,
        "overwrite_interval_s": 5,
        "heartbeat": beat,
        "lifecycle": runtime.get("lifecycle"),
        "health": runtime.get("health"),
        "kill_switch": runtime.get("kill_switch"),
        "live_armed": runtime.get("live_armed"),
        "http_200_not_running": True,
        "live_ev": unavailable("UNAVAILABLE"),
        "sharpe": unavailable("UNAVAILABLE"),
    }


def controls_view(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    return {
        "bot_id": BOT_ID,
        "layer": "controls",
        "actions": list(CONTROL_ACTIONS),
        "post": ROUTES["commands"],
        "enabled": control_enabled(),
        "control_env": CONTROL_ENV,
        "dispatch_mode": dispatch_mode(),
        "dispatch_env": DISPATCH_ENV,
        "confirmation_token_name": CONTROL_CONFIRMATION,
        "live_confirmation_is_not_control": LIVE_CONFIRMATION,
        "start_is_not_live_arm": True,
        "kill_is_not_stop": True,
        "kill_does_not_flatten": True,
        "http_200_not_running": True,
        "fail_closed": True,
        "default_status": "CONTROL_DISABLED",
        "note": (
            f"Production writes require {CONTROL_ENV}=1 and "
            f"confirmation={CONTROL_CONFIRMATION}. Default is fail-closed. "
            f"When armed, dispatch is {dispatch_mode()} via {DISPATCH_ENV}."
        ),
    }


def boundary_view(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    record = get_bot_boundary(bot_id, root=root)
    return {
        "bot_id": BOT_ID,
        "layer": "boundary",
        "engine_pointer": ENGINE_POINTER,
        "strategy_pointer": STRATEGY_POINTER,
        **record,
    }
