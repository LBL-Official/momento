"""Read-only SSM inspect of momento-live.service. No Vital. No submit."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.ls.identity import (
    BASELINE_SHA256,
    INSTANCE_ID,
    REGION,
    SERVICE_NAME,
)

INSTANCE_ENV = "MOMENTO_LS_INSTANCE_ID"
REGION_ENV = "MOMENTO_LS_REGION"
FIXTURE_ENV = "MOMENTO_LS_INSPECT_FIXTURE"
RUNNER_ENV = "MOMENTO_LS_SSM_RUNNER"

WRITE_FORBIDDEN = re.compile(
    r"systemctl\s+(start|stop|restart|kill|enable|disable)|"
    r"(?:^|[\s;|&])(?:kill|pkill|killall)\s|"
    r"(?:touch|install|tee|echo|printf)\b[^\n]*state/KILL|"
    r"(?:>|>>)\s*/var/lib/momento",
    re.IGNORECASE,
)

INSPECT_SHELL = r"""
set +e
python3 - <<'LS_INSPECT_PY'
import hashlib, json, os, subprocess
from pathlib import Path
from collections import Counter

def run(args, timeout=20):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except Exception as exc:
        return 1, "", str(exc)

service = "momento-live.service"
binary = "/usr/local/bin/momento-trading-engine"
config = "/var/lib/momento/config/live.toml"
runtime = "/var/lib/momento/state/live-runtime.json"
snapshot = "/var/lib/momento/state/weekly-snapshot.json"
kill_path = "/var/lib/momento/state/KILL"
unit = "/etc/systemd/system/momento-live.service"

