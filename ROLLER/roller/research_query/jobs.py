"""Background research-query jobs.

Execute never occupies the FastAPI event loop or the default AnyIO thread pool.
/health and /compile stay reachable while a warehouse scan runs.
"""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="research-query")
_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def _now_ms() -> int:
    return int(time.time() * 1000)


def active_counts() -> dict[str, int]:
    with _LOCK:
        statuses = [str(j.get("status")) for j in _JOBS.values()]
    return {
        "queued": sum(1 for s in statuses if s == "queued"),
        "running": sum(1 for s in statuses if s == "running"),
        "complete": sum(1 for s in statuses if s == "complete"),
        "failed": sum(1 for s in statuses if s == "failed"),
    }


def submit_execute(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = uuid.uuid4().hex
    rec: dict[str, Any] = {
        "job_id": job_id,
        "status": "queued",
        "submitted_ms": _now_ms(),
        "started_ms": None,
        "finished_ms": None,
        "result": None,
        "error": None,
    }
    with _LOCK:
        _JOBS[job_id] = rec

    def run() -> None:
        rec["status"] = "running"
        rec["started_ms"] = _now_ms()
        try:
            from roller.research_query.execute import execute_question

            rec["result"] = execute_question(payload)
            rec["status"] = "complete"
        except Exception as exc:  # noqa: BLE001 — surface to the poller
            rec["status"] = "failed"
            rec["error"] = {"message": str(exc), "type": type(exc).__name__}
        rec["finished_ms"] = _now_ms()

    _POOL.submit(run)
    return job_public(rec)


def job_public(rec: dict[str, Any], *, include_result: bool = False) -> dict[str, Any]:
    out = {
        "job_id": rec["job_id"],
        "status": rec["status"],
        "submitted_ms": rec["submitted_ms"],
        "started_ms": rec["started_ms"],
        "finished_ms": rec["finished_ms"],
        "error": rec["error"],
    }
    if include_result and rec["status"] == "complete":
        out["result"] = rec["result"]
    return out


def get_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        rec = _JOBS.get(job_id)
        if rec is None:
            return None
        return job_public(rec, include_result=rec["status"] == "complete")
