"""Systimo-backed source catalog for Jump. CSV is the registry, not a copy."""

from __future__ import annotations

from typing import Any

from roller.jump.data.models import LIVE_EXECUTION, READ_OK, UNAVAILABLE
from roller.systimo.store import CsvStore


def _store() -> CsvStore:
    return CsvStore()


def jump_connections(store: CsvStore | None = None) -> list[dict[str, str]]:
    csv = store or _store()
    return [row for row in csv.read("connections") if row["target_system_id"] == "jump"]


def connection_for_capability(capability: str, store: CsvStore | None = None) -> dict[str, str] | None:
    wanted = str(capability or "").strip()
    matches = [row for row in jump_connections(store) if row.get("capability") == wanted]
    implemented = [row for row in matches if row.get("lifecycle") == "IMPLEMENTED"]
    return (implemented or matches or [None])[0]


def require_query_connection(capability: str, store: CsvStore | None = None) -> dict[str, str]:
    from roller.jump.errors import JumpError

    row = connection_for_capability(capability, store)
    if row is None:
        raise JumpError("UNREGISTERED_INTERFACE", f"no Jump tunnel for {capability}")
    if row.get("permission") not in READ_OK:
        raise JumpError("QUERY_REJECTED", f"{capability} permission={row.get('permission')} DENY")
    if row.get("lifecycle") == "DECLARED":
        raise JumpError("UNAVAILABLE", f"{capability} lifecycle=DECLARED")
    return row


def sources(store: CsvStore | None = None) -> list[dict[str, Any]]:
    csv = store or _store()
    systems = {row["system_id"]: row for row in csv.read("systems")}
    datasets = csv.read("datasets")
    interfaces = csv.read("interfaces")
    out = []
    for row in jump_connections(csv):
        owner = systems.get(row["source_system_id"], {})
        caps = [
            item["capability"]
            for item in interfaces
            if item["owner_system_id"] == row["source_system_id"] and item.get("capability")
        ]
        if row.get("capability") and row["capability"] not in caps:
            caps.append(row["capability"])
        ds = [item for item in datasets if item["owner_system_id"] == row["source_system_id"]]
        out.append(
            {
                "system_id": row["source_system_id"],
                "resource_id": row["source_interface"],
                "resource_type": row["connection_type"],
                "owner": owner.get("name") or row["source_system_id"],
                "consumer": "jump",
                "capabilities": caps,
                "connection_id": row["connection_id"],
                "schema": row.get("schema_version") or "v1",
                "schema_version": row.get("schema_version") or "v1",
                "data_mode": row.get("data_mode") or "",
                "read_permission": row.get("permission") or "",
                "health": row.get("health") or "UNKNOWN",
                "lifecycle": row.get("lifecycle") or "",
                "location": owner.get("data_roots") or "",
                "lineage_parent_ids": [item["dataset_id"] for item in ds],
                "query_interface": row.get("adapter") or "",
                "expected_lock": row.get("expected_lock") or "",
                "live_execution": LIVE_EXECUTION,
            }
        )
    return out


def source(system_id: str, store: CsvStore | None = None) -> dict[str, Any]:
    from roller.jump.errors import JumpError

    wanted = str(system_id or "").strip()
    rows = [row for row in sources(store) if row["system_id"] == wanted]
    if not rows:
        raise JumpError("RESULT_NOT_FOUND", f"no Jump source {wanted}")
    return {"system_id": wanted, "tunnels": rows, "availability": "OBSERVED"}
