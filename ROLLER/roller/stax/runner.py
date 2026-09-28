"""Commit STAX executions to immutable versions."""

from __future__ import annotations

import uuid
from typing import Any, Callable

from roller.stax.compatibility import canonicalize_universe
from roller.stax.executor import execute_stack
from roller.stax.library import load_head, load_version, write_head, write_version
from roller.stax.membership import assert_members_share_universe, definition_hash
from roller.stax.models import utc_now
from roller.stax.provenance import stack_provenance
from roller.stax.versioning import next_version_record
from roller.stax.versions import AGGREGATION_METHOD, DEFAULT_TIMEZONE, LIVE_EXECUTION


def latest_version_record(head: dict[str, Any], *, root=None) -> dict[str, Any] | None:
    ver = head.get("latest_version")
    if not ver:
        return None
    return load_version(str(head["stax_id"]), str(ver), root=root)


def persist_run(
    stax_id: str,
    members: list[dict[str, Any]],
    *,
    root=None,
    automated: bool = False,
    execute_fn: Callable[..., dict[str, Any]] | None = None,
    execute_question=None,
    execute_research_object=None,
) -> dict[str, Any]:
    head = load_head(stax_id, root=root)
    universe = assert_members_share_universe(members)
    started = utc_now()
    if execute_fn is not None:
        execution = execute_fn(members)
    else:
        execution = execute_stack(
            members,
            execute_question=execute_question,
            execute_research_object=execute_research_object,
        )
    execution_id = uuid.uuid4().hex
    execution["execution_id"] = execution_id
    execution["started_at"] = started
    execution["completed_at"] = utc_now()
    def_hash = execution.get("definition_hash") or definition_hash(members)
    dataset_fp = execution.get("dataset_fingerprint") or ""
    parent = latest_version_record(head, root=root)
    bump = next_version_record(
        parent,
        definition_hash_value=def_hash,
        dataset_fingerprint=dataset_fp,
    )
    if bump is None and parent is not None:
        return {
            **parent,
            "unchanged": True,
            "execution_id": execution_id,
            "message": "definition and dataset unchanged — no new version",
        }
    if bump is None:
        bump = {
            "version": "1.0.0",
            "kind": "MINOR",
            "parent_version": None,
            "definition_hash": def_hash,
            "dataset_fingerprint": dataset_fp,
        }
    created = utc_now()
    enriched_members = []
    for member in members:
        rec = dict(member)
        match = next((r for r in execution["results"] if r.get("member_id") == member["member_id"]), None)
        if match:
            summary = match.get("summary") or {}
            rec["status"] = match.get("status")
            rec["dataset_hash"] = summary.get("dataset_version")
            rec["dataset_version"] = summary.get("dataset_version")
            rec["query_hash"] = summary.get("question_hash") or rec.get("query_hash")
            rec["question_hash"] = summary.get("question_hash") or rec.get("question_hash")
            rec["research_object_id"] = summary.get("research_object_id") or rec.get("research_object_id")
        enriched_members.append(rec)
    provenance = stack_provenance(
        stax_id=stax_id,
        version=bump["version"],
        created_at=created,
        executed_at=execution["completed_at"],
        timezone=str(head.get("timezone") or DEFAULT_TIMEZONE),
        members=enriched_members,
        results=execution["results"],
        execution_status=execution["status"],
        automation_status="ACTIVE" if automated else "OFF",
        overlap_method=(execution.get("overlap") or {}).get("overlap_method") or "UNAVAILABLE",
    )
    record = {
        "stax_id": stax_id,
        "version": bump["version"],
        "kind": bump["kind"],
        "parent_version": bump["parent_version"],
        "created_at": created,
        "executed_at": execution["completed_at"],
        "execution_id": execution_id,
        "status": execution["status"],
        "definition_hash": def_hash,
        "dataset_fingerprint": dataset_fp,
        "strategy_count": execution["strategy_count"],
        "completed_count": execution["completed_count"],
        "failed_count": execution["failed_count"],
        "sum_of_strategy_n": execution.get("sum_of_strategy_n"),
        "sum_of_strategy_n_label": execution.get("sum_of_strategy_n_label"),
        "aggregation_method": AGGREGATION_METHOD,
        "live_execution": LIVE_EXECUTION,
        "automated": automated,
        "universe": universe.to_dict(),
        "members": enriched_members,
        "results": execution["results"],
        "overlap": execution.get("overlap") or {},
        "provenance": provenance,
        "execution": {
            "execution_id": execution_id,
            "started_at": started,
            "completed_at": execution["completed_at"],
            "status": execution["status"],
            "automated": automated,
        },
    }
    write_version(stax_id, record, root=root)
    head = load_head(stax_id, root=root)
    head["latest_version"] = bump["version"]
    head["latest_status"] = execution["status"]
    head["last_run_at"] = execution["completed_at"]
    head["universe"] = universe.to_dict()
    head["working_members"] = enriched_members
    head["updated_at"] = utc_now()
    write_head(head, root=root)
    return record


def run_stax(
    stax_id: str,
    *,
    root=None,
    automated: bool = False,
    execute_question=None,
    execute_research_object=None,
) -> dict[str, Any]:
    head = load_head(stax_id, root=root)
    members = list(head.get("working_members") or [])
    if not members:
        from roller.stax.models import StaxError

        raise StaxError("STAX_EMPTY", "STAX has no strategies")
    for member in members:
        canonicalize_universe(member["universe"])
    return persist_run(
        stax_id,
        members,
        root=root,
        automated=automated,
        execute_question=execute_question,
        execute_research_object=execute_research_object,
    )
