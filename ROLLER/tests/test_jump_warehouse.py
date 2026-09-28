"""Jump warehouse workbench. Read-only Phase 8 parquet. No copies."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roller.jump.drive import handle_preview, handle_refresh, handle_root, reset_library_cache
from roller.jump.errors import JumpError
from roller.jump.research import ASKED_SIX_KEY
from roller.jump.warehouse.parquet_desk import adapter_for, reset_connections
from roller.jump.warehouse.registry import get_warehouse, list_warehouses, require_available
from roller.jump.warehouse.relationships import relationship_graph
from roller.jump.warehouse.sql_guard import assert_readonly_sql
from roller.warehouse.layout import GAME_COLUMNS, warehouse_root
from roller.config import RollerConfig

REPO = Path(__file__).resolve().parents[2]
ROLLER_ROOT = REPO / "ROLLER"
NBA_WAREHOUSE = ROLLER_ROOT / "data" / "nba" / "2025_2026" / "derived" / "warehouse"
JUMP_UI = REPO / "frontend" / "roller-terminal" / "src" / "jump"
LIVE = (NBA_WAREHOUSE / "manifest.json").is_file() and (NBA_WAREHOUSE / "games" / "games.parquet").is_file()


def _client() -> TestClient:
    import sys

    sys.path.insert(0, str(ROLLER_ROOT / "scripts"))
    import terminal_api

    return TestClient(terminal_api.app)


@pytest.fixture(autouse=True)
def _workbench_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("JUMP_WORKBENCH_ROOT", str(tmp_path))
    reset_connections()
    reset_library_cache()
    yield
    reset_connections()
    reset_library_cache()


def test_sql_guard_rejects_mutating_statements():
    assert_readonly_sql("SELECT 1")
    assert_readonly_sql("WITH x AS (SELECT 1) SELECT * FROM x")
    with pytest.raises(JumpError) as exc:
        assert_readonly_sql("DELETE FROM games")
    assert exc.value.code == "QUERY_REJECTED"
    with pytest.raises(JumpError):
        assert_readonly_sql("DROP TABLE games")
    with pytest.raises(JumpError):
        assert_readonly_sql("INSERT INTO games SELECT * FROM games")
    with pytest.raises(JumpError):
        assert_readonly_sql("SELECT 1; SELECT 2")
    with pytest.raises(JumpError):
        assert_readonly_sql("COPY games TO 'out.csv'")
    with pytest.raises(JumpError):
        assert_readonly_sql("SELECT * FROM read_parquet('/tmp/x.parquet')")


def test_registry_lists_phase8_and_wnba_unavailable():
    rows = {row.id: row for row in list_warehouses()}
    assert "nba" in rows
    assert "wnba" in rows
    wnba = rows["wnba"]
    assert wnba.status == "WAREHOUSE_UNAVAILABLE"
    assert wnba.source_uri
    with pytest.raises(JumpError) as exc:
        require_available("wnba")
    assert exc.value.code == "WAREHOUSE_UNAVAILABLE"


@pytest.mark.skipif(not LIVE, reason="NBA Phase 8 warehouse absent")
def test_nba_registry_and_validate():
    rec = get_warehouse("nba")
    assert rec.status == "AVAILABLE"
    assert rec.source_uri == "ROLLER/data/nba/2025_2026/derived/warehouse"
    assert rec.read_only is True
    desk = adapter_for("nba")
    body = desk.validate()
    assert body["status"] == "ok"
    assert body["games_present"] is True


@pytest.mark.skipif(not LIVE, reason="NBA Phase 8 warehouse absent")
def test_nba_tables_match_layout_and_manifest():
    desk = adapter_for("nba")
    tables = {row["name"]: row for row in desk.list_tables()}
    assert set(tables) == {"games", "markets", "game_market_links", "observations", "pbp", "settlements"}
    man = json.loads((NBA_WAREHOUSE / "manifest.json").read_text(encoding="utf-8"))
    assert tables["games"]["row_count"] == man["games"]
    assert tables["markets"]["row_count"] == man["markets"]
    assert tables["observations"]["row_count"] == man["observation_rows"]
    assert tables["pbp"]["row_count"] == man["pbp_rows"]
    games = desk.describe_table("games")
    names = [c["name"] for c in games["columns"]]
    assert names[: len(GAME_COLUMNS)] == GAME_COLUMNS or all(col in names for col in GAME_COLUMNS)
    assert "orderbook" not in tables
    unavailable = {row["name"] for row in desk.unavailable_sources()}
    assert "orderbook" in unavailable
    assert "ticks" in unavailable


@pytest.mark.skipif(not LIVE, reason="NBA Phase 8 warehouse absent")
def test_observations_paginate_sort_filter_nulls():
    desk = adapter_for("nba")
    page = desk.preview_rows("observations", limit=50, page=1, sort="available_at", order="asc")
    assert page["returned"] == 50
    assert page["limit"] == 50
    assert page["table_row_count"] > 1_000_000
    assert page["nulls_preserved"] is True
    cols = page["columns"]
    assert "available_at" in cols
    assert "yes_bid_close" in cols
    two = desk.preview_rows("observations", limit=50, page=2, sort="available_at", order="asc")
    assert two["rows"] != page["rows"]
    games = desk.preview_rows(
        "games",
        columns=["internal_game_id", "sport", "season"],
        filters=[{"column": "sport", "op": "eq", "value": "NBA"}],
        limit=10,
    )
    assert games["returned"] >= 1
    assert all(row["sport"] == "NBA" for row in games["rows"])
    for row in page["rows"]:
        close = row.get("yes_bid_close")
        if close is not None:
            assert close == close


@pytest.mark.skipif(not LIVE, reason="NBA Phase 8 warehouse absent")
def test_mutating_sql_rejected_on_adapter():
    desk = adapter_for("nba")
    with pytest.raises(JumpError) as exc:
        desk.query("UPDATE games SET sport = 'X'")
    assert exc.value.code == "QUERY_REJECTED"
    out = desk.query("SELECT internal_game_id FROM games LIMIT 5")
    assert out["returned"] == 5
    assert out["read_only"] is True


@pytest.mark.skipif(not LIVE, reason="NBA Phase 8 warehouse absent")
def test_saved_query_persist_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("JUMP_WORKBENCH_ROOT", str(tmp_path))
    from roller.jump.warehouse.queries import create_saved, get_saved, list_saved

    row = create_saved(warehouse_id="nba", name="games head", sql="SELECT * FROM games LIMIT 3")
    loaded = get_saved(row["id"])
    assert loaded["sql"].upper().startswith("SELECT")
    assert loaded["materialized"] is False
    assert any(item["id"] == row["id"] for item in list_saved("query", warehouse_id="nba"))


@pytest.mark.skipif(not LIVE, reason="NBA Phase 8 warehouse absent")
def test_canonical_relationships_not_name_match():
    graph = relationship_graph("nba")
    statuses = {edge["status"] for edge in graph["edges"]}
    assert statuses == {"DECLARED"}
    assert all(edge.get("trusted") is True for edge in graph["edges"])
    assert any(edge["from_table"] == "games" and edge["to_table"] == "markets" for edge in graph["edges"])
    assert all(row["status"] == "CANDIDATE" for row in graph["candidates"])
    assert all(row.get("trusted") is False for row in graph["candidates"])


@pytest.mark.skipif(not LIVE, reason="NBA Phase 8 warehouse absent")
def test_lineage_source_uri_is_phase8():
    lineage = adapter_for("nba").lineage("observations")
    assert lineage["source_uri"] == "ROLLER/data/nba/2025_2026/derived/warehouse"
    assert "FIRST80_ASKED_SIX_80_40" in lineage["used_by"]
    assert lineage["writable_rows"] is False


@pytest.mark.skipif(not LIVE, reason="NBA Phase 8 warehouse absent")
def test_first80_nba_warehouse_is_warehouse_type():
    reset_library_cache()
    asked = handle_refresh()
    assert asked["writable"] is False
    from roller.jump.drive import build_index

    index = build_index()
    row = index["file.FIRST80_ASKED_SIX_80_40.warehouse-nba"]
    assert row["artifact_type"] == "WAREHOUSE"
    assert row["source_path"] == "ROLLER/data/nba/2025_2026/derived/warehouse"
    preview = handle_preview("file.FIRST80_ASKED_SIX_80_40.warehouse-nba")
    assert preview["artifact_type"] == "WAREHOUSE"
    assert "Directory pointer" not in (preview.get("note") or "")
    table = index["file.FIRST80_ASKED_SIX_80_40.warehouse-nba-games"]
    assert table["artifact_type"] == "TABLE"
    assert table["table_name"] == "games"
    assert "FIRST80_ASKED_SIX_80_40" in (table.get("used_by") or [])


def test_jump_still_defaults_nba_and_bots_http():
    root = handle_root()
    assert root["default_sport"] == "NBA"
    client = _client()
    assert client.get("/jump").json()["sport"] == "NBA"
    children = client.get(f"/jump/research/{ASKED_SIX_KEY}/children")
    assert children.status_code == 200
    assert client.get("/jump/bots").status_code == 200


@pytest.mark.skipif(not LIVE, reason="NBA Phase 8 warehouse absent")
def test_warehouse_http_opens_desk():
    client = _client()
    listed = client.get("/jump/warehouses").json()
    ids = [row["id"] for row in listed["warehouses"]]
    assert "nba" in ids
    nba = client.get("/jump/warehouses/nba").json()
    assert nba["status"] == "AVAILABLE"
    tables = client.get("/jump/warehouses/nba/tables").json()["tables"]
    names = [row["name"] for row in tables]
    assert "observations" in names
    cols = client.get("/jump/warehouses/nba/tables/games/columns").json()["columns"]
    assert any(col["name"] == "internal_game_id" for col in cols)
    rows = client.get("/jump/warehouses/nba/tables/observations/rows?limit=25&page=1").json()
    assert rows["returned"] == 25
    denied = client.post("/jump/warehouses/nba/query", json={"sql": "DELETE FROM games"})
    assert denied.status_code == 400
    wnba = client.get("/jump/warehouses/wnba").json()
    assert wnba["status"] == "WAREHOUSE_UNAVAILABLE"
    missing = client.get("/jump/warehouses/wnba/tables")
    assert missing.status_code == 404
    saved = client.post(
        "/jump/queries",
        json={"warehouse_id": "nba", "name": "probe", "sql": "SELECT 1 AS n"},
    )
    assert saved.status_code == 200
    qid = saved.json()["id"]
    assert client.get(f"/jump/queries/{qid}").status_code == 200
    rel = client.get("/jump/warehouses/nba/relationships").json()
    assert rel["edges"]


def test_frontend_warehouse_routes_exist():
    routing = (JUMP_UI / "routing.ts").read_text(encoding="utf-8")
    assert "warehouses" in routing
    assert "#/databases" in routing or '"#/databases"' in routing
    shell = (JUMP_UI / "JumpShell.tsx").read_text(encoding="utf-8")
    assert "WarehouseShell" in shell
    assert "WAREHOUSE" in shell
    sources = "\n".join(path.read_text(encoding="utf-8") for path in JUMP_UI.rglob("*.tsx"))
    assert "📁" not in sources
    assert "Create Bot" not in sources
    assert "5180" not in sources


def test_other_sports_use_same_adapter_shape():
    cfg = RollerConfig(root=ROLLER_ROOT)
    for sport, wid in (("NCAAB", "ncaab"), ("MLB", "mlb"), ("ATP", "atp"), ("WTA", "wta")):
        rec = get_warehouse(wid)
        desk = warehouse_root(cfg, sport, "2025-2026")
        present = (desk / "manifest.json").is_file()
        if present:
            assert rec.status == "AVAILABLE"
            assert rec.query_adapter == "duckdb_parquet"
        else:
            assert rec.status == "WAREHOUSE_UNAVAILABLE"
