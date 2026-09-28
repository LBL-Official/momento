"""Read-only SSM observe of momento-nba-001.service. No submit. No control.

RUNNING != HEALTHY != EXECUTING. Unread is OBSERVATION_UNAVAILABLE, never $0.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import threading
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.ls.host import WRITE_FORBIDDEN, instance_id, region

SERVICE = "momento-nba-001.service"
BINARY = "/usr/local/bin/momento-nba-001"
STATE_DIR = "/var/lib/momento/nba-001"
FIXTURE_ENV = "MOMENTO_NBA001_INSPECT_FIXTURE"
DISABLE_ENV = "MOMENTO_NBA001_OBSERVE"
CACHE_S = 20.0
HEARTBEAT_FRESH_S = 90

INSPECT_SHELL = r"""
set +e
python3 - <<'NBA001_INSPECT_PY'
import base64, hashlib, json, subprocess, zlib
from pathlib import Path

def run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""

def sha(path):
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None

props = {}
for line in run(["systemctl", "show", "momento-nba-001.service", "--no-pager",
                 "-p", "ActiveState,SubState,MainPID,NRestarts,ActiveEnterTimestamp,MemoryCurrent,MemoryMax,ExecMainStatus,LoadState"]).splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        props[k] = v
status_path = Path("/var/lib/momento/nba-001/status.json")
status_blob = None
if status_path.is_file():
    status_blob = base64.b64encode(zlib.compress(status_path.read_bytes(), 9)).decode()
