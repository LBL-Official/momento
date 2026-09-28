"""SSM control for isolated Kalshi Demo units. Does not submit orders."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from roller.jump.bots.factory import FACTORY
from roller.jump.dashboard.host_state import (
    DEFAULT_INSTANCE_ID,
    DEFAULT_REGION,
    _read_json_file,
    _run_aws,
    _ssm_instance,
    _ssm_region,
)
from roller.jump.errors import JumpError
from roller.jump.library import repo_root

DEMO_SECRET_ENV = "JUMP_BOT_DEMO_SECRET_ID"
DEMO_STATE_ROOT_ENV = "JUMP_BOT_DEMO_STATE_ROOT"
DEFAULT_DEMO_SECRET = "momento/kalshi/demo"
HOST_DEMO_ROOT = "/var/lib/momento/demo"
_BOT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")
_VITAL_ID_RE = re.compile(r"^(mlb|nba|ncaab|wnba|atp|wta)-\d{3}$")
_RESERVED_LIVE = "mlb-001"
_SSM_TTL_S = 30.0
_OBSERVE_CACHE: dict[str, Any] = {}
_LEDGER_CACHE: dict[str, Any] = {}
_INSPECT_CACHE: dict[str, Any] = {}
_LEDGER_MODULE = Path(__file__).resolve().parents[1] / "dashboard" / "ledger.py"
_HEARTBEAT_MARK = "demo_heartbeat"


def demo_secret_id() -> str:
    raw = (os.environ.get(DEMO_SECRET_ENV) or DEFAULT_DEMO_SECRET).strip()
    lowered = raw.lower()
    if "production" in lowered or lowered.endswith("/prod") or "kalshi/prod" in lowered:
        raise JumpError("DEPLOY_REQUIRED", "demo fetch refuses a production secret id")
    return raw


def safe_bot_id(bot_id: str) -> str:
    text = str(bot_id or "").strip()
    if text == _RESERVED_LIVE:
        raise JumpError("DEPLOY_REQUIRED", "mlb-001 is the live factory unit; demo ITI cannot use it")
    if _VITAL_ID_RE.match(text) or _BOT_ID_RE.match(text):
        return text
    raise JumpError("DEPLOY_REQUIRED", "bot_id is not safe for a host unit")


def _int_setting(settings: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(settings.get(key) or default)
    except (TypeError, ValueError):
        return default


def iti_demo_toml(bot: dict[str, Any]) -> str:
    """Write mode=demo research_iti. Never the factory 80–83 band."""
    settings = bot.get("settings") if isinstance(bot.get("settings"), dict) else {}
    engine = bot.get("engine") if isinstance(bot.get("engine"), dict) else {}
    prices = engine.get("prices") if isinstance(engine.get("prices"), dict) else {}
    iti = bot.get("iti") if isinstance(bot.get("iti"), dict) else {}
    sport = str(engine.get("sport") or bot.get("sport") or "").strip().lower()
    if sport not in {"mlb", "nba", "ncaab", "wnba", "atp", "wta"}:
        raise JumpError("DEPLOY_REQUIRED", "ITI demo toml requires a known sport")
    try:
        entry = int(prices.get("entry_cents") if prices.get("entry_cents") is not None else iti.get("entry_cents"))
        win = int(prices.get("win_cents") if prices.get("win_cents") is not None else iti.get("win_cents"))
        loss = int(prices.get("loss_cents") if prices.get("loss_cents") is not None else iti.get("loss_cents"))
    except (TypeError, ValueError) as exc:
        raise JumpError("DEPLOY_REQUIRED", "ITI demo toml requires integer entry/win/loss") from exc
    if not (1 <= loss < entry < win <= 99):
        raise JumpError("DEPLOY_REQUIRED", "ITI prices must satisfy 1 <= loss < entry < win <= 99")
    bankroll = _int_setting(settings, "bankroll_cents", 5000)
    if bankroll <= 0:
        bankroll = 5000
    allocation_bps = _int_setting(settings, "allocation_bps", 1250)
    if allocation_bps < 1 or allocation_bps > 10_000:
        allocation_bps = 1250
    mode = str(settings.get("sizing_mode") or "FIXED_CENTS").strip().upper()
    if mode not in {"FIXED_CENTS", "PCT_CURRENT", "PCT_WEEKLY"}:
        mode = "FIXED_CENTS"
    max_entry = win - 1
    lines = [
        'mode = "demo"',
        'timezone = "America/Los_Angeles"',
        f"allocation_bps = {allocation_bps}",
        f"max_entry_price_cents = {max_entry}",
        f"preferred_entry_price_cents = {entry}",
        f"min_entry_price_cents = {entry}",
        f"initial_bankroll_cents = {bankroll}",
        f'sizing_mode = "{mode}"',
        'strategy_profile = "research_iti"',
        f"iti_entry_cents = {entry}",
        f"iti_win_cents = {win}",
        f"iti_loss_cents = {loss}",
        f'sport = "{sport}"',
    ]
    if mode == "FIXED_CENTS":
        budget = _int_setting(settings, "max_position_budget_cents", 0)
        if budget <= 0:
            budget = _int_setting(settings, "amount_cents", 0)
        if budget > 0:
            lines.append(f"max_position_budget_cents = {budget}")
    for key in (
        "max_daily_entries",
        "max_daily_wins",
        "max_daily_losses",
        "max_daily_win_cents",
        "max_daily_loss_cents",
    ):
        raw = settings.get(key)
        if raw is None or raw == "":
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            lines.append(f"{key} = {value}")
    lines.extend(["", "[live]", "enabled = false", 'confirmation = ""', ""])
    text = "\n".join(lines)
    if "80" in text and "max_entry_price_cents = 83" in text:
        raise JumpError("DEPLOY_REQUIRED", "ITI demo toml must not write the factory 80–83 band")
    if 'mode = "paper"' in text or 'mode = "live"' in text:
        raise JumpError("DEPLOY_REQUIRED", "ITI demo toml must be mode=demo")
    return text


def start_iti_demo_unit(bot: dict[str, Any]) -> dict[str, Any]:
    """Start momento-demo@{vital-or-jump-id} with ITI toml. Not factory 80–83."""
    raw_id = str(bot.get("bot_id") or "")
    bot_id = safe_bot_id(raw_id)
    secret = demo_secret_id()
    config = iti_demo_toml(bot)
    if 'max_entry_price_cents = 83' in config or "preferred_entry_price_cents = 80" in config:
        raise JumpError("DEPLOY_REQUIRED", "ITI unit refused factory 80–83 toml")
    try:
        unit = _unit_text()
        fetch = _fetch_script()
    except OSError as exc:
        raise JumpError("DEPLOY_REQUIRED", "demo unit files are missing from the repo") from exc
    if "momento/kalshi/demo" not in fetch:
        raise JumpError("DEPLOY_REQUIRED", "demo fetch must use momento/kalshi/demo")
    if 'SECRET_ID="${JUMP_BOT_DEMO_SECRET_ID:-momento/kalshi/demo}"' not in fetch:
        raise JumpError("DEPLOY_REQUIRED", "demo fetch must default to the demo secret id")
    if "Conflicts=momento-live" in unit:
        raise JumpError("DEPLOY_REQUIRED", "demo unit must not stop Bot One")
    if "ExecStart=/usr/local/bin/momento-trading-engine-demo" not in unit:
        raise JumpError("DEPLOY_REQUIRED", "demo unit must use the isolated demo engine binary")
    if "ExecStart=/usr/local/bin/momento-trading-engine\n" in unit:
        raise JumpError("DEPLOY_REQUIRED", "demo unit must not reuse the factory live binary")
    if "momento-kalshi-demo-%i.json" not in unit:
        raise JumpError("DEPLOY_REQUIRED", "demo unit must use a per-unit shm secret path")
    if "MOMENTO_KALSHI_SECRET_FILE=/dev/shm/momento-kalshi-demo.json" in unit:
        raise JumpError("DEPLOY_REQUIRED", "demo unit must not share /dev/shm/momento-kalshi-demo.json")
    if "MOMENTO_KALSHI_SECRET_FILE:?demo fetch requires" not in fetch and "momento-kalshi-demo-*.json" not in fetch:
        raise JumpError("DEPLOY_REQUIRED", "demo fetch must write the per-unit shm path")
    payload = {
        "bot_id": bot_id,
        "secret_id": secret,
        "demo_toml": config,
        "unit": unit,
        "fetch": fetch,
    }
    python = (
        "python3 - <<'JUMP_DEMO_PY'\n"
        + "import json, os, subprocess, sys, time\n"
        + f"P = json.loads({json.dumps(json.dumps(payload))})\n"
        + (
            "bot_id = P['bot_id']\n"
            "secret = P['secret_id']\n"
            "if bot_id == 'mlb-001':\n"
            "    print(json.dumps({'ok': False, 'active': False, 'reason': 'mlb-001 live unit refused'}))\n"
            "    raise SystemExit(0)\n"
            "if 'production' in secret.lower():\n"
            "    print(json.dumps({'ok': False, 'active': False, 'reason': 'production secret refused'}))\n"
            "    raise SystemExit(0)\n"
            "if not os.path.isfile('/usr/local/bin/momento-trading-engine-demo'):\n"
            "    print(json.dumps({'ok': False, 'active': False, 'reason': 'demo engine binary missing on host'}))\n"
            "    raise SystemExit(0)\n"
            "root = f'/var/lib/momento/demo/{bot_id}'\n"
            "os.makedirs(f'{root}/state', exist_ok=True)\n"
            "open(f'{root}/demo.toml','w',encoding='utf-8').write(P['demo_toml'])\n"
            "subprocess.run(['chown','-R','momento:momento',root],check=False)\n"
            "desc = subprocess.run(['aws','secretsmanager','describe-secret','--secret-id',secret,'--region',os.environ.get('AWS_DEFAULT_REGION','us-east-1')],capture_output=True,text=True)\n"
            "if desc.returncode != 0:\n"
            "    print(json.dumps({'ok': False, 'active': False, 'secret_missing': True, 'reason': 'demo secret not present on host'}))\n"
            "    raise SystemExit(0)\n"
            "os.makedirs('/usr/local/libexec', exist_ok=True)\n"
            "open('/usr/local/libexec/m-demo-fetch-secret.sh','w',encoding='utf-8').write(P['fetch'])\n"
            "os.chmod('/usr/local/libexec/m-demo-fetch-secret.sh', 0o755)\n"
            "open('/etc/systemd/system/momento-demo@.service','w',encoding='utf-8').write(P['unit'])\n"
            "subprocess.run(['systemctl','daemon-reload'],check=False)\n"
            "en = subprocess.run(['systemctl','enable','--now',f'momento-demo@{bot_id}.service'],capture_output=True,text=True)\n"
            "time.sleep(3)\n"
            "active = subprocess.run(['systemctl','is-active',f'momento-demo@{bot_id}.service'],capture_output=True,text=True)\n"
            "is_active = active.returncode == 0 and active.stdout.strip() == 'active'\n"
            "journal = subprocess.run(['journalctl','-u',f'momento-demo@{bot_id}.service','-n','40','--no-pager','-o','cat'],capture_output=True,text=True)\n"
            "hb = os.path.isfile(f'{root}/state/live-runtime.json') or ('demo_heartbeat' in (journal.stdout or ''))\n"
            "ok = is_active and hb\n"
            "reason = None\n"
            "if not is_active:\n"
            "    reason = (en.stderr or active.stdout or 'unit not active').strip()[:240]\n"
            "elif not hb:\n"
            "    reason = 'unit active but demo heartbeat unread'\n"
            "print(json.dumps({'ok': ok, 'active': is_active, 'heartbeat': hb, 'secret_missing': False, 'reason': reason, 'unit': f'momento-demo@{bot_id}.service'}))\n"
        )
        + "JUMP_DEMO_PY\n"
    )
    result = _ssm_run([python], f"Vital start ITI demo unit {bot_id}", timeout=40)
    if result.get("secret_missing") or "demo secret not present" in str(result.get("reason") or ""):
        return {
            "ok": False,
            "active": False,
            "secret_missing": True,
            "unit_started": False,
            "aws_runtime_id": None,
            "reason": str(result.get("reason") or "demo secret missing"),
            "source": result.get("source") or "ssm",
        }
    if not result.get("ok") and not result.get("active"):
        return {
            "ok": False,
            "active": False,
            "secret_missing": False,
            "unit_started": False,
            "aws_runtime_id": None,
            "reason": str(result.get("reason") or "AWS session or demo credentials are not available; bot is not marked running"),
            "source": result.get("source") or "ssm",
        }
    if not result.get("active"):
        return {
            "ok": False,
            "active": False,
            "unit_started": False,
            "aws_runtime_id": None,
            "reason": str(result.get("reason") or "demo unit did not become active"),
            "source": result.get("source") or "ssm",
        }
    if not result.get("heartbeat"):
        return {
            "ok": False,
            "active": True,
            "heartbeat": False,
            "unit_started": False,
            "aws_runtime_id": f"momento-demo@{bot_id}.service",
            "reason": str(result.get("reason") or "unit active but demo heartbeat unread"),
            "source": result.get("source") or "ssm",
        }
    unit = f"momento-demo@{bot_id}.service"
    payload_out = {
        "ok": True,
        "active": True,
        "heartbeat": True,
        "status": "RUNNING_DEMO",
        "environment": "DEMO",
        "aws_runtime_id": unit,
        "observed": True,
        "source": "ssm",
        "reason": None,
    }
    _OBSERVE_CACHE[bot_id] = {"at": time.monotonic(), "payload": payload_out}
    return {
        "ok": True,
        "active": True,
        "unit_started": True,
        "aws_runtime_id": unit,
        "unit": unit,
        "environment": "DEMO",
        "kalshi_env": "demo",
        "live_enabled": False,
        "heartbeat": True,
        "state_dir": f"{HOST_DEMO_ROOT}/{bot_id}/state",
        "source": "ssm",
    }


def demo_toml(bot: dict[str, Any]) -> str:
    settings = bot.get("settings") if isinstance(bot.get("settings"), dict) else {}
    try:
        bankroll = int(settings.get("bankroll_cents") or FACTORY["bankroll_cents"])
    except (TypeError, ValueError):
        bankroll = int(FACTORY["bankroll_cents"])
    if bankroll <= 0:
        bankroll = int(FACTORY["bankroll_cents"])
    try:
        allocation_bps = int(settings.get("allocation_bps") or FACTORY["allocation_bps"])
    except (TypeError, ValueError):
        allocation_bps = int(FACTORY["allocation_bps"])
    if allocation_bps < 1 or allocation_bps > 10_000:
        allocation_bps = int(FACTORY["allocation_bps"])
    mode = str(settings.get("sizing_mode") or "PCT_WEEKLY").strip().upper()
    if mode not in {"FIXED_CENTS", "PCT_CURRENT", "PCT_WEEKLY"}:
        mode = "PCT_WEEKLY"
    lines = [
        'mode = "paper"',
        'timezone = "America/Los_Angeles"',
        f"allocation_bps = {allocation_bps}",
        f"max_entry_price_cents = {int(FACTORY['max_entry_cents'])}",
        f"preferred_entry_price_cents = {int(FACTORY['preferred_entry_cents'])}",
        f"min_entry_price_cents = {int(FACTORY['min_entry_cents'])}",
        f"initial_bankroll_cents = {bankroll}",
        f'sizing_mode = "{mode}"',
    ]
    if mode == "FIXED_CENTS":
        try:
            budget = int(settings.get("max_position_budget_cents") or settings.get("amount_cents") or 0)
        except (TypeError, ValueError):
            budget = 0
        if budget > 0:
            lines.append(f"max_position_budget_cents = {budget}")
    for key in (
        "max_daily_entries",
        "max_daily_wins",
        "max_daily_losses",
        "max_daily_win_cents",
        "max_daily_loss_cents",
    ):
        raw = settings.get(key)
        if raw is None or raw == "":
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            lines.append(f"{key} = {value}")
    lines.extend(["", "[live]", "enabled = false", 'confirmation = ""', ""])
    return "\n".join(lines)


def _unit_text() -> str:
    return (repo_root() / "deploy" / "momento-demo@.service").read_text(encoding="utf-8")


def _fetch_script() -> str:
    return (repo_root() / "deploy" / "m-demo-fetch-secret.sh").read_text(encoding="utf-8")


def load_local_demo_state(bot_id: str) -> dict[str, Any]:
    root = (os.environ.get(DEMO_STATE_ROOT_ENV) or "").strip()
    if not root:
        return {"ok": False, "reason": "demo state path unset", "source": "local_path"}
    ident = safe_bot_id(bot_id)
    base = Path(root) / ident
    runtime_path = base / "state" / "live-runtime.json"
    if not runtime_path.is_file():
        runtime_path = base / "live-runtime.json"
    runtime = _read_json_file(runtime_path)
    if runtime is None:
        return {"ok": False, "reason": "demo live-runtime.json unreadable", "source": "local_path"}
    snapshot = _read_json_file(base / "state" / "weekly-snapshot.json") or _read_json_file(
        base / "weekly-snapshot.json"
    )
    return {"ok": True, "runtime": runtime, "snapshot": snapshot, "source": "local_path"}


def _parse_ssm_json(blob: str) -> dict[str, Any] | None:
    text = (blob or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _ssm_run(commands: list[str], comment: str, timeout: int = 20) -> dict[str, Any]:
    instance = _ssm_instance()
    if not instance.startswith("i-"):
        return {"ok": False, "reason": "instance id invalid", "source": "ssm"}
    send = _run_aws(
        [
            "ssm",
            "send-command",
            "--instance-ids",
            instance,
            "--document-name",
            "AWS-RunShellScript",
            "--comment",
            comment,
            "--parameters",
            json.dumps({"commands": commands}),
            "--region",
            _ssm_region(),
            "--output",
            "json",
        ],
        timeout=timeout,
    )
    if send.returncode != 0:
        return {"ok": False, "reason": "ssm send-command failed", "source": "ssm"}
    try:
        sent = json.loads(send.stdout)
        command_id = sent["Command"]["CommandId"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return {"ok": False, "reason": "ssm send-command unreadable", "source": "ssm"}
    stdout = ""
    for _ in range(30):
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
            err = str(body.get("StandardErrorContent") or "")[:240]
            return {"ok": False, "reason": err or f"ssm invocation {status or 'failed'}", "source": "ssm"}
        stdout = str(body.get("StandardOutputContent") or "")
        break
    parsed = _parse_ssm_json(stdout)
    if parsed is None:
        return {"ok": False, "reason": "ssm output unreadable", "source": "ssm"}
    parsed.setdefault("source", "ssm")
    parsed.setdefault("aws_runtime_id", instance)
    return parsed


def start_demo_unit(bot: dict[str, Any]) -> dict[str, Any]:
    """Install isolated demo.toml + momento-demo@bot. RUNNING only if is-active."""
    bot_id = safe_bot_id(str(bot.get("bot_id") or ""))
    secret = demo_secret_id()
    config = demo_toml(bot)
    try:
        unit = _unit_text()
        fetch = _fetch_script()
    except OSError as exc:
        raise JumpError("DEPLOY_REQUIRED", "demo unit files are missing from the repo") from exc
    if "momento/kalshi/demo" not in fetch:
        raise JumpError("DEPLOY_REQUIRED", "demo fetch must use momento/kalshi/demo")
    if 'SECRET_ID="${JUMP_BOT_DEMO_SECRET_ID:-momento/kalshi/demo}"' not in fetch:
        raise JumpError("DEPLOY_REQUIRED", "demo fetch must default to the demo secret id")
    if "Conflicts=momento-live" in unit:
        raise JumpError("DEPLOY_REQUIRED", "demo unit must not stop Bot One")
    if "momento-kalshi-demo-%i.json" not in unit:
        raise JumpError("DEPLOY_REQUIRED", "demo unit must use a per-unit shm secret path")
    payload = {
        "bot_id": bot_id,
        "secret_id": secret,
        "demo_toml": config,
        "unit": unit,
        "fetch": fetch,
    }
    python = (
        "python3 - <<'JUMP_DEMO_PY'\n"
        + "import json, os, subprocess, sys\n"
        + f"P = json.loads({json.dumps(json.dumps(payload))})\n"
        + (
            "bot_id = P['bot_id']\n"
            "secret = P['secret_id']\n"
            "if 'production' in secret.lower():\n"
            "    print(json.dumps({'ok': False, 'active': False, 'reason': 'production secret refused'}))\n"
            "    raise SystemExit(0)\n"
            "root = f'/var/lib/momento/demo/{bot_id}'\n"
            "os.makedirs(f'{root}/state', exist_ok=True)\n"
            "open(f'{root}/demo.toml','w',encoding='utf-8').write(P['demo_toml'])\n"
            "desc = subprocess.run(['aws','secretsmanager','describe-secret','--secret-id',secret,'--region',os.environ.get('AWS_DEFAULT_REGION','us-east-1')],capture_output=True,text=True)\n"
            "if desc.returncode != 0:\n"
            "    print(json.dumps({'ok': False, 'active': False, 'reason': 'demo secret not present on host'}))\n"
            "    raise SystemExit(0)\n"
            "os.makedirs('/usr/local/libexec', exist_ok=True)\n"
            "open('/usr/local/libexec/m-demo-fetch-secret.sh','w',encoding='utf-8').write(P['fetch'])\n"
            "os.chmod('/usr/local/libexec/m-demo-fetch-secret.sh', 0o755)\n"
            "open('/etc/systemd/system/momento-demo@.service','w',encoding='utf-8').write(P['unit'])\n"
            "subprocess.run(['systemctl','daemon-reload'],check=False)\n"
            "en = subprocess.run(['systemctl','enable','--now',f'momento-demo@{bot_id}.service'],capture_output=True,text=True)\n"
            "active = subprocess.run(['systemctl','is-active',f'momento-demo@{bot_id}.service'],capture_output=True,text=True)\n"
            "ok = active.returncode == 0 and active.stdout.strip() == 'active'\n"
            "print(json.dumps({'ok': ok, 'active': ok, 'reason': None if ok else (en.stderr or active.stdout or 'unit not active').strip()[:240], 'unit': f'momento-demo@{bot_id}.service'}))\n"
        )
        + "JUMP_DEMO_PY\n"
    )
    result = _ssm_run([python], f"Jump B start demo unit {bot_id}", timeout=25)
    if not result.get("ok") and not result.get("active"):
        raise JumpError(
            "DEPLOY_REQUIRED",
            str(result.get("reason") or "AWS session or demo credentials are not available; bot is not marked running"),
        )
    if not result.get("active"):
        raise JumpError(
            "DEPLOY_REQUIRED",
            str(result.get("reason") or "demo unit did not become active"),
        )
    payload = {
        "ok": True,
        "active": True,
        "status": "RUNNING_DEMO",
        "environment": "DEMO",
        "aws_runtime_id": f"momento-demo@{bot_id}.service",
        "observed": True,
        "source": "ssm",
        "reason": None,
    }
    _OBSERVE_CACHE[bot_id] = {"at": time.monotonic(), "payload": payload}
    return {
        "ok": True,
        "active": True,
        "aws_runtime_id": f"momento-demo@{bot_id}.service",
        "unit": f"momento-demo@{bot_id}.service",
        "environment": "DEMO",
        "kalshi_env": "demo",
        "live_enabled": False,
        "state_dir": f"{HOST_DEMO_ROOT}/{bot_id}/state",
        "source": "ssm",
    }


def _demo_unit_name(bot_id: str) -> str:
    return f"momento-demo@{safe_bot_id(bot_id)}.service"


def _host_inspect_enabled() -> bool:
    raw = (os.environ.get("JUMP_BOT_ONE_HOST_FETCH") or os.environ.get("VITAL_AWS_HOST_FETCH") or "").strip().lower()
    return raw in {"1", "true", "yes", "ssm"}


def inspect_demo_unit(bot_id: str, *, refresh: bool = False) -> dict[str, Any]:
    """Read-only isolated unit inspect. Never tails momento-live.service."""
    ident = safe_bot_id(bot_id)
    now = time.monotonic()
    cached = _INSPECT_CACHE.get(ident)
    if (
        not refresh
        and isinstance(cached, dict)
        and now - float(cached.get("at") or 0) < _SSM_TTL_S
    ):
        return cached["payload"]
    unit = _demo_unit_name(ident)
    if not _host_inspect_enabled():
        return {
            "ok": False,
            "active": False,
            "heartbeat": False,
            "unit": unit,
            "logs": [],
            "reason": "isolated demo unit unread",
            "source": "unread",
        }
    payload = {"bot_id": ident, "unit": unit}
    python = (
        "python3 - <<'JUMP_DEMO_INSPECT'\n"
        "import json, os, subprocess, sys\n"
        f"P = json.loads({json.dumps(json.dumps(payload))})\n"
        "bot_id = P['bot_id']\n"
        "unit = P['unit']\n"
        "if bot_id == 'mlb-001' or unit == 'momento-live.service':\n"
        "    print(json.dumps({'ok': False, 'reason': 'ITI inspect refused Bot One journal'}))\n"
        "    raise SystemExit(0)\n"
        "def run(args):\n"
        "    try:\n"
        "        p = subprocess.run(args, capture_output=True, text=True, timeout=8)\n"
        "        return p.returncode, (p.stdout or ''), (p.stderr or '')\n"
        "    except Exception as exc:\n"
        "        return 1, '', str(exc)\n"
        "rc, active_out, _ = run(['systemctl', 'is-active', unit])\n"
        "active = (active_out or '').strip()\n"
        "_, journal, _ = run(['journalctl', '-u', unit, '-n', '40', '--no-pager', '-o', 'cat'])\n"
        "runtime_path = f'/var/lib/momento/demo/{bot_id}/state/live-runtime.json'\n"
        "runtime = None\n"
        "if os.path.isfile(runtime_path):\n"
        "    try:\n"
        "        raw = json.loads(open(runtime_path, encoding='utf-8').read())\n"
        "        if isinstance(raw, dict):\n"
        "            runtime = {k: raw.get(k) for k in ('updated_at','observed_at','mode','kill_switch','live_armed') if k in raw}\n"
        "            runtime['present'] = True\n"
        "        else:\n"
        "            runtime = {'present': True}\n"
        "    except Exception:\n"
        "        runtime = {'present': True, 'unreadable': True}\n"
        "redacted = []\n"
        "for line in (journal or '').splitlines()[-40:]:\n"
        "    low = line.lower()\n"
        "    if any(tok in low for tok in ('secret', 'private_key', 'api_key', 'password', '-----begin')):\n"
        "        redacted.append('[redacted]')\n"
        "    else:\n"
        "        redacted.append(line[:240])\n"
        "is_active = rc == 0 and active == 'active'\n"
        "hb = runtime is not None or any('demo_heartbeat' in row for row in redacted)\n"
        "config = {}\n"
        "toml_path = f'/var/lib/momento/demo/{bot_id}/demo.toml'\n"
        "allowed = {'strategy_profile','mode','sport','iti_entry_cents','iti_win_cents','iti_loss_cents','preferred_entry_price_cents'}\n"
        "if os.path.isfile(toml_path):\n"
        "    for line in open(toml_path, encoding='utf-8'):\n"
        "        row = line.strip()\n"
        "        if not row or row.startswith('#') or '=' not in row:\n"
        "            continue\n"
        "        key, val = row.split('=', 1)\n"
        "        key = key.strip()\n"
        "        if key in allowed:\n"
        "            config[key] = val.strip().strip('\"')\n"
        "_, show, _ = run(['systemctl', 'show', unit, '--property=MainPID,WorkingDirectory,NRestarts,ExecMainStartTimestamp', '--no-pager'])\n"
        "pid = None\n"
        "cwd = None\n"
        "for line in (show or '').splitlines():\n"
        "    if line.startswith('MainPID=') and line.split('=',1)[1].isdigit():\n"
        "        pid = int(line.split('=',1)[1])\n"
        "    if line.startswith('WorkingDirectory='):\n"
        "        cwd = line.split('=',1)[1] or None\n"
        "print(json.dumps({'ok': True, 'active': is_active, 'heartbeat': hb, 'unit': unit, 'logs': redacted, 'runtime': runtime, 'config': config, 'process': {'main_pid': pid, 'cwd': cwd}, 'service': {'name': unit, 'active': active, 'working_directory': cwd}, 'reason': None if is_active else (active or 'demo unit not active')}))\n"
        "JUMP_DEMO_INSPECT\n"
    )
    parsed = _ssm_run([python], f"Vital inspect demo {ident}", timeout=25)
    if not parsed.get("ok"):
        payload = {
            "ok": False,
            "active": False,
            "heartbeat": False,
            "unit": unit,
            "logs": [],
            "reason": parsed.get("reason") or "isolated demo unit unread",
            "source": parsed.get("source") or "ssm",
        }
        _INSPECT_CACHE[ident] = {"at": now, "payload": payload}
        return payload
    logs = parsed.get("logs") if isinstance(parsed.get("logs"), list) else []
    payload = {
        "ok": True,
        "active": bool(parsed.get("active")),
        "heartbeat": bool(parsed.get("heartbeat")),
        "unit": unit,
        "logs": logs,
        "runtime": parsed.get("runtime") if isinstance(parsed.get("runtime"), dict) else None,
        "config": parsed.get("config") if isinstance(parsed.get("config"), dict) else {},
        "process": parsed.get("process") if isinstance(parsed.get("process"), dict) else {},
        "service": parsed.get("service") if isinstance(parsed.get("service"), dict) else {"name": unit},
        "reason": parsed.get("reason"),
        "source": "ssm",
    }
    _INSPECT_CACHE[ident] = {"at": now, "payload": payload}
    return payload


def apply_iti_demo_toml(bot: dict[str, Any]) -> dict[str, Any]:
    """Rewrite isolated demo.toml and restart only that momento-demo@ unit."""
    raw_id = str(bot.get("bot_id") or "")
    if raw_id == _RESERVED_LIVE:
        raise JumpError("DEPLOY_REQUIRED", "mlb-001 factory toml is locked")
    bot_id = safe_bot_id(raw_id)
    config = iti_demo_toml(bot)
    if "momento-live.service" in config:
        raise JumpError("DEPLOY_REQUIRED", "ITI apply refused momento-live.service")
    unit = _demo_unit_name(bot_id)
    python = (
        "python3 - <<'JUMP_DEMO_APPLY'\n"
        "import json, os, subprocess, time\n"
        f"bot_id = {bot_id!r}\n"
        f"unit = {unit!r}\n"
        f"toml = {json.dumps(config)}\n"
        "if bot_id == 'mlb-001' or unit == 'momento-live.service':\n"
        "    print(json.dumps({'ok': False, 'reason': 'mlb-001 live unit refused'}))\n"
        "    raise SystemExit(0)\n"
        "if not unit.startswith('momento-demo@') or 'momento-live.service' in unit:\n"
        "    print(json.dumps({'ok': False, 'reason': 'apply refuses factory live unit'}))\n"
        "    raise SystemExit(0)\n"
        "root = f'/var/lib/momento/demo/{bot_id}'\n"
        "os.makedirs(f'{root}/state', exist_ok=True)\n"
        "open(f'{root}/demo.toml','w',encoding='utf-8').write(toml)\n"
        "subprocess.run(['chown','-R','momento:momento',root],check=False)\n"
        "rst = subprocess.run(['systemctl','restart',unit],capture_output=True,text=True)\n"
        "time.sleep(3)\n"
        "active = subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True)\n"
        "is_active = active.returncode == 0 and active.stdout.strip() == 'active'\n"
        "journal = subprocess.run(['journalctl','-u',unit,'-n','40','--no-pager','-o','cat'],capture_output=True,text=True)\n"
        "hb = os.path.isfile(f'{root}/state/live-runtime.json') or ('demo_heartbeat' in (journal.stdout or ''))\n"
        "ok = rst.returncode == 0 and is_active and hb\n"
        "reason = None\n"
        "if rst.returncode != 0:\n"
        "    reason = (rst.stderr or 'restart failed').strip()[:240]\n"
        "elif not is_active:\n"
        "    reason = (active.stdout or 'unit not active').strip()[:240]\n"
        "elif not hb:\n"
        "    reason = 'unit active but demo heartbeat unread'\n"
        "print(json.dumps({'ok': ok, 'active': is_active, 'heartbeat': hb, 'unit': unit, 'reason': reason}))\n"
        "JUMP_DEMO_APPLY\n"
    )
    result = _ssm_run([python], f"Vital apply ITI demo toml {bot_id}", timeout=40)
    _OBSERVE_CACHE.pop(bot_id, None)
    _INSPECT_CACHE.pop(bot_id, None)
    return {
        "attempted": True,
        "ok": bool(result.get("ok") and result.get("active") and result.get("heartbeat")),
        "active": bool(result.get("active")),
        "heartbeat": bool(result.get("heartbeat")),
        "unit": unit,
        "reason": None if result.get("ok") else (result.get("reason") or "isolated demo apply unread"),
        "source": result.get("source") or "ssm",
        "never_momento_live": True,
        "http_200_not_running": True,
    }


def observe_demo_unit(bot_id: str) -> dict[str, Any]:
    ident = safe_bot_id(bot_id)
    now = time.monotonic()
    cached = _OBSERVE_CACHE.get(ident)
    if isinstance(cached, dict) and now - float(cached.get("at") or 0) < _SSM_TTL_S:
        return cached["payload"]
    inspected = inspect_demo_unit(ident)
    running = bool(inspected.get("ok") and inspected.get("active") and inspected.get("heartbeat"))
    payload = {
        "ok": bool(inspected.get("ok")),
        "active": bool(inspected.get("active")),
        "heartbeat": bool(inspected.get("heartbeat")),
        "status": "RUNNING_DEMO" if running else "CREATED",
        "environment": "DEMO",
        "aws_runtime_id": _demo_unit_name(ident),
        "observed": running,
        "source": inspected.get("source") or "ssm",
        "reason": None if running else (inspected.get("reason") or "demo unit not active or heartbeat unread"),
        "logs": inspected.get("logs") if isinstance(inspected.get("logs"), list) else [],
    }
    _OBSERVE_CACHE[ident] = {"at": now, "payload": payload}
    return payload


def fetch_ssm_demo_ledger(bot_id: str) -> dict[str, Any]:
    ident = safe_bot_id(bot_id)
    now = time.monotonic()
    cached = _LEDGER_CACHE.get(ident)
    if isinstance(cached, dict) and now - float(cached.get("at") or 0) < _SSM_TTL_S:
        return cached["payload"]
    try:
        script = _LEDGER_MODULE.read_text(encoding="utf-8")
    except OSError:
        return {"ok": False, "reason": "ledger.py unreadable", "source": "ssm"}
    runtime = f"{HOST_DEMO_ROOT}/{ident}/state/live-runtime.json"
    snapshot = f"{HOST_DEMO_ROOT}/{ident}/state/weekly-snapshot.json"
    command = (
        "python3 - "
        f"{runtime} {snapshot} "
        "<<'JUMP_LEDGER_PY'\n"
        f"{script}\n"
        "JUMP_LEDGER_PY"
    )
    parsed = _ssm_run([command], f"Jump C demo ledger {ident}", timeout=20)
    if not parsed.get("ok"):
        return parsed
    payload = {
        "ok": True,
        "fields": parsed.get("fields") or {},
        "trades": parsed.get("trades") if isinstance(parsed.get("trades"), list) else [],
        "runtime": parsed.get("runtime"),
        "snapshot": parsed.get("snapshot"),
        "source": "ssm",
        "week_start": parsed.get("week_start"),
        "formula": parsed.get("formula"),
    }
    _LEDGER_CACHE[ident] = {"at": now, "payload": payload}
    return payload


def load_demo_host_state(bot_id: str) -> dict[str, Any]:
    local = load_local_demo_state(bot_id)
    if local.get("ok"):
        return local
    host_fetch = (os.environ.get("JUMP_BOT_ONE_HOST_FETCH") or "").strip().lower()
    if host_fetch in {"1", "true", "yes", "ssm"}:
        return fetch_ssm_demo_ledger(bot_id)
    return local


# Re-export host constants so tests can stub instance selection.
INSTANCE_DEFAULT = DEFAULT_INSTANCE_ID
REGION_DEFAULT = DEFAULT_REGION
