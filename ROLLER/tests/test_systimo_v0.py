"""Systimo V0: CSV registry, graph, health, Jump tunnels, query, artifacts."""

from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "research" / "systimo"
SYSTIMO_PY = Path(__file__).resolve().parents[1] / "roller" / "systimo"
JUMP_PY = Path(__file__).resolve().parents[1] / "roller" / "jump"
SYSTIMO_UI = REPO / "frontend" / "systimo" / "src"
AUSTIN_N = 604
CHOOSIN_N = 936


@pytest.fixture()
def store(tmp_path, monkeypatch):
    dst = tmp_path / "systimo"
    shutil.copytree(SEED, dst, ignore=shutil.ignore_patterns("generated", "__pycache__"))
    monkeypatch.setenv("SYSTIMO_ROOT", str(dst))
    from roller.systimo.store import CsvStore

    csv_store = CsvStore(dst)
    csv_store.validate_all()
    return csv_store


def _client() -> TestClient:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    return TestClient(terminal_api.app)


def test_n_locks_have_not_drifted():
    from roller.austin.locks import N_TRADES
    from roller.choosin_texas.locks import POOL_N

    assert int(N_TRADES) == AUSTIN_N
    assert int(POOL_N) == CHOOSIN_N


def test_csv_pk_fk_enums_and_append_only(store):
    from roller.systimo.errors import SystimoError

    systems = store.read("systems")
    assert {row["system_id"] for row in systems} >= {
        "austin",
        "choosin_texas",
        "ballhog",
        "tk_ultra",
        "jump",
        "systimo",
        "ls",
        "position_management",
    }
    with pytest.raises(SystimoError) as dup:
        store.append(
            "systems",
            {**systems[0], "system_id": systems[0]["system_id"]},
        )
    assert dup.value.code == "DUPLICATE_PK"
    with pytest.raises(SystimoError) as fk:
        row = dict(store.read("connections")[0])
        row["connection_id"] = "broken_fk"
        row["source_system_id"] = "not_a_system"
        store.append("connections", row)
    assert fk.value.code == "BROKEN_FK"
    with pytest.raises(SystimoError) as enum_err:
        row = dict(store.read("connections")[0])
        row["connection_id"] = "bad_enum"
        row["lifecycle"] = "LIVE"
        store.upsert("connections", row)
    assert enum_err.value.code == "BAD_ENUM"
    store.append(
        "connection_events",
        {
            "event_id": "evt1",
            "connection_id": "austin_to_jump",
            "observed_at": "2026-09-21T00:00:00Z",
            "previous_status": "UNKNOWN",
            "new_status": "HEALTHY",
            "check_type": "TEST",
            "latency_ms": "1",
            "error_code": "",
            "error_message": "",
            "source_timestamp": "2026-09-21T00:00:00Z",
        },
    )
    with pytest.raises(SystimoError) as append_err:
        store.write("connection_events", [])
    assert append_err.value.code == "APPEND_ONLY"


def test_atomic_write_does_not_leave_tmp(store):
    store.upsert(
        "systems",
        {**store.read("systems")[0], "description": "rewritten"},
    )
    leftovers = list(store.path_for("systems").parent.glob(".systems.*.tmp"))
    assert leftovers == []
    assert any(row["description"] == "rewritten" for row in store.read("systems"))


def test_graph_and_tree_from_csv_only(store):
    from roller.systimo.graph.build import load_graph, load_tree, path_back, paths, write_generated

    graph = load_graph(store)
    tree = load_tree(store)
    ids = {node["id"] for node in graph["nodes"]}
    assert "austin" in ids
    assert "jump" in ids
    edge_ids = {edge["id"] for edge in graph["edges"]}
    assert "austin_to_ballhog" in edge_ids
    assert "austin_to_tk_ultra" in edge_ids
    assert "austin_to_jump" in edge_ids
    assert "austin_to_ballhog_to_tk_ultra" not in edge_ids
    assert "POSITION_STRATIFICATION" in tree["domains"]
    found = paths(store, "choosin_texas", "jump")
    assert ["choosin_texas", "jump"] in found
    back = path_back(store, "jump")
    nodes = {node for trail in back for node in trail}
    assert "austin" in nodes
    assert "ballhog" in nodes or "roller" in nodes
    written = write_generated(store)
    assert Path(written["tree"]).is_file()
    assert Path(written["graph"]).is_file()


