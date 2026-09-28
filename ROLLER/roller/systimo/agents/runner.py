"""Deterministic maintenance workers. No LLM."""

from __future__ import annotations

import uuid
from typing import Any

from roller.systimo.actions.handlers import propose
from roller.systimo.errors import SystimoError
from roller.systimo.models import now_iso
from roller.systimo.query.executor import execute
from roller.systimo.store import CsvStore


SCOPE_PARAMS: dict[str, dict[str, str]] = {
    "paths": {"from": "choosin_texas", "to": "jump"},
    "dependencies": {"system": "jump"},
    "reverse_dependencies": {"system": "austin"},
}


def list_agents(store: CsvStore | None = None) -> list[dict[str, str]]:
    return (store or CsvStore()).read("agents")


def run_agent(agent_id: str, store: CsvStore | None = None) -> dict[str, Any]:
    csv = store or CsvStore()
    rows = [row for row in csv.read("agents") if row["agent_id"] == agent_id]
    if not rows:
        raise SystimoError("UNKNOWN_AGENT", agent_id, 404)
    agent = rows[0]
    if agent.get("enabled") != "true":
        raise SystimoError("AGENT_DISABLED", agent_id)
    scopes = [item for item in agent["allowed_query_scopes"].split("|") if item]
    query_ids = []
    artifact_ids: list[str] = []
    proposed: list[str] = []
    started = now_iso()
    status = "COMPLETE"
    error = ""
    try:
        for scope in scopes:
            payload = {"query_type": scope, "requested_by": agent_id}
            payload.update(SCOPE_PARAMS.get(scope, {}))
            answer = execute(payload, csv)
            query_ids.append(answer["query_id"])
            for row in propose(answer["answer_id"], csv):
                if row["action_type"] not in agent["allowed_action_types"].split("|"):
                    raise SystimoError("ACTION_NOT_ALLOWED", row["action_type"])
                proposed.append(row["action_id"])
    except Exception as exc:  # noqa: BLE001
        status = "FAILED"
        error = str(exc)
    finished = now_iso()
    run_id = uuid.uuid4().hex[:16]
    csv.append(
        "agent_runs",
        {
            "run_id": run_id,
            "agent_id": agent_id,
            "started_at": started,
            "finished_at": finished,
            "query_ids": ",".join(query_ids),
            "artifact_ids": ",".join(artifact_ids),
            "proposed_action_ids": ",".join(proposed),
            "applied_action_ids": "",
            "status": status,
            "error": error,
        },
    )
    return {
        "run_id": run_id,
        "agent_id": agent_id,
        "status": status,
        "query_ids": query_ids,
        "proposed_action_ids": proposed,
        "error": error or None,
    }