journal = Path("/var/lib/momento/nba-001/journal.jsonl")
tail = []
if journal.is_file():
    with journal.open("rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        fh.seek(max(0, size - 12000))
        tail = fh.read().decode("utf-8", "replace").splitlines()[-25:]
tail_blob = base64.b64encode(zlib.compress("\n".join(tail).encode(), 9)).decode()
print(json.dumps({
    "ok": True,
    "unit": props,
    "unit_file_exists": Path("/etc/systemd/system/momento-nba-001.service").is_file(),
    "binary_sha256": sha("/usr/local/bin/momento-nba-001"),
    "config_sha256": sha("/etc/momento/nba-001.toml"),
    "contract_sha256": sha("/etc/momento/nba-001/execution_contract.json"),
    "status_z": status_blob,
    "journal_tail_z": tail_blob,
    "momento_live_active": run(["systemctl", "is-active", "momento-live.service"]),
    "host_mem_available_kb": next((int(l.split()[1]) for l in Path("/proc/meminfo").read_text().splitlines() if l.startswith("MemAvailable")), None),
}))
NBA001_INSPECT_PY
"""

_lock = threading.Lock()
_cache: dict[str, Any] = {"at": 0.0, "value": None}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def unread(reason: str) -> dict[str, Any]:
    return {"ok": False, "status": "OBSERVATION_UNAVAILABLE", "reason": reason, "observed_at": _now()}


def inspect_script() -> str:
    if WRITE_FORBIDDEN.search(INSPECT_SHELL):
        raise PermissionError("nba-001 inspect refuses host-mutating commands")
    return INSPECT_SHELL


def _aws(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["aws", *args], check=False, capture_output=True, text=True, timeout=timeout)


def _ssm_inspect() -> dict[str, Any]:
    ident = instance_id()
    if not ident.startswith("i-"):
        return unread("instance id invalid")
    try:
        send = _aws(
            [
                "ssm", "send-command", "--instance-ids", ident,
                "--document-name", "AWS-RunShellScript",
                "--comment", "nba-001 read-only status observe",
                "--parameters", json.dumps({"commands": [inspect_script()]}),
                "--region", region(), "--output", "json",
            ],
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return unread("aws cli unavailable")
    if send.returncode != 0:
        return unread("ssm send-command failed")
    try:
        command_id = json.loads(send.stdout)["Command"]["CommandId"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return unread("ssm send-command unreadable")
    for _ in range(16):
        time.sleep(1.0)
        try:
            inv = _aws(
                ["ssm", "get-command-invocation", "--command-id", str(command_id),
                 "--instance-id", ident, "--region", region(), "--output", "json"],
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            continue
        if inv.returncode != 0:
            continue
        try:
            body = json.loads(inv.stdout)
        except json.JSONDecodeError:
            continue
        state = str(body.get("Status") or "")
        if state in {"Pending", "InProgress", "Delayed"}:
            continue
        if state != "Success":
            return unread(f"ssm invocation {state or 'failed'}")
        try:
            parsed = json.loads(str(body.get("StandardOutputContent") or "").strip())
        except json.JSONDecodeError:
            return unread("ssm inspect unreadable")
        return parsed if isinstance(parsed, dict) else unread("ssm inspect invalid")
    return unread("ssm inspect timeout")


def _unz(blob: Any) -> str | None:
    if not isinstance(blob, str) or not blob:
        return None
    try:
        return zlib.decompress(base64.b64decode(blob)).decode("utf-8", "replace")
    except (ValueError, zlib.error):
        return None


def raw_inspect(*, refresh: bool = False) -> dict[str, Any]:
    fixture = (os.environ.get(FIXTURE_ENV) or "").strip()
    if fixture:
        try:
            value = json.loads(Path(fixture).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return unread("inspect fixture unreadable")
        return value if isinstance(value, dict) else unread("inspect fixture invalid")
    if (os.environ.get(DISABLE_ENV) or "").strip().lower() == "off":
        return unread("observe disabled")
    with _lock:
        if not refresh and _cache["value"] is not None and time.time() - _cache["at"] < CACHE_S:
            return _cache["value"]
        value = _ssm_inspect()
        _cache.update(at=time.time(), value=value)
        return value


def observe(*, refresh: bool = False) -> dict[str, Any]:
    raw = raw_inspect(refresh=refresh)
    if not raw.get("ok"):
        return {
            "runtime": "OBSERVATION_UNAVAILABLE",
            "reason": raw.get("reason"),
            "observed_at": raw.get("observed_at") or _now(),
            "heartbeat": "UNAVAILABLE",
            "running": "UNAVAILABLE",
            "healthy": "UNAVAILABLE",
            "executing": False,
            "status": None,
        }
    unit = raw.get("unit") if isinstance(raw.get("unit"), dict) else {}
    if not raw.get("unit_file_exists") or unit.get("LoadState") == "not-found":
        return {
            "runtime": "NOT_DEPLOYED",
            "observed_at": _now(),
            "heartbeat": "UNAVAILABLE",
            "running": False,
            "healthy": False,
            "executing": False,
            "status": None,
            "momento_live_active": raw.get("momento_live_active"),
        }
    status: dict[str, Any] | None = None
    text = _unz(raw.get("status_z"))
    if text:
        try:
            parsed = json.loads(text)
            status = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            status = None
    journal_tail = []
    for line in (_unz(raw.get("journal_tail_z")) or "").splitlines():
        try:
            journal_tail.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    running = unit.get("ActiveState") == "active" and unit.get("SubState") == "running"
    heartbeat_at = status.get("heartbeat_at") if status else None
    age = int(time.time()) - int(heartbeat_at) if isinstance(heartbeat_at, int) else None
    fresh = age is not None and age <= HEARTBEAT_FRESH_S
    binary_match = bool(status) and status.get("binary_sha256") == raw.get("binary_sha256")
    return {
        "runtime": "DEPLOYED",
        "observed_at": _now(),
        "service": SERVICE,
        "unit": unit,
        "running": running,
        "heartbeat_at": heartbeat_at,
        "heartbeat_age_s": age,
        "heartbeat": "FRESH" if fresh else ("STALE" if age is not None else "UNAVAILABLE"),
        "healthy": bool(running and fresh and binary_match),
        "binary_sha256_on_disk": raw.get("binary_sha256"),
        "binary_matches_process": binary_match,
        "config_sha256": raw.get("config_sha256"),
        "contract_sha256_on_disk": raw.get("contract_sha256"),
        "executing": False,
        "momento_live_active": raw.get("momento_live_active"),
        "host_mem_available_kb": raw.get("host_mem_available_kb"),
        "status": status,
        "journal_tail": journal_tail,
    }