rc_active, active, _ = run(["systemctl", "is-active", service])
_, show, _ = run([
    "systemctl", "show", service,
    "--property=Id,ActiveState,SubState,MainPID,FragmentPath,ExecMainStartTimestamp,ExecMainStartTimestampMonotonic,WorkingDirectory,NRestarts,ExecStart,Environment,Restart,RestartPreventExitStatus,RestartSec,StartLimitBurst,StartLimitIntervalUSec",
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

def file_sha(path):
    p = Path(path)
    if not p.is_file():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()

def file_bytes(path):
    p = Path(path)
    return p.stat().st_size if p.is_file() else None

version = file_sha(binary)
_, journal, _ = run(["journalctl", "-u", service, "-n", "120", "--no-pager", "-o", "cat"])
redacted = []
for line in (journal or "").splitlines():
    if any(token in line.lower() for token in ("secret", "private_key", "api_key", "password")):
        redacted.append("[redacted]")
    else:
        redacted.append(line[:500])

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
    return False

def _open_mlb(runtime_obj):
    tracker = runtime_obj.get("tracker") if isinstance(runtime_obj.get("tracker"), dict) else {}
    positions = tracker.get("positions") if isinstance(tracker.get("positions"), list) else []
    n = 0
    for row in positions:
        pos = row.get("position") if isinstance(row, dict) and isinstance(row.get("position"), dict) else row
        if not isinstance(pos, dict):
            continue
        life = pos.get("lifecycle")
        if life in {"Open", "Building"} or (isinstance(life, dict) and ("Open" in life or "Building" in life)):
            filled = pos.get("filled_quantity") or pos.get("quantity")
            try:
                if int(filled or 0) > 0:
                    n += 1
            except (TypeError, ValueError):
                pass
    return n

def _hb_kv(journal, key):
    last = None
    count = 0
    for line in (journal or "").splitlines():
        if "momento heartbeat" not in line:
            continue
        count += 1
        for part in line.split():
            if part.startswith(key + "="):
                last = part.split("=", 1)[1]
    if key == "_count":
        return count
    return last

def _int_or_none(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None

config_text = Path(config).read_text() if Path(config).is_file() else ""
gates_armed = (
    'mode = "live"' in config_text
    and "enabled = true" in config_text
    and "ENABLE_LIVE_TRADING" in config_text
)

pid = int(props["MainPID"]) if str(props.get("MainPID") or "").isdigit() else None
exe = cwd = cmdline = None
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

ERROR_NEEDLES = (
    "fill_apply_failed",
    "market_discovery_error",
    "fill_map_failed",
    "venue_error",
    "auth=failed",
    "unauthorized",
    "invalid_signature",
    "traceback",
    "panic",
    "production_auth=false",
)

def _activity(started_at):
    args = ["journalctl", "-u", service, "--no-pager", "-o", "cat"]
    if started_at:
        args.extend(["--since", started_at])
    else:
        args.extend(["-n", "4000"])
    rc, out, _ = run(args, timeout=20)
    if rc != 0 and not out:
        return None
    text = out or ""
    last_ticker = last_bid = last_ask = None
    last_error = last_heartbeat = last_recon = None
    last_hb = {}
    yes_n = 0
    errors = []
    counts = Counter()
    for line in text.splitlines():
        low = line.lower()
        if "yes_bid_update ticker=kxmlbgame" in low:
            yes_n += 1
            ticker = bid = ask = None
            for part in line.split():
                if part.startswith("ticker=") and part.split("=", 1)[1].startswith("KXMLBGAME"):
                    ticker = part.split("=", 1)[1]
                elif part.startswith("bid="):
                    bid = _int_or_none(part.split("=", 1)[1])
                elif part.startswith("ask="):
                    ask = _int_or_none(part.split("=", 1)[1])
            if ticker:
                last_ticker, last_bid, last_ask = ticker, bid, ask
        if "momento heartbeat" in line:
            counts["heartbeat"] += 1
            last_heartbeat = line[:800]
            fields = {}
            for part in line.split():
                if "=" in part:
                    key, value = part.split("=", 1)
                    fields[key] = value
            last_hb = fields
        if "recon_cleared" in line:
            counts["recon_cleared"] += 1
            last_recon = line[:500]
        if "fill_apply_failed" in line:
            counts["fill_apply_failed"] += 1
        if "fill_applied " in line:
            counts["fill_applied"] += 1
        if "submit_to_ack" in line:
            counts["submit_to_ack"] += 1
        if "submit_refused" in line:
            counts["submit_refused"] += 1
        if "First80Observed" in line:
            counts["first80"] += 1
        if "First81Confirmed" in line:
            counts["first81"] += 1
        if "occupancy_held_venue_filled" in line:
            counts["occupancy_held"] += 1
        if "preflight" in line:
            counts["preflight"] += 1
        if any(n in low for n in ERROR_NEEDLES):
            counts["errors"] += 1
            last_error = line[:500]
            if len(errors) < 20:
                errors.append(line[:500])
    return {
        "ok": True,
        "journal_since": started_at or "last_4000",
        "mlb_yes_bid_n": yes_n,
        "first80_n": counts["first80"],
        "first81_n": counts["first81"],
        "submit_to_ack_n": counts["submit_to_ack"],
        "submit_refused_n": counts["submit_refused"],
        "heartbeat_n": counts["heartbeat"],
        "recon_cleared_n": counts["recon_cleared"],
        "fill_apply_failed_n": counts["fill_apply_failed"],
        "fill_applied_n": counts["fill_applied"],
        "occupancy_held_n": counts["occupancy_held"],
        "preflight_n": counts["preflight"],
        "error_n": counts["errors"],
        "last_mlb_ticker": last_ticker,
        "last_mlb_bid_cents": last_bid,
        "last_mlb_ask_cents": last_ask,
        "last_error": last_error,
        "last_heartbeat": last_heartbeat,
        "last_recon_cleared": last_recon,
        "recent_errors": errors[-12:],
        "hb_open_slots": _int_or_none(last_hb.get("open_slots")),
        "hb_max_open_slots": _int_or_none(last_hb.get("max_open_slots")),
        "hb_markets": _int_or_none(last_hb.get("markets")),
        "hb_strategy_games": _int_or_none(last_hb.get("strategy_games")),
        "hb_wnba_games": _int_or_none(last_hb.get("wnba_games")),
        "hb_unknown_orders": _int_or_none(last_hb.get("unknown_orders")),
        "hb_reconciliation": last_hb.get("reconciliation"),
        "hb_order_submission": last_hb.get("order_submission"),
    }

runtime_obj = _read_json(runtime)
snapshot_obj = _read_json(snapshot)
tracker = runtime_obj.get("tracker") if isinstance(runtime_obj, dict) and isinstance(runtime_obj.get("tracker"), dict) else {}
risk = runtime_obj.get("risk") if isinstance(runtime_obj, dict) and isinstance(runtime_obj.get("risk"), dict) else {}
activity = _activity(props.get("ExecMainStartTimestamp") or None)
journal_full = journal or ""

ledger = {"ok": False, "reason": "runtime unread"}
if runtime_obj is not None:
    reservations = risk.get("reservations")
    unknown = runtime_obj.get("unknown_submissions")
    recon = (
        tracker.get("recon")
        or (activity or {}).get("hb_reconciliation")
        or _hb_kv(journal_full, "reconciliation")
    )
    ledger = {
        "ok": True,
        "kill_switch": _kill_tripped(risk, kill_path),
        "live_armed": gates_armed,
        "open_mlb_positions": _open_mlb(runtime_obj),
        "bankroll_cents": (snapshot_obj or {}).get("bankroll", {}).get("cents") if isinstance((snapshot_obj or {}).get("bankroll"), dict) else None,
        "reconciliation": recon,
        "reservations_n": len(reservations) if isinstance(reservations, list) else None,
        "unknown_orders": len(unknown) if isinstance(unknown, list) else (activity or {}).get("hb_unknown_orders"),
        "open_slots": (activity or {}).get("hb_open_slots"),
        "order_submission": (activity or {}).get("hb_order_submission") or _hb_kv(journal_full, "order_submission"),
        "heartbeat_markets": (activity or {}).get("hb_markets"),
        "strategy_games": (activity or {}).get("hb_strategy_games"),
        "wnba_games": (activity or {}).get("hb_wnba_games"),
        "max_open_slots": (activity or {}).get("hb_max_open_slots"),
    }

print(json.dumps({
    "ok": True,
    "source": "ssm",
    "service": {
        "name": service,
        "active": active,
        "active_state": props.get("ActiveState"),
        "sub_state": props.get("SubState"),
        "fragment": props.get("FragmentPath"),
        "started_at": props.get("ExecMainStartTimestamp") or None,
        "working_directory": props.get("WorkingDirectory") or None,
        "n_restarts": int(props["NRestarts"]) if str(props.get("NRestarts") or "").isdigit() else None,
        "exec_start": (props.get("ExecStart") or "")[:240] or None,
        "restart": props.get("Restart"),
        "restart_prevent_exit_status": props.get("RestartPreventExitStatus"),
        "restart_sec": props.get("RestartSec"),
        "start_limit_burst": int(props["StartLimitBurst"]) if str(props.get("StartLimitBurst") or "").isdigit() else None,
        "start_limit_interval": props.get("StartLimitIntervalUSec"),
    },
    "process": {
        "main_pid": pid,
        "exe": exe,
        "cwd": cwd,
        "cmdline": cmdline,
        "exe_matches": bool(exe and exe.endswith("momento-trading-engine")),
    },
    "hashes": {
        "binary": version,
        "binary_bytes": file_bytes(binary),
        "unit": file_sha(unit),
        "live_toml": file_sha(config),
        "persist": file_sha(runtime),
        "snapshot": file_sha(snapshot),
    },
    "environment": {
        "env_names": env_names,
        "kalshi_env": kalshi_env,
    },
    "paths": {
        "runtime_exists": Path(runtime).is_file(),
        "snapshot_exists": Path(snapshot).is_file(),
        "kill_exists": Path(kill_path).is_file(),
        "config_exists": Path(config).is_file(),
        "unit_exists": Path(unit).is_file(),
        "binary_exists": Path(binary).is_file(),
    },
    "ledger": ledger,
    "activity": activity,
    "gates": {"ok": bool(config_text), "armed": gates_armed},
    "logs": redacted[-80:],
}))
LS_INSPECT_PY
"""


def assert_readonly(command: str) -> None:
    if WRITE_FORBIDDEN.search(command or ""):
        raise PermissionError("Momento LS refuses host-mutating commands")


def inspect_script() -> str:
    assert_readonly(INSPECT_SHELL)
    return INSPECT_SHELL


def instance_id() -> str:
    return (os.environ.get(INSTANCE_ENV) or INSTANCE_ID).strip()


def region() -> str:
    return (
        (os.environ.get(REGION_ENV) or "").strip()
        or (os.environ.get("AWS_REGION") or "").strip()
        or (os.environ.get("AWS_DEFAULT_REGION") or "").strip()
        or REGION
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_json_blob(blob: str) -> dict[str, Any] | None:
    text = (blob or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def unread(reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "OBSERVATION_UNAVAILABLE",
        "source": "ssm",
        "reason": reason,
        "observed_at": _utc_now(),
        "product": "Momento LS",
        "observe_only": True,
        "submits": False,
    }


def _run_aws(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["aws", *args], check=False, capture_output=True, text=True, timeout=timeout)


def inspect_host(*, refresh: bool = True) -> dict[str, Any]:
    fixture = (os.environ.get(FIXTURE_ENV) or "").strip()
    if fixture:
        try:
            raw = json.loads(Path(fixture).read_text())
        except Exception:
            return unread("inspect fixture unreadable")
        return raw if isinstance(raw, dict) else unread("inspect fixture invalid")
    ident = instance_id()
    if not ident.startswith("i-"):
        return unread("instance id invalid")
    command = inspect_script()
    runner = (os.environ.get(RUNNER_ENV) or "").strip()
    if runner:
        sent = subprocess.run(
            [runner, ident, region(), command],
            check=False,
            capture_output=True,
            text=True,
            timeout=40,
        )
        parsed = _parse_json_blob(sent.stdout)
        return parsed if parsed else unread("ssm runner unreadable")
    send = _run_aws(
        [
            "ssm",
            "send-command",
            "--instance-ids",
            ident,
            "--document-name",
            "AWS-RunShellScript",
            "--comment",
            "Momento LS read-only momento-live.service inspect",
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
        return unread("ssm send-command failed")
    try:
        command_id = json.loads(send.stdout)["Command"]["CommandId"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return unread("ssm send-command unreadable")
    for _ in range(16):
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
            return unread(f"ssm invocation {status or 'failed'}")
        parsed = _parse_json_blob(str(body.get("StandardOutputContent") or ""))
        return parsed if parsed else unread("ssm inspect unreadable")
    return unread("ssm inspect timeout")


def compose_snapshot(raw: dict[str, Any] | None) -> dict[str, Any]:
    payload = raw if isinstance(raw, dict) else {}
    observed_at = _utc_now()
    if not payload.get("ok"):
        return unread(str(payload.get("reason") or "host unread"))
    ledger = payload.get("ledger") if isinstance(payload.get("ledger"), dict) else {}
    activity = payload.get("activity") if isinstance(payload.get("activity"), dict) else {}
    hashes = payload.get("hashes") if isinstance(payload.get("hashes"), dict) else {}
    service = payload.get("service") if isinstance(payload.get("service"), dict) else {}
    process = payload.get("process") if isinstance(payload.get("process"), dict) else {}
    gates = payload.get("gates") if isinstance(payload.get("gates"), dict) else {}
    recon = str(ledger.get("reconciliation") or "")
    submit = str(ledger.get("order_submission") or "")
    binary = hashes.get("binary")
    authorized = recon.lower() == "healthy" and submit.lower() == "enabled"
    return {
        "ok": True,
        "product": "Momento LS",
        "observe_only": True,
        "submits": False,
        "http_200_not_running": True,
        "source": payload.get("source") or "ssm",
        "observed_at": observed_at,
        "instance_id": instance_id(),
        "service_name": SERVICE_NAME,
        "service": service,
        "process": process,
        "hashes": {
            **hashes,
            "baseline": BASELINE_SHA256,
            "baseline_match": bool(binary and binary == BASELINE_SHA256),
        },
        "environment": payload.get("environment") or {},
        "paths": payload.get("paths") or {},
        "gates": {
            "live_armed": bool(gates.get("armed") if gates.get("ok") else ledger.get("live_armed")),
            "reconciliation": recon or None,
            "order_submission": submit or None,
            "authorized_to_submit": authorized,
            "kill_switch": ledger.get("kill_switch"),
            "process_up_is_not_authorization": True,
        },
        "occupancy": {
            "open_slots": ledger.get("open_slots"),
            "max_open_slots": ledger.get("max_open_slots"),
            "reservations_n": ledger.get("reservations_n"),
            "unknown_orders": ledger.get("unknown_orders"),
            "open_mlb_positions": ledger.get("open_mlb_positions"),
        },
        "updates": {
            "mlb_yes_bid_n": activity.get("mlb_yes_bid_n"),
            "first80_n": activity.get("first80_n"),
            "first81_n": activity.get("first81_n"),
            "submit_to_ack_n": activity.get("submit_to_ack_n"),
            "submit_refused_n": activity.get("submit_refused_n"),
            "heartbeat_n": activity.get("heartbeat_n"),
            "recon_cleared_n": activity.get("recon_cleared_n"),
            "fill_applied_n": activity.get("fill_applied_n"),
            "fill_apply_failed_n": activity.get("fill_apply_failed_n"),
            "occupancy_held_n": activity.get("occupancy_held_n"),
            "preflight_n": activity.get("preflight_n"),
            "heartbeat_markets": ledger.get("heartbeat_markets"),
            "strategy_games": ledger.get("strategy_games"),
            "wnba_games": ledger.get("wnba_games"),
            "last_mlb_ticker": activity.get("last_mlb_ticker"),
            "last_mlb_bid_cents": activity.get("last_mlb_bid_cents"),
            "last_mlb_ask_cents": activity.get("last_mlb_ask_cents"),
            "journal_since": activity.get("journal_since"),
            "last_heartbeat": activity.get("last_heartbeat"),
            "last_recon_cleared": activity.get("last_recon_cleared"),
        },
        "errors": {
            "n": activity.get("error_n"),
            "last": activity.get("last_error"),
            "recent": activity.get("recent_errors") or [],
        },
        "journal": payload.get("logs") if isinstance(payload.get("logs"), list) else [],
        "bankroll_cents": ledger.get("bankroll_cents"),
    }
