"""Explicit dataset export. Jump does not become the owner."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from roller.jump.data.adapters import austin
from roller.jump.data.models import HANDLE_SCHEMA, LIVE_EXECUTION, now_iso
from roller.jump.errors import JumpError
from roller.jump.library import repo_root


def export_dir() -> Path:
    root = repo_root() / "research" / "jump" / "exports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def dataset_handles() -> list[dict[str, Any]]:
    from roller.jump.data.adapters.roller import dataset_handle
    from roller.systimo.store import CsvStore

    rows = []
    for item in CsvStore().read("datasets"):
        rows.append(
            {
                "schema": HANDLE_SCHEMA,
                "dataset_id": item["dataset_id"],
                "owner": item["owner_system_id"],
                "name": item.get("name"),
                "universe": item.get("universe"),
                "row_count": item.get("n_expected"),
                "location": item.get("location"),
                "schema_version": item.get("schema_version"),
                "query_capabilities": [],
                "filters_supported": ["trade_id", "as_of"],
                "copy": False,
            }
        )
    rows.append(dataset_handle({}))
    return rows


def export_dataset(dataset_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(params or {})
    wanted = str(dataset_id or "").strip()
    if wanted in {"austin_nba_2q3q_604", "austin"}:
        body = austin.list_universe()
        if body.get("availability") != "OBSERVED":
            raise JumpError("UNAVAILABLE", body.get("detail") or "Austin universe UNAVAILABLE")
        artifact_id = uuid.uuid4().hex[:16]
        created = now_iso()
        record = {
            "artifact_id": artifact_id,
            "dataset_id": "austin_nba_2q3q_604",
            "owner": "austin",
            "consumer": "jump",
            "n": body.get("n"),
            "n_lock": body.get("n_lock"),
            "universe": body.get("universe"),
            "trade_ids": body.get("trade_ids"),
            "created_at": created,
            "copy": False,
            "source_location": "ROLLER/roller/austin/",
            "live_execution": LIVE_EXECUTION,
        }
        raw = json.dumps(record, indent=2, sort_keys=True) + "\n"
        checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        rel = f"{artifact_id}.json"
        path = export_dir() / rel
        path.write_text(raw, encoding="utf-8")
        systimo_artifact = _systimo_export_record(
            dataset_id="austin_nba_2q3q_604",
            checksum=checksum,
            path=rel,
            payload={"n": body.get("n"), "universe": body.get("universe")},
        )
        return {
            "schema": "jump.export.v0",
            "artifact_id": artifact_id,
            "dataset_id": "austin_nba_2q3q_604",
            "owner": "austin",
            "checksum": checksum,
            "path": str(path),
            "systimo": systimo_artifact,
            "copy": False,
            "live_execution": LIVE_EXECUTION,
        }
    if wanted.startswith("roller") or wanted == "nba":
        from roller.jump.data.adapters.roller import dataset_handle

        handle = dataset_handle({"warehouse_id": "nba"})
        artifact_id = uuid.uuid4().hex[:16]
        record = {
            "artifact_id": artifact_id,
            "dataset_id": handle.get("dataset_id"),
            "owner": "roller",
            "export_kind": "manifest_plus_partitions",
            "handle": handle,
            "created_at": now_iso(),
            "copy": False,
            "note": "ROLLER export is a pointer + partition references. Jump does not copy parquet.",
            "live_execution": LIVE_EXECUTION,
        }
        raw = json.dumps(record, indent=2, sort_keys=True) + "\n"
        checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        path = export_dir() / f"{artifact_id}.json"
        path.write_text(raw, encoding="utf-8")
        return {
            "schema": "jump.export.v0",
            "artifact_id": artifact_id,
            "dataset_id": handle.get("dataset_id"),
            "owner": "roller",
            "checksum": checksum,
            "path": str(path),
            "copy": False,
            "live_execution": LIVE_EXECUTION,
        }
    raise JumpError("UNKNOWN_DATASET", f"export not registered for {wanted}")


def _systimo_export_record(dataset_id: str, checksum: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    from roller.systimo.query.executor import execute
    from roller.systimo.artifacts.writer import save_artifact

    answer = execute(
        {
            "query_type": "datasets",
            "system": "austin" if "austin" in dataset_id else "roller",
            "requested_by": "jump.export",
            "export": {"dataset_id": dataset_id, "checksum": checksum, "path": path, **payload},
        }
    )
    saved = save_artifact(answer["query_id"], kind="json")
    return {"query_id": answer["query_id"], "artifact_id": saved.get("artifact_id"), "checksum": saved.get("checksum")}
