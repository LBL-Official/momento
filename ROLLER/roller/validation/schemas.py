"""Schema helpers for registry-driven validation."""

from __future__ import annotations

from roller.config import RollerConfig


def expected_columns(cfg: RollerConfig, dataset: str) -> list[str]:
    spec = cfg.schemas.get("datasets", {}).get(dataset) or {}
    return list(spec.get("columns") or [])
