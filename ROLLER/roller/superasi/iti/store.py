"""ITI job + commit store. Jobs live in the Jump library. Commit nests under Phase B."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.config import RollerConfig
from roller.jump.errors import JumpError
from roller.superasi.iti.rank import recommend_slot_id
from roller.superasi.iti.versions import CAVEATS, HONESTY, ITI_VERSION
from roller.jump.library import default_library_root
from roller.labs.schema import csv_filename as roller_csv_filename
from roller.labs.schema import sanitize_name
from roller.labs.store import get_lab_csv_bytes
from roller.superasi.base.export_csv import csv_filename as abase_csv_filename
from roller.superasi.base.store import get_base_csv_bytes
from roller.superasi.debase.export_csv import csv_filename as debase_csv_filename
from roller.superasi.debase import store as debase_store
from roller.superasi.debase.store import get_debase_csv_bytes


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def job_dir(run_id: str, *, root: Path | None = None) -> Path:
    return (root or default_library_root()) / run_id


def job_path(run_id: str, *, root: Path | None = None) -> Path:
    return job_dir(run_id, root=root) / "job.json"


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="jump_iti_", dir=str(path.parent))) / "job.json"
    tmp.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    tmp.parent.rmdir()


def load_job(run_id: str, *, root: Path | None = None) -> dict[str, Any]:
    path = job_path(run_id, root=root)
    if not path.is_file():
        raise JumpError("RUN_NOT_FOUND", f"ITI run not found: {run_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_job(job: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    run_id = str(job["run_id"])
    job["recommended_slot_id"] = recommend_slot_id(list(job.get("slots") or []))
    job["updated_at"] = _utc_now()
    _write_json(job_path(run_id, root=root), job)
    return job


def create_job(
    *,
    source: dict[str, Any],
    slots: list[dict[str, Any]],
    root: Path | None = None,
) -> dict[str, Any]:
    run_id = uuid.uuid4().hex
    job = {
        "run_id": run_id,
        "status": "PENDING",
        "iti_version": ITI_VERSION,
        "debase_result_id": source["debase_result_id"],
        "source_folder": source["source_folder"],
        "source_lab_id": source["source_lab_id"],
        "strategy_name": source["strategy_name"],
        "source_question_sha256": slots[0]["source_question_sha256"] if slots else "",
        "source_snapshot": dict(source.get("snapshot") or {}),
        "orchestrator": None,
        "job_ms": None,
        "slots": slots,
        "slot_n": len(slots),
        "progress_done": 0,
        "recommended_slot_id": None,
        "committed_slot_id": None,
        "commit_path": None,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "cancel_requested": False,
        "honesty": dict(HONESTY),
        "caveats": list(CAVEATS),
        "live_execution": False,
    }
    save_job(job, root=root)
    return job


def public_job(job: dict[str, Any]) -> dict[str, Any]:
    slots = []
    for slot in job.get("slots") or []:
        row = {k: v for k, v in slot.items() if k != "question"}
        slots.append(row)
    out = dict(job)
    out["slots"] = slots
    out["recommended_slot_id"] = recommend_slot_id(list(job.get("slots") or []))
    return out


def list_jobs(*, root: Path | None = None, debase_result_id: str | None = None) -> list[dict[str, Any]]:
    base = root or default_library_root()
    if not base.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for child in sorted(base.iterdir()):
        if child.name.startswith(".") or not child.is_dir():
            continue
        path = child / "job.json"
        if not path.is_file():
            continue
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if debase_result_id and str(job.get("debase_result_id") or "") != debase_result_id:
            continue
        items.append(public_job(job))
    items.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
    return items


def latest_job(*, debase_result_id: str, root: Path | None = None) -> dict[str, Any] | None:
    items = list_jobs(root=root, debase_result_id=debase_result_id)
    return items[0] if items else None


def request_cancel(run_id: str, *, root: Path | None = None) -> dict[str, Any]:
    job = load_job(run_id, root=root)
    job["cancel_requested"] = True
    if job.get("status") in {"PENDING", "RUNNING"}:
        job["status"] = "CANCELLED"
    return save_job(job, root=root)


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def commit_slot(
    run_id: str,
    slot_id: str,
    *,
    root: Path | None = None,
    cfg: RollerConfig | None = None,
) -> dict[str, Any]:
    job = load_job(run_id, root=root)
    slot = next((s for s in job.get("slots") or [] if s.get("slot_id") == slot_id), None)
    if slot is None:
        raise JumpError("INVALID_SLOT", f"unknown ITI slot {slot_id}")
    if slot.get("status") != "COMPLETE":
        raise JumpError("SLOT_NOT_COMPLETE", f"slot {slot_id} is {slot.get('status')}; not committed")
    strategy = sanitize_name(f"{job['strategy_name']}_ITI")
    parent = debase_store.phase_b_root(cfg) / str(job["source_folder"])
    if not parent.is_dir():
        raise JumpError("RESULT_NOT_FOUND", f"source Phase B folder missing: {parent}")
    dest = parent / strategy
    dest.mkdir(parents=True, exist_ok=True)

    lab_bytes = get_lab_csv_bytes(str(slot.get("lab_id") or ""), cfg)
    abase = get_base_csv_bytes(str(slot.get("phase_a_result_id") or ""), which="base", cfg=cfg)
    debase = get_debase_csv_bytes(str(slot.get("phase_b_result_id") or ""), which="debase", cfg=cfg)
    if lab_bytes is None or abase is None or debase is None:
        raise JumpError("SLOT_NOT_COMPLETE", "variant CSVs are missing; commit fails closed")

    roller_name = roller_csv_filename(strategy)
    abase_name = abase_csv_filename(strategy)
    debase_name = debase_csv_filename(strategy)
    _write_bytes(dest / roller_name.replace(".csv", "") / roller_name, lab_bytes[1])
    _write_bytes(dest / abase_name.replace(".csv", "") / abase_name, abase[1])
    _write_bytes(dest / debase_name.replace(".csv", "") / debase_name, debase[1])

    metadata = {
        "artifact": "jump_iti",
        "iti_version": ITI_VERSION,
        "run_id": run_id,
        "slot_id": slot_id,
        "strategy_name": strategy,
        "source_folder": job["source_folder"],
        "source_debase_result_id": job["debase_result_id"],
        "lab_id": slot.get("lab_id"),
        "phase_a_result_id": slot.get("phase_a_result_id"),
        "phase_b_result_id": slot.get("phase_b_result_id"),
        "BASE_GRADE": slot.get("BASE_GRADE"),
        "DEBASE_GRADE": slot.get("DEBASE_GRADE"),
        "population": slot.get("population"),
        "entry_cents": slot.get("entry_cents"),
        "win_cents": slot.get("win_cents"),
        "loss_cents": slot.get("loss_cents"),
        "question": slot.get("question") if isinstance(slot.get("question"), dict) else None,
        "engine_kind": "research_iti",
        "created_at": _utc_now(),
        "honesty": dict(HONESTY),
        "live_execution": False,
        "files": {
            "roller": f"{roller_name.replace('.csv', '')}/{roller_name}",
            "abase": f"{abase_name.replace('.csv', '')}/{abase_name}",
            "debase": f"{debase_name.replace('.csv', '')}/{debase_name}",
        },
    }
    (dest / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    job["committed_slot_id"] = slot_id
    job["commit_path"] = str(dest)
    save_job(job, root=root)
    iti_folder = f"{job['source_folder']}/{strategy}"
    return {**metadata, "path": str(dest), "iti_folder": iti_folder, "run": public_job(job)}
