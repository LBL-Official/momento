"""STAX provenance. No invented aggregate statistic."""

from __future__ import annotations

from typing import Any

from roller.stax.versions import (
    AGGREGATION_METHOD,
    CODE_VERSION,
    LIVE_EXECUTION,
    STAX_SCHEMA,
)


def member_provenance(member: dict[str, Any], result: dict[str, Any] | None = None) -> dict[str, Any]:
    result = result or {}
    hashes = result.get("hashes") if isinstance(result.get("hashes"), dict) else {}
    return {
        "member_id": member.get("member_id"),
        "position": member.get("position"),
        "display_id": member.get("display_id"),
        "roller_object_id": member.get("roller_object_id") or member.get("save_id"),
        "research_object_id": result.get("research_object_id") or member.get("research_object_id"),
        "roller_result_id": result.get("roller_result_id") or member.get("roller_result_id"),
        "query_hash": hashes.get("question_hash") or member.get("query_hash") or member.get("question_hash"),
        "dataset_hash": result.get("dataset_version") or member.get("dataset_hash"),
        "definition_version": member.get("definition_version") or "1.0.0",
        "question_hash": hashes.get("question_hash") or member.get("question_hash"),
        "execution_status": result.get("execution_status") or member.get("status"),
    }


def stack_provenance(
    *,
    stax_id: str,
    version: str,
    created_at: str,
    executed_at: str | None,
    timezone: str,
    members: list[dict[str, Any]],
    results: list[dict[str, Any]] | None = None,
    execution_status: str,
    automation_status: str | None,
    overlap_method: str,
) -> dict[str, Any]:
    results = results or []
    by_id = {r.get("member_id"): r for r in results if r.get("member_id")}
    return {
        "stax_schema_version": STAX_SCHEMA,
        "stax_code_version": CODE_VERSION,
        "stax_id": stax_id,
        "stax_version": version,
        "created_at": created_at,
        "executed_at": executed_at,
        "timezone": timezone,
        "strategy_count": len(members),
        "members": [member_provenance(m, by_id.get(m.get("member_id")) or {}) for m in members],
        "execution_status": execution_status,
        "automation_status": automation_status,
        "overlap_method": overlap_method,
        "aggregation_method": AGGREGATION_METHOD,
        "live_execution": LIVE_EXECUTION,
    }
