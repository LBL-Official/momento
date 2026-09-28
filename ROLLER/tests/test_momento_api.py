"""Momento /momento façade. Adapters only. No NBA bot."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from roller.momento.registry import SYSTEM_COUNT, load_registry

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend" / "momento-systems" / "src"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _client() -> TestClient:
    import terminal_api

    return TestClient(terminal_api.app)


def test_momento_systems_facade():
    body = _client().get("/momento/systems").json()
    assert body["live_execution"] is False
    assert body["count"] == SYSTEM_COUNT == 19
    ids = [row["id"] for row in body["systems"]]
    assert len(ids) == len(set(ids))
    assert set(ids) == {row.id for row in load_registry().systems}
    for row in body["systems"]:
        assert row["frontend_target"]["url"]
        assert row["backend_target"]["kind"]
        assert row["live_capability"] is False


def test_momento_system_routes_and_existing_desks():
    client = _client()
    for system_id in load_registry().by_id():
        one = client.get(f"/momento/systems/{system_id}")
        assert one.status_code == 200, system_id
        logic = client.get(f"/momento/systems/{system_id}/logic")
        assert logic.status_code == 200, system_id
        assert logic.json()["live_execution"] is False
        health = client.get(f"/momento/systems/{system_id}/health")
        assert health.status_code == 200, system_id
        assert health.json()["state"] in {
            "RESEARCH_ONLY",
            "PARTIAL",
            "NOT_IMPLEMENTED",
            "UNKNOWN",
        }
        assert health.json()["ok"] is not True or health.json()["state"] != "NOT_IMPLEMENTED"
        schema = client.get(f"/momento/systems/{system_id}/schema")
        assert schema.status_code == 200, system_id
    assert client.get("/momento/systems/not-a-system").status_code == 404
    assert client.get("/choosin-texas/health").status_code == 200
    assert client.get("/austin/health").status_code == 200
    assert client.get("/vital/health").status_code == 200
    assert client.get("/health").json()["product"] == "ROLLER Terminal"


def test_algorithmic_execution_api_is_not_nba_bot():
    client = _client()
    row = client.get("/momento/systems/algorithmic_execution").json()
    assert row["status"] == "NOT_IMPLEMENTED"
    assert row["frontend_target"]["kind"] == "momento_page"
    assert "5180" not in row["frontend_target"]["url"]
    assert row["api_namespace"] != "/vital"
    health = client.get("/momento/systems/algorithmic_execution/health").json()
    assert health["state"] == "NOT_IMPLEMENTED"
    assert health["ok"] is None
    logic = client.get("/momento/systems/algorithmic_execution/logic").json()
    assert "NO NBA SUBMISSION IMPLEMENTATION" in logic["logic"]
    assert "No submission adapter is linked" in logic["logic"]
    vital = client.get("/vital/health")
    assert vital.status_code == 200


def test_existing_product_links_from_api():
    by_id = {row["id"]: row for row in _client().get("/momento/systems").json()["systems"]}
    assert by_id["database"]["frontend_target"]["url"] == "http://127.0.0.1:5179"
    assert by_id["data_analysis"]["frontend_target"]["url"] == "http://127.0.0.1:5179/?app=superasi"
    assert by_id["data_modeling"]["frontend_target"]["url"] == "http://127.0.0.1:5179/?app=jump"
    assert by_id["data_modeling"]["frontend_target"]["product"] == "Jump"
    assert "5180" not in by_id["data_modeling"]["frontend_target"]["url"]
    assert by_id["trade_breakdown"]["frontend_target"]["url"] == "http://127.0.0.1:5182#/"
    assert by_id["position_stratification"]["frontend_target"]["url"] == "http://127.0.0.1:5182#/austin"
    assert by_id["dynamic_risk_engine"]["frontend_target"]["url"] == "http://127.0.0.1:5191/"
    assert by_id["dynamic_risk_engine"]["frontend_target"]["product"] == "Drevo"
    assert by_id["hedging_analysis"]["frontend_target"]["url"] == "http://127.0.0.1:5192/"
    assert by_id["hedging_analysis"]["frontend_target"]["product"] == "Ballhog"
    assert by_id["relative_value_hedging"]["frontend_target"]["url"] == "http://127.0.0.1:5190/#/tk-ultra"
    assert by_id["relative_value_hedging"]["frontend_target"]["product"] == "TK Ultra"


def test_dataflow_and_aggregate_health():
    client = _client()
    flow = client.get("/momento/dataflow").json()
    assert ["database", "data_modeling"] in flow["bracket_edges"]
    assert flow["live_execution"] is False
    health = client.get("/momento/health").json()
    assert health["live_execution"] is False
    assert health["nba_bot"] == "NOT_IMPLEMENTED"
    assert health["count"] == 19
    assert health["frontend_probe"] == "UNKNOWN"
    dre = next(row for row in health["systems"] if row["system_id"] == "dynamic_risk_engine")
    assert "not execution policy" in dre["detail"].lower() or "Austin" in dre["detail"]
    exec_row = next(row for row in health["systems"] if row["system_id"] == "algorithmic_execution")
    assert exec_row["state"] == "NOT_IMPLEMENTED"
    assert exec_row["ok"] is None
    assert exec_row["frontend_probe"] == "UNKNOWN"
    maint = next(row for row in health["systems"] if row["system_id"] == "system_maintenance")
    assert maint["state"] in {"PARTIAL", "UNKNOWN"}
    db = next(row for row in health["systems"] if row["system_id"] == "database")
    assert db["nba"] in {"AVAILABLE", "WAREHOUSE_UNAVAILABLE"}
    assert db["ncaab"] in {"AVAILABLE", "WAREHOUSE_UNAVAILABLE"}
    assert db["delegate"] == "/momento/connection"


def test_momento_connection_nba_ncaab_query():
    body = _client().get("/momento/connection").json()
    assert body["live_execution"] is False
    assert body["roller"]["status"] == "CONNECTED"
    assert body["markets"]["nba"]["warehouse_id"] == "nba"
    assert body["markets"]["ncaab"]["warehouse_id"] == "ncaab"
    assert body["markets"]["nba"]["query"] in {"OK", "UNAVAILABLE"}
    assert body["markets"]["ncaab"]["query"] in {"OK", "UNAVAILABLE"}
    if body["markets"]["nba"]["query"] == "UNAVAILABLE":
        assert body["markets"]["nba"]["n"] is None
    if body["markets"]["ncaab"]["query"] == "UNAVAILABLE":
        assert body["markets"]["ncaab"]["n"] is None
    nba_rq = body["research_query"]["nba"]
    ncaab_rq = body["research_query"]["ncaab"]
    combined = body["research_query"]["combined"]
    if nba_rq["status"] == "OK":
        assert nba_rq["execution_path"] == "generic_query"
    if ncaab_rq["status"] == "OK":
        assert ncaab_rq["execution_path"] == "generic_query"
    if combined["status"] == "OK":
        assert "combined_league_union" in combined["available"]
    if body["markets"]["nba"]["query"] == "OK" and body["markets"]["ncaab"]["query"] == "OK":
        assert body["connected"] is True
        assert body["markets"]["nba"]["returned"] >= 1
        assert body["markets"]["ncaab"]["returned"] >= 1
        nba_sql = _client().post(
            "/jump/warehouses/nba/query",
            json={"sql": "SELECT sport, count(*) AS n FROM games GROUP BY 1"},
        )
        ncaab_sql = _client().post(
            "/jump/warehouses/ncaab/query",
            json={"sql": "SELECT sport, count(*) AS n FROM games GROUP BY 1"},
        )
        assert nba_sql.status_code == 200
        assert ncaab_sql.status_code == 200
        assert nba_sql.json()["returned"] >= 1
        assert ncaab_sql.json()["returned"] >= 1
        assert nba_sql.json()["read_only"] is True
        assert ncaab_sql.json()["read_only"] is True


def test_frontend_uses_registry_api_not_hardcoded_products():
    if not FRONTEND.is_dir():
        return
    sources = "\n".join(p.read_text(encoding="utf-8") for p in FRONTEND.rglob("*.tsx"))
    sources += "\n" + "\n".join(p.read_text(encoding="utf-8") for p in FRONTEND.rglob("*.ts"))
    assert "/api/momento/systems" in sources
    assert "/api/momento/connection" in sources
    assert "/api/momento/tk-ultra" in sources
    assert "Backend" in sources
    assert "Frontend" in sources
    assert "http://127.0.0.1:5179" not in Path(FRONTEND / "Bracket.tsx").read_text(encoding="utf-8")
    assert "http://127.0.0.1:5182" not in Path(FRONTEND / "Bracket.tsx").read_text(encoding="utf-8")
    assert "http://127.0.0.1:5180" not in sources
    inspector = Path(FRONTEND / "Inspector.tsx").read_text(encoding="utf-8")
    assert 'systemId === "system_maintenance"' in inspector
    assert 'systemId === "data_ingestion"' in inspector
    assert 'systemId === "database"' in inspector
    assert "MarketQuery" in inspector
    assert "NO NBA SUBMISSION IMPLEMENTATION" in inspector
    app = Path(FRONTEND / "App.tsx").read_text(encoding="utf-8")
    assert "CONNECTING" in app
    assert "fetchConnection" in app
    for token in ("pkill", "lsof", "killExisting", "spawnApi"):
        assert token not in sources
    spin = REPO / "scripts" / "spin_momento_bracket.sh"
    spin_text = spin.read_text(encoding="utf-8")
    assert "8791" in spin_text
    assert "5190" in spin_text
    assert "5179" in spin_text
    assert "/momento/connection" in spin_text
    assert "nba" in spin_text and "ncaab" in spin_text
    assert "start_new_session" in spin_text
    layout = Path(FRONTEND / "layout.ts").read_text(encoding="utf-8")
    assert "trade_reconciliation:" in layout
    assert "system_orchestration:" in layout
    assert "h: 476" in layout
