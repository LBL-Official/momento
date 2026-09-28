"""Read-only Bot One state. No Kalshi credentials. No order submit."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

STATE_DIR_ENV = "JUMP_BOT_ONE_STATE_DIR"
RUNTIME_PATH_ENV = "JUMP_BOT_ONE_RUNTIME_PATH"
SNAPSHOT_PATH_ENV = "JUMP_BOT_ONE_SNAPSHOT_PATH"
HOST_FETCH_ENV = "JUMP_BOT_ONE_HOST_FETCH"
INSTANCE_ENV = "JUMP_BOT_ONE_INSTANCE_ID"
AWS_REGION_ENV = "JUMP_BOT_ONE_AWS_REGION"

DEFAULT_INSTANCE_ID = "i-0f0849d5829476c31"
DEFAULT_REGION = "us-east-1"
HOST_RUNTIME = "/var/lib/momento/state/live-runtime.json"
HOST_SNAPSHOT = "/var/lib/momento/state/weekly-snapshot.json"
_SSM_TTL_S = 60.0
_SSM_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}

_LEDGER_MODULE = Path(__file__).with_name("ledger.py")


def host_fetch_enabled() -> bool:
    raw = (os.environ.get(HOST_FETCH_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes", "ssm"}


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _runtime_path() -> Path | None:
    explicit = (os.environ.get(RUNTIME_PATH_ENV) or "").strip()
    if explicit:
        return Path(explicit)
    root = (os.environ.get(STATE_DIR_ENV) or "").strip()
    if root:
        return Path(root) / "live-runtime.json"
    return None


def _snapshot_path() -> Path | None:
    explicit = (os.environ.get(SNAPSHOT_PATH_ENV) or "").strip()
    if explicit:
        return Path(explicit)
    root = (os.environ.get(STATE_DIR_ENV) or "").strip()
    if root:
        return Path(root) / "weekly-snapshot.json"
    return None


def load_local_host_state() -> dict[str, Any]:
    runtime_path = _runtime_path()
    if runtime_path is None:
        return {"ok": False, "reason": "host state path unset"}
    runtime = _read_json_file(runtime_path)
    if runtime is None:
        return {"ok": False, "reason": "live-runtime.json unreadable", "source": "local_path"}
    snapshot_path = _snapshot_path()
    snapshot = _read_json_file(snapshot_path) if snapshot_path is not None else None
    return {
        "ok": True,
        "runtime": runtime,
        "snapshot": snapshot,
        "source": "local_path",
    }


def _ssm_instance() -> str:
    return (os.environ.get(INSTANCE_ENV) or DEFAULT_INSTANCE_ID).strip()


def _ssm_region() -> str:
    return (
        (os.environ.get(AWS_REGION_ENV) or "").strip()
        or (os.environ.get("AWS_REGION") or "").strip()
        or (os.environ.get("AWS_DEFAULT_REGION") or "").strip()
        or DEFAULT_REGION
    )


def _run_aws(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["aws", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _parse_ssm_summary(blob: str) -> dict[str, Any] | None:
    text = (blob or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def fetch_ssm_ledger() -> dict[str, Any]:
    now = time.monotonic()
    cached = _SSM_CACHE.get("payload")
    if isinstance(cached, dict) and now - float(_SSM_CACHE.get("at") or 0) < _SSM_TTL_S:
        return cached
    instance = _ssm_instance()
    if not instance.startswith("i-"):
        return {"ok": False, "reason": "instance id invalid", "source": "ssm"}
    try:
        script = _LEDGER_MODULE.read_text(encoding="utf-8")
    except OSError:
        return {"ok": False, "reason": "ledger.py unreadable", "source": "ssm"}
    command = (
        "python3 - "
        f"{HOST_RUNTIME} {HOST_SNAPSHOT} "
        "<<'JUMP_LEDGER_PY'\n"
        f"{script}\n"
        "JUMP_LEDGER_PY"
    )
    send = _run_aws(
        [
            "ssm",
            "send-command",
            "--instance-ids",
            instance,
            "--document-name",
            "AWS-RunShellScript",
            "--comment",
            "Jump C read-only Bot One MLB ledger summary",
            "--parameters",
            json.dumps({"commands": [command]}),
            "--region",
            _ssm_region(),
            "--output",
            "json",
        ],
        timeout=20,
    )
    if send.returncode != 0:
        return {"ok": False, "reason": "ssm send-command failed", "source": "ssm"}
    try:
        sent = json.loads(send.stdout)
        command_id = sent["Command"]["CommandId"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return {"ok": False, "reason": "ssm send-command unreadable", "source": "ssm"}
    stdout = ""
    for _ in range(12):
        time.sleep(1.0)
        inv = _run_aws(
            [
                "ssm",
                "get-command-invocation",
                "--command-id",
                str(command_id),
                "--instance-id",
                instance,
                "--region",
                _ssm_region(),
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
            return {"ok": False, "reason": f"ssm invocation {status or 'failed'}", "source": "ssm"}
        stdout = str(body.get("StandardOutputContent") or "")
        break
    parsed = _parse_ssm_summary(stdout)
    if parsed is None or not parsed.get("ok"):
        return {
            "ok": False,
            "reason": (parsed or {}).get("reason") or "ssm ledger summary unreadable",
            "source": "ssm",
        }
    payload = {
        "ok": True,
        "fields": parsed.get("fields") or {},
        "trades": parsed.get("trades") if isinstance(parsed.get("trades"), list) else [],
        "source": "ssm",
        "aws_runtime_id": instance,
        "week_start": parsed.get("week_start"),
        "formula": parsed.get("formula"),
    }
    _SSM_CACHE["at"] = time.monotonic()
    _SSM_CACHE["payload"] = payload
    return payload


def load_host_state() -> dict[str, Any]:
    """Local ledger only. Production Bot One SSM is Vital-owned (Phase 8)."""
    local = load_local_host_state()
    if local.get("ok"):
        return local
    packed = dict(local)
    packed["ssm_skipped"] = True
    packed["reason"] = local.get("reason") or "Jump no longer owns Bot One SSM"
    return packed
