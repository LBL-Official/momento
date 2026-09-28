"""Port leases. A free-port probe is not a reservation. Occupants are not adopted."""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

from roller.systimo.errors import SystimoError
from roller.systimo.store import CsvStore


def _lease_path(store: CsvStore) -> Path:
    return store.root / "state" / "port_leases.json"


def read_leases(store: CsvStore) -> dict[str, Any]:
    path = _lease_path(store)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_leases(store: CsvStore, leases: dict[str, Any]) -> None:
    path = _lease_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(leases, indent=2), encoding="utf-8")
    path.chmod(0o600)


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    """True when the port cannot be bound. A connect probe is not a reservation."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return True
        return False


def allocate(service: dict[str, str], store: CsvStore, *, occupied: set[int] | None = None) -> int:
    """Reserve a port for a service. Does not kill or adopt an occupant."""
    preferred = int(service["preferred_port"] or "0")
    policy = service["port_policy"]
    leases = read_leases(store)
    owned = {int(row["port"]) for row in leases.values() if row.get("service_id") == service["service_id"]}
    blocked = set(occupied or ())
    blocked.update(int(row["port"]) for row in leases.values() if row.get("service_id") != service["service_id"])

    def free(port: int) -> bool:
        if port in blocked and port not in owned:
            return False
        if port_open(port) and port not in owned:
            return False
        return True

    chosen: int | None = None
    if preferred and free(preferred):
        chosen = preferred
    elif policy == "pinned":
        raise SystimoError("PORT_CONFLICT", f"{service['service_id']} pinned port {preferred} is occupied", 409)
    else:
        start = preferred + 1 if preferred else 20000
        for port in range(start, start + 200):
            if free(port):
                chosen = port
                break
    if chosen is None:
        raise SystimoError("PORT_EXHAUSTED", service["service_id"], 409)
    leases[service["service_id"]] = {"service_id": service["service_id"], "port": chosen, "policy": policy}
    write_leases(store, leases)
    return chosen
