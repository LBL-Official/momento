"""Auditable host control. Fail-closed. HTTP 200 is not RUNNING."""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from roller.vital.aws import WRITE_FORBIDDEN, clear_ssm_cache, instance_id, region
from roller.vital.errors import VitalError
from roller.vital.models import resolve_bot_id, utc_now
from roller.vital.observe import observe_bot
from roller.vital.store import append_event, commands_root, write_json
from roller.vital.versions import (
    BOT_ID,
    CONTROL_ACTIONS,
    CONTROL_CONFIRMATION,
    HOST_KILL,
    LIVE_CONFIRMATION,
    SERVICE_NAME,
)

CONTROL_ENV = "VITAL_AWS_CONTROL"
CONFIRM_ENV = "VITAL_ENABLE_CONTROL"
DISPATCH_ENV = "VITAL_AWS_CONTROL_DISPATCH"
CONTROL_RUNNER_ENV = "VITAL_AWS_CONTROL_RUNNER"

DESIRED_FOR = {
    "deploy": "DEPLOYED",
    "start": "RUNNING",
    "stop": "STOPPED",
    "restart": "RUNNING",
    "kill": "KILLED",
}

HOST_EFFECT = {
    "start": f"systemctl start {SERVICE_NAME}",
    "stop": f"systemctl stop {SERVICE_NAME}",
    "restart": f"systemctl restart {SERVICE_NAME}",
    "kill": f"install -m 644 /dev/null {HOST_KILL}",
    "deploy": "record desired fingerprint; no silent binary replace",
}


