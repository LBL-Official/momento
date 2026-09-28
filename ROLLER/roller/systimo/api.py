"""Systimo HTTP handlers. Registry operates tunnels. Not a data owner."""

from __future__ import annotations

from typing import Any

from roller.systimo.actions.handlers import apply_action, dry_run, list_actions, propose
from roller.systimo.agents.runner import list_agents, run_agent
from roller.systimo.artifacts.writer import list_artifacts, save_artifact
from roller.systimo.errors import SystimoError
from roller.systimo.graph.build import load_graph, load_tree
from roller.systimo.health.refresh import refresh
from roller.systimo.models import LIVE_EXECUTION, PRODUCT, SYSTEM_ID
from roller.systimo.query.executor import execute, get_answer
from roller.systimo.store import CsvStore


def handle_health() -> dict[str, Any]:
    from roller.systimo.store.schema import TABLES

    store = CsvStore()
    csv_valid = True
    csv_error = ""
    try:
        store.validate_all()
    except SystimoError as exc:
        csv_valid = False
        csv_error = f"{exc.code}: {exc.message}"
    connections = store.read("connections")
    drift = [
        {
            "connection_id": row["connection_id"],
            "reason": row.get("reason") or "",
            "health": row.get("health") or "",
        }
        for row in connections
        if row.get("reason") == "INTEGRITY_DRIFT"
    ]
    row_counts = {table: len(store.read(table)) for table in TABLES}
    return {
        "ok": csv_valid,
        "product": PRODUCT,
        "system_id": SYSTEM_ID,
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "submits": False,
        "csv_valid": csv_valid,
        "csv_error": csv_error or None,
        "row_counts": row_counts,
        "drift": drift,
        "systems": len(store.read("systems")),
        "connections": len(connections),
        "unavailable": sum(1 for row in connections if row["health"] == "UNAVAILABLE"),
        "position_management": "QUERY",
        "note": "Systimo registers tunnels and the transition audit loop. It does not own Austin/Choosin/Vital data.",
    }


def handle_systems(system_id: str | None = None) -> dict[str, Any]:
    rows = CsvStore().read("systems")
    if system_id:
        match = next((row for row in rows if row["system_id"] == system_id), None)
        if match is None:
            raise SystimoError("UNKNOWN_SYSTEM", system_id, 404)
        return match
    return {"systems": rows, "n": len(rows)}


def handle_connections(connection_id: str | None = None) -> dict[str, Any]:
    rows = CsvStore().read("connections")
    if connection_id:
        match = next((row for row in rows if row["connection_id"] == connection_id), None)
        if match is None:
            raise SystimoError("UNKNOWN_CONNECTION", connection_id, 404)
        return match
    return {"connections": rows, "n": len(rows)}


def handle_tree() -> dict[str, Any]:
    return load_tree()


def handle_graph() -> dict[str, Any]:
    return load_graph()


def handle_datasets() -> dict[str, Any]:
    rows = CsvStore().read("datasets")
    return {"datasets": rows, "n": len(rows)}


def handle_artifacts() -> dict[str, Any]:
    rows = list_artifacts()
    return {"artifacts": rows, "n": len(rows)}


def handle_refresh(body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = body if isinstance(body, dict) else {}
    return refresh(connection_id=payload.get("connection_id"))


def handle_query(body: dict[str, Any] | None = None) -> dict[str, Any]:
    return execute(body)


def handle_query_get(query_id: str) -> dict[str, Any]:
    return get_answer(query_id)


def handle_query_artifact(query_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = body if isinstance(body, dict) else {}
    return save_artifact(
        query_id,
        kind=str(payload.get("kind") or "json"),
        rerun_of=str(payload.get("rerun_of") or ""),
    )


def handle_actions() -> dict[str, Any]:
    return {"actions": list_actions()}


def handle_action_propose(body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = body if isinstance(body, dict) else {}
    answer_id = str(payload.get("answer_id") or "").strip()
    if not answer_id:
        raise SystimoError("INVALID_INPUT", "answer_id required")
    return {"actions": propose(answer_id)}


def handle_action_dry_run(action_id: str) -> dict[str, Any]:
    return dry_run(action_id)


def handle_action_apply(action_id: str) -> dict[str, Any]:
    return apply_action(action_id)


def handle_agents() -> dict[str, Any]:
    store = CsvStore()
    return {"agents": list_agents(store), "runs": store.read("agent_runs")}


def handle_agent_run(agent_id: str) -> dict[str, Any]:
    return run_agent(agent_id)


def handle_traces(trace_id: str | None = None) -> dict[str, Any]:
    from roller.systimo.transitions import get_trace, list_traces

    if trace_id:
        return get_trace(trace_id)
    return {"traces": list_traces(), "n": len(list_traces())}


def handle_orchestra_context(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    from roller.systimo.orchestra import handle_orchestra_context as compose

    return compose(trade_id, as_of)


def handle_topology() -> dict[str, Any]:
    from roller.systimo.topology import DRAWN_SLOTS, MIN_CAPACITY, RESERVED_CAPACITY, load, topology_status

    store = CsvStore()
    status = topology_status(store)
    if status != "V1":
        return {"status": status, "drawn_slots": DRAWN_SLOTS, "reserved_capacity": RESERVED_CAPACITY}
    rows = load(store)
    return {
        "status": status,
        "drawn_slots": DRAWN_SLOTS,
        "reserved_capacity": RESERVED_CAPACITY,
        "capacity_floor": MIN_CAPACITY,
        "quadrants": rows["quadrants"],
        "instances": rows["instances"],
        "nodes": rows["nodes"],
        "services": rows["services"],
        "service_bindings": rows["service_bindings"],
        "bots": rows["bots"],
        "live_execution": LIVE_EXECUTION,
    }


def handle_scope_session(body: dict[str, Any] | None = None) -> dict[str, Any]:
    from roller.systimo.scope import create_session

    body = body or {}
    return create_session(
        str(body.get("source_node_id") or ""),
        caller_session_id=body.get("caller_session_id") or None,
    )


def handle_runtime_endpoints(session_id: str) -> dict[str, Any]:
    from roller.systimo.lifecycle import read_runtime
    from roller.systimo.scope import endpoints_for_session, get_session

    session = get_session(session_id)
    payload = endpoints_for_session(session)
    runs = read_runtime().get("runs", {})
    for endpoint in payload["endpoints"]:
        run = runs.get(endpoint["service_id"])
        if run and run.get("owned"):
            endpoint["port"] = run.get("port")
            endpoint["bound"] = True
        else:
            endpoint["bound"] = False
    payload["trading_armed"] = False
    return payload


def handle_plan(scope: str) -> dict[str, Any]:
    from roller.systimo.lifecycle import plan

    return plan(scope)


def handle_run() -> dict[str, Any]:
    from roller.systimo.lifecycle import run_named

    return run_named()


def handle_bots(session_id: str) -> dict[str, Any]:
    from roller.systimo.scope import get_session
    from roller.systimo.topology import load

    session = get_session(session_id)
    bots = load()["bots"]
    if session["scope_level"] != "global":
        bots = [row for row in bots if row["quadrant_id"] == session["quadrant_id"]]
    return {"bots": bots, "trading_armed": False}
