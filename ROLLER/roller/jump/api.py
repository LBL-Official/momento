"""Jump HTTP handlers. Mounted on the ROLLER terminal API."""

from __future__ import annotations

from typing import Any

from roller.jump.bots.api import (
    handle_avatar as handle_bots_avatar,
    handle_create as handle_bots_create,
    handle_draft as handle_bots_draft,
    handle_get as handle_bots_get,
    handle_iti_commits as handle_iti_commits,
    handle_list as handle_bots_list,
    handle_production as handle_bots_production,
    handle_profile as handle_bots_profile,
    handle_trades as handle_bots_trades,
)
from roller.jump.catalog.api import handle_catalog as handle_catalog
from roller.jump.catalog.api import handle_refresh as handle_catalog_refresh
from roller.jump.catalog.connection import handle_status as handle_kalshi_status
from roller.jump.catalog.connection import handle_sync as handle_kalshi_sync
from roller.jump.catalog.mybots import handle_mybots as handle_mybots
from roller.jump.dashboard.api import handle_dashboard as handle_dashboard
from roller.jump.dashboard.api import handle_logs as handle_dashboard_logs
from roller.jump.errors import JumpError
from roller.jump.iti.pipeline import start_run
from roller.jump.iti.store import commit_slot, latest_job, list_jobs, load_job, public_job
from roller.jump.library import default_library_root, list_items
from roller.jump.versions import (
    CAVEATS,
    CODE_VERSION,
    HONESTY,
    LIVE_EXECUTION,
    PHASE_STATUS,
    SCHEMA_VERSION,
)


def handle_health(*, root=None) -> dict[str, Any]:
    items = list_items(root=root)
    return {
        "status": "ok",
        "product": "Jump",
        "role": "data_modeling_drive",
        "bot_ui": False,
        "code_version": CODE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "phases": dict(PHASE_STATUS),
        "library_n": len(items),
        "library_path": str(root or default_library_root()),
        "live_execution": LIVE_EXECUTION,
        "honesty": HONESTY,
        "caveats": list(CAVEATS),
    }


def handle_research_context_austin(trade_id: str | None = None, as_of: str | None = None) -> dict[str, Any]:
    from roller.jump.adapters.austin import research_context

    return research_context(trade_id=trade_id, as_of=as_of)


def handle_research_context_choosin() -> dict[str, Any]:
    from roller.jump.adapters.choosin import research_context

    return research_context()


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


def handle_drive_root(sport: str | None = None) -> dict[str, Any]:
    from roller.jump.drive import handle_root

    return handle_root(sport)


def handle_drive_tree() -> dict[str, Any]:
    from roller.jump.drive import handle_tree

    return handle_tree()


def handle_drive_folder(folder_id: str) -> dict[str, Any]:
    from roller.jump.drive import handle_folder

    return handle_folder(folder_id)


def handle_drive_artifacts() -> dict[str, Any]:
    from roller.jump.drive import build_index, handle_recent

    index = build_index()
    return {
        "count": len(index),
        "recent": handle_recent(),
        "live_execution": LIVE_EXECUTION,
    }


def handle_drive_artifact(artifact_id: str) -> dict[str, Any]:
    from roller.jump.drive import handle_artifact

    return handle_artifact(artifact_id)


def handle_drive_search(q: str) -> dict[str, Any]:
    from roller.jump.drive import handle_search

    return handle_search(q)


def handle_drive_recent() -> dict[str, Any]:
    from roller.jump.drive import handle_recent

    return handle_recent()


def handle_drive_edges(artifact_id: str, direction: str) -> dict[str, Any]:
    from roller.jump.drive import handle_edges

    return handle_edges(artifact_id, direction)


def handle_drive_sports() -> dict[str, Any]:
    from roller.jump.drive import handle_sports

    return handle_sports()


def handle_drive_research(sport: str | None = None) -> dict[str, Any]:
    from roller.jump.drive import handle_research

    return handle_research(sport)


def handle_drive_research_object(canonical_key: str) -> dict[str, Any]:
    from roller.jump.drive import handle_research_object

    return handle_research_object(canonical_key)


def handle_drive_research_children(canonical_key: str) -> dict[str, Any]:
    from roller.jump.drive import handle_research_children

    return handle_research_children(canonical_key)


def handle_drive_document(doc_id: str) -> dict[str, Any]:
    from roller.jump.drive import handle_document

    return handle_document(doc_id)


def handle_drive_preview(artifact_id: str) -> dict[str, Any]:
    from roller.jump.drive import handle_preview

    return handle_preview(artifact_id)


def handle_drive_refresh() -> dict[str, Any]:
    from roller.jump.drive import handle_refresh

    return handle_refresh()


__all__ = [
    "handle_health",
    "handle_drive_root",
    "handle_drive_tree",
    "handle_drive_folder",
    "handle_drive_artifacts",
    "handle_drive_artifact",
    "handle_drive_search",
    "handle_drive_recent",
    "handle_drive_edges",
    "handle_drive_sports",
    "handle_drive_research",
    "handle_drive_research_object",
    "handle_drive_research_children",
    "handle_drive_document",
    "handle_drive_preview",
    "handle_drive_refresh",
    "handle_iti_run",
    "handle_iti_get",
    "handle_iti_list",
    "handle_iti_commit",
    "handle_iti_commits",
    "handle_bots_list",
    "handle_bots_get",
    "handle_bots_draft",
    "handle_bots_create",
    "handle_bots_production",
    "handle_bots_profile",
    "handle_bots_avatar",
    "handle_bots_trades",
    "handle_dashboard",
    "handle_dashboard_logs",
    "handle_catalog",
    "handle_catalog_refresh",
    "handle_kalshi_status",
    "handle_kalshi_sync",
    "handle_mybots",
]
