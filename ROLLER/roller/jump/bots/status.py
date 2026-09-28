"""Read-only host observation. Never invent RUNNING or P&L. Never submit orders."""

from __future__ import annotations

import json
import os
from typing import Any

from roller.jump.bots.versions import BOT_ONE_ID, LIVE_CONFIRMATION

PROBE_ENV = "JUMP_BOT_ONE_PROBE"


def _parse_probe(raw: str) -> dict[str, Any]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return {"status": "OBSERVATION_UNAVAILABLE", "environment": None, "live_armed_confirmed": False}
    live_armed = bool(payload.get("live_armed_confirmed"))
    environment = payload.get("environment")
    status = str(payload.get("status") or "OBSERVATION_UNAVAILABLE")
    if live_armed:
        environment = "PRODUCTION"
        if status in {"", "OBSERVATION_UNAVAILABLE"}:
            status = "PRODUCTION"
    elif status in {"RUNNING", "PRODUCTION"}:
        status = "OBSERVATION_UNAVAILABLE"
        environment = None
    return {
        "status": status,
        "environment": environment,
        "live_armed_confirmed": live_armed,
        "aws_runtime_id": payload.get("aws_runtime_id"),
        "observed": True,
    }


def probe_bot_one() -> dict[str, Any]:
    raw = os.environ.get(PROBE_ENV)
    if raw:
        try:
            return _parse_probe(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return {
        "status": "OBSERVATION_UNAVAILABLE",
        "environment": None,
        "live_armed_confirmed": False,
        "aws_runtime_id": None,
        "observed": False,
        "detail": "host probe unset; Jump does not invent Bot One as RUNNING",
    }


def probe_demo(bot: dict[str, Any]) -> dict[str, Any]:
    from roller.jump.bots.deploy import observe_demo

    return observe_demo(bot)


def apply_observation(bot: dict[str, Any]) -> dict[str, Any]:
    from roller.jump.vital_client import jump_observation_from_vital, vital_id_for_jump_bot

    vital_id = vital_id_for_jump_bot(bot)
    try:
        observed = jump_observation_from_vital(bot_id=vital_id)
    except Exception:
        observed = {
            "status": "OBSERVATION_UNAVAILABLE",
            "environment": None,
            "live_armed_confirmed": False,
            "observed": False,
            "source": "vital",
            "detail": "Vital has not confirmed this bot; Jump does not invent RUNNING",
            "vital_bot_id": vital_id,
        }
    if observed.get("observed"):
        bot["status"] = observed["status"]
        bot["environment"] = observed.get("environment") or bot.get("environment")
        bot["live_armed_confirmed"] = bool(observed.get("live_armed_confirmed"))
    elif str(bot.get("bot_id")) == BOT_ONE_ID or bot.get("kind") == "grandfathered":
        bot["status"] = "OBSERVATION_UNAVAILABLE"
        bot["environment"] = None
        bot["live_armed_confirmed"] = False
    else:
        bot["live_armed_confirmed"] = False
    if observed.get("observed") and observed.get("aws_runtime_id"):
        bot["aws_runtime_id"] = observed["aws_runtime_id"]
    bot["observation"] = observed
    bot["vital_bot_id"] = vital_id
    return bot


def live_gate_ok(body: dict[str, Any] | None) -> bool:
    body = body or {}
    mode = str(body.get("mode") or "").strip().lower()
    enabled = body.get("live_enabled")
    if enabled is None:
        enabled = body.get("enabled")
    confirmation = str(body.get("confirmation") or "").strip()
    enabled_ok = enabled is True or enabled == 1 or str(enabled).strip().lower() in {"true", "1", "yes"}
    return mode == "live" and enabled_ok and confirmation == LIVE_CONFIRMATION
