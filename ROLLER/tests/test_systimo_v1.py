"""Systimo V1 topology, scope, ports, and bot ownership."""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def store(tmp_path, monkeypatch):
    import shutil

    dst = tmp_path / "systimo"
    shutil.copytree(REPO / "research" / "systimo", dst, ignore=shutil.ignore_patterns("generated", "__pycache__"))
    monkeypatch.setenv("SYSTIMO_ROOT", str(dst))
    from roller.systimo.store import CsvStore

    return CsvStore(dst)


def _client() -> TestClient:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    return TestClient(terminal_api.app)


def test_drawn_slots_and_capacity(store):
    from roller.systimo.topology import DRAWN_SLOTS, MIN_CAPACITY, RESERVED_CAPACITY, SYSTEM_TYPES, load

    rows = load(store)
    assert len(rows["instances"]) == DRAWN_SLOTS == 80
    assert len(rows["nodes"]) == 80
    assert RESERVED_CAPACITY == 10
    assert MIN_CAPACITY == 90
    assert len(SYSTEM_TYPES) == 19
    types = {row["system_type"] for row in rows["instances"] if row["quadrant_id"] == "quad-1"}
    assert types == set(SYSTEM_TYPES)
    sample = rows["instances"][0]
    for index in range(10):
        store.upsert(
            "instances",
            {
                **sample,
                "instance_id": f"capacity:{index}",
                "quadrant_id": "quad-2",
                "label": "",
                "interactive": "false",
            },
        )
    assert len(store.read("instances")) == 90
    assert len(store.read("nodes")) == 80


def test_quad_scope_plans_differ(store):
    from roller.systimo.lifecycle import plan

    everything = plan("all", store)["services"]
    nba = plan("quad-1", store)["services"]
    assert "mlb-execution-desk" in everything
    assert "mlb-execution-desk" not in nba
    assert "roller-api" in nba
    assert "momento-ls" not in everything
    assert "mlb-001" not in everything


def test_new_autostart_row_joins_plan_without_launcher_edit(store):
    from roller.systimo.lifecycle import plan

    template = next(row for row in store.read("services") if row["service_id"] == "drevo")
    store.upsert("services", {**template, "service_id": "extra-observer", "scope": "quad-2"})
    store.upsert(
        "service_bindings",
        {"binding_id": "bind:extra-observer", "service_id": "extra-observer", "instance_id": "quad-2:database"},
    )
    assert "extra-observer" in plan("quad-2", store)["services"]
    launcher = (REPO / "ROLLER" / "roller" / "systimo" / "cli.py").read_text(encoding="utf-8")
    assert "extra-observer" not in launcher


def test_preferred_port_moves_and_pinned_conflicts(store):
    from roller.systimo.errors import SystimoError
    from roller.systimo.ports import allocate

    occupant = socket.socket()
    occupant.bind(("127.0.0.1", 0))
    occupant.listen(1)
    port = occupant.getsockname()[1]
    service = next(row for row in store.read("services") if row["service_id"] == "roller-api")
    moved = allocate({**service, "preferred_port": str(port), "port_policy": "preferred-with-fallback"}, store)
    assert moved != port
    assert occupant.getsockname()[1] == port
    with pytest.raises(SystimoError) as raised:
        allocate({**service, "preferred_port": str(port), "port_policy": "pinned"}, store)
    assert raised.value.code == "PORT_CONFLICT"
    occupant.close()


def test_unowned_occupant_is_not_adopted_by_classification(store):
    from roller.systimo.lifecycle import classify_occupant, record_run

    record_run("roller-api", pid=os.getpid(), port=8791, argv=["owned"], store=store)
    assert classify_occupant("roller-api", 8791, listener_pid=os.getpid() + 1, store=store) == "unowned"
    assert classify_occupant("roller-api", 8791, listener_pid=os.getpid(), store=store) == "owned"


def test_controller_claim_is_single(store):
    from roller.systimo.lifecycle import claim_controller, read_runtime

    stale = read_runtime(store)
    stale["runs"]["roller-api"] = {"service_id": "roller-api", "pid": 2**22, "port": 1, "owned": True}
    from roller.systimo.lifecycle import write_runtime

    write_runtime(store, stale)
    first = claim_controller(store, pid=os.getpid(), port=8801)
    results = []

    def second():
        results.append(claim_controller(store, pid=os.getpid() + 1, port=8802))

    thread = threading.Thread(target=second)
    thread.start()
    thread.join()
    assert first["pid"] == os.getpid()
    assert results[0]["pid"] == os.getpid()
    assert results[0]["port"] == 8801


def test_partial_tables_are_pre_v1_and_keep_leases(store):
    from roller.systimo.errors import SystimoError
    from roller.systimo.lifecycle import plan
    from roller.systimo.ports import read_leases, write_leases
    from roller.systimo.topology import topology_status

    write_leases(store, {"roller-api": {"service_id": "roller-api", "port": 8791, "policy": "preferred-with-fallback"}})
    (store.root / "registry" / "service_bindings.csv").unlink()
    assert topology_status(store) == "PRE_V1"
    with pytest.raises(SystimoError) as raised:
        plan("all", store)
    assert raised.value.code == "PRE_V1"
    assert read_leases(store)["roller-api"]["port"] == 8791


