"""STAX HTTP handlers. Mounted on the ROLLER terminal API."""

from __future__ import annotations

from typing import Any

from roller.research_library.saves import list_saves, load_save
from roller.stax.automation import arm_automation, tick
from roller.stax.compatibility import universe_from_source
from roller.stax.create_strategy import handle_create_strategy
from roller.stax.library import (
    list_stax,
    list_versions,
    load_head,
    load_version,
    new_head,
    write_head,
)
from roller.stax.membership import (
    add_member,
    assert_members_share_universe,
    definition_hash,
    remove_member,
    reorder_members,
)
from roller.stax.models import StaxError, utc_now
from roller.stax.runner import persist_run, run_stax
from roller.stax.validation import reject_rolling_fields, require_name, strip_client_overrides
from roller.stax.versioning import compare_versions
from roller.stax.versions import (
    AGGREGATION_METHOD,
    CODE_VERSION,
    DEFAULT_TIMEZONE,
    LIVE_EXECUTION,
    STAX_SCHEMA,
)


def handle_create(body: dict[str, Any], *, root=None) -> dict[str, Any]:
    reject_rolling_fields(body)
    name = require_name(body.get("name"))
    head = new_head(
        name=name,
        description=str(body.get("description") or ""),
        timezone=str(body.get("timezone") or DEFAULT_TIMEZONE),
        root=root,
    )
    sources = list(body.get("members") or body.get("strategies") or [])
    members: list[dict[str, Any]] = []
    seq = 0
    for source in sources:
        if not isinstance(source, dict):
            continue
        seq += 1
        members = add_member(
            members,
            strip_client_overrides(source),
            stax_id=head["stax_id"],
            member_seq=seq,
        )
    if members:
        head["universe"] = assert_members_share_universe(members).to_dict()
    head["working_members"] = members
    head["member_seq"] = seq
    write_head(head, root=root)
    return {"stax": _public_head(head), "members": members}


def handle_list(*, root=None) -> dict[str, Any]:
    items = list_stax(root=root)
    return {"stax": items, "n": len(items)}


def handle_get(stax_id: str, *, root=None) -> dict[str, Any]:
    head = load_head(stax_id, root=root)
    latest = None
    if head.get("latest_version"):
        latest = load_version(stax_id, str(head["latest_version"]), root=root)
    return {
        "stax": _public_head(head),
        "members": head.get("working_members") or [],
        "latest": latest,
        "versions": list_versions(stax_id, root=root),
    }


def handle_versions(stax_id: str, *, root=None) -> dict[str, Any]:
    load_head(stax_id, root=root)
    items = list_versions(stax_id, root=root)
    return {"stax_id": stax_id, "versions": items, "n": len(items)}


def handle_version(stax_id: str, version: str, *, root=None) -> dict[str, Any]:
    return load_version(stax_id, version.lstrip("v"), root=root)


