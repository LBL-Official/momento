"""Human-readable Auto Roller reports. Failures are not hidden."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.config import RollerConfig


def reports_dir(cfg: RollerConfig | None = None) -> Path:
    cfg = cfg or RollerConfig()
    dest = cfg.root / "reports" / "auto_roller"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def write_report(name: str, payload: dict[str, Any], cfg: RollerConfig | None = None) -> Path:
    dest = reports_dir(cfg) / name
    import json

    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return dest
