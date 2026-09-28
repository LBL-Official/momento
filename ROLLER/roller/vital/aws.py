"""Read-only AWS / host inspect. Phase 4. No start/stop/restart/kill."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.jump.dashboard.ledger import summarize_mlb_ledger
from roller.vital.honesty import confirmed, observation_unavailable
from roller.vital.versions import (
    DOCUMENTED_INSTANCE_ID,
    DOCUMENTED_REGION,
    SERVICE_NAME,
)

HOST_FETCH_ENV = "VITAL_AWS_HOST_FETCH"
INSTANCE_ENV = "VITAL_AWS_INSTANCE_ID"
REGION_ENV = "VITAL_AWS_REGION"
STATE_DIR_ENV = "VITAL_BOT_STATE_DIR"
RUNTIME_PATH_ENV = "VITAL_BOT_RUNTIME_PATH"
SNAPSHOT_PATH_ENV = "VITAL_BOT_SNAPSHOT_PATH"
INSPECT_FIXTURE_ENV = "VITAL_AWS_INSPECT_FIXTURE"
SSM_RUNNER_ENV = "VITAL_AWS_SSM_RUNNER"

WRITE_FORBIDDEN = re.compile(
    r"systemctl\s+(start|stop|restart|kill|enable|disable)|"
    r"(?:^|[\s;|&])(?:kill|pkill|killall)\s|"
    r"(?:touch|install|tee|echo|printf)\b[^\n]*state/KILL|"
    r"(?:>|>>)\s*/var/lib/momento",
    re.IGNORECASE,
)

_SSM_TTL_S = 60.0
_SSM_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}

INSPECT_SHELL = r"""
set +e
python3 - <<'VITAL_INSPECT_PY'
import hashlib, json, os, subprocess
from pathlib import Path

def run(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=8)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except Exception as exc:
        return 1, "", str(exc)

service = "momento-live.service"
binary = "/usr/local/bin/momento-trading-engine"
config = "/var/lib/momento/config/live.toml"
runtime = "/var/lib/momento/state/live-runtime.json"
snapshot = "/var/lib/momento/state/weekly-snapshot.json"
kill_path = "/var/lib/momento/state/KILL"

rc_active, active, _ = run(["systemctl", "is-active", service])
_, show, _ = run([
    "systemctl", "show", service,
    "--property=Id,ActiveState,SubState,MainPID,FragmentPath,ExecMainStartTimestamp,ExecMainStartTimestampMonotonic,WorkingDirectory,NRestarts,ExecStart,Environment",
    "--no-pager",
])
props = {}
env_names = []
kalshi_env = None
for line in show.splitlines():
    if "=" not in line:
        continue
    key, value = line.split("=", 1)
    if key == "Environment":
        for part in value.split():
            name = part.split("=", 1)[0]
            if name:
                env_names.append(name)
            if part.startswith("MOMENTO_KALSHI_ENV="):
                raw_env = part.split("=", 1)[1].strip().lower()
                if raw_env in {"production", "demo", "paper", "sandbox"}:
                    kalshi_env = raw_env
        continue
    props[key] = value

version = None
if Path(binary).is_file():
    version = hashlib.sha256(Path(binary).read_bytes()).hexdigest()

_, journal, _ = run(["journalctl", "-u", service, "-n", "40", "--no-pager", "-o", "cat"])
redacted = []
for line in (journal or "").splitlines():
    if any(token in line.lower() for token in ("secret", "private_key", "api_key", "password")):
        redacted.append("[redacted]")
    else:
        redacted.append(line[:400])

def _read_json(path):
    p = Path(path)
    if not p.is_file():
        return None
    try:
        payload = json.loads(p.read_text())
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None

def _kill_tripped(risk, kill_path):
    if Path(kill_path).is_file():
        return True
    raw = risk.get("kill_switch") if isinstance(risk, dict) else None
    if raw is True:
        return True
    if raw in (False, None, ""):
        return False
    if isinstance(raw, dict):
        if "Tripped" in raw or raw.get("tripped") is True:
            return True
        if "Armed" in raw or raw.get("armed") is True:
            return False
    text = str(raw).strip().lower()
    if text in {"tripped", "true", "1", "yes"}:
        return True
    if text in {"armed", "false", "0", "no", "not_tripped"}:
        return False
    return False

