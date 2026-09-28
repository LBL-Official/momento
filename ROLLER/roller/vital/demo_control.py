"""Demo-only lifecycle writes. Never touches momento-live.service."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.vital.control import confirmation_ok, control_enabled
from roller.vital.errors import VitalError
from roller.vital.integration_proof import persist_demo_control_proof
from roller.vital.models import utc_now
from roller.vital.store import append_event
from roller.vital.versions import BOT_ID, LIVE_CONFIRMATION, SERVICE_NAME

RESERVED_LIVE = BOT_ID


def _safe_demo_id(bot_id: str) -> str:
    from roller.jump.bots.demo_host import safe_bot_id
    from roller.jump.errors import JumpError

    text = str(bot_id or "").strip()
    if text == RESERVED_LIVE or text in {"mlb-bot-one"}:
        raise VitalError("REJECTED", "mlb-001 factory unit is not a demo control target")
    try:
        ident = safe_bot_id(text)
    except JumpError as exc:
        raise VitalError("REJECTED", str(exc)) from exc
    if ident == RESERVED_LIVE:
        raise VitalError("REJECTED", "mlb-001 factory unit is not a demo control target")
    return ident


def demo_unit_name(bot_id: str) -> str:
    ident = _safe_demo_id(bot_id)
    return f"momento-demo@{ident}.service"


def stop_script(bot_id: str) -> str:
    unit = demo_unit_name(bot_id)
    if SERVICE_NAME in unit or "momento-live.service" in unit:
        raise VitalError("REJECTED", "demo stop refuses the factory live unit")
    if not unit.startswith("momento-demo@"):
        raise VitalError("REJECTED", "demo stop only accepts momento-demo@ units")
    return (
        "python3 - <<'VITAL_DEMO_STOP'\n"
        "import json, subprocess\n"
        f"unit = {unit!r}\n"
        "if unit == 'momento-live.service' or 'momento-live.service' in unit:\n"
        "    print(json.dumps({'ok': False, 'reason': 'factory live unit refused'}))\n"
        "    raise SystemExit(0)\n"
        "if not unit.startswith('momento-demo@'):\n"
        "    print(json.dumps({'ok': False, 'reason': 'demo stop refuses non-demo unit'}))\n"
        "    raise SystemExit(0)\n"
        "stopped = subprocess.run(['systemctl', 'stop', unit], capture_output=True, text=True)\n"
        "active = subprocess.run(['systemctl', 'is-active', unit], capture_output=True, text=True)\n"
        "state = (active.stdout or '').strip()\n"
        "ok = stopped.returncode == 0 and state != 'active'\n"
        "print(json.dumps({'ok': ok, 'stopped': state != 'active', 'active': state, 'unit': unit, 'reason': None if ok else (stopped.stderr or state or 'stop unread')[:240]}))\n"
        "VITAL_DEMO_STOP\n"
    )


def _lifecycle_from_inspect(inspected: dict[str, Any]) -> str:
    if not inspected.get("ok"):
        return "OBSERVATION_UNAVAILABLE"
    if inspected.get("active") and inspected.get("heartbeat"):
        return "RUNNING_DEMO"
    if inspected.get("active") is False:
        return "STOPPED"
    return "OBSERVATION_UNAVAILABLE"


def _inspect(bot_id: str, *, refresh: bool = True) -> dict[str, Any]:
    from roller.jump.bots.demo_host import inspect_demo_unit

    inspected = inspect_demo_unit(bot_id, refresh=refresh)
    unit = str(inspected.get("unit") or "")
    if SERVICE_NAME in unit or bot_id == RESERVED_LIVE:
        raise VitalError("REJECTED", "demo inspect refused the factory live unit")
    return inspected


def _stop(bot_id: str) -> dict[str, Any]:
    from roller.jump.bots.demo_host import _ssm_run

    script = stop_script(bot_id)
    if SERVICE_NAME in script.split("unit = ", 1)[-1][:80] and "momento-demo@" not in script:
        raise VitalError("REJECTED", "demo stop script refused")
    if "systemctl stop momento-live.service" in script:
        raise VitalError("REJECTED", "demo stop refuses momento-live.service")
    result = _ssm_run([script], f"Vital demo stop {bot_id}", timeout=25)
    return {
        "ok": bool(result.get("ok") and result.get("stopped")),
        "stopped": bool(result.get("stopped") or result.get("ok")),
        "active": result.get("active"),
        "unit": result.get("unit") or demo_unit_name(bot_id),
        "reason": result.get("reason"),
        "source": result.get("source") or "ssm",
        "never_momento_live": True,
    }


def _start(bot: dict[str, Any]) -> dict[str, Any]:
    from roller.jump.bots.demo_host import start_iti_demo_unit
    from roller.jump.errors import JumpError

    if str(bot.get("bot_id") or "") == RESERVED_LIVE:
        raise VitalError("REJECTED", "mlb-001 factory unit is not a demo start target")
    try:
        started = start_iti_demo_unit(bot)
    except JumpError as exc:
        raise VitalError("DEPLOY_REQUIRED", str(exc)) from exc
    unit = str(started.get("unit") or started.get("aws_runtime_id") or "")
    if SERVICE_NAME in unit:
        raise VitalError("REJECTED", "demo start refused a factory unit result")
    return started


def run_demo_lifecycle(
    bot: dict[str, Any],
    body: dict[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """inspect → stop → inspect → start → inspect. Demo units only."""
    body = body or {}
    if str(body.get("confirmation") or "").strip() == LIVE_CONFIRMATION:
        raise VitalError("REJECTED", "ENABLE_LIVE_TRADING is not a demo lifecycle token")
    if not control_enabled():
        raise VitalError("CONTROL_DISABLED", "demo lifecycle writes require VITAL_AWS_CONTROL=1")
    if not confirmation_ok(body):
        raise VitalError("REJECTED", "demo lifecycle requires confirmation=VITAL_ENABLE_CONTROL")
    bot_id = _safe_demo_id(str(bot.get("bot_id") or ""))
    if str(bot.get("environment") or "DEMO").upper() != "DEMO":
        raise VitalError("REJECTED", "demo lifecycle refuses a production ITI unit")
    unit = demo_unit_name(bot_id)
    steps: list[dict[str, Any]] = []

    first = _inspect(bot_id, refresh=True)
    steps.append(
        {
            "action": "inspect",
            "lifecycle": _lifecycle_from_inspect(first),
            "ok": bool(first.get("ok")),
            "active": first.get("active"),
            "heartbeat": first.get("heartbeat"),
            "unit": first.get("unit"),
            "command": None,
            "observed": {"active": first.get("active"), "heartbeat": first.get("heartbeat")},
        }
    )
    stopped = _stop(bot_id)
    steps.append(
        {
            "action": "stop",
            "ok": bool(stopped.get("ok")),
            "unit": stopped.get("unit"),
            "command": {"kind": "systemctl stop", "unit": stopped.get("unit"), "never_momento_live": True},
            "observed": {"stopped": stopped.get("stopped"), "active": stopped.get("active")},
        }
    )
    mid = _inspect(bot_id, refresh=True)
    steps.append(
        {
            "action": "inspect",
            "lifecycle": _lifecycle_from_inspect(mid),
            "ok": bool(mid.get("ok")),
            "active": mid.get("active"),
            "heartbeat": mid.get("heartbeat"),
            "unit": mid.get("unit"),
            "command": None,
            "observed": {"active": mid.get("active"), "heartbeat": mid.get("heartbeat")},
        }
    )
    started = _start(bot)
    steps.append(
        {
            "action": "start",
            "ok": bool(started.get("ok") or started.get("active")),
            "unit": started.get("unit") or started.get("aws_runtime_id"),
            "command": {"kind": "systemctl enable --now", "unit": started.get("unit"), "never_momento_live": True},
            "observed": {"active": started.get("active"), "heartbeat": started.get("heartbeat")},
        }
    )
    last = _inspect(bot_id, refresh=True)
    steps.append(
        {
            "action": "inspect",
            "lifecycle": _lifecycle_from_inspect(last),
            "ok": bool(last.get("ok")),
            "active": last.get("active"),
            "heartbeat": last.get("heartbeat"),
            "unit": last.get("unit"),
            "command": None,
            "observed": {"active": last.get("active"), "heartbeat": last.get("heartbeat")},
        }
    )

    observed_stop = steps[2].get("lifecycle") == "STOPPED"
    observed_run = steps[4].get("lifecycle") == "RUNNING_DEMO"
    ok = bool(stopped.get("ok") and (started.get("ok") or started.get("active")) and observed_stop and observed_run)
    proof = {
        "ok": ok,
        "status": "CONFIRMED" if ok else "OBSERVATION_UNAVAILABLE",
        "bot_id": bot_id,
        "unit": unit,
        "never_momento_live": True,
        "http_200_not_running": True,
        "steps": steps,
        "lifecycle": "CONFIRMED" if ok else "OBSERVATION_UNAVAILABLE",
        "observed_at": utc_now(),
    }
    persist_demo_control_proof(proof, root=root)
    append_event(bot_id, {"kind": "demo_lifecycle", "ok": ok, "unit": unit}, root=root)
    return proof
