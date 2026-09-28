"""Jump canonical data plane. Query the stack. Do not copy sources."""

from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roller.jump.data.models import AUSTIN_N, CHOOSIN_N, DEFAULT_TRADE_ID, LIVE_EXECUTION
from roller.jump.errors import JumpError

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "research" / "systimo"
JUMP_PY = Path(__file__).resolve().parents[1] / "roller" / "jump"
JUMP_UI = REPO / "frontend" / "roller-terminal" / "src" / "jump"
NBA_WAREHOUSE = REPO / "ROLLER" / "data" / "nba" / "2025_2026" / "derived" / "warehouse"
LIVE_NBA = (NBA_WAREHOUSE / "manifest.json").is_file()


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


def test_capability_resolution_uses_systimo_tunnels(store):
    from roller.jump.data.catalog import require_query_connection
    from roller.jump.data.router import HANDLERS, capabilities

    for cap in (
        "AUSTIN_QUERY_AT",
        "CHOOSIN_TRADE_CONTEXT",
        "ROLLER_OBSERVATIONS",
        "BALLHOG_INTENT",
        "TK_ULTRA_ASSESSMENT",
        "VITAL_BOT_STATUS",
        "SYSTIMO_CATALOG",
    ):
        row = require_query_connection(cap, store)
        assert row["permission"] in {"QUERY", "READ"}
        assert row["lifecycle"] == "IMPLEMENTED"
        assert row["target_system_id"] == "jump"
        assert cap in HANDLERS
    assert "AUSTIN_QUERY_AT" in capabilities()
    with pytest.raises(JumpError) as missing:
        require_query_connection("NOT_A_CAPABILITY", store)
    assert missing.value.code == "UNREGISTERED_INTERFACE"


def test_router_envelope_and_no_if_austin_in_ui():
    from roller.jump.data.api import handle_query

    body = handle_query({"capability": "CHOOSIN_TRADE_CONTEXT"})
    assert body["schema"] == "jump.data.v0"
    assert body["query_id"]
    assert body["source_system"] == "choosin_texas"
    assert body["source_resource"]
    assert "result" in body
    assert body["provenance"]["copy"] is False
    assert body["live_execution"] is False
    assert "warnings" in body
    blob = (JUMP_UI / "data" / "DataExplorer.tsx").read_text(encoding="utf-8")
    assert "if (query === \"austin\")" not in blob
    assert "const TREE" not in blob


def test_austin_query_through_jump():
    from roller.jump.data.api import handle_query

    body = handle_query({"capability": "AUSTIN_QUERY_AT", "trade_id": DEFAULT_TRADE_ID})
    result = body["result"]
    assert body["source_system"] == "austin"
    assert result["universe"] == "choosin_nba_2q3q_604"
    assert result["n"] == AUSTIN_N
    assert result["write"] == "DENY"
    assert result["live_execution"] is False
    assert "austin.conditional_ev_cents" in result
    if result.get("availability") != "UNAVAILABLE":
        assert result["trade_id"] == DEFAULT_TRADE_ID


def test_choosin_query_through_jump():
    from roller.jump.data.api import handle_query

    body = handle_query({"capability": "CHOOSIN_TRADE_CONTEXT"})
    result = body["result"]
    assert result["universe"] == "derived_four_936"
    assert result["n"] == CHOOSIN_N
    assert result["pit_kind"] == "STATIC"
    assert result["data_mode"] == "STATIC"
    assert "choosin.population_survival" in result


def test_roller_query_through_jump():
    from roller.jump.data.api import handle_query

    body = handle_query({"capability": "ROLLER_GAME_IDENTITY", "limit": 5})
    result = body["result"]
    assert result["source_system"] == "roller"
    assert result["write"] == "DENY" or result.get("availability") == "UNAVAILABLE"
    assert result.get("handle", {}).get("copy") is False or result.get("availability") == "UNAVAILABLE"
    if LIVE_NBA and result.get("availability") != "UNAVAILABLE":
        assert result["table"] in {"games", "game_market_links"}