def _open_mlb(runtime):
    tracker = runtime.get("tracker") if isinstance(runtime.get("tracker"), dict) else {}
    positions = tracker.get("positions")
    if not isinstance(positions, list):
        return None
    open_n = 0
    for pos in positions:
        if not isinstance(pos, dict):
            continue
        life = str(pos.get("lifecycle") or "")
        if life in {"Flat", "Settled"}:
            continue
        qty = pos.get("filled_quantity")
        if isinstance(qty, dict):
            qty = qty.get("qty")
        if qty in (0, None, ""):
            continue
        sid = pos.get("strategy_id")
        if isinstance(sid, dict):
            sid = sid.get("0")
        if sid in (None, 1, "1"):
            open_n += 1
    return open_n

runtime_obj = _read_json(runtime)
snapshot_obj = _read_json(snapshot)
config_text = Path(config).read_text() if Path(config).is_file() else ""
gates_armed = (
    'mode = "live"' in config_text
    and "enabled = true" in config_text
    and "ENABLE_LIVE_TRADING" in config_text
    and 'strategy_profile = "research_iti"' not in config_text
)
risk = runtime_obj.get("risk") if isinstance(runtime_obj, dict) and isinstance(runtime_obj.get("risk"), dict) else {}
tracker = runtime_obj.get("tracker") if isinstance(runtime_obj, dict) and isinstance(runtime_obj.get("tracker"), dict) else {}
ledger = {"ok": False, "reason": "runtime missing"}

def _hb_kv(journal, key):
    last = None
    n = 0
    for line in (journal or "").splitlines():
        if line.startswith("momento heartbeat "):
            last = line
            n += 1
    if key == "_count":
        return n
    if not last:
        return None
    token = key + "="
    for part in last.split():
        if part.startswith(token):
            return part.split("=", 1)[1]
    return None


pid = int(props["MainPID"]) if str(props.get("MainPID") or "").isdigit() else None
exe = None
cwd = None
cmdline = None
if pid:
    try:
        exe = os.readlink(f"/proc/{pid}/exe").replace(" (deleted)", "")
    except OSError:
        exe = None
    try:
        cwd = os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        cwd = None
    try:
        cmdline = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\x00", b" ").decode("utf-8", "replace").strip()[:400]
    except OSError:
        cmdline = None

def _int_or_none(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None

def _activity(started_at):
    args = ["journalctl", "-u", service, "--no-pager", "-o", "cat"]
    if started_at:
        args.extend(["--since", started_at])
    else:
        args.extend(["-n", "2000"])
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=20)
    except Exception:
        return None
    if p.returncode != 0 and not (p.stdout or "").strip():
        return None
    text = p.stdout or ""
    last_ticker = last_bid = last_ask = None
    yes_n = 0
    for line in text.splitlines():
        if "yes_bid_update ticker=KXMLBGAME" not in line:
            continue
        yes_n += 1
        ticker = bid = ask = None
        for part in line.split():
            if part.startswith("ticker="):
                raw = part.split("=", 1)[1]
                if raw.startswith("KXMLBGAME"):
                    ticker = raw
            elif part.startswith("bid="):
                bid = _int_or_none(part.split("=", 1)[1])
            elif part.startswith("ask="):
                ask = _int_or_none(part.split("=", 1)[1])
        if ticker:
            last_ticker, last_bid, last_ask = ticker, bid, ask
    return {
        "ok": True,
        "journal_since": started_at or "last_2000",
        "mlb_yes_bid_n": yes_n,
        "first80_n": text.count("First80Observed"),
        "first81_n": text.count("First81Confirmed"),
        "submit_to_ack_n": text.count("submit_to_ack"),
        "submit_refused_n": text.count("submit_refused"),
        "last_mlb_ticker": last_ticker,
        "last_mlb_bid_cents": last_bid,
        "last_mlb_ask_cents": last_ask,
    }

activity = _activity(props.get("ExecMainStartTimestamp") or None)

