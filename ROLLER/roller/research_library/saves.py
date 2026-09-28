"""Persist named result snapshots on disk.

localStorage cannot hold a full N-row envelope. The browser stores metadata;
this module stores the measurement.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]


def saves_dir() -> Path:
    raw = os.environ.get("ROLLER_LIBRARY_DIR")
    if raw:
        return Path(raw)
    return _REPO / "data" / ".cache" / "research_saves"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_save(body: dict[str, Any]) -> dict[str, Any]:
    save_id = str(body.get("id") or uuid.uuid4().hex)
    result = body.get("result") if isinstance(body.get("result"), dict) else {}
    pop = result.get("population") if isinstance(result.get("population"), dict) else {}
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    n = pop.get("count")
    if n is None:
        n = summary.get("population_n")
    hashes = body.get("hashes") if isinstance(body.get("hashes"), dict) else {}
    result_hashes = result.get("hashes") if isinstance(result.get("hashes"), dict) else {}
    if not hashes.get("question_hash") and result_hashes:
        hashes = {**result_hashes, **hashes}
    record = {
        "id": save_id,
        "name": str(body.get("name") or "Untitled result").strip() or "Untitled result",
        "folder": str(body.get("folder") or "Experimental"),
        "description": str(body.get("description") or ""),
        "question": str(body.get("question") or ""),
        "saved_at": _now(),
        "population_n": n,
        "execution_status": result.get("execution_status"),
        "hashes": hashes,
        "workflow_draft": body.get("workflow_draft") or body.get("draft"),
        "research_spec": body.get("research_spec") if isinstance(body.get("research_spec"), dict) else {},
        "result": result,
    }
    root = saves_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{save_id}.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return {
        "id": save_id,
        "name": record["name"],
        "folder": record["folder"],
        "description": record["description"],
        "saved_at": record["saved_at"],
        "population_n": record["population_n"],
        "execution_status": record["execution_status"],
        "path": str(path),
        "message": "RESULT SAVED",
    }


def list_saves() -> list[dict[str, Any]]:
    root = saves_dir()
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items.append(
            {
                "id": rec.get("id") or path.stem,
                "name": rec.get("name"),
                "folder": rec.get("folder"),
                "description": rec.get("description"),
                "saved_at": rec.get("saved_at"),
                "population_n": rec.get("population_n"),
                "execution_status": rec.get("execution_status"),
            }
        )
    return items


def load_save(save_id: str) -> dict[str, Any] | None:
    path = saves_dir() / f"{save_id}.json"
    if not path.is_file():
        return None
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return rec if isinstance(rec, dict) else None
