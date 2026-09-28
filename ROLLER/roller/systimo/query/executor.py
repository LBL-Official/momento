"""Structured Systimo queries. No LLM. CSV + adapters."""

from __future__ import annotations

import json
import uuid
from typing import Any

from roller.systimo.errors import SystimoError
from roller.systimo.graph.build import path_back as graph_path_back
from roller.systimo.graph.build import paths as graph_paths
from roller.systimo.models import ANSWER_SCHEMA, QUERY_TYPES, now_iso
from roller.systimo.query.capabilities import invoke_capability
from roller.systimo.store import CsvStore


def _params(body: dict[str, Any] | None) -> dict[str, Any]:
    return body if isinstance(body, dict) else {}


def execute(body: dict[str, Any] | None, store: CsvStore | None = None) -> dict[str, Any]:
    csv = store or CsvStore()
    payload = _params(body)
    query_type = str(payload.get("query_type") or payload.get("type") or "").strip()
    if query_type not in QUERY_TYPES:
        raise SystimoError("UNKNOWN_QUERY_TYPE", f"query_type must be one of {QUERY_TYPES}")
    query_id = uuid.uuid4().hex[:16]
    requested = now_iso()
    csv.append(
        "queries",
        {
            "query_id": query_id,
            "query_type": query_type,
            "requested_at": requested,
            "completed_at": "",
            "requested_by": str(payload.get("requested_by") or "operator"),
            "params_json": json.dumps(payload, sort_keys=True),
            "status": "RUNNING",
        },
    )
    result, sources, warnings = _run(query_type, payload, csv)
    completed = now_iso()
    answer_id = uuid.uuid4().hex[:16]
    csv.upsert(
        "queries",
        {
            "query_id": query_id,
            "query_type": query_type,
            "requested_at": requested,
            "completed_at": completed,
            "requested_by": str(payload.get("requested_by") or "operator"),
            "params_json": json.dumps(payload, sort_keys=True),
            "status": "COMPLETE",
        },
    )
    csv.append(
        "answers",
        {
            "answer_id": answer_id,
            "query_id": query_id,
            "completed_at": completed,
            "result_schema": ANSWER_SCHEMA,
            "result_json": json.dumps(result),
            "warnings": ";".join(warnings),
            "artifact_id": "",
        },
    )
    for src in sources:
        csv.append(
            "sources",
            {
                "source_id": uuid.uuid4().hex[:16],
                "query_id": query_id,
                "system_id": src["system_id"],
                "interface_id": src.get("interface_id") or "",
                "schema_version": src.get("schema_version") or "v0",
                "provenance": src.get("provenance") or "systimo.registry",
            },
        )
    return {
        "schema": ANSWER_SCHEMA,
        "query_id": query_id,
        "answer_id": answer_id,
        "query_type": query_type,
        "requested_at": requested,
        "completed_at": completed,
        "sources": sources,
        "result": result,
        "result_schema": ANSWER_SCHEMA,
        "provenance": {"store": str(csv.root), "live_execution": False},
        "warnings": warnings,
        "artifact_id": None,
    }