def handle_validate(stax_id: str, body: dict[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    body = body or {}
    reject_rolling_fields(body)
    head = load_head(stax_id, root=root)
    members = list(head.get("working_members") or [])
    if "members" in body or "add" in body or "remove" in body or "order" in body:
        members = list(head.get("working_members") or [])
        if body.get("replace"):
            members = []
        for source in body.get("members") or []:
            if not isinstance(source, dict):
                continue
            head["member_seq"] = int(head.get("member_seq") or 0) + 1
            members = add_member(
                members,
                strip_client_overrides(source),
                stax_id=stax_id,
                member_seq=head["member_seq"],
            )
        if body.get("add") and isinstance(body.get("add"), dict):
            head["member_seq"] = int(head.get("member_seq") or 0) + 1
            members = add_member(
                members,
                strip_client_overrides(body["add"]),
                stax_id=stax_id,
                member_seq=head["member_seq"],
            )
        if body.get("remove"):
            members = remove_member(members, str(body["remove"]), stax_id=stax_id)
        if body.get("order"):
            members = reorder_members(members, list(body["order"]), stax_id=stax_id)
        if members:
            head["universe"] = assert_members_share_universe(members).to_dict()
        else:
            head["universe"] = None
        head["working_members"] = members
        head["updated_at"] = utc_now()
        write_head(head, root=root)
    universe = head.get("universe")
    return {
        "ok": True,
        "universe": universe,
        "members": members,
        "definition_hash": definition_hash(members) if members else None,
        "message": "SPORT / LEAGUE / TIMEFRAME MATCH" if members else "EMPTY",
    }


def handle_run(stax_id: str, body: dict[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    body = strip_client_overrides(body or {})
    reject_rolling_fields(body)
    if body.get("members"):
        handle_validate(
            stax_id,
            {
                "replace": True,
                "members": [
                    strip_client_overrides(m) for m in body["members"] if isinstance(m, dict)
                ],
            },
            root=root,
        )
    return run_stax(stax_id, root=root, automated=bool(body.get("automated")))


def handle_automation(stax_id: str, body: dict[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    body = body or {}
    head = load_head(stax_id, root=root)
    enabled = body.get("enabled")
    if enabled is None:
        enabled = body.get("automation_enabled")
    if enabled is None:
        enabled = True
    head = arm_automation(
        head,
        enabled=bool(enabled),
        timezone_name=body.get("timezone"),
        schedule=body.get("schedule"),
    )
    write_head(head, root=root)
    from roller.stax.automation import ensure_loop

    if head.get("automation_enabled"):
        ensure_loop()
    return {
        "stax_id": stax_id,
        "automation_enabled": head.get("automation_enabled"),
        "timezone": head.get("timezone"),
        "schedule": head.get("automation_schedule"),
        "next_run_at": head.get("next_run_at"),
        "research_automation": True,
        "live_execution": LIVE_EXECUTION,
        "message": "RESEARCH AUTOMATION — NOT EXECUTION",
    }


def handle_compare(stax_id: str, body: dict[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    body = body or {}
    older_v = str(body.get("from") or body.get("older") or "")
    newer_v = str(body.get("to") or body.get("newer") or "")
    if not older_v or not newer_v:
        raise StaxError("STAX_COMPARE_INVALID", "from and to versions are required")
    older = load_version(stax_id, older_v.lstrip("v"), root=root)
    newer = load_version(stax_id, newer_v.lstrip("v"), root=root)
    return compare_versions(older, newer)


def handle_tick(*, root=None) -> dict[str, Any]:
    return tick(root=root)


def handle_create_in_stax(stax_id: str, body: dict[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    out = handle_create_strategy(stax_id, body, root=root)
    if out.get("persisted"):
        head = load_head(stax_id, root=root)
        out["stax"] = _public_head(head)
    return out


def handle_candidates() -> dict[str, Any]:
    items = []
    for meta in list_saves():
        rec = load_save(str(meta["id"]))
        if not rec:
            continue
        try:
            universe = universe_from_source(rec).to_dict()
        except Exception:
            universe = None
        result = rec.get("result") if isinstance(rec.get("result"), dict) else {}
        compile_block = result.get("compile") if isinstance(result.get("compile"), dict) else {}
        hashes = rec.get("hashes") if isinstance(rec.get("hashes"), dict) else {}
        items.append(
            {
                "save_id": rec.get("id"),
                "name": rec.get("name"),
                "population_n": rec.get("population_n"),
                "execution_status": rec.get("execution_status"),
                "saved_at": rec.get("saved_at"),
                "universe": universe,
                "research_object_id": result.get("research_object_id"),
                "question_hash": hashes.get("question_hash"),
                "question": compile_block.get("question"),
                "draft": rec.get("workflow_draft") or rec.get("draft"),
                "result": result,
                "hashes": hashes,
                "research_spec": rec.get("research_spec"),
            }
        )
    return {"candidates": items, "n": len(items)}


def handle_export(stax_id: str, version: str | None = None, *, root=None) -> dict[str, Any]:
    head = load_head(stax_id, root=root)
    ver = (version or head.get("latest_version") or "").lstrip("v")
    if not ver:
        raise StaxError("STAX_VERSION_NOT_FOUND", "no executed version to export")
    rec = load_version(stax_id, ver, root=root)
    return {
        "schema_version": "stax_result_package_v1",
        "stax_schema_version": STAX_SCHEMA,
        "stax_code_version": CODE_VERSION,
        "stax_id": stax_id,
        "stax_version": rec.get("version"),
        "name": head.get("name"),
        "universe": rec.get("universe") or head.get("universe"),
        "members": rec.get("members") or [],
        "results": rec.get("results") or [],
        "overlap": rec.get("overlap") or {},
        "provenance": rec.get("provenance") or {},
        "automation": {
            "enabled": head.get("automation_enabled"),
            "timezone": head.get("timezone"),
            "schedule": head.get("automation_schedule"),
            "last_run_at": head.get("last_run_at"),
        },
        "aggregation_method": AGGREGATION_METHOD,
        "live_execution": LIVE_EXECUTION,
        "note": "STAX result package. Strategies remain independent. SuperASI is downstream.",
    }


def error_payload(exc: StaxError, status_code: int = 400) -> tuple[int, dict[str, Any]]:
    return status_code, exc.as_dict()


def _public_head(head: dict[str, Any]) -> dict[str, Any]:
    return {
        "stax_id": head.get("stax_id"),
        "name": head.get("name"),
        "description": head.get("description"),
        "created_at": head.get("created_at"),
        "updated_at": head.get("updated_at"),
        "universe": head.get("universe"),
        "timezone": head.get("timezone"),
        "automation_enabled": head.get("automation_enabled"),
        "automation_schedule": head.get("automation_schedule"),
        "latest_version": head.get("latest_version"),
        "latest_status": head.get("latest_status"),
        "last_run_at": head.get("last_run_at"),
        "next_run_at": head.get("next_run_at"),
        "strategy_count": len(head.get("working_members") or []),
        "live_execution": LIVE_EXECUTION,
        "schema_version": head.get("schema_version") or STAX_SCHEMA,
    }