def test_health_lock_drift_is_integrity_drift_not_repaired(store, monkeypatch):
    from roller.systimo.health.refresh import check_austin_lock, check_choosin_lock, refresh

    monkeypatch.setattr("roller.austin.locks.N_TRADES", 999)
    row = next(item for item in store.read("connections") if item["connection_id"] == "austin_to_jump")
    result = check_austin_lock(row)
    assert result["error_code"] == "INTEGRITY_DRIFT"
    assert result["status"] == "MISCONFIGURED"
    assert row["expected_lock"] == "N=604"
    monkeypatch.setattr("roller.choosin_texas.locks.POOL_N", 1)
    choosin = next(item for item in store.read("connections") if item["connection_id"] == "choosin_to_jump")
    bad = check_choosin_lock(choosin)
    assert bad["error_code"] == "INTEGRITY_DRIFT"
    body = refresh(store, connection_id="ballhog_to_pm")
    assert body["results"][0]["health"] == "HEALTHY"
    assert all(item["health"] != "RUNNING" for item in store.read("connections"))


def test_seeded_edges_match_recon(store):
    rows = {row["connection_id"]: row for row in store.read("connections")}
    implemented = {
        "austin_to_ballhog",
        "choosin_to_ballhog",
        "austin_to_tk_ultra",
        "choosin_to_tk_ultra",
        "austin_to_dre",
        "choosin_to_dre",
        "vital_to_jump",
        "roller_warehouse_to_jump",
        "superasi_iti_to_jump",
        "tk_ultra_ballhog_sibling",
        "austin_to_jump",
        "choosin_to_jump",
        "ls_observe",
        "ballhog_to_pm",
        "tk_ultra_to_pm",
        "positman_to_drevo",
        "positman_to_jump",
        "drevo_to_jump",
    }
    for key in implemented:
        assert rows[key]["lifecycle"] == "IMPLEMENTED"
        assert rows[key]["permission"] in {"QUERY", "READ", "WRITE"}
    assert rows["ballhog_to_pm"]["lifecycle"] == "IMPLEMENTED"
    assert rows["tk_ultra_to_pm"]["permission"] == "QUERY"
    assert rows["ballhog_to_pm"]["permission"] == "QUERY"


def test_query_consumers_of_austin_and_path(store):
    from roller.systimo.query.executor import execute

    reverse = execute({"query_type": "reverse_dependencies", "system": "austin"}, store)
    consumers = {row["target_system_id"] for row in reverse["result"]}
    assert consumers == {"ballhog", "tk_ultra", "dre", "jump"}
    path = execute({"query_type": "paths", "from": "choosin_texas", "to": "jump"}, store)
    assert ["choosin_texas", "jump"] in path["result"]
    deps = execute({"query_type": "dependencies", "system": "jump"}, store)
    sources = {row["source_system_id"] for row in deps["result"]}
    assert {"austin", "choosin_texas", "vital"} <= sources


def test_artifact_immutable_and_rerun(store):
    from roller.systimo.artifacts.writer import save_artifact
    from roller.systimo.query.executor import execute

    answer = execute({"query_type": "systems"}, store)
    first = save_artifact(answer["query_id"], store)
    path = Path(first["path"])
    original = path.read_text(encoding="utf-8")
    checksum = first["checksum"]
    path.write_text("tamper", encoding="utf-8")
    path.write_text(original, encoding="utf-8")
    second = save_artifact(answer["query_id"], store, kind="md", rerun_of=first["artifact_id"])
    assert second["artifact_id"] != first["artifact_id"]
    assert second["rerun_of"] == first["artifact_id"]
    assert second["format"] == "md"
    rows = {row["artifact_id"]: row for row in store.read("artifacts_index")}
    assert rows[first["artifact_id"]]["checksum"] == checksum
    assert rows[second["artifact_id"]]["rerun_of"] == first["artifact_id"]


def test_observe_plan_apply_allowlist(store):
    from roller.systimo.actions.handlers import apply_action, dry_run, propose
    from roller.systimo.agents.runner import run_agent
    from roller.systimo.errors import SystimoError
    from roller.systimo.query.executor import execute

    answer = execute({"query_type": "health"}, store)
    proposed = propose(answer["answer_id"], store)
    assert proposed[0]["action_type"] == "RECHECK_HEALTH"
    plan = dry_run(proposed[0]["action_id"], store)
    assert plan["mode"] == "PLAN"
    assert plan["result"]["mutates"] is False
    applied = apply_action("act_validate", store)
    assert applied["status"] == "APPLIED"
    store.append(
        "actions",
        {
            "action_id": "act_shell",
            "action_type": "UI_SHELL",
            "target_system": "systimo",
            "target_resource": "ui",
            "reason": "forbidden",
            "source_answer_id": "",
            "dry_run_supported": "false",
            "approval_required": "true",
            "risk_class": "HIGH",
            "handler": "UI_SHELL",
            "status": "PROPOSED",
        },
    )
    with pytest.raises(SystimoError) as rejected:
        apply_action("act_shell", store)
    assert rejected.value.code == "APPLY_REJECTED"
    run = run_agent("dependency_manager", store)
    assert run["status"] == "COMPLETE"
    assert run["proposed_action_ids"]
    history = store.read("agent_runs")
    assert history[-1]["applied_action_ids"] == ""


