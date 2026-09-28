"""Read-only confirmed heartbeat and Bot One MLB ledger fields."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from roller.jump.bots.status import PROBE_ENV
from roller.jump.dashboard.host_state import load_host_state
from roller.jump.dashboard.ledger import summarize_mlb_ledger

CONFIRMED_INT_KEYS = (
    "bankroll_cents",
    "open_mlb_positions",
    "open_desk_positions",
    "day_pnl_cents",
    "week_pnl_cents",
    "trade_n",
    "weekly_trade_n",
)
CONFIRMED_BOOL_KEYS = ("kill_switch", "live_armed_confirmed")
CONFIRMED_STR_KEYS = ("aws_runtime_id", "last_trade")
REJECTED_EV_KEYS = ("day_ev_cents", "week_ev_cents", "day_ev", "week_ev", "ev_cents")


def unavailable(reason: str = "UNAVAILABLE") -> dict[str, Any]:
    return {"value": None, "status": reason}


def confirmed(value: Any) -> dict[str, Any]:
    return {"value": value, "status": "CONFIRMED"}


def _int_field(payload: dict[str, Any], key: str) -> int | None:
    if key not in payload:
        return None
    raw = payload[key]
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _bool_field(payload: dict[str, Any], key: str) -> bool | None:
    if key not in payload:
        return None
    raw = payload[key]
    if raw is True or raw == 1:
        return True
    if raw is False or raw == 0:
        return False
    if isinstance(raw, str) and raw.strip().lower() in {"true", "1", "yes"}:
        return True
    if isinstance(raw, str) and raw.strip().lower() in {"false", "0", "no"}:
        return False
    return None


def parse_heartbeat_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"observed": False, "fields": {}, "status": "OBSERVATION_UNAVAILABLE"}
    fields: dict[str, Any] = {}
    for key in CONFIRMED_INT_KEYS:
        value = _int_field(payload, key)
        if value is not None:
            fields[key] = value
    for key in CONFIRMED_BOOL_KEYS:
        value = _bool_field(payload, key)
        if value is not None:
            fields[key] = value
    for key in CONFIRMED_STR_KEYS:
        raw = payload.get(key)
        if raw is not None and str(raw).strip():
            fields[key] = str(raw).strip()
    return {"observed": True, "fields": fields, "status": "CONFIRMED" if fields else "EMPTY"}


def load_probe_heartbeat() -> dict[str, Any]:
    raw = os.environ.get(PROBE_ENV)
    if not raw:
        return {
            "observed": False,
            "fields": {},
            "status": "OBSERVATION_UNAVAILABLE",
            "detail": "host probe unset; Jump C does not invent bankroll, P&L, or positions",
        }
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {
            "observed": False,
            "fields": {},
            "status": "OBSERVATION_UNAVAILABLE",
            "detail": "host probe invalid; Jump C does not invent metrics",
        }
    parsed = parse_heartbeat_payload(payload if isinstance(payload, dict) else None)
    if not parsed.get("observed"):
        parsed["detail"] = "host probe invalid; Jump C does not invent metrics"
    return parsed


def load_ledger_heartbeat(*, now: datetime | None = None) -> dict[str, Any]:
    host = load_host_state()
    if not host.get("ok"):
        return {
            "observed": False,
            "fields": {},
            "status": "OBSERVATION_UNAVAILABLE",
            "source": host.get("source"),
            "detail": host.get("reason") or "Bot One ledger unread",
        }
    if host.get("source") == "ssm":
        fields = dict(host.get("fields") or {})
        if not fields:
            return {
                "observed": False,
                "fields": {},
                "status": "OBSERVATION_UNAVAILABLE",
                "source": "ssm",
                "detail": "Bot One SSM ledger fields empty",
            }
        if host.get("aws_runtime_id") and "aws_runtime_id" not in fields:
            fields["aws_runtime_id"] = host["aws_runtime_id"]
        return {
            "observed": True,
            "fields": fields,
            "status": "CONFIRMED",
            "source": "ssm",
            "detail": (
                "Bot One MLB day/week PNL from live-runtime.json via PnlBreakdown; "
                "live EV is UNAVAILABLE"
            ),
        }
    clock = now or datetime.now(timezone.utc)
    summary = summarize_mlb_ledger(host["runtime"], host.get("snapshot"), clock)
    if not summary.get("ok"):
        return {
            "observed": False,
            "fields": {},
            "status": "OBSERVATION_UNAVAILABLE",
            "source": host.get("source"),
            "detail": summary.get("reason") or "Bot One ledger PNL unreadable",
        }
    fields = dict(summary["fields"])
    if host.get("aws_runtime_id") and "aws_runtime_id" not in fields:
        fields["aws_runtime_id"] = host["aws_runtime_id"]
    return {
        "observed": True,
        "fields": fields,
        "status": "CONFIRMED",
        "source": host.get("source"),
        "detail": (
            "Bot One MLB day/week PNL from live-runtime.json via PnlBreakdown; "
            "live EV is UNAVAILABLE"
        ),
    }


def load_bot_one_heartbeat(*, now: datetime | None = None, host_fetch: bool = True) -> dict[str, Any]:
    """Vital only. Probe and local ledger are not Jump C truth."""
    from roller.jump.vital_client import jump_heartbeat_from_vital

    del host_fetch
    try:
        return jump_heartbeat_from_vital(now=now)
    except Exception:
        return {
            "observed": False,
            "fields": {},
            "status": "OBSERVATION_UNAVAILABLE",
            "ledger": False,
            "source": "vital",
            "detail": "Vital host unread; Jump does not invent Bot One metrics",
        }


def load_demo_heartbeat(bot_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    from roller.jump.bots.demo_host import load_demo_host_state

    host = load_demo_host_state(bot_id)
    if not host.get("ok"):
        return {
            "observed": False,
            "fields": {},
            "status": "OBSERVATION_UNAVAILABLE",
            "source": host.get("source"),
            "detail": host.get("reason") or "demo ledger unread",
        }
    if host.get("runtime"):
        clock = now or datetime.now(timezone.utc)
        summary = summarize_mlb_ledger(host["runtime"], host.get("snapshot"), clock)
        if not summary.get("ok"):
            return {
                "observed": False,
                "fields": {},
                "status": "OBSERVATION_UNAVAILABLE",
                "source": host.get("source"),
                "detail": summary.get("reason") or "demo ledger PNL unreadable",
            }
        return {
            "observed": True,
            "fields": dict(summary.get("fields") or {}),
            "status": "CONFIRMED",
            "source": host.get("source"),
            "detail": "demo MLB day/week PNL from isolated live-runtime.json; live EV is UNAVAILABLE",
            "ledger": True,
        }
    fields = dict(host.get("fields") or {})
    if not fields:
        return {
            "observed": False,
            "fields": {},
            "status": "OBSERVATION_UNAVAILABLE",
            "source": host.get("source"),
            "detail": "demo SSM ledger fields empty",
        }
    return {
        "observed": True,
        "fields": fields,
        "status": "CONFIRMED",
        "source": host.get("source"),
        "detail": "demo MLB ledger via SSM; live EV is UNAVAILABLE",
        "ledger": True,
    }


def field_metric(fields: dict[str, Any], key: str, *, missing: str = "UNAVAILABLE") -> dict[str, Any]:
    if key not in fields:
        return unavailable(missing)
    return confirmed(fields[key])