if runtime_obj is not None:
    open_n = _open_mlb(runtime_obj)
    reservations = risk.get("reservations")
    unknown = runtime_obj.get("unknown_submissions")
    recon = tracker.get("recon") or _hb_kv(journal, "reconciliation")
    open_slots = _int_or_none(_hb_kv(journal, "open_slots"))
    unknown_n = len(unknown) if isinstance(unknown, list) else _int_or_none(_hb_kv(journal, "unknown_orders"))
    ledger = {
        "ok": True,
        "reason": None if open_n is not None else "positions unreadable",
        "kill_switch": _kill_tripped(risk, kill_path),
        "live_armed": gates_armed,
        "live_armed_confirmed": gates_armed,
        "open_mlb_positions": open_n,
        "bankroll_cents": (snapshot_obj or {}).get("bankroll", {}).get("cents") if isinstance((snapshot_obj or {}).get("bankroll"), dict) else None,
        "updated_at": runtime_obj.get("updated_at") or runtime_obj.get("observed_at"),
        "reconciliation": recon,
        "reservations_n": len(reservations) if isinstance(reservations, list) else None,
        "unknown_orders": unknown_n,
        "open_slots": open_slots,
        "order_submission": _hb_kv(journal, "order_submission"),
        "heartbeat_n": _hb_kv(journal, "_count"),
        "heartbeat_markets": _int_or_none(_hb_kv(journal, "markets")),
        "strategy_games": _int_or_none(_hb_kv(journal, "strategy_games")),
        "wnba_games": _int_or_none(_hb_kv(journal, "wnba_games")),
        "max_open_slots": _int_or_none(_hb_kv(journal, "max_open_slots")),
    }
    if isinstance(activity, dict) and activity.get("ok"):
        for key in (
            "mlb_yes_bid_n",
            "first80_n",
            "first81_n",
            "submit_to_ack_n",
            "submit_refused_n",
            "last_mlb_ticker",
            "last_mlb_bid_cents",
            "last_mlb_ask_cents",
            "journal_since",
        ):
            if activity.get(key) is not None:
                ledger[key] = activity.get(key)

