"""Observe MLB 001 host + production Kalshi. Start only if already armed and down."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from roller.jump.library import repo_root
from roller.vital.control import CONTROL_ENV, control_enabled, submit_command
from roller.vital.mlb_001.kalshi_observe import observe_kalshi
from roller.vital.observe import observe_bot
from roller.vital.versions import BOT_ID, CONTROL_CONFIRMATION, LIVE_CONFIRMATION


def _live_toml_armed() -> dict[str, Any]:
    path = repo_root() / "config" / "live.toml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {
            "ok": False,
            "armed": False,
            "reason": "config/live.toml unreadable",
            "path": str(path),
        }
    armed = (
        'mode = "live"' in text
        and "enabled = true" in text
        and LIVE_CONFIRMATION in text
        and "strategy_profile = \"research_iti\"" not in text
    )
    return {
        "ok": True,
        "armed": armed,
        "reason": None if armed else "triple live gate incomplete or ITI profile present",
        "path": str(path),
    }


def diagnose_mlb_001(*, root: Path | None = None, pull_kalshi: bool = True) -> dict[str, Any]:
    observed = observe_bot(BOT_ID, root=root, persist=False)
    runtime = observed.get("runtime") if isinstance(observed.get("runtime"), dict) else {}
    lifecycle = runtime.get("lifecycle")
    service = runtime.get("service") if isinstance(runtime.get("service"), dict) else {}
    service_value = service.get("value") if isinstance(service.get("value"), dict) else {}
    service_status = str(service.get("status") or "")
    host_confirmed = service_status == "CONFIRMED"
    active = host_confirmed and str(service_value.get("active") or "").strip().lower() == "active"
    gates = _live_toml_armed()
    kalshi: dict[str, Any]
    if pull_kalshi and (os.environ.get("JUMP_SKIP_KALSHI") or "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        kalshi = observe_kalshi(environment="PRODUCTION")
    else:
        kalshi = {
            "status": "OBSERVATION_UNAVAILABLE",
            "detail": "Kalshi pull skipped",
            "read_only": True,
            "submits": False,
        }
    can_start = (
        gates.get("armed") is True
        and host_confirmed
        and not active
        and lifecycle != "RUNNING"
        and control_enabled()
    )
    from roller.vital.parameters import parameters_view

    return {
        "bot_id": BOT_ID,
        "lifecycle": lifecycle or "OBSERVATION_UNAVAILABLE",
        "host_confirmed": host_confirmed,
        "service_active": active,
        "live_toml": gates,
        "kalshi": {
            "status": kalshi.get("status") or "OBSERVATION_UNAVAILABLE",
            "detail": kalshi.get("detail"),
            "read_only": True,
            "submits": False,
        },
        "control_enabled": control_enabled(),
        "can_start_if_armed": can_start,
        "start_is_not_live_arm": True,
        "http_200_not_running": True,
        "invented_fills": False,
        "parameters": parameters_view(BOT_ID, root=root),
        "factory_locked": True,
        "note": (
            "Start only if live.toml is already armed and the unit is inactive. "
            "HTTP 200 is not RUNNING. Trades require a real 80→81 YES bid."
        ),
    }


def start_mlb_001_if_armed(
    body: dict[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Start momento-live.service only when already armed and inactive."""
    diagnosis = diagnose_mlb_001(root=root, pull_kalshi=False)
    if not diagnosis["live_toml"].get("armed"):
        return {
            **diagnosis,
            "started": False,
            "command_status": "REJECTED",
            "detail": diagnosis["live_toml"].get("reason") or "live.toml is not armed",
        }
    if not diagnosis.get("host_confirmed"):
        return {
            **diagnosis,
            "started": False,
            "command_status": "REJECTED",
            "detail": "host is unread; start stays fail-closed",
        }
    if diagnosis.get("service_active") or diagnosis.get("lifecycle") == "RUNNING":
        return {
            **diagnosis,
            "started": False,
            "command_status": "CONFIRMED",
            "detail": "momento-live.service is already active; start skipped",
        }
    if not control_enabled():
        return {
            **diagnosis,
            "started": False,
            "command_status": "CONTROL_DISABLED",
            "detail": f"production writes require {CONTROL_ENV}=1 and confirmation={CONTROL_CONFIRMATION}",
        }
    command = submit_command(BOT_ID, {"action": "start", **(body or {})}, root=root)
    return {
        **diagnosis,
        "started": command.get("command_status") in {"DISPATCHED", "CONFIRMING", "CONFIRMED"},
        "command": command,
        "command_status": command.get("command_status"),
        "http_200_not_running": True,
    }
