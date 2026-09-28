"""Local lifecycle. The controller is a service identity, not a fixed port."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Callable
from urllib.request import urlopen

from roller.systimo.errors import SystimoError
from roller.systimo.ports import allocate, port_open, read_leases, write_leases
from roller.systimo.store import CsvStore
from roller.systimo.topology import load, require_v1, services_for_scope, topology_status


def _runtime_path(store: CsvStore) -> Path:
    return store.root / "state" / "runtime.json"


def read_runtime(store: CsvStore | None = None) -> dict[str, Any]:
    store = store or CsvStore()
    path = _runtime_path(store)
    if not path.is_file():
        return {"runs": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"runs": {}}
    data.setdefault("runs", {})
    return data


def write_runtime(store: CsvStore, body: dict[str, Any]) -> None:
    path = _runtime_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    path.chmod(0o600)


def _ordered(services: list[dict[str, str]]) -> list[dict[str, str]]:
    pending = {row["service_id"]: row for row in services}
    ordered: list[dict[str, str]] = []
    while pending:
        ready = [
            row
            for row in pending.values()
            if all(dep not in pending for dep in (row.get("dependencies") or "").split(",") if dep)
        ]
        if not ready:
            raise SystimoError("DEPENDENCY_CYCLE", ",".join(sorted(pending)))
        ready.sort(key=lambda row: row["service_id"])
        ordered.append(ready[0])
        del pending[ready[0]["service_id"]]
    return ordered


def plan(scope: str, store: CsvStore | None = None) -> dict[str, Any]:
    store = require_v1(store)
    rows = load(store)
    services = _ordered(services_for_scope(rows, scope))
    return {
        "scope": scope,
        "status": "V1",
        "services": [row["service_id"] for row in services],
        "live_execution": False,
        "arms_trading": False,
    }


def startup_ids(scope: str, store: CsvStore | None = None) -> list[str]:
    return plan(scope, store)["services"]


def record_run(service_id: str, *, pid: int, port: int, argv: list[str], store: CsvStore | None = None) -> dict[str, Any]:
    store = store or CsvStore()
    runtime = read_runtime(store)
    runtime["runs"][service_id] = {
        "service_id": service_id,
        "pid": pid,
        "port": port,
        "argv": argv,
        "owned": True,
    }
    write_runtime(store, runtime)
    return runtime["runs"][service_id]


def adopt(service_id: str, *, pid: int, port: int, store: CsvStore | None = None) -> dict[str, Any]:
    """Explicit adopt only. up never calls this."""
    return record_run(service_id, pid=pid, port=port, argv=["adopted"], store=store)


def classify_occupant(service_id: str, port: int, *, listener_pid: int | None, store: CsvStore | None = None) -> str:
    store = store or CsvStore()
    run = read_runtime(store)["runs"].get(service_id)
    if run and run.get("owned") and run.get("pid") == listener_pid and run.get("port") == port:
        return "owned"
    return "unowned"


def prepare_bind(service: dict[str, str], store: CsvStore, *, occupied: set[int] | None = None) -> int:
    if topology_status(store) != "V1":
        raise SystimoError("PRE_V1", "topology tables are missing or partial", 409)
    return allocate(service, store, occupied=occupied)


def claim_controller(store: CsvStore, *, pid: int, port: int) -> dict[str, Any]:
    """One owned controller. A second caller observes the live claim and does not start another."""
    with store.exclusive():
        runtime = read_runtime(store)
        current = runtime["runs"].get("roller-api")
        if current and current.get("owned") and _pid_alive(int(current.get("pid") or 0)):
            return current
        runtime["runs"]["roller-api"] = {
            "service_id": "roller-api",
            "pid": pid,
            "port": port,
            "owned": True,
        }
        write_runtime(store, runtime)
        return runtime["runs"]["roller-api"]


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def controller_port(store: CsvStore | None = None) -> int | None:
    store = store or CsvStore()
    run = read_runtime(store)["runs"].get("roller-api")
    if not run or not run.get("owned"):
        return None
    return int(run["port"])


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def launch(
    scope: str,
    store: CsvStore | None = None,
    *,
    popen: Callable[..., Any] = subprocess.Popen,
) -> dict[str, Any]:
    """Start owned processes for a scope. An occupied preferred port is left alone."""
    store = require_v1(store)
    rows = {row["service_id"]: row for row in _ordered(services_for_scope(load(store), scope))}
    started = []
    for service_id in plan(scope, store)["services"]:
        service = rows[service_id]
        argv = json.loads(service["argv_json"] or "[]")
        if not argv:
            continue
        port = prepare_bind(service, store)
        env = env_for(service, port)
        proc = popen(
            argv,
            cwd=str(repo_root()),
            env=env,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        record_run(service_id, pid=int(proc.pid), port=port, argv=argv, store=store)
        started.append(service_id)
    return {"scope": scope, "started": started, "live_execution": False, "arms_trading": False}


def named_services(store: CsvStore | None = None) -> list[dict[str, str]]:
    """Autostart processes bound to a box that has a visible name."""
    store = require_v1(store)
    rows = load(store)
    by_instance = {row["instance_id"]: row for row in rows["instances"]}
    named_ids: set[str] = set()
    for binding in rows["service_bindings"]:
        inst = by_instance.get(binding["instance_id"])
        if inst and (inst.get("label") or "").strip():
            named_ids.add(binding["service_id"])
    selected = []
    for service in _ordered(services_for_scope(rows, "all")):
        if service["service_id"] not in named_ids:
            continue
        if not json.loads(service.get("argv_json") or "[]"):
            continue
        selected.append(service)
    return selected


def _http_answers(port: int, service: dict[str, str]) -> bool:
    path = "/health" if service["service_id"] == "roller-api" else "/"
    try:
        with urlopen(f"http://127.0.0.1:{port}{path}", timeout=0.8) as response:
            body = response.read()
    except Exception:
        return False
    if service["service_id"] == "roller-api":
        return b"ok" in body.lower()
    return True


def run_named(
    store: CsvStore | None = None,
    *,
    popen: Callable[..., Any] = subprocess.Popen,
    probe: Callable[[int, dict[str, str]], bool] | None = None,
) -> dict[str, Any]:
    """Start named frontends and the shared backend on their preferred ports.

    A preferred port that already answers is left running. An occupant is not killed
    and is not replaced with a second copy.
    """
    store = require_v1(store)
    check = probe or _http_answers
    results = []
    for service in named_services(store):
        port = int(service["preferred_port"] or "0")
        service_id = service["service_id"]
        if port_open(port):
            results.append(
                {
                    "service_id": service_id,
                    "port": port,
                    "state": "up" if check(port, service) else "occupied",
                }
            )
            continue
        argv = json.loads(service["argv_json"])
        proc = popen(
            argv,
            cwd=str(repo_root()),
            env=env_for(service, port),
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        record_run(service_id, pid=int(proc.pid), port=port, argv=argv, store=store)
        ready = False
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if check(port, service):
                ready = True
                break
            time.sleep(0.05)
        results.append({"service_id": service_id, "port": port, "state": "started" if ready else "failed"})
    return {"results": results, "live_execution": False, "arms_trading": False}


def stop_owned(scope: str, store: CsvStore | None = None, *, killer: Callable[[int, int], None] = os.kill) -> dict[str, Any]:
    """Stop owned processes for this scope. An unowned occupant is left running."""
    store = require_v1(store)
    runtime = read_runtime(store)
    stopped = []
    for service_id in reversed(plan(scope, store)["services"]):
        run = runtime["runs"].get(service_id)
        if not run or not run.get("owned"):
            continue
        pid = int(run.get("pid") or 0)
        if not _pid_alive(pid):
            continue
        killer(pid, signal.SIGTERM)
        stopped.append(service_id)
    if scope == "all":
        controller = runtime["runs"].get("roller-api")
        if controller and controller.get("owned") and _pid_alive(int(controller.get("pid") or 0)):
            if "roller-api" not in stopped:
                killer(int(controller["pid"]), signal.SIGTERM)
                stopped.append("roller-api")
    return {"scope": scope, "stopped": stopped, "arms_trading": False}


def env_for(service: dict[str, str], port: int) -> dict[str, str]:
    env = dict(os.environ)
    env["MOMENTO_BIND_PORT"] = str(port)
    env["MOMENTO_SERVICE_ID"] = service["service_id"]
    env.pop("VITAL_AWS_CONTROL", None)
    return env


def leases_kept_on_pre_v1(store: CsvStore) -> dict[str, Any]:
    """Configuration failure must not delete leases for processes still recorded as owned."""
    return read_leases(store)


def apply_port(
    service_id: str,
    *,
    policy: str,
    preferred: int,
    session: dict[str, Any],
    store: CsvStore | None = None,
    probe=None,
    restart_frontends=None,
) -> dict[str, Any]:
    """Publish a live binding only after the restarted frontend answers on the new port."""
    store = require_v1(store)
    rows = load(store)
    service = next((row for row in rows["services"] if row["service_id"] == service_id), None)
    if service is None:
        raise SystimoError("UNKNOWN_SERVICE", service_id, 404)
    if session.get("scope_level") != "global":
        if service["scope"] in {"shared", "global"} or service["scope"] != session.get("quadrant_id"):
            raise SystimoError("SCOPE_DENIED", "shared port changes belong on the global desk", 403)
    previous = read_leases(store).get(service_id)
    updated = dict(service)
    updated["port_policy"] = policy
    updated["preferred_port"] = str(preferred)
    port = allocate(updated, store)
    try:
        if restart_frontends is not None:
            restart_frontends(service_id, port)
        if probe is not None and not probe(port):
            raise SystimoError("PROBE_FAILED", f"{service_id} did not answer on {port}", 409)
    except Exception:
        leases = read_leases(store)
        if previous:
            leases[service_id] = previous
        elif service_id in leases:
            del leases[service_id]
        write_leases(store, leases)
        raise
    runtime = read_runtime(store)
    runtime["runs"].setdefault(service_id, {"service_id": service_id, "owned": True})
    runtime["runs"][service_id]["port"] = port
    runtime["runs"][service_id]["owned"] = True
    write_runtime(store, runtime)
    store.upsert(
        "services",
        {**service, "port_policy": policy, "preferred_port": str(preferred)},
    )
    return {"service_id": service_id, "port": port, "bound": True, "trading_armed": False}