print(json.dumps({
    "ok": True,
    "source": "ssm",
    "host": {"instance_verified": True},
    "service": {
        "name": service,
        "active": active,
        "active_state": props.get("ActiveState"),
        "sub_state": props.get("SubState"),
        "fragment": props.get("FragmentPath"),
        "started_at": props.get("ExecMainStartTimestamp") or None,
        "started_monotonic": props.get("ExecMainStartTimestampMonotonic") or None,
        "working_directory": props.get("WorkingDirectory") or None,
        "n_restarts": int(props["NRestarts"]) if str(props.get("NRestarts") or "").isdigit() else None,
        "exec_start": (props.get("ExecStart") or "")[:240] or None,
    },
    "process": {
        "main_pid": pid,
        "exe": exe,
        "cwd": cwd,
        "cmdline": cmdline,
        "expected_exe": binary,
        "exe_matches": bool(exe and (exe == binary or exe.endswith("momento-trading-engine"))),
        "cwd_matches": bool((cwd or props.get("WorkingDirectory")) == "/var/lib/momento"),
    },
    "version": {"binary_sha256": version, "binary_exists": Path(binary).is_file()},
    "environment": {
        "env_names": env_names,
        "kalshi_env_name": "MOMENTO_KALSHI_ENV",
        "kalshi_env": kalshi_env,
        "label": kalshi_env or ("production" if "MOMENTO_KALSHI_ENV" in env_names else None),
    },
    "paths": {
        "runtime_exists": Path(runtime).is_file(),
        "snapshot_exists": Path(snapshot).is_file(),
        "kill_exists": Path(kill_path).is_file(),
        "config_exists": Path(config).is_file(),
    },
    "ledger": ledger,
    "activity": activity,
    "gates": {"ok": bool(config_text), "armed": gates_armed},
    "logs": redacted[-40:],
}))
VITAL_INSPECT_PY
"""


def host_fetch_enabled() -> bool:
    """Read-only SSM inspect. Default on so Jump in-process matches terminal_api.

    Explicit 0/false/no/off disables. Control writes still require VITAL_AWS_CONTROL.
    """
    raw = (os.environ.get(HOST_FETCH_ENV) or "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "ssm"}:
        return True
    return True


def instance_id() -> str:
    return (os.environ.get(INSTANCE_ENV) or DOCUMENTED_INSTANCE_ID).strip()


def region() -> str:
    return (
        (os.environ.get(REGION_ENV) or "").strip()
        or (os.environ.get("AWS_REGION") or "").strip()
        or (os.environ.get("AWS_DEFAULT_REGION") or "").strip()
        or DOCUMENTED_REGION
    )


def assert_readonly(command: str) -> None:
    if WRITE_FORBIDDEN.search(command or ""):
        raise PermissionError("vital aws adapter refuses host-mutating commands")


def _run_aws(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["aws", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


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


def load_local_snapshot() -> dict[str, Any] | None:
    """Read-only weekly-snapshot.json. Does not invent bankroll."""
    return _read_json(_snapshot_path())


def load_local_runtime() -> dict[str, Any]:
    """Read-only live-runtime.json. Does not inspect systemd. Does not mutate."""
    path = _runtime_path()
    if path is None:
        return {
            "ok": False,
            "reason": "host state path unset",
            "source": "HOST_LEDGER",
            "snapshot": load_local_snapshot(),
        }
    runtime = _read_json(path)
    if runtime is None:
        return {
            "ok": False,
            "reason": "live-runtime.json unreadable",
            "source": "HOST_LEDGER",
            "snapshot": load_local_snapshot(),
        }
    return {
        "ok": True,
        "source": "HOST_LEDGER",
        "runtime": runtime,
        "snapshot": load_local_snapshot(),
        "path": str(path),
    }


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def unread(*, reason: str, source: str = "unread") -> dict[str, Any]:
    return {
        "ok": False,
        "source": source,
        "status": "OBSERVATION_UNAVAILABLE",
        "reason": reason,
        "host": observation_unavailable(reason),
        "service": observation_unavailable(reason),
        "process": observation_unavailable(reason),
        "version": observation_unavailable(reason),
        "environment": observation_unavailable(reason),
        "heartbeat": observation_unavailable(reason),
        "logs": [],
        "instance_id": instance_id(),
        "instance_verified": False,
        "region": region(),
    }


def _heartbeat_from_runtime(
    runtime: dict[str, Any] | None,
    snapshot: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(runtime, dict):
        return {"ok": False, "reason": "live-runtime.json unreadable"}
    clock = now or datetime.now(timezone.utc)
    summary = summarize_mlb_ledger(runtime, snapshot, clock)
    if not summary.get("ok"):
        return {"ok": False, "reason": summary.get("reason") or "ledger unreadable"}
    return {"ok": True, "fields": dict(summary.get("fields") or {})}


def _local_live_gates() -> dict[str, Any]:
    try:
        from roller.jump.library import repo_root

        text = (repo_root() / "config" / "live.toml").read_text(encoding="utf-8")
    except OSError:
        return {"ok": False, "armed": False}
    armed = (
        'mode = "live"' in text
        and "enabled = true" in text
        and "ENABLE_LIVE_TRADING" in text
        and 'strategy_profile = "research_iti"' not in text
    )
    return {"ok": True, "armed": armed}


def inspect_local(*, now: datetime | None = None) -> dict[str, Any]:
    runtime_path = _runtime_path()
    if runtime_path is None:
        return unread(reason="host state path unset", source="local_path")
    runtime = _read_json(runtime_path)
    if runtime is None:
        return unread(reason="live-runtime.json unreadable", source="local_path")
    snapshot = _read_json(_snapshot_path())
    beat = _heartbeat_from_runtime(runtime, snapshot, now=now)
    fields = dict(beat.get("fields") or {}) if beat.get("ok") else {}
    tracker = runtime.get("tracker") if isinstance(runtime.get("tracker"), dict) else {}
    risk = runtime.get("risk") if isinstance(runtime.get("risk"), dict) else {}
    if tracker.get("recon") is not None:
        fields.setdefault("reconciliation", tracker.get("recon"))
    reservations = risk.get("reservations")
    if isinstance(reservations, list):
        fields.setdefault("reservations_n", len(reservations))
    unknown = runtime.get("unknown_submissions")
    if isinstance(unknown, list):
        fields.setdefault("unknown_orders", len(unknown))
    gates = _local_live_gates()
    if gates.get("ok"):
        fields.setdefault("live_armed", bool(gates.get("armed")))
        fields.setdefault("live_armed_confirmed", bool(gates.get("armed")))
    heartbeat = confirmed(fields) if fields else observation_unavailable(str(beat.get("reason") or "heartbeat unread"))
    return {
        "ok": True,
        "source": "local_path",
        "status": "OBSERVED",
        "instance_id": instance_id(),
        "instance_verified": False,
        "region": region(),
        "host": {"value": {"instance_id": instance_id(), "verified": False}, "status": "OBSERVED"},
        "service": {
            "value": {"name": SERVICE_NAME, "active": None, "detail": "local ledger only"},
            "status": "OBSERVED",
        },
        "process": observation_unavailable("process not on local ledger"),
        "version": observation_unavailable("binary hash not on local ledger"),
        "environment": {
            "value": {"kalshi_env_name": "MOMENTO_KALSHI_ENV", "label": "production"},
            "status": "OBSERVED",
        },
        "heartbeat": heartbeat,
        "paths": {
            "runtime_exists": True,
            "snapshot_exists": snapshot is not None,
        },
        "logs": [],
        "ledger": beat,
    }


def inspect_script() -> str:
    assert_readonly(INSPECT_SHELL)
    return INSPECT_SHELL


def _parse_json_blob(blob: str) -> dict[str, Any] | None:
    text = (blob or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _heartbeat_from_inspect(raw: dict[str, Any]) -> dict[str, Any]:
    ledger = raw.get("ledger") if isinstance(raw.get("ledger"), dict) else {}
    gates = raw.get("gates") if isinstance(raw.get("gates"), dict) else {}
    fields: dict[str, Any] = {}
    if ledger.get("ok"):
        for key in (
            "kill_switch",
            "live_armed",
            "live_armed_confirmed",
            "open_mlb_positions",
            "bankroll_cents",
            "updated_at",
            "reconciliation",
            "reservations_n",
            "unknown_orders",
            "open_slots",
            "order_submission",
            "heartbeat_n",
            "heartbeat_markets",
            "strategy_games",
            "wnba_games",
            "max_open_slots",
            "mlb_yes_bid_n",
            "first80_n",
            "first81_n",
            "submit_to_ack_n",
            "submit_refused_n",
            "last_mlb_ticker",
            "last_mlb_bid_cents",
            "last_mlb_ask_cents",
            "journal_since",
        ):
            if ledger.get(key) is not None:
                fields[key] = ledger.get(key)
    if gates.get("ok") and "armed" in gates:
        fields.setdefault("live_armed", bool(gates.get("armed")))
        fields.setdefault("live_armed_confirmed", bool(gates.get("armed")))
    activity = raw.get("activity") if isinstance(raw.get("activity"), dict) else {}
    if activity.get("ok"):
        for key in (
            "mlb_yes_bid_n",
            "first80_n",
            "first81_n",
            "submit_to_ack_n",
            "submit_refused_n",
            "last_mlb_ticker",
            "last_mlb_bid_cents",
            "last_mlb_ask_cents",
            "journal_since",
        ):
            if activity.get(key) is not None:
                fields.setdefault(key, activity.get(key))
    if not fields:
        return observation_unavailable(str(ledger.get("reason") or "host ledger unread"))
    return confirmed(fields)


def _normalize_ssm(raw: dict[str, Any]) -> dict[str, Any]:
    reason = str(raw.get("reason") or "ssm inspect unread")
    if not raw.get("ok"):
        return unread(reason=reason, source="ssm")
    host = raw.get("host") if isinstance(raw.get("host"), dict) else {}
    service = raw.get("service") if isinstance(raw.get("service"), dict) else {}
    process = raw.get("process") if isinstance(raw.get("process"), dict) else {}
    version = raw.get("version") if isinstance(raw.get("version"), dict) else {}
    environment = raw.get("environment") if isinstance(raw.get("environment"), dict) else {}
    logs = raw.get("logs") if isinstance(raw.get("logs"), list) else []
    verified = bool(host.get("instance_verified"))
    return {
        "ok": True,
        "source": "ssm",
        "status": "OBSERVED",
        "instance_id": instance_id(),
        "instance_verified": verified,
        "region": region(),
        "host": {"value": {"instance_id": instance_id(), "verified": verified}, "status": "CONFIRMED" if verified else "OBSERVED"},
        "service": {"value": service, "status": "CONFIRMED" if service.get("active") else "OBSERVED"},
        "process": {"value": process, "status": "CONFIRMED" if process.get("main_pid") else "OBSERVATION_UNAVAILABLE"},
        "version": {"value": version, "status": "CONFIRMED" if version.get("binary_sha256") else "OBSERVATION_UNAVAILABLE"},
        "environment": {"value": environment, "status": "OBSERVED"},
        "heartbeat": _heartbeat_from_inspect(raw),
        "paths": raw.get("paths") if isinstance(raw.get("paths"), dict) else {},
        "logs": logs,
        "raw_ok": True,
        "ledger": raw.get("ledger") if isinstance(raw.get("ledger"), dict) else None,
        "gates": raw.get("gates") if isinstance(raw.get("gates"), dict) else None,
    }


def inspect_ssm(*, refresh: bool = False) -> dict[str, Any]:
    now = time.monotonic()
    cached = _SSM_CACHE.get("payload")
    if (
        not refresh
        and isinstance(cached, dict)
        and now - float(_SSM_CACHE.get("at") or 0) < _SSM_TTL_S
    ):
        return cached
    ident = instance_id()
    if not ident.startswith("i-"):
        return unread(reason="instance id invalid", source="ssm")
    command = inspect_script()
    runner = (os.environ.get(SSM_RUNNER_ENV) or "").strip()
    if runner:
        sent = subprocess.run(
            [runner, ident, region(), command],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        parsed = _parse_json_blob(sent.stdout)
        if parsed is None:
            return unread(reason="ssm runner unreadable", source="ssm")
        payload = _normalize_ssm(parsed)
        _SSM_CACHE["at"] = now
        _SSM_CACHE["payload"] = payload
        return payload
    send = _run_aws(
        [
            "ssm",
            "send-command",
            "--instance-ids",
            ident,
            "--document-name",
            "AWS-RunShellScript",
            "--comment",
            "Vital Phase 4 read-only MLB 001 inspect",
            "--parameters",
            json.dumps({"commands": [command]}),
            "--region",
            region(),
            "--output",
            "json",
        ],
        timeout=20,
    )
    if send.returncode != 0:
        return unread(reason="ssm send-command failed", source="ssm")
    try:
        sent = json.loads(send.stdout)
        command_id = sent["Command"]["CommandId"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return unread(reason="ssm send-command unreadable", source="ssm")
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
            return unread(reason=f"ssm invocation {status or 'failed'}", source="ssm")
        stdout = str(body.get("StandardOutputContent") or "")
        break
    parsed = _parse_json_blob(stdout)
    if parsed is None:
        return unread(reason="ssm inspect unreadable", source="ssm")
    payload = _normalize_ssm(parsed)
    _SSM_CACHE["at"] = time.monotonic()
    _SSM_CACHE["payload"] = payload
    return payload


def inspect_mlb_001(*, now: datetime | None = None, refresh: bool = False) -> dict[str, Any]:
    fixture = (os.environ.get(INSPECT_FIXTURE_ENV) or "").strip()
    if fixture:
        raw = _read_json(Path(fixture))
        if raw is None:
            return unread(reason="inspect fixture unreadable", source="fixture")
        if raw.get("ok") is False:
            return unread(reason=str(raw.get("reason") or "fixture unread"), source="fixture")
        packed = dict(raw)
        packed.setdefault("source", "fixture")
        packed.setdefault("ok", True)
        packed.setdefault("status", "OBSERVED")
        packed.setdefault("instance_id", instance_id())
        packed.setdefault("instance_verified", bool(packed.get("instance_verified")))
        packed.setdefault("region", region())
        return packed
    local = inspect_local(now=now)
    if local.get("ok"):
        return local
    if host_fetch_enabled():
        return inspect_ssm(refresh=refresh)
    return local


def clear_ssm_cache() -> None:
    _SSM_CACHE["at"] = 0.0
    _SSM_CACHE["payload"] = None
