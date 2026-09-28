"""Append-only provenance for ingest and derived artifacts. Never synthesize sources."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    tmp.replace(path)


def record_provenance(
    path: Path,
    *,
    source: str,
    action: str,
    season: str,
    league: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rec = {
        "source": source,
        "action": action,
        "league": league,
        "season": season,
        "download_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": "terminal_efficiency.provenance.1",
    }
    if extra:
        rec.update(extra)
    write_json(path, rec)
    return rec


def data_gap(
    *,
    source: str,
    required_field: str,
    why: str,
    future_source: str,
    impact: str,
) -> dict[str, str]:
    return {
        "status": "DATA_GAP",
        "source": source,
        "required_field": required_field,
        "why_unavailable": why,
        "potential_future_source": future_source,
        "impact_on_model": impact,
    }
