"""Per-tab scope sessions. A cookie never authenticates a scoped request."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any

from roller.systimo.errors import SystimoError
from roller.systimo.store import CsvStore
from roller.systimo.topology import load, topology_status


def _path(store: CsvStore):
    return store.root / "state" / "sessions.json"


def _read(store: CsvStore) -> list[dict[str, Any]]:
    path = _path(store)
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _write(store: CsvStore, rows: list[dict[str, Any]]) -> None:
    path = _path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    path.chmod(0o600)


def get_session(session_id: str, store: CsvStore | None = None) -> dict[str, Any]:
    store = store or CsvStore()
    match = next((row for row in _read(store) if row.get("session_id") == session_id), None)
    if match is None:
        raise SystimoError("SCOPE_REQUIRED", "unknown scope session", 401)
    return match


def create_session(
    source_node_id: str,
    *,
    caller_session_id: str | None = None,
    store: CsvStore | None = None,
) -> dict[str, Any]:
    store = store or CsvStore()
    if topology_status(store) != "V1":
        raise SystimoError("PRE_V1", "topology tables are missing or partial", 409)
    rows = load(store)
    node = next((row for row in rows["nodes"] if row["node_id"] == source_node_id), None)
    if node is None:
        raise SystimoError("UNKNOWN_NODE", source_node_id, 404)
    inst = next((row for row in rows["instances"] if row["instance_id"] == node["instance_id"]), None)
    if inst is None:
        raise SystimoError("UNKNOWN_INSTANCE", node["instance_id"], 404)
    if inst["interactive"] != "true":
        raise SystimoError("NODE_CLOSED", source_node_id, 403)
    if inst["quadrant_id"] == "global":
        sport = "GLOBAL"
    else:
        quad = next((row for row in rows["quadrants"] if row["quadrant_id"] == inst["quadrant_id"]), None)
        if quad is None:
            raise SystimoError("UNKNOWN_QUADRANT", inst["quadrant_id"], 404)
        sport = quad["sport"]
    caller = None
    if caller_session_id:
        caller = get_session(caller_session_id, store)
        if caller["scope_level"] != "global" and (
            inst["quadrant_id"] == "global" or inst["quadrant_id"] != caller["quadrant_id"]
        ):
            raise SystimoError("SCOPE_DENIED", "session cannot widen scope", 403)
    scope_level = "global" if inst["quadrant_id"] == "global" else "quadrant"
    body = {
        "session_id": secrets.token_hex(16),
        "scope_level": scope_level,
        "quadrant_id": inst["quadrant_id"],
        "sport": sport,
        "source_node_id": source_node_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    current = _read(store)
    current.append(body)
    _write(store, current)
    return body


def token_from_request(header: str | None, query_token: str | None) -> str:
    """Header or URL session parameter. Cookies are ignored."""
    token = (header or "").strip() or (query_token or "").strip()
    if not token:
        raise SystimoError("SCOPE_REQUIRED", "scoped route missing session", 401)
    return token


def endpoints_for_session(session: dict[str, Any], store: CsvStore | None = None) -> dict[str, Any]:
    store = store or CsvStore()
    rows = load(store)
    by_instance = {row["instance_id"]: row for row in rows["instances"]}
    visible: set[str] = set()
    shared: set[str] = set()
    for binding in rows["service_bindings"]:
        inst = by_instance.get(binding["instance_id"])
        if inst is None:
            continue
        service_id = binding["service_id"]
        if session["scope_level"] == "global":
            visible.add(service_id)
            continue
        if inst["quadrant_id"] == session["quadrant_id"]:
            visible.add(service_id)
        elif inst["quadrant_id"] == "global":
            shared.add(service_id)
    services = {row["service_id"]: row for row in rows["services"]}
    full = []
    sanitized = []
    for service_id in sorted(visible):
        service = services.get(service_id)
        if service is None:
            continue
        if service["scope"] in {"shared", "global"} and session["scope_level"] != "global":
            sanitized.append({"service_id": service_id, "shared": True, "health": "UNAVAILABLE"})
            continue
        full.append({"service_id": service_id, "scope": service["scope"], "preferred_port": service["preferred_port"]})
    for service_id in sorted(shared - visible):
        sanitized.append({"service_id": service_id, "shared": True, "health": "UNAVAILABLE"})
    return {"endpoints": full, "shared": sanitized, "quadrant_id": session["quadrant_id"]}
