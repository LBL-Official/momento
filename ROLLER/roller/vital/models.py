"""Vital domain facts. Desired ≠ observed ≠ confirmed."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.vital.honesty import confirmed, observation_unavailable, unavailable
from roller.vital.versions import (
    BOT_ALIASES,
    BOT_DISPLAY,
    BOT_ID,
    ENGINE_POINTER,
    ENVIRONMENTS,
    FACTORY,
    HEALTH,
    KIND,
    LIFECYCLE,
    SERVICE_NAME,
    STRATEGY_POINTER,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def factory_snapshot() -> dict[str, Any]:
    return dict(FACTORY)


def resolve_bot_id(raw: str) -> str:
    token = str(raw or "").strip()
    if token == BOT_ID or token in BOT_ALIASES:
        return BOT_ID
    return token


def is_known_lifecycle(value: str) -> bool:
    return value in LIFECYCLE


def is_known_environment(value: str) -> bool:
    return value in ENVIRONMENTS


def is_known_health(value: str) -> bool:
    return value in HEALTH


def unread_runtime() -> dict[str, Any]:
    return {
        "lifecycle": "OBSERVATION_UNAVAILABLE",
        "health": "UNKNOWN",
        "environment": "PRODUCTION",
        "desired": {
            "lifecycle": "OBSERVATION_UNAVAILABLE",
            "detail": "Vital does not claim the host is running until observe confirms it",
        },
        "observed": observation_unavailable("host unread"),
        "confirmed": observation_unavailable("host unread"),
        "host": observation_unavailable(),
        "service": observation_unavailable(),
        "process": observation_unavailable(),
        "version": observation_unavailable(),
        "heartbeat": observation_unavailable(),
        "kill_switch": observation_unavailable(),
        "live_armed": observation_unavailable(),
        "live_ev": unavailable("UNAVAILABLE"),
        "sharpe": unavailable("UNAVAILABLE"),
    }


def mlb_001_identity() -> dict[str, Any]:
    return {
        "bot_id": BOT_ID,
        "aliases": list(BOT_ALIASES),
        "name": BOT_DISPLAY,
        "kind": KIND,
        "environment": "PRODUCTION",
        "status": "OBSERVATION_UNAVAILABLE",
        "health": "UNKNOWN",
        "aws_runtime_id": SERVICE_NAME,
        "engine_pointer": ENGINE_POINTER,
        "strategy_pointer": STRATEGY_POINTER,
        "iti_lineage": None,
        "live_armed_confirmed": False,
        "factory": factory_snapshot(),
        "notes": (
            "Existing MLB desk. Grandfathered. Canonical Vital owner. "
            "Not created through ITI. Execution stays apps/trading-engine + Risk."
        ),
    }


def metric_from_fields(fields: dict[str, Any], key: str, *, missing: str = "OBSERVATION_UNAVAILABLE") -> dict[str, Any]:
    if key not in fields:
        return {"value": None, "status": missing}
    return confirmed(fields[key])
