"""NBA 001 V1 control-room projection. Missing is UNAVAILABLE, never $0."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LIVE_EXECUTION = False
UNAVAILABLE = "UNAVAILABLE"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def handle_nba001_v1() -> dict[str, Any]:
    raw = Path(__file__).resolve().parents[3] / "data" / "nba-001" / "v1_control_room.json"
    override = Path(os.environ.get("NBA001_STATE_DIR", "") or "")
    if override:
        raw = override / "v1_control_room.json"
    if not raw.is_file():
        return {
            "schema": "systimo.nba001_v1.v0",
            "availability": UNAVAILABLE,
            "armed": False,
            "executing": False,
            "equity": UNAVAILABLE,
            "cash": UNAVAILABLE,
            "drevo": UNAVAILABLE,
            "positman": UNAVAILABLE,
            "orchestra": "QUERY",
            "live_execution": LIVE_EXECUTION,
            "note": "V1 control room absent. UNAVAILABLE ≠ $0. Drevo/Positman observe only.",
            "completed_at": _now_iso(),
        }
    try:
        body = json.loads(raw.read_text())
    except (OSError, ValueError) as exc:
        return {
            "schema": "systimo.nba001_v1.v0",
            "availability": UNAVAILABLE,
            "detail": f"{type(exc).__name__}",
            "armed": False,
            "executing": False,
            "equity": UNAVAILABLE,
            "drevo": UNAVAILABLE,
            "positman": UNAVAILABLE,
            "live_execution": LIVE_EXECUTION,
            "completed_at": _now_iso(),
        }
    account = body.get("account") if isinstance(body, dict) else None
    return {
        "schema": "systimo.nba001_v1.v0",
        "availability": "OBSERVED",
        "armed": bool(body.get("armed")) if isinstance(body, dict) else False,
        "executing": bool(body.get("executing")) if isinstance(body, dict) else False,
        "mode": body.get("mode") if isinstance(body, dict) else UNAVAILABLE,
        "production_orders_compiled": body.get("production_orders_compiled")
        if isinstance(body, dict)
        else None,
        "policy_hash": body.get("policy_hash") if isinstance(body, dict) else UNAVAILABLE,
        "account": account if isinstance(account, dict) else {"availability": UNAVAILABLE},
        "authority": body.get("authority") if isinstance(body, dict) else UNAVAILABLE,
        "epochs": body.get("epochs") if isinstance(body, dict) else UNAVAILABLE,
        "p5": body.get("p5") if isinstance(body, dict) else UNAVAILABLE,
        "drevo": body.get("drevo") if isinstance(body, dict) else UNAVAILABLE,
        "positman": body.get("positman") if isinstance(body, dict) else UNAVAILABLE,
        "orchestra": "QUERY",
        "live_execution": LIVE_EXECUTION,
        "note": "Projection only. Drevo/Positman never change admissions.",
        "completed_at": _now_iso(),
    }


if __name__ == "__main__":
    os.environ["NBA001_STATE_DIR"] = str(Path("/tmp/momento-nba001-v1-missing"))
    body = handle_nba001_v1()
    assert body["availability"] == UNAVAILABLE
    assert body["equity"] == UNAVAILABLE
    assert body["armed"] is False
    print("nba001_v1_self_test_ok")
