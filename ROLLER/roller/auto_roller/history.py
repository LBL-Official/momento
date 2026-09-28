"""Immutable Auto Roller run history."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.config import RollerConfig


def history_dir(cfg: RollerConfig | None = None) -> Path:
    cfg = cfg or RollerConfig()
    dest = cfg.root / "data" / ".cache" / "auto_roller" / "runs"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def new_run_id() -> str:
    return uuid.uuid4().hex


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_run(record: dict[str, Any], cfg: RollerConfig | None = None) -> Path:
    dest = history_dir(cfg) / f"{record['started_at'].replace(':', '')}_{record['run_id']}.json"
    dest.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dest


def list_runs(cfg: RollerConfig | None = None, *, limit: int = 50) -> list[dict[str, Any]]:
    files = sorted(history_dir(cfg).glob("*.json"), reverse=True)
    out: list[dict[str, Any]] = []
    for path in files[:limit]:
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def latest(job_type: str | None = None, cfg: RollerConfig | None = None) -> dict[str, Any] | None:
    for rec in list_runs(cfg, limit=200):
        if job_type is None or rec.get("job_type") == job_type:
            return rec
    return None
