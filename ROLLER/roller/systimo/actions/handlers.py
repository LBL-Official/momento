"""Allowlisted maintenance actions. OBSERVE/PLAN do not mutate. APPLY is explicit."""

from __future__ import annotations

import json
import uuid
from typing import Any

from roller.systimo.errors import SystimoError
from roller.systimo.graph.build import write_generated
from roller.systimo.health.refresh import refresh
from roller.systimo.models import ALLOWLISTED_ACTIONS, now_iso
from roller.systimo.store import CsvStore


def propose(answer_id: str, store: CsvStore | None = None) -> list[dict[str, str]]:
    csv = store or CsvStore()
    answers = [row for row in csv.read("answers") if row["answer_id"] == answer_id]
    if not answers:
        raise SystimoError("UNKNOWN_ANSWER", answer_id, 404)
    queries = [row for row in csv.read("queries") if row["query_id"] == answers[0]["query_id"]]
    qtype = queries[0]["query_type"] if queries else ""
    mapping = {
        "health": "RECHECK_HEALTH",
        "drift": "VALIDATE_SCHEMA",
        "connections": "REFRESH_CONNECTION",
        "paths": "REGENERATE_TREE",
        "dependencies": "REGENERATE_TREE",
        "reverse_dependencies": "REGENERATE_TREE",
        "artifacts": "EXPORT_ARTIFACT",
        "governance": "VALIDATE_SCHEMA",
    }
    action_type = mapping.get(qtype, "RECHECK_HEALTH")
    action_id = uuid.uuid4().hex[:16]
    row = {
        "action_id": action_id,
        "action_type": action_type,
        "target_system": "systimo",
        "target_resource": qtype,
        "reason": f"proposed from query_type={qtype}",
        "source_answer_id": answer_id,
        "dry_run_supported": "true",
        "approval_required": "false",
        "risk_class": "LOW",
        "handler": action_type,
        "status": "PROPOSED",
    }
    csv.append("actions", row)
    return [row]


def dry_run(action_id: str, store: CsvStore | None = None) -> dict[str, Any]:
    return _run(action_id, mode="PLAN", apply=False, store=store)


def apply_action(action_id: str, store: CsvStore | None = None) -> dict[str, Any]:
    return _run(action_id, mode="APPLY", apply=True, store=store)


def _run(action_id: str, *, mode: str, apply: bool, store: CsvStore | None) -> dict[str, Any]:
    csv = store or CsvStore()
    rows = [row for row in csv.read("actions") if row["action_id"] == action_id]
    if not rows:
        raise SystimoError("UNKNOWN_ACTION", action_id, 404)
    action = rows[0]
    kind = action["action_type"]
    if kind not in ALLOWLISTED_ACTIONS:
        raise SystimoError("APPLY_REJECTED", f"{kind} is not allowlisted")
    run_id = uuid.uuid4().hex[:16]
    started = now_iso()
    result: dict[str, Any]
    if not apply:
        result = {"dry_run": True, "would": kind, "mutates": False}
        status = "DRY_RUN"
        error = ""
    else:
        try:
            result = _apply(kind, csv)
            status = "APPLIED"
            error = ""
        except Exception as exc:  # noqa: BLE001
            result = {}
            status = "FAILED"
            error = str(exc)
    finished = now_iso()
    csv.append(
        "action_runs",
        {
            "run_id": run_id,
            "action_id": action_id,
            "started_at": started,
            "finished_at": finished,
            "mode": mode,
            "status": status,
            "error": error,
            "result_json": json.dumps(result),
        },
    )
    return {"run_id": run_id, "action_id": action_id, "mode": mode, "status": status, "result": result, "error": error}


def _apply(kind: str, csv: CsvStore) -> dict[str, Any]:
    if kind in {"REFRESH_CONNECTION", "RECHECK_HEALTH"}:
        return refresh(csv)
    if kind == "REGENERATE_TREE":
        return write_generated(csv)
    if kind == "VALIDATE_SCHEMA":
        csv.validate_all()
        return {"ok": True, "validated": True}
    if kind in {"REBUILD_QUERY_INDEX", "EXPORT_ARTIFACT"}:
        return {"ok": True, "note": "CSV remains SSOT. No derived index required."}
    raise SystimoError("APPLY_REJECTED", kind)


def list_actions(store: CsvStore | None = None) -> list[dict[str, str]]:
    return (store or CsvStore()).read("actions")
