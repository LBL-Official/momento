"""SSM control for isolated Kalshi production ITI units. Does not submit orders."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from roller.jump.bots.demo_host import _ssm_run, iti_demo_toml, safe_bot_id
from roller.jump.errors import JumpError
from roller.jump.library import repo_root

LIVE_SECRET_ENV = "JUMP_BOT_LIVE_SECRET_ID"
DEFAULT_LIVE_SECRET = "momento/kalshi/production"
HOST_LIVE_ROOT = "/var/lib/momento/live"
_RESERVED_LIVE = "mlb-001"


LIVE_STATE_ROOT_ENV = "JUMP_BOT_LIVE_STATE_ROOT"


def load_local_live_state(bot_id: str) -> dict[str, Any]:
    from pathlib import Path

    from roller.jump.dashboard.host_state import _read_json_file

    root = (os.environ.get(LIVE_STATE_ROOT_ENV) or "").strip()
    if not root:
        return {"ok": False, "reason": "live state path unset", "source": "local_path"}
    ident = safe_bot_id(bot_id)
    base = Path(root) / ident
    runtime_path = base / "state" / "live-runtime.json"
    if not runtime_path.is_file():
        runtime_path = base / "live-runtime.json"
    runtime = _read_json_file(runtime_path)
    if runtime is None:
        return {"ok": False, "reason": "live live-runtime.json unreadable", "source": "local_path"}
    snapshot = _read_json_file(base / "state" / "weekly-snapshot.json") or _read_json_file(
        base / "weekly-snapshot.json"
    )
    return {"ok": True, "runtime": runtime, "snapshot": snapshot, "source": "local_path"}


def live_secret_id() -> str:
    raw = (os.environ.get(LIVE_SECRET_ENV) or DEFAULT_LIVE_SECRET).strip()
    lowered = raw.lower()
    if "demo" in lowered or lowered.endswith("/demo"):
        raise JumpError("DEPLOY_REQUIRED", "ITI live fetch refuses a demo secret id")
    if "production" not in lowered:
        raise JumpError("DEPLOY_REQUIRED", "ITI live fetch requires the production secret id")
    return raw


def iti_live_toml(bot: dict[str, Any]) -> str:
    """Write mode=live research_iti. Never the factory 80–83 band."""
    text = iti_demo_toml(bot)
    text = text.replace('mode = "demo"', 'mode = "live"', 1)
    text = text.replace("enabled = false", "enabled = true", 1)
    text = text.replace('confirmation = ""', 'confirmation = "ENABLE_LIVE_TRADING"', 1)
    if 'mode = "demo"' in text or 'mode = "paper"' in text:
        raise JumpError("DEPLOY_REQUIRED", "ITI live toml must be mode=live")
    if "enabled = false" in text or "ENABLE_LIVE_TRADING" not in text:
        raise JumpError("DEPLOY_REQUIRED", "ITI live toml requires the triple live gate")
    if "max_entry_price_cents = 83" in text or "preferred_entry_price_cents = 80" in text:
        raise JumpError("DEPLOY_REQUIRED", "ITI live toml must not write the factory 80–83 band")
    return text


def _unit_text() -> str:
    return (repo_root() / "deploy" / "momento-live@.service").read_text(encoding="utf-8")


def _fetch_script() -> str:
    return (repo_root() / "deploy" / "m-iti-live-fetch-secret.sh").read_text(encoding="utf-8")


def stop_iti_demo_unit(bot_id: str) -> dict[str, Any]:
    ident = safe_bot_id(bot_id)
    if ident == _RESERVED_LIVE:
        raise JumpError("DEPLOY_REQUIRED", "mlb-001 demo stop is refused")
    result = _ssm_run(
        [
            f"systemctl stop momento-demo@{ident}.service >/dev/null 2>&1; "
            f"systemctl disable momento-demo@{ident}.service >/dev/null 2>&1; "
            f"echo '{{\"ok\":true,\"stopped\":true}}'"
        ],
        f"Vital stop ITI demo unit {ident}",
        timeout=20,
    )
    return {
        "ok": bool(result.get("ok")),
        "stopped": bool(result.get("stopped") or result.get("ok")),
        "reason": result.get("reason"),
        "source": result.get("source") or "ssm",
    }


def start_iti_live_unit(bot: dict[str, Any]) -> dict[str, Any]:
    """Start momento-live@{vital-id} with ITI live.toml. Never momento-live.service."""
    raw_id = str(bot.get("vital_bot_id") or bot.get("bot_id") or "")
    bot_id = safe_bot_id(raw_id)
    if bot_id == _RESERVED_LIVE:
        raise JumpError("DEPLOY_REQUIRED", "mlb-001 is the live factory unit; ITI cannot use it")
    secret = live_secret_id()
    config = iti_live_toml(bot)
    try:
        unit = _unit_text()
        fetch = _fetch_script()
    except OSError as exc:
        raise JumpError("DEPLOY_REQUIRED", "ITI live unit files are missing from the repo") from exc
    if "momento-live.service" in unit and "momento-live@" not in unit:
        raise JumpError("DEPLOY_REQUIRED", "isolated live unit must be momento-live@")
    if "MOMENTO_FACTORY_UNIT=1" in unit:
        raise JumpError("DEPLOY_REQUIRED", "isolated live unit must not set MOMENTO_FACTORY_UNIT=1")
    stop_iti_demo_unit(bot_id)
    payload = {
        "bot_id": bot_id,
        "secret_id": secret,
        "live_toml": config,
        "unit": unit,
        "fetch": fetch,
    }
    python = (
        "python3 - <<'JUMP_LIVE_PY'\n"
        + "import json, os, subprocess\n"
        + f"P = json.loads({json.dumps(json.dumps(payload))})\n"
        + (
            "bot_id = P['bot_id']\n"
            "secret = P['secret_id']\n"
            "if bot_id == 'mlb-001':\n"
            "    print(json.dumps({'ok': False, 'active': False, 'reason': 'mlb-001 live unit refused'}))\n"
            "    raise SystemExit(0)\n"
            "if 'demo' in secret.lower():\n"
            "    print(json.dumps({'ok': False, 'active': False, 'reason': 'demo secret refused'}))\n"
            "    raise SystemExit(0)\n"
            "root = f'/var/lib/momento/live/{bot_id}'\n"
            "os.makedirs(f'{root}/state', exist_ok=True)\n"
            "open(f'{root}/live.toml','w',encoding='utf-8').write(P['live_toml'])\n"
            "desc = subprocess.run(['aws','secretsmanager','describe-secret','--secret-id',secret,'--region',os.environ.get('AWS_DEFAULT_REGION','us-east-1')],capture_output=True,text=True)\n"
            "if desc.returncode != 0:\n"
            "    print(json.dumps({'ok': False, 'active': False, 'secret_missing': True, 'reason': 'production secret not present on host'}))\n"
            "    raise SystemExit(0)\n"
            "os.makedirs('/usr/local/libexec', exist_ok=True)\n"
            "open('/usr/local/libexec/m-iti-live-fetch-secret.sh','w',encoding='utf-8').write(P['fetch'])\n"
            "os.chmod('/usr/local/libexec/m-iti-live-fetch-secret.sh', 0o755)\n"
            "open('/etc/systemd/system/momento-live@.service','w',encoding='utf-8').write(P['unit'])\n"
            "subprocess.run(['systemctl','daemon-reload'],check=False)\n"
            "en = subprocess.run(['systemctl','enable','--now',f'momento-live@{bot_id}.service'],capture_output=True,text=True)\n"
            "active = subprocess.run(['systemctl','is-active',f'momento-live@{bot_id}.service'],capture_output=True,text=True)\n"
            "ok = active.returncode == 0 and active.stdout.strip() == 'active'\n"
            "print(json.dumps({'ok': ok, 'active': ok, 'secret_missing': False, 'reason': None if ok else (en.stderr or active.stdout or 'unit not active').strip()[:240], 'unit': f'momento-live@{bot_id}.service'}))\n"
        )
        + "JUMP_LIVE_PY\n"
    )
    result = _ssm_run([python], f"Vital start ITI live unit {bot_id}", timeout=25)
    if result.get("secret_missing") or "production secret not present" in str(result.get("reason") or ""):
        return {
            "ok": False,
            "active": False,
            "secret_missing": True,
            "unit_started": False,
            "aws_runtime_id": None,
            "reason": str(result.get("reason") or "production secret missing"),
            "source": result.get("source") or "ssm",
        }
    if not result.get("ok") and not result.get("active"):
        return {
            "ok": False,
            "active": False,
            "secret_missing": False,
            "unit_started": False,
            "aws_runtime_id": None,
            "reason": str(result.get("reason") or "AWS session or production credentials are not available; bot is not marked running"),
            "source": result.get("source") or "ssm",
        }
    if not result.get("active"):
        return {
            "ok": False,
            "active": False,
            "unit_started": False,
            "aws_runtime_id": None,
            "reason": str(result.get("reason") or "live unit did not become active"),
            "source": result.get("source") or "ssm",
        }
    unit = f"momento-live@{bot_id}.service"
    return {
        "ok": True,
        "active": True,
        "unit_started": True,
        "aws_runtime_id": unit,
        "unit": unit,
        "environment": "PRODUCTION",
        "kalshi_env": "production",
        "live_enabled": True,
        "state_dir": f"{HOST_LIVE_ROOT}/{bot_id}/state",
        "source": "ssm",
    }


def observe_iti_live_unit(bot_id: str) -> dict[str, Any]:
    ident = safe_bot_id(bot_id)
    check = _ssm_run(
        [
            f"if systemctl is-active --quiet momento-live@{ident}.service; "
            f"then echo '{{\"ok\":true,\"active\":true}}'; "
            f"else echo '{{\"ok\":true,\"active\":false}}'; fi"
        ],
        f"Vital observe ITI live {ident}",
        timeout=15,
    )
    return {
        "ok": bool(check.get("ok")),
        "active": bool(check.get("active")),
        "status": "RUNNING" if check.get("active") else "DEPLOY_REQUIRED",
        "environment": "PRODUCTION",
        "aws_runtime_id": f"momento-live@{ident}.service",
        "observed": bool(check.get("active")),
        "source": "ssm",
        "reason": None if check.get("active") else (check.get("reason") or "live unit not active"),
    }