def test_jump_research_context_tunnels():
    from roller.jump.adapters.austin import query_at, research_context as austin_ctx
    from roller.jump.adapters.choosin import research_context as choosin_ctx
    from roller.jump.errors import JumpError

    austin = austin_ctx()
    assert austin["live_execution"] is False
    assert austin["n"] == AUSTIN_N
    assert austin["availability"] != "$0"
    choosin = choosin_ctx()
    assert choosin["n"] == CHOOSIN_N
    assert choosin["write"] == "DENY"
    assert choosin["availability"] != "$0"
    with pytest.raises(JumpError):
        query_at({}, "2026-01-01T00:00:00Z", persist=True)
    client = _client()
    austin_http = client.get("/jump/research-context/austin").json()
    choosin_http = client.get("/jump/research-context/choosin").json()
    assert austin_http["source"] == "AUSTIN"
    assert choosin_http["source"] == "CHOOSIN_TEXAS"
    assert austin_http.get("conditional_ev_cents") != 0 or austin_http["availability"] in {
        "UNAVAILABLE",
        "OBSERVED",
        "OK",
        "READY",
    }


def test_jump_does_not_import_ballhog_or_tk_ultra_adapters():
    blob = "\n".join(path.read_text(encoding="utf-8") for path in (JUMP_PY / "adapters").glob("*.py"))
    assert "roller.ballhog.adapters" not in blob
    assert "roller.tk_ultra.adapters" not in blob


def test_http_health_query_artifact_and_cli(store, monkeypatch, capsys):
    monkeypatch.setenv("SYSTIMO_ROOT", str(store.root))
    client = _client()
    health = client.get("/systimo/health").json()
    assert health["product"] == "Systimo"
    assert health["live_execution"] is False
    assert health["csv_valid"] is True
    assert health["position_management"] == "QUERY"
    tree = client.get("/systimo/tree").json()
    assert "austin" in tree["systems"]
    reverse = client.post(
        "/systimo/query",
        json={"query_type": "reverse_dependencies", "system": "austin"},
    ).json()
    consumers = {row["target_system_id"] for row in reverse["result"]}
    assert "jump" in consumers
    art = client.post(f"/systimo/query/{reverse['query_id']}/artifact", json={"kind": "json"}).json()
    assert art["checksum"]
    dry = client.post("/systimo/actions/act_tree/dry-run").json()
    assert dry["status"] == "DRY_RUN"
    from roller.systimo.__main__ import main

    assert main(["health"]) == 0
    out = capsys.readouterr().out
    assert "Systimo" in out


def test_package_and_frontend_have_no_orders_or_hidden_graph():
    blob = "\n".join(path.read_text(encoding="utf-8") for path in SYSTIMO_PY.rglob("*.py"))
    assert "place_order" not in blob
    assert "ENABLE_LIVE_TRADING" not in blob
    assert "momento-live.service" not in blob or "Does not start/stop" in blob
    tree = ast.parse((SYSTIMO_PY / "api.py").read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    assert not any("kalshi" in name for name in imported)
    if not SYSTIMO_UI.is_dir():
        return
    sources = "\n".join(path.read_text(encoding="utf-8") for path in SYSTIMO_UI.rglob("*.tsx"))
    sources += "\n" + "\n".join(path.read_text(encoding="utf-8") for path in SYSTIMO_UI.rglob("*.ts"))
    assert "/systimo/" in sources
    assert 'const API_BASE = "/api"' in sources
    assert "place_order" not in sources
    assert "/vital/start" not in sources
    assert "austin_to_ballhog" not in sources
    assert "const EDGES" not in sources
    assert "ENABLE_LIVE_TRADING" not in sources


def test_capability_unregistered_is_unavailable(store):
    from roller.systimo.query.capabilities import invoke_capability
    from roller.systimo.query.executor import execute

    missing = invoke_capability("NOT_A_CAPABILITY")
    assert missing["availability"] == "UNAVAILABLE"
    assert missing["error_code"] == "UNREGISTERED_INTERFACE"
    body = execute(
        {"query_type": "interfaces", "capability": "CHOOSIN_TRADE_CONTEXT"},
        store,
    )
    invoked = body["result"]["invoked"]
    assert invoked["n"] == CHOOSIN_N or invoked["availability"] == "UNAVAILABLE"
    assert invoked.get("conditional_ev_cents") != 0 or "n" in invoked