def test_ballhog_and_tk_ultra_read_only():
    from roller.jump.data.api import handle_query

    ballhog = handle_query({"capability": "BALLHOG_INTENT", "trade_id": DEFAULT_TRADE_ID})
    tk = handle_query({"capability": "TK_ULTRA_ASSESSMENT", "trade_id": DEFAULT_TRADE_ID})
    assert ballhog["source_system"] == "ballhog"
    assert tk["source_system"] == "tk_ultra"
    assert ballhog["result"]["write"] == "DENY" or ballhog["result"].get("availability") == "UNAVAILABLE"
    assert "ballhog.rho_star" in ballhog["result"]
    assert "tk_ultra.gross_route_edge" in tk["result"]
    blob = "\n".join(path.read_text(encoding="utf-8") for path in (JUMP_PY / "data" / "adapters").glob("*.py"))
    assert "roller.ballhog.adapters" not in blob
    assert "roller.tk_ultra.adapters" not in blob


def test_unavailable_source_isolation(monkeypatch):
    from roller.jump.data import context as ctx
    from roller.jump.data.models import UNAVAILABLE

    def down(_params):
        raise RuntimeError("austin fixture down")

    monkeypatch.setattr(ctx.austin, "query_at_payload", down)
    monkeypatch.setattr(ctx.austin, "get_trade_payload", down)
    body = ctx.compose(DEFAULT_TRADE_ID, None)
    assert body["Austin"]["availability"] == UNAVAILABLE
    assert body["Austin"]["n"] == AUSTIN_N
    assert body["Choosin"]["n"] == CHOOSIN_N
    assert body["Choosin"]["availability"] != "$0"
    assert body["Ballhog"]["availability"] != "$0"
    assert body["live_execution"] is False
    assert body["write"] == "DENY"


def test_pit_rejects_future_source_timestamp(monkeypatch):
    from roller.jump.data.adapters import austin as austin_ad
    from roller.jump.adapters import austin as austin_src

    monkeypatch.setattr(
        austin_src,
        "get_trade",
        lambda _tid: {
            "trade_id": DEFAULT_TRADE_ID,
            "ticker": "KXTEST",
            "event_id": "E1",
            "game_id": "G1",
        },
    )
    monkeypatch.setattr(
        austin_src,
        "query_at",
        lambda _trade, _stamp, persist=False: {
            "status": "OBSERVED",
            "source_timestamp": "2099-01-01T00:00:00Z",
            "conditional_ev": {"conditional_ev_cents": 1},
            "support": {},
        },
    )
    body = austin_ad.query_at_payload({"trade_id": DEFAULT_TRADE_ID, "as_of": "2020-01-01T00:00:00Z"})
    assert body["availability"] == "UNAVAILABLE"
    assert body["error_code"] == "PIT_REJECTED"


def test_lineage_show_source_does_not_invent_row_ids():
    from roller.jump.data.api import handle_lineage

    body = handle_lineage("austin", {"capability": "AUSTIN_QUERY_AT", "trade_id": DEFAULT_TRADE_ID})
    lineage = body["lineage"]
    assert lineage["result_system"] == "jump"
    assert lineage["copy"] is False
    assert any(row["system_id"] == "austin" for row in lineage["parents"])
    for row in lineage["source_rows"]:
        assert "parquet_row_id" not in row
        assert row.get("kind") in {"trade", "game", "observation", None} or "kind" in row
    assert "universe" in body
    assert body["live_execution"] is False


def test_dataset_export_does_not_transfer_ownership(tmp_path, monkeypatch, store):
    from roller.jump.data import export as export_mod

    monkeypatch.setattr(export_mod, "export_dir", lambda: tmp_path)
    body = export_mod.export_dataset("austin_nba_2q3q_604")
    assert body["owner"] == "austin"
    assert body["copy"] is False
    assert body["checksum"]
    assert Path(body["path"]).is_file()
    roller = export_mod.export_dataset("roller_nba_warehouse")
    assert roller["owner"] == "roller"
    assert roller["copy"] is False
    handles = export_mod.dataset_handles()
    ids = {row["dataset_id"] for row in handles}
    assert "austin_nba_2q3q_604" in ids
    assert any(str(row.get("dataset_id") or "").startswith("roller") for row in handles)


def test_no_cache_module():
    assert not (JUMP_PY / "data" / "cache.py").exists()