def test_scope_session_cannot_widen_and_endpoints_hide_other_sports(store):
    from roller.systimo.errors import SystimoError
    from roller.systimo.scope import create_session, endpoints_for_session

    nba = create_session("node:quad-1:system_maintenance", store=store)
    with pytest.raises(SystimoError) as raised:
        create_session("node:global:system_maintenance", caller_session_id=nba["session_id"], store=store)
    assert raised.value.code == "SCOPE_DENIED"
    payload = endpoints_for_session(nba, store)
    ids = {row["service_id"] for row in payload["endpoints"]}
    assert "mlb-execution-desk" not in ids
    assert all(row["service_id"] != "mlb-execution-desk" for row in payload["shared"])
    quad4 = create_session("node:quad-4:algorithmic_execution", store=store)
    quad4_ids = {row["service_id"] for row in endpoints_for_session(quad4, store)["endpoints"]}
    assert "mlb-execution-desk" in quad4_ids


def test_strip_header_and_session_fails_closed(store):
    from roller.systimo.scope import create_session

    session = create_session("node:quad-1:database", store=store)
    client = _client()
    missing = client.get("/scoped/quad-1/health", headers={"cookie": f"momento_scope={session['session_id']}"})
    assert missing.status_code == 401
    forged = client.post(
        "/scoped/quad-1/research-query/compile",
        headers={"x-momento-scope": session["session_id"]},
        json={"sport": "WNBA"},
    )
    assert forged.status_code == 403
    allowed = client.get("/scoped/quad-1/health", headers={"x-momento-scope": session["session_id"]})
    assert allowed.status_code == 200


def test_nba_cannot_list_quad4_bots_or_rebind_shared_port(store):
    from roller.systimo.api import handle_bots
    from roller.systimo.errors import SystimoError
    from roller.systimo.lifecycle import apply_port
    from roller.systimo.scope import create_session

    nba = create_session("node:quad-1:trade_breakdown", store=store)
    listed = handle_bots(nba["session_id"])
    assert [row["bot_id"] for row in listed["bots"]] == ["nba-001"]
    assert all(row["quadrant_id"] == "quad-1" for row in listed["bots"])
    assert listed["trading_armed"] is False
    with pytest.raises(SystimoError) as raised:
        apply_port(
            "roller-api",
            policy="preferred-with-fallback",
            preferred=8791,
            session=nba,
            store=store,
            probe=lambda _port: True,
        )
    assert raised.value.code == "SCOPE_DENIED"