def control_enabled() -> bool:
    raw = (os.environ.get(CONTROL_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes"}


def dispatch_mode() -> str:
    raw = (os.environ.get(DISPATCH_ENV) or "").strip().lower()
    if raw in {"mock"}:
        return "mock"
    if raw in {"ssm", "1", "true", "yes"}:
        return "ssm"
    return "ssm" if control_enabled() else "mock"


def confirmation_ok(body: dict[str, Any] | None) -> bool:
    token = str((body or {}).get("confirmation") or "").strip()
    if token == LIVE_CONFIRMATION:
        return False
    expected = (os.environ.get(CONFIRM_ENV) or CONTROL_CONFIRMATION).strip()
    return token == expected and token == CONTROL_CONFIRMATION


def _command_path(command_id: str, *, root: Path | None = None) -> Path:
    return commands_root(root=root) / f"{command_id}.json"


def persist_command(command: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    write_json(_command_path(str(command["command_id"]), root=root), command)
    return command


def _dispatch_script(action: str) -> str:
    if action == "start":
        return f"systemctl start {SERVICE_NAME}"
    if action == "stop":
        return f"systemctl stop {SERVICE_NAME}"
    if action == "restart":
        return f"systemctl restart {SERVICE_NAME}"
    if action == "kill":
        return f"install -m 644 /dev/null {HOST_KILL}"
    if action == "deploy":
        return "true"
    raise VitalError("REJECTED", f"unknown action: {action}")


def _mock_dispatch(action: str) -> dict[str, Any]:
    return {"ok": True, "mode": "mock", "action": action, "dispatched": True}


def _parse_json_blob(blob: str) -> dict[str, Any] | None:
    text = (blob or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _run_aws(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["aws", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _ssm_control_run(script: str, action: str) -> dict[str, Any]:
    if script != _dispatch_script(action):
        return {"ok": False, "mode": "ssm", "action": action, "dispatched": False, "reason": "dispatch script mismatch"}
    if action == "kill" and ("systemctl stop" in script or "systemctl kill" in script):
        return {"ok": False, "mode": "ssm", "action": action, "dispatched": False, "reason": "kill must not flatten"}
    ident = instance_id()
    if not ident.startswith("i-"):
        return {"ok": False, "mode": "ssm", "action": action, "dispatched": False, "reason": "instance id invalid"}
    runner = (os.environ.get(CONTROL_RUNNER_ENV) or "").strip()
    if runner:
        sent = subprocess.run(
            [runner, ident, region(), script],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        parsed = _parse_json_blob(sent.stdout)
        if sent.returncode != 0 or parsed is None:
            return {
                "ok": False,
                "mode": "ssm",
                "action": action,
                "dispatched": False,
                "reason": (parsed or {}).get("reason") or "control runner unreadable",
            }
        return {
            "ok": bool(parsed.get("ok", True)),
            "mode": "ssm",
            "action": action,
            "dispatched": bool(parsed.get("ok", True)),
            "script": script,
            "reason": parsed.get("reason"),
        }
    send = _run_aws(
        [
            "ssm",
            "send-command",
            "--instance-ids",
            ident,
            "--document-name",
            "AWS-RunShellScript",
            "--comment",
            f"Vital control {action} {SERVICE_NAME}",
            "--parameters",
            json.dumps({"commands": [script]}),
            "--region",
            region(),
            "--output",
            "json",
        ],
        timeout=20,
    )
    if send.returncode != 0:
        err = (send.stderr or send.stdout or "")[:240]
        return {
            "ok": False,
            "mode": "ssm",
            "action": action,
            "dispatched": False,
            "reason": err or "ssm send-command failed",
        }
    try:
        sent = json.loads(send.stdout)
        command_id = sent["Command"]["CommandId"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return {
            "ok": False,
            "mode": "ssm",
            "action": action,
            "dispatched": False,
            "reason": "ssm send-command unreadable",
        }
    for _ in range(20):
        time.sleep(1.0)
        inv = _run_aws(
            [
                "ssm",
                "get-command-invocation",
                "--command-id",
                str(command_id),
                "--instance-id",
                ident,
                "--region",
                region(),
                "--output",
                "json",
            ],
            timeout=15,
        )
        if inv.returncode != 0:
            continue
        try:
            body = json.loads(inv.stdout)
        except json.JSONDecodeError:
            continue
        status = str(body.get("Status") or "")
        if status in {"Pending", "InProgress", "Delayed"}:
            continue
        if status != "Success":
            err = str(body.get("StandardErrorContent") or "")[:240]
            return {
                "ok": False,
                "mode": "ssm",
                "action": action,
                "dispatched": False,
                "command_id": str(command_id),
                "reason": err or f"ssm invocation {status or 'failed'}",
            }
        return {
            "ok": True,
            "mode": "ssm",
            "action": action,
            "dispatched": True,
            "command_id": str(command_id),
            "script": script,
        }
    return {
        "ok": False,
        "mode": "ssm",
        "action": action,
        "dispatched": False,
        "reason": "ssm invocation timeout",
    }


def _confirm_after_dispatch(
    command: dict[str, Any],
    action: str,
    *,
    root: Path | None,
) -> dict[str, Any]:
    clear_ssm_cache()
    persist_command(command, root=root)
    observed = observe_bot(command["bot_id"], root=root, persist=True, refresh=True)
    confirmed = observed["runtime"]["confirmed"]
    lifecycle = observed["runtime"]["lifecycle"]
    if (
        isinstance(confirmed.get("lifecycle"), dict)
        and confirmed["lifecycle"].get("status") == "CONFIRMED"
        and confirmed["lifecycle"].get("value") == DESIRED_FOR[action]
    ):
        command["command_status"] = "CONFIRMED"
        command.pop("detail", None)
    else:
        command["command_status"] = "CONFIRMING"
        command["detail"] = "dispatch acknowledged; independent observe has not confirmed desired state"
    command["confirmed_runtime"] = confirmed
    command["lifecycle_after"] = lifecycle
    persist_command(command, root=root)
    append_event(
        command["bot_id"],
        {
            "kind": "command",
            **{k: command[k] for k in ("command_id", "action", "command_status", "desired_state")},
        },
        root=root,
    )
    return command


def submit_command(
    bot_id: str,
    body: dict[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    resolved = resolve_bot_id(bot_id)
    if resolved != BOT_ID:
        raise VitalError("BOT_NOT_FOUND", f"control is implemented for {BOT_ID} only")
    body = body or {}
    action = str(body.get("action") or "").strip().lower()
    if action not in CONTROL_ACTIONS:
        raise VitalError("REJECTED", f"action must be one of {', '.join(CONTROL_ACTIONS)}")
    if action != "kill":
        script = _dispatch_script(action)
        if action in {"start", "stop", "restart"} and not WRITE_FORBIDDEN.search(script):
            # start/stop/restart are write verbs; they are allowed only in the control layer.
            pass
    else:
        script = _dispatch_script("kill")
        if "systemctl stop" in script or "systemctl kill" in script:
            raise VitalError("REJECTED", "kill must not flatten or stop systemd")

    command = {
        "command_id": uuid.uuid4().hex,
        "bot_id": resolved,
        "action": action,
        "requested_at": utc_now(),
        "desired_state": DESIRED_FOR[action],
        "command_status": "ACCEPTED",
        "target_unit": SERVICE_NAME,
        "instance_id": instance_id(),
        "region": region(),
        "start_is_not_live_arm": True,
        "kill_is_not_stop": action == "kill",
        "http_200_not_running": True,
        "live_confirmation_rejected": str(body.get("confirmation") or "") == LIVE_CONFIRMATION,
        "host_effect": HOST_EFFECT[action],
    }

    if str(body.get("confirmation") or "") == LIVE_CONFIRMATION:
        command["command_status"] = "REJECTED"
        command["detail"] = "ENABLE_LIVE_TRADING is the engine live gate, not a Vital control token"
        persist_command(command, root=root)
        append_event(resolved, {"kind": "command", **command}, root=root)
        return command

    if not control_enabled() or not confirmation_ok(body):
        command["command_status"] = "CONTROL_DISABLED"
        command["detail"] = (
            "production writes require VITAL_AWS_CONTROL=1 and confirmation="
            f"{CONTROL_CONFIRMATION}; this session does not mutate the live host"
        )
        persist_command(command, root=root)
        append_event(resolved, {"kind": "command", **command}, root=root)
        observed = observe_bot(resolved, root=root, persist=True)
        command["confirmed_runtime"] = observed["runtime"]["confirmed"]
        command["lifecycle_after"] = observed["runtime"]["lifecycle"]
        return command

    mode = dispatch_mode()
    command["dispatch_mode"] = mode
    if mode == "mock":
        command["command_status"] = "DISPATCHED"
        command["dispatch"] = _mock_dispatch(action)
        return _confirm_after_dispatch(command, action, root=root)

    if WRITE_FORBIDDEN.search(script) is None and action in {"start", "stop", "restart", "kill"}:
        # Control layer is the only place allowed to contain these write verbs.
        pass
    dispatched = _ssm_control_run(script, action)
    command["dispatch"] = dispatched
    if not dispatched.get("ok"):
        command["command_status"] = "FAILED"
        command["detail"] = str(dispatched.get("reason") or "ssm dispatch failed")
        persist_command(command, root=root)
        append_event(
            resolved,
            {"kind": "command", **{k: command[k] for k in ("command_id", "action", "command_status", "desired_state")}},
            root=root,
        )
        observed = observe_bot(resolved, root=root, persist=True, refresh=True)
        command["confirmed_runtime"] = observed["runtime"]["confirmed"]
        command["lifecycle_after"] = observed["runtime"]["lifecycle"]
        persist_command(command, root=root)
        return command
    command["command_status"] = "DISPATCHED"
    return _confirm_after_dispatch(command, action, root=root)