def test_universes_displayed_not_mixed():
    from roller.jump.data.context import compose

    body = compose(DEFAULT_TRADE_ID, None)
    assert body["universes"]["austin"]["n"] == AUSTIN_N
    assert body["universes"]["choosin_texas"]["n"] == CHOOSIN_N
    assert body["Austin"]["n"] != body["Choosin"]["n"]
    assert "not mixed" in body["note"].lower()
    assert "austin.conditional_ev_cents" in body["Austin"]
    assert "choosin.population_survival" in body["Choosin"]
    assert "ballhog.rho_star" in body["Ballhog"]
    assert "tk_ultra.gross_route_edge" in body["TKUltra"]
    tree = body.get("tree")
    # tree is attached by handle_context
    from roller.jump.data.api import handle_context

    full = handle_context(DEFAULT_TRADE_ID, None)
    ids = [node["id"] for node in full["tree"]["nodes"]]
    assert ids == ["identity", "market", "pbp", "first80", "alpha", "hedge", "rv", "position", "risk", "execution"]
    assert full["identity"]["trade_id"] == DEFAULT_TRADE_ID
    assert full["live_execution"] is LIVE_EXECUTION


def test_http_data_plane_and_acceptance_trade():
    client = _client()
    sources = client.get("/jump/data/sources").json()
    assert sources["write"] == "DENY"
    assert "AUSTIN_QUERY_AT" in sources["capabilities"]
    ctx = client.get(f"/jump/data/context/{DEFAULT_TRADE_ID}").json()
    assert ctx["identity"]["trade_id"] == DEFAULT_TRADE_ID
    assert ctx["Austin"]["n"] == AUSTIN_N
    assert ctx["Choosin"]["n"] == CHOOSIN_N
    assert ctx["tree"]["nodes"]
    queried = client.post(
        "/jump/data/query",
        json={"capability": "AUSTIN_QUERY_AT", "trade_id": DEFAULT_TRADE_ID},
    ).json()
    assert queried["schema"] == "jump.data.v0"
    lineage = client.get(
        f"/jump/data/lineage/austin?capability=AUSTIN_QUERY_AT&trade_id={DEFAULT_TRADE_ID}"
    ).json()
    assert lineage["lineage"]["parents"]
    datasets = client.get("/jump/data/datasets").json()
    assert datasets["n"] >= 1
    health = client.get("/health").json()
    assert "jump_data" in health["capabilities"]


def test_systimo_jump_tunnels_and_path_back(store):
    from roller.systimo.graph.build import path_back
    from roller.systimo.query.executor import execute

    rows = {row["connection_id"]: row for row in store.read("connections")}
    for key in (
        "austin_to_jump",
        "choosin_to_jump",
        "ballhog_to_jump",
        "tk_ultra_to_jump",
        "roller_observations_to_jump",
        "vital_to_jump",
        "systimo_catalog_to_jump",
    ):
        assert rows[key]["permission"] in {"QUERY", "READ"}
        assert rows[key]["lifecycle"] == "IMPLEMENTED"
        assert rows[key]["target_system_id"] == "jump"
    trails = path_back(store, "jump")
    flat = {node for trail in trails for node in trail}
    assert "austin" in flat
    assert "choosin_texas" in flat
    assert "roller" in flat
    body = execute({"query_type": "path_back", "from": "jump"}, store)
    assert body["result"]
    gov = {row["governance_id"]: row for row in store.read("governance")}
    assert gov["gov_austin_jump_write"]["permission"] == "DENY"
    assert gov["gov_ballhog_jump"]["permission"] == "QUERY"


def test_frontend_data_explorer_uses_backend_tree():
    routing = (JUMP_UI / "routing.ts").read_text(encoding="utf-8")
    assert "dataPlane" in routing
    assert "#/${sport}/data" in routing or "#/${sport}/data/" in routing
    shell = (JUMP_UI / "JumpShell.tsx").read_text(encoding="utf-8")
    assert "DataExplorer" in shell
    explorer = (JUMP_UI / "data" / "DataExplorer.tsx").read_text(encoding="utf-8")
    assert "context?.tree" in explorer
    assert "place_order" not in explorer
    assert "/vital/start" not in explorer
    assert "ENABLE_LIVE_TRADING" not in explorer
    blob = "\n".join(path.read_text(encoding="utf-8") for path in (JUMP_PY / "data").rglob("*.py"))
    assert "place_order" not in blob
    assert "ENABLE_LIVE_TRADING" not in blob
    assert LIVE_EXECUTION is False
