"""Read-only Kalshi book pull. Jump never POSTs orders. Never logs secrets."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from roller.jump.catalog.versions import DEMO_SECRET_ID, PRODUCTION_SECRET_ID
from roller.jump.library import repo_root

FILLS_BIN_ENV = "JUMP_FILLS_BIN"
DEMO_FILE_ENV = "JUMP_KALSHI_SECRET_FILE_DEMO"
PROD_FILE_ENV = "JUMP_KALSHI_SECRET_FILE_PRODUCTION"
SKIP_ENV = "JUMP_SKIP_KALSHI"
DEMO_UNREAD_REASON = (
    "DEMO secret unread. Create API keys at https://demo.kalshi.co/ "
    "(not kalshi.com). Official Trade API: https://external-api.demo.kalshi.co/trade-api/v2"
)


def fills_bin() -> str | None:
    explicit = (os.environ.get(FILLS_BIN_ENV) or "").strip()
    if explicit:
        return explicit
    root = repo_root()
    for rel in (
        Path("target/debug/momento-jump-fills-read"),
        Path("target/release/momento-jump-fills-read"),
    ):
        path = root / rel
        if path.is_file():
            return str(path)
    return None


def secret_id(environment: str) -> str:
    env = environment.strip().upper()
    if env == "DEMO":
        return DEMO_SECRET_ID
    return PRODUCTION_SECRET_ID


def default_demo_secret_file() -> Path:
    return Path.home() / ".kalshi" / "demo.json"


def _secret_file(environment: str) -> Path | None:
    env = environment.strip().upper()
    key = DEMO_FILE_ENV if env == "DEMO" else PROD_FILE_ENV
    raw = (os.environ.get(key) or "").strip()
    if raw:
        path = Path(raw).expanduser()
        return path if path.is_file() else None
    if env == "DEMO":
        fallback = default_demo_secret_file()
        if fallback.is_file():
            return fallback
    return None


def demo_unread_reason() -> str:
    if (os.environ.get(SKIP_ENV) or "").strip().lower() in {"1", "true", "yes"}:
        return "Kalshi pull skipped"
    if _secret_file("DEMO") is not None:
        return "DEMO secret present; book observe unread"
    return DEMO_UNREAD_REASON


def _fetch_secret_to_temp(environment: str) -> Path | None:
    sid = secret_id(environment)
    wanted = environment.strip().upper()
    if wanted == "DEMO" and ("production" in sid.lower() or sid.lower().endswith("/prod")):
        return None
    if wanted == "PRODUCTION" and "demo" in sid.lower():
        return None
    try:
        proc = subprocess.run(
            [
                "aws",
                "secretsmanager",
                "get-secret-value",
                "--secret-id",
                sid,
                "--query",
                "SecretString",
                "--output",
                "text",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    blob = proc.stdout
    if not blob or not blob.strip():
        return None
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        return None
    tagged = str(parsed.get("environment") or "").strip().lower()
    if wanted == "DEMO" and tagged not in {"demo", "sandbox"}:
        return None
    if wanted == "PRODUCTION" and tagged not in {"production", "prod"}:
        return None
    handle = tempfile.NamedTemporaryFile(prefix="jump_kalshi_", suffix=".json", delete=False)
    path = Path(handle.name)
    handle.write(blob.encode("utf-8"))
    handle.close()
    os.chmod(path, 0o600)
    return path


def _run_cli(environment: str, mode: str, *, timeout: int) -> dict[str, Any]:
    env = environment.strip().upper()
    if env not in {"DEMO", "PRODUCTION"}:
        return {"ok": False, "status": "OBSERVATION_UNAVAILABLE", "detail": "unknown book"}
    if (os.environ.get(SKIP_ENV) or "").strip().lower() in {"1", "true", "yes"}:
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "environment": env,
            "detail": "Kalshi pull skipped",
        }
    binary = fills_bin()
    if not binary:
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "environment": env,
            "detail": "read-only fills binary missing",
        }
    owned: Path | None = None
    secret = _secret_file(env)
    if secret is None:
        owned = _fetch_secret_to_temp(env)
        secret = owned
    if secret is None:
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "environment": env,
            "detail": demo_unread_reason() if env == "DEMO" else f"{env} secret or host unread",
        }
    try:
        proc = subprocess.run(
            [
                binary,
                mode,
                "--environment",
                "demo" if env == "DEMO" else "production",
                "--secret-file",
                str(secret),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "MOMENTO_KALSHI_SECRET_FILE": str(secret)},
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "environment": env,
            "detail": f"{mode} CLI unread",
        }
    finally:
        if owned is not None:
            try:
                owned.unlink()
            except OSError:
                pass
    if proc.returncode != 0:
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "environment": env,
            "detail": f"{mode} CLI refused or unread",
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "environment": env,
            "detail": f"{mode} CLI JSON unreadable",
        }
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "environment": env,
            "detail": f"{mode} payload missing",
        }
    return {"ok": True, "status": "CONFIRMED", "environment": env, "payload": payload}


def fetch_book(environment: str) -> dict[str, Any]:
    """GET fills via the read-only CLI. Missing secret/host → OBSERVATION_UNAVAILABLE."""
    ran = _run_cli(environment, "fills", timeout=90)
    if not ran.get("ok"):
        return {
            "ok": False,
            "status": ran.get("status") or "OBSERVATION_UNAVAILABLE",
            "environment": ran.get("environment") or environment.strip().upper(),
            "fills": [],
            "detail": ran.get("detail") or "fills unread",
        }
    payload = ran["payload"]
    fills = payload.get("fills")
    if not isinstance(fills, list):
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "environment": ran["environment"],
            "fills": [],
            "detail": "fills payload missing",
        }
    return {
        "ok": True,
        "status": "CONFIRMED",
        "environment": ran["environment"],
        "fills": fills,
        "mutating_sent": bool(payload.get("mutating_sent")),
    }


def fetch_connection(environment: str) -> dict[str, Any]:
    """One read-only book pull: balance + fills + positions. Never POSTs."""
    ran = _run_cli(environment, "book", timeout=90)
    env = ran.get("environment") or environment.strip().upper()
    if not ran.get("ok"):
        return {
            "ok": False,
            "status": ran.get("status") or "OBSERVATION_UNAVAILABLE",
            "environment": env,
            "fills": [],
            "positions": [],
            "detail": ran.get("detail") or "book unread",
        }
    payload = ran["payload"]
    if payload.get("mutating_sent"):
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "environment": env,
            "fills": [],
            "positions": [],
            "detail": "mutating Kalshi request was sent; aborting",
        }
    try:
        cents = int(payload["balance_cents"])
    except (KeyError, TypeError, ValueError):
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "environment": env,
            "fills": [],
            "positions": [],
            "detail": "balance_cents missing",
        }
    fills = payload.get("fills")
    positions = payload.get("positions")
    if not isinstance(fills, list):
        fills = []
    if not isinstance(positions, list):
        positions = []
    return {
        "ok": True,
        "status": "CONFIRMED",
        "environment": env,
        "current_cents": cents,
        "balance_dollars": payload.get("balance_dollars"),
        "portfolio_value_cents": payload.get("portfolio_value_cents"),
        "balance_breakdown": payload.get("balance_breakdown"),
        "fills": fills,
        "positions": positions,
        "source": "kalshi_book",
        "mutating_sent": False,
    }


def fetch_balance(environment: str) -> dict[str, Any]:
    """GET /portfolio/balance via the read-only CLI. Never POSTs. Missing → UNAVAILABLE."""
    ran = _run_cli(environment, "balance", timeout=30)
    env = ran.get("environment") or environment.strip().upper()
    if not ran.get("ok"):
        return {
            "ok": False,
            "status": ran.get("status") or "OBSERVATION_UNAVAILABLE",
            "environment": env,
            "detail": ran.get("detail") or "balance unread",
        }
    payload = ran["payload"]
    try:
        cents = int(payload["balance_cents"])
    except (KeyError, TypeError, ValueError):
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "environment": env,
            "detail": "balance_cents missing",
        }
    if payload.get("mutating_sent"):
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "environment": env,
            "detail": "mutating Kalshi request was sent; aborting",
        }
    return {
        "ok": True,
        "status": "CONFIRMED",
        "environment": env,
        "current_cents": cents,
        "balance_dollars": payload.get("balance_dollars"),
        "portfolio_value_cents": payload.get("portfolio_value_cents"),
        "balance_breakdown": payload.get("balance_breakdown"),
        "source": "kalshi_get_balance",
        "mutating_sent": False,
    }


def fetch_candles(ticker: str, start_ts: int, end_ts: int, *, environment: str = "PRODUCTION") -> dict[str, Any]:
    env = environment.strip().upper()
    if (os.environ.get(SKIP_ENV) or "").strip() in {"1", "true", "yes"}:
        return {"ok": False, "status": "DATA_REQUIRED", "candles": []}
    if not ticker or ticker.isdigit() or len(ticker) < 4:
        return {"ok": False, "status": "DATA_REQUIRED", "candles": []}
    binary = fills_bin()
    if not binary:
        return {"ok": False, "status": "DATA_REQUIRED", "candles": []}
    try:
        proc = subprocess.run(
            [
                binary,
                "candles",
                "--ticker",
                ticker,
                "--start-ts",
                str(start_ts),
                "--end-ts",
                str(end_ts),
                "--period",
                "1",
                "--environment",
                "demo" if env == "DEMO" else "production",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"ok": False, "status": "DATA_REQUIRED", "candles": []}
    if proc.returncode != 0:
        return {"ok": False, "status": "DATA_REQUIRED", "candles": []}
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "status": "DATA_REQUIRED", "candles": []}
    candles = payload.get("candles") if isinstance(payload, dict) else None
    if not isinstance(candles, list) or not candles:
        return {"ok": False, "status": "DATA_REQUIRED", "candles": []}
    return {"ok": True, "status": "CONFIRMED", "candles": candles, "ticker": payload.get("ticker") or ticker}
