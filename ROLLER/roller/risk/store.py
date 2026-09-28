"""Persist risk results separately from research Labs CSV."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.config import RollerConfig


def risk_root(cfg: RollerConfig | None = None) -> Path:
    cfg = cfg or RollerConfig()
    return Path(cfg.root) / "risk_results"


def save_risk_result(payload: dict[str, Any], cfg: RollerConfig | None = None) -> dict[str, Any]:
    cfg = cfg or RollerConfig()
    risk_id = uuid.uuid4().hex
    dest = risk_root(cfg) / risk_id
    dest.mkdir(parents=True, exist_ok=True)
    rec = {
        **payload,
        "risk_id": risk_id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "artifact": "risk_result",
    }
    (dest / "risk_result.json").write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"risk_id": risk_id, "risk_result_hash": rec.get("risk_result_hash"), "created_at": rec["created_at"]}
