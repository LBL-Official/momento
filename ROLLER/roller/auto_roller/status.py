"""Server-authoritative Auto Roller status."""

from __future__ import annotations

from typing import Any

from roller.auto_roller.history import latest, list_runs
from roller.config import RollerConfig
from roller.warehouse.catalog import UNAVAILABLE_SPORTS, catalog
from roller.warehouse.gap_audit import run_audit


def status_payload(cfg: RollerConfig | None = None) -> dict[str, Any]:
    cfg = cfg or RollerConfig()
    ingest = latest("ingest", cfg)
    verify = latest("verify", cfg)
    return {
        "display": {"ingest": "AUTO ROLLER INGEST", "verify": "AUTO ROLLER VERIFY"},
        "ingest": ingest,
        "verify": verify,
        "history": list_runs(cfg, limit=20),
        "unavailable_sports": list(UNAVAILABLE_SPORTS),
        "declared_seasons": [
            {"sport": s.sport, "season": s.season, "root_exists": s.root.is_dir()} for s in catalog(cfg)
        ],
    }


def coverage_payload(cfg: RollerConfig | None = None) -> dict[str, Any]:
    return run_audit(cfg)
