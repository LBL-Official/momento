"""Raw pointer + hash manifests. Warehouse files are never overwritten."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.io_csv import sha256_file, write_json
from roller.timeutil import now_utc_iso


def pointer_record(source_path: Path, role: str, ingested_at: str | None = None) -> dict[str, Any]:
    rec = {
        "source_path": str(source_path),
        "source_identifier": source_path.name,
        "role": role,
        "exists": source_path.is_file(),
        "ingested_at": ingested_at or now_utc_iso(),
    }
    if source_path.is_file():
        rec["source_hash"] = sha256_file(source_path)
        rec["source_bytes"] = source_path.stat().st_size
    else:
        rec["source_hash"] = ""
        rec["source_bytes"] = 0
    return rec


def write_manifest(path: Path, records: list[dict[str, Any]]) -> None:
    write_json(path, {"records": records, "written_at": now_utc_iso()})
