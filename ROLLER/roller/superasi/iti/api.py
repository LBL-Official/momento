"""SuperASI ITI HTTP handlers. Canonical ITI home after Final Results."""

from __future__ import annotations

from typing import Any

from roller.jump.errors import JumpError
from roller.superasi.iti.pipeline import start_run
from roller.superasi.iti.store import commit_slot, latest_job, list_jobs, load_job, public_job


def handle_iti_run(body: dict[str, Any] | None = None, *, root=None, cfg=None, background: bool = True) -> dict[str, Any]:
    body = body or {}
    debase_id = str(body.get("debase_result_id") or "").strip()
    if not debase_id:
        raise JumpError("RESULT_NOT_FOUND", "debase_result_id is required")
    paths = body.get("monte_carlo_paths")
    orchestrator = body.get("orchestrator")
    reuse = body.get("reuse_control")
    return start_run(
        debase_result_id=debase_id,
        root=root,
        cfg=cfg,
        background=background,
        monte_carlo_paths=int(paths) if paths else None,
        orchestrator=str(orchestrator) if orchestrator else None,
        reuse_control=bool(reuse) if reuse is not None else None,
    )


def handle_iti_get(run_id: str, *, root=None) -> dict[str, Any]:
    return public_job(load_job(run_id, root=root))


def handle_iti_list(debase_result_id: str | None = None, *, root=None) -> dict[str, Any]:
    wanted = str(debase_result_id or "").strip()
    if wanted:
        job = latest_job(debase_result_id=wanted, root=root)
        return {"results": [job] if job else [], "latest": job}
    return {"results": list_jobs(root=root), "latest": None}


def handle_iti_commit(run_id: str, body: dict[str, Any] | None = None, *, root=None, cfg=None) -> dict[str, Any]:
    body = body or {}
    slot_id = str(body.get("slot_id") or "").strip()
    if not slot_id:
        raise JumpError("INVALID_SLOT", "slot_id is required")
    return commit_slot(run_id, slot_id, root=root, cfg=cfg)