def test_port_apply_requires_a_real_proxied_request(store):
    hits = {"health": 0, "ws": 0}
    old_hits = {"n": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/health":
                hits["health"] += 1
                body = b'{"ok":true}'
            elif self.path == "/ws":
                hits["ws"] += 1
                body = b"reconnected"
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    class OldHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            old_hits["n"] += 1
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    preferred = holder.getsockname()[1]
    holder.close()
    old_server = ThreadingHTTPServer(("127.0.0.1", 0), OldHandler)
    threading.Thread(target=old_server.serve_forever, daemon=True).start()
    proxy = {"target": old_server.server_address[1]}
    started: dict[str, ThreadingHTTPServer] = {}

    class Proxy(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            with urlopen(f"http://127.0.0.1:{proxy['target']}{self.path}") as upstream:
                body = upstream.read()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    proxy_server = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    threading.Thread(target=proxy_server.serve_forever, daemon=True).start()

    def restart(_service_id, port):
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        started["server"] = server
        threading.Thread(target=server.serve_forever, daemon=True).start()
        proxy["target"] = port

    def probe(port):
        for _ in range(20):
            try:
                with urlopen(f"http://127.0.0.1:{port}/health", timeout=0.2) as response:
                    return b"ok" in response.read()
            except OSError:
                threading.Event().wait(0.05)
        return False

    from roller.systimo.lifecycle import apply_port
    from roller.systimo.scope import create_session

    global_session = create_session("node:global:system_maintenance", store=store)
    try:
        applied = apply_port(
            "roller-api",
            policy="preferred-with-fallback",
            preferred=preferred,
            session=global_session,
            store=store,
            probe=probe,
            restart_frontends=restart,
        )
        assert applied["port"] == preferred
        assert applied["bound"] is True
        assert applied["trading_armed"] is False
        with urlopen(f"http://127.0.0.1:{proxy_server.server_address[1]}/health") as response:
            assert json.loads(response.read())["ok"] is True
        with urlopen(f"http://127.0.0.1:{proxy_server.server_address[1]}/ws") as response:
            assert response.read() == b"reconnected"
        assert hits["health"] >= 1
        assert hits["ws"] == 1
        assert old_hits["n"] == 0
    finally:
        proxy_server.shutdown()
        old_server.shutdown()
        if "server" in started:
            started["server"].shutdown()


def test_bot_ownership_and_closed_nba_execution(store):
    from roller.systimo.topology import load

    rows = load(store)
    bots = rows["bots"]
    assert [row["bot_id"] for row in bots] == ["mlb-001", "nba-001"]
    assert bots[0]["quadrant_id"] == "quad-4"
    assert bots[0]["owner"] == "vital"
    assert bots[0]["runtime_pointer"] == "momento-live.service"
    assert bots[1]["quadrant_id"] == "quad-1"
    assert bots[1]["runtime_pointer"] == "momento-nba-001.service"
    assert bots[1]["desk_instance_id"] == "quad-1:algorithmic_execution"
    wnba = [row for row in rows["instances"] if row["quadrant_id"] == "quad-3" and row["system_type"] == "algorithmic_execution"]
    assert wnba[0]["interactive"] == "true"
    nba_exec = [row for row in rows["instances"] if row["quadrant_id"] == "quad-1" and row["system_type"] == "algorithmic_execution"]
    assert nba_exec[0]["interactive"] == "true"
    assert not list((REPO / "research" / "vital" / "bots").glob("wnba-*"))
    north = next(row for row in rows["nodes"] if row["instance_id"] == "quad-1:momento_systems")
    assert north["label_override"] == "NBA North"


def test_launch_does_not_kill_an_unowned_port_or_arm_trading(store):
    from roller.systimo.lifecycle import launch, stop_owned

    class Proc:
        pid = os.getpid()

    calls = []

    def fake_popen(argv, **kwargs):
        assert kwargs["start_new_session"] is True
        assert "VITAL_AWS_CONTROL" not in kwargs["env"]
        calls.append(argv)
        return Proc()

    body = launch("quad-1", store, popen=fake_popen)
    assert body["arms_trading"] is False
    assert "mlb-execution-desk" not in body["started"]
    assert calls
    killed = []
    stopped = stop_owned("quad-1", store, killer=lambda pid, sig: killed.append(pid))
    assert os.getpid() in killed
    assert stopped["arms_trading"] is False


def test_named_run_includes_real_frontends_and_skips_bots(store):
    from roller.systimo.lifecycle import named_services

    ids = [row["service_id"] for row in named_services(store)]
    for required in ("drevo", "choosin-texas", "roller-terminal", "mlb-execution-desk", "ballhog", "positman", "roller-api"):
        assert required in ids
    assert "mlb-001" not in ids
    assert "momento-ls" not in ids
    assert "fair_odds_modeling" not in ids
    assert "signal_generation" not in ids


def test_run_named_leaves_an_occupied_port_alone(store, monkeypatch):
    from roller.systimo import lifecycle

    monkeypatch.setattr(lifecycle, "port_open", lambda port, host="127.0.0.1": True)
    calls = []

    def fake_popen(*args, **kwargs):
        calls.append(args)
        raise AssertionError("occupied port must not be started")

    body = lifecycle.run_named(store, popen=fake_popen, probe=lambda _port, _service: False)
    assert calls == []
    assert body["arms_trading"] is False
    assert body["live_execution"] is False
    assert body["results"]
    assert {row["state"] for row in body["results"]} == {"occupied"}
    drevo = next(row for row in body["results"] if row["service_id"] == "drevo")
    assert drevo["port"] == 5191


def test_run_named_starts_a_free_port_once(store, monkeypatch):
    from roller.systimo import lifecycle

    monkeypatch.setattr(lifecycle, "port_open", lambda port, host="127.0.0.1": False)
    calls = []

    class Proc:
        pid = 424242

    def fake_popen(argv, **kwargs):
        assert kwargs["start_new_session"] is True
        assert "VITAL_AWS_CONTROL" not in kwargs["env"]
        calls.append(argv)
        return Proc()

    body = lifecycle.run_named(store, popen=fake_popen, probe=lambda _port, _service: True)
    assert all(row["state"] == "started" for row in body["results"])
    assert any("frontend/dynamic-risk-engine" in part for argv in calls for part in argv)
    started = len(calls)
    monkeypatch.setattr(lifecycle, "port_open", lambda port, host="127.0.0.1": True)
    again = lifecycle.run_named(store, popen=fake_popen, probe=lambda _port, _service: True)
    assert len(calls) == started
    assert all(row["state"] == "up" for row in again["results"])


def test_cli_plan_does_not_arm_trading(store, monkeypatch):
    monkeypatch.setenv("SYSTIMO_ROOT", str(store.root))
    from roller.systimo.cli import main

    assert main(["plan", "--scope", "quad-1"]) == 0
    assert main(["doctor", "--scope", "all"]) == 0
    text = (REPO / "ROLLER" / "roller" / "systimo" / "cli.py").read_text(encoding="utf-8")
    assert "VITAL_AWS_CONTROL" not in text or "does not set VITAL_AWS_CONTROL" in text
    assert "momento-live.service" in text
