"""ITI job timing facts. Recorded values only. Do not invent totals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from roller.jump.library import default_library_root

STAGE_KEYS = (
    "compile_ms",
    "execute_ms",
    "lab_ms",
    "base_ms",
    "debase_ms",
    "slot_ms",
)


def job_dir(run_id: str, *, root: Path | None = None) -> Path:
    return (root or default_library_root()) / run_id


def timings_path(run_id: str, *, root: Path | None = None) -> Path:
    return job_dir(run_id, root=root) / "timings.json"


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def summarize_timings(job: dict[str, Any]) -> dict[str, Any]:
    slots = list(job.get("slots") or [])
    rows: list[dict[str, Any]] = []
    sums = {key: 0 for key in STAGE_KEYS}
    present = {key: 0 for key in STAGE_KEYS}
    for slot in slots:
        row = {
            "slot_id": slot.get("slot_id"),
            "status": slot.get("status"),
            "skip_reason": slot.get("skip_reason"),
            "reused_source": bool(slot.get("reused_source")),
            "executed": bool(slot.get("executed")),
            "population": slot.get("population"),
            "result_hash": slot.get("result_hash"),
            "BASE_GRADE": slot.get("BASE_GRADE"),
            "DEBASE_GRADE": slot.get("DEBASE_GRADE"),
        }
        for key in STAGE_KEYS:
            ms = _int_or_none(slot.get(key))
            row[key] = ms
            if ms is not None:
                sums[key] += ms
                present[key] += 1
        rows.append(row)
    return {
        "run_id": job.get("run_id"),
        "status": job.get("status"),
        "orchestrator": job.get("orchestrator"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "job_ms": _int_or_none(job.get("job_ms")),
        "slot_n": len(slots),
        "complete_n": sum(1 for s in slots if s.get("status") == "COMPLETE"),
        "skipped_n": sum(1 for s in slots if s.get("status") == "SKIPPED"),
        "reused_n": sum(1 for s in slots if s.get("reused_source")),
        "sums_ms": sums,
        "stages_present": present,
        "slots": rows,
    }


def write_timing_facts(job: dict[str, Any], *, root: Path | None = None) -> Path:
    run_id = str(job["run_id"])
    dest = timings_path(run_id, root=root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    facts = summarize_timings(job)
    dest.write_text(json.dumps(facts, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return dest