def _run(query_type: str, payload: dict[str, Any], csv: CsvStore) -> tuple[Any, list[dict[str, str]], list[str]]:
    systems = csv.read("systems")
    connections = csv.read("connections")
    src = [{"system_id": "systimo", "interface_id": "registry", "provenance": "research/systimo"}]
    system = str(payload.get("system") or payload.get("system_id") or "").strip()
    if query_type == "systems":
        if payload.get("execution_capable") in {True, "true"}:
            return [row for row in systems if row["execution_capable"] == "true"], src, []
        return systems, src, []
    if query_type == "connections":
        status = str(payload.get("health") or "").strip()
        rows = connections
        if status:
            rows = [row for row in rows if row["health"] == status]
        if system:
            rows = [row for row in rows if system in {row["source_system_id"], row["target_system_id"]}]
        return rows, src, []
    if query_type == "dependencies":
        wanted = system or "jump"
        rows = [row for row in connections if row["target_system_id"] == wanted]
        return rows, src, []
    if query_type == "reverse_dependencies":
        wanted = system or "austin"
        rows = [row for row in connections if row["source_system_id"] == wanted]
        return rows, src, []
    if query_type == "datasets":
        rows = csv.read("datasets")
        if system:
            rows = [row for row in rows if row["owner_system_id"] == system]
        return rows, src, []
    if query_type == "interfaces":
        rows = csv.read("interfaces")
        if system:
            rows = [row for row in rows if row["owner_system_id"] == system]
        capability = str(payload.get("capability") or "").strip()
        if capability:
            rows = [row for row in rows if row.get("capability") == capability]
            return {"interfaces": rows, "invoked": invoke_capability(capability)}, src, []
        return rows, src, []
    if query_type == "health":
        return connections, src, []
    if query_type == "artifacts":
        query_id = str(payload.get("query_id") or "").strip()
        rows = csv.read("artifacts_index")
        if query_id:
            rows = [row for row in rows if row["query_id"] == query_id]
        return rows, src, []
    if query_type == "provenance":
        query_id = str(payload.get("query_id") or "").strip()
        rows = csv.read("sources")
        if query_id:
            rows = [row for row in rows if row["query_id"] == query_id]
        return rows, src, []
    if query_type == "paths":
        src_id = str(payload.get("from") or payload.get("source") or "").strip()
        dst_id = str(payload.get("to") or payload.get("target") or "").strip()
        if not src_id or not dst_id:
            raise SystimoError("INVALID_INPUT", "paths requires from and to")
        return graph_paths(csv, src_id, dst_id), src, []
    if query_type == "path_back":
        start = str(payload.get("from") or payload.get("system") or "jump").strip()
        return graph_path_back(csv, start), src, []
    if query_type == "drift":
        rows = [
            row
            for row in connections
            if row.get("reason") == "INTEGRITY_DRIFT" or "INTEGRITY_DRIFT" in (row.get("notes") or "")
        ]
        snaps = [row for row in csv.read("health_snapshots") if row.get("error_code") == "INTEGRITY_DRIFT"]
        return {"connections": rows, "snapshots": snaps}, src, []
    if query_type == "governance":
        rows = csv.read("governance")
        if system:
            rows = [
                row
                for row in rows
                if system in {row["owner_system_id"], row["consumer_system_id"]}
            ]
        return rows, src, []
    from roller.systimo.query.transitions import run_transition_query
    from roller.systimo.transitions.types import TRANSITION_QUERY_TYPES

    if query_type in TRANSITION_QUERY_TYPES:
        return run_transition_query(query_type, payload, csv)
    raise SystimoError("UNKNOWN_QUERY_TYPE", query_type)


def get_answer(query_id: str, store: CsvStore | None = None) -> dict[str, Any]:
    csv = store or CsvStore()
    queries = [row for row in csv.read("queries") if row["query_id"] == query_id]
    if not queries:
        raise SystimoError("UNKNOWN_QUERY", query_id, 404)
    answers = [row for row in csv.read("answers") if row["query_id"] == query_id]
    sources = [row for row in csv.read("sources") if row["query_id"] == query_id]
    answer = answers[-1] if answers else {}
    result = json.loads(answer["result_json"]) if answer.get("result_json") else None
    return {
        "schema": ANSWER_SCHEMA,
        "query_id": query_id,
        "answer_id": answer.get("answer_id"),
        "query_type": queries[0]["query_type"],
        "requested_at": queries[0]["requested_at"],
        "completed_at": queries[0]["completed_at"],
        "sources": sources,
        "result": result,
        "warnings": [answer["warnings"]] if answer.get("warnings") else [],
        "artifact_id": answer.get("artifact_id") or None,
    }
