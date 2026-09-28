"""Per-bot host journal and Kalshi query health. Never returns Bot One's unit for an ITI id."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.vital.bots import get_bot
from roller.vital.honesty import observation_unavailable
from roller.vital.versions import BOT_ID, SERVICE_NAME

DEMO_INSPECT_FIXTURE_ENV = "VITAL_DEMO_INSPECT_FIXTURE"
HEARTBEAT_MARK = "demo_heartbeat"
REFUSED_MARK = "demo_submit_refused"
POLL_ERROR_MARK = "demo_poll_error"
SHARD_MARK = "insufficient_shard_balance"

_SECRET_TOKENS = (
    "secret",
    "private_key",
    "api_key",
    "password",
    "-----begin",
    "-----end",
    "begin rsa",
    "begin private",
)


def redact_log_line(line: str) -> str:
    text = str(line or "")
    lowered = text.lower()
    if any(token in lowered for token in _SECRET_TOKENS):
        return "[redacted]"
    return text[:400]


def redact_logs(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    out: list[str] = []
    for row in rows:
        if row is None:
            continue
        line = redact_log_line(str(row))
        if line:
            out.append(line)
    return out[-80:]


def factory_bot(bot: dict[str, Any] | None) -> bool:
    if not isinstance(bot, dict):
        return False
    return str(bot.get("bot_id") or "") == BOT_ID or bot.get("kind") == "grandfathered"


def journal_unit(bot: dict[str, Any]) -> str:
    if factory_bot(bot):
        return SERVICE_NAME
    runtime = str(bot.get("aws_runtime_id") or "").strip()
    if runtime.endswith(".service") and "momento-live.service" not in runtime:
        return runtime
    bot_id = str(bot.get("bot_id") or "").strip()
    if str(bot.get("environment") or "DEMO").upper() == "PRODUCTION":
        return f"momento-live@{bot_id}.service"
    return f"momento-demo@{bot_id}.service"


def parse_kalshi_health(logs: list[str], *, environment: str) -> dict[str, Any]:
    last_heartbeat = None
    last_series = None
    last_refuse = None
    last_poll_error = None
    last_http = None
    last_reject = None
    for line in logs:
        text = str(line)
        if HEARTBEAT_MARK in text or "momento heartbeat" in text:
            last_heartbeat = text
            match = re.search(r"series=([A-Za-z0-9_]+)", text)
            if match:
                last_series = match.group(1)
        if "yes_bid_update ticker=" in text:
            match = re.search(r"ticker=([A-Za-z0-9-]+)", text)
            if match:
                last_series = match.group(1)
            last_heartbeat = last_heartbeat or text
        if REFUSED_MARK in text:
            last_refuse = text
            if SHARD_MARK in text:
                last_reject = SHARD_MARK
            else:
                code = re.search(r"code[=:]([A-Za-z0-9_]+)", text)
                if code:
                    last_reject = code.group(1)
            http = re.search(r"HTTP\s+(\d{3})", text)
            if http:
                last_http = int(http.group(1))
        if POLL_ERROR_MARK in text:
            last_poll_error = text
            http = re.search(r"HTTP\s+(\d{3})", text)
            if http:
                last_http = int(http.group(1))
        if SHARD_MARK in text and last_reject is None:
            last_reject = SHARD_MARK
    observed = bool(last_heartbeat or last_refuse or last_poll_error)
    return {
        "environment": environment,
        "last_poll_ts": last_heartbeat,
        "last_series": last_series,
        "last_http_class": last_http,
        "last_reject_code": last_reject,
        "last_submit_refused": last_refuse,
        "last_poll_error": last_poll_error,
        "status": "CONFIRMED" if observed else "OBSERVATION_UNAVAILABLE",
        "read_only": True,
        "submits": False,
        "invented_fills": False,
    }


def _factory_logs() -> dict[str, Any]:
    from roller.vital.aws import inspect_mlb_001

    inspect = inspect_mlb_001()
    logs = redact_logs(inspect.get("logs"))
    if not inspect.get("ok"):
        return {
            "ok": False,
            "bot_id": BOT_ID,
            "unit": SERVICE_NAME,
            "status": "OBSERVATION_UNAVAILABLE",
            "logs": [],
            "detail": inspect.get("reason") or "host unread",
            "source": inspect.get("source"),
        }
    return {
        "ok": True,
        "bot_id": BOT_ID,
        "unit": SERVICE_NAME,
        "status": "OBSERVED",
        "logs": logs,
        "source": inspect.get("source"),
        "inspect": inspect,
    }


def _fixture_inspect(bot_id: str) -> dict[str, Any] | None:
    raw = (os.environ.get(DEMO_INSPECT_FIXTURE_ENV) or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_file():
        return None
    from roller.vital.store import read_json

    payload = read_json(path)
    if not isinstance(payload, dict):
        return None
    if payload.get("bot_id") and str(payload.get("bot_id")) != bot_id:
        return None
    return payload


def inspect_isolated_unit(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if factory_bot(bot):
        return _factory_logs()
    fixture = _fixture_inspect(str(bot.get("bot_id") or bot_id))
    if fixture is not None:
        logs = redact_logs(fixture.get("logs"))
        unit = str(fixture.get("unit") or journal_unit(bot))
        if SERVICE_NAME in unit and not factory_bot(bot):
            return {
                "ok": False,
                "bot_id": bot.get("bot_id"),
                "unit": journal_unit(bot),
                "status": "OBSERVATION_UNAVAILABLE",
                "logs": [],
                "detail": "ITI inspect refused Bot One journal",
            }
        return {
            "ok": bool(fixture.get("ok", True)),
            "bot_id": bot.get("bot_id"),
            "unit": unit,
            "status": "OBSERVED" if fixture.get("ok", True) else "OBSERVATION_UNAVAILABLE",
            "logs": logs,
            "active": bool(fixture.get("active")),
            "heartbeat": bool(fixture.get("heartbeat")),
            "runtime": fixture.get("runtime") if isinstance(fixture.get("runtime"), dict) else None,
            "config": fixture.get("config") if isinstance(fixture.get("config"), dict) else {},
            "process": fixture.get("process") if isinstance(fixture.get("process"), dict) else {},
            "source": fixture.get("source") or "fixture",
            "detail": fixture.get("detail"),
            "inspect": fixture,
        }
    from roller.jump.bots.demo_host import inspect_demo_unit

    inspected = inspect_demo_unit(str(bot.get("bot_id") or bot_id))
    logs = redact_logs(inspected.get("logs"))
    unit = str(inspected.get("unit") or journal_unit(bot))
    if SERVICE_NAME in unit:
        return {
            "ok": False,
            "bot_id": bot.get("bot_id"),
            "unit": journal_unit(bot),
            "status": "OBSERVATION_UNAVAILABLE",
            "logs": [],
            "detail": "ITI inspect refused Bot One journal",
        }
    if not inspected.get("ok"):
        return {
            "ok": False,
            "bot_id": bot.get("bot_id"),
            "unit": unit,
            "status": "OBSERVATION_UNAVAILABLE",
            "logs": [],
            "detail": inspected.get("reason") or "isolated demo unit unread",
            "source": inspected.get("source"),
        }
    return {
        "ok": True,
        "bot_id": bot.get("bot_id"),
        "unit": unit,
        "status": "OBSERVED",
        "logs": logs,
        "active": bool(inspected.get("active")),
        "heartbeat": bool(inspected.get("heartbeat")),
        "runtime": inspected.get("runtime") if isinstance(inspected.get("runtime"), dict) else None,
        "config": inspected.get("config") if isinstance(inspected.get("config"), dict) else {},
        "process": inspected.get("process") if isinstance(inspected.get("process"), dict) else {},
        "source": inspected.get("source") or "ssm",
        "inspect": inspected,
    }


def kalshi_health_view(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    environment = "PRODUCTION" if factory_bot(bot) else str(bot.get("environment") or "DEMO").upper()
    inspected = inspect_isolated_unit(str(bot.get("bot_id") or bot_id), root=root)
    logs = inspected.get("logs") if isinstance(inspected.get("logs"), list) else []
    parsed = parse_kalshi_health(logs, environment=environment)
    from roller.vital.mlb_001.kalshi_observe import kalshi_demo_status, kalshi_status

    book = kalshi_status() if environment == "PRODUCTION" else kalshi_demo_status()
    shard = book.get("mlb_shard_cents") if isinstance(book, dict) else None
    parsed.update(
        {
            "bot_id": bot.get("bot_id"),
            "unit": inspected.get("unit"),
            "book_status": book.get("status") if isinstance(book, dict) else "OBSERVATION_UNAVAILABLE",
            "mlb_shard_cents": shard if shard is not None else None,
            "shard_status": "CONFIRMED" if shard is not None else "OBSERVATION_UNAVAILABLE",
            "observed_at": book.get("observed_at") if isinstance(book, dict) else None,
            "http_200_not_running": True,
        }
    )
    if not inspected.get("ok") and parsed["status"] != "CONFIRMED":
        parsed["status"] = "OBSERVATION_UNAVAILABLE"
        parsed["detail"] = inspected.get("detail") or "unit journal unread"
    return parsed


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def unread_runtime(bot_id: str, *, reason: str) -> dict[str, Any]:
    return {
        "bot_id": bot_id,
        "environment": "DEMO",
        "desired": {"lifecycle": "OBSERVATION_UNAVAILABLE"},
        "observed": {"status": "OBSERVATION_UNAVAILABLE", "reason": reason},
        "confirmed": {
            "lifecycle": observation_unavailable(reason),
            "health": observation_unavailable(reason),
        },
        "lifecycle": "OBSERVATION_UNAVAILABLE",
        "health": "UNKNOWN",
        "http_200_not_running": True,
        "live_ev": {"value": None, "status": "UNAVAILABLE"},
        "sharpe": {"value": None, "status": "UNAVAILABLE"},
    }
