"""Quad 1 NBA review desk. No submit. MLB routes stay on their own session."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _client() -> TestClient:
    import terminal_api

    return TestClient(terminal_api.app)


def test_policy_hash_matches_spec():
    policy_path = REPO / "research" / "vital" / "bots" / "nba-001" / "strategy" / "policy.json"
    spec = (REPO / "research" / "vital" / "bots" / "nba-001" / "strategy" / "NBA_001_STRATEGY_SPEC.md").read_text(
        encoding="utf-8"
    )
    digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    assert digest in spec
    assert payload["version"] in spec
    assert payload["decision_status"] == "PROVISIONAL"
    assert payload["submits"] is False
    assert payload["execution_authorized"] is False


def test_quad4_execution_binding_unchanged():
    text = (REPO / "research" / "systimo" / "registry" / "instances.csv").read_text(encoding="utf-8")
    assert "quad-4:algorithmic_execution,quad-4,algorithmic_execution,Algorithmic Execution,true" in text
    assert "quad-3:algorithmic_execution,quad-3,algorithmic_execution,Algorithmic Execution,true" in text
    assert "quad-1:algorithmic_execution,quad-1,algorithmic_execution,Algorithmic Execution,true" in text


def test_nba_routes_reject_non_nba_and_hide_mlb_artifacts(monkeypatch, tmp_path):
    from roller.systimo.errors import SystimoError

    fixture = tmp_path / "inspect.json"
    fixture.write_text(json.dumps({"ok": True, "unit_file_exists": False, "unit": {"LoadState": "not-found"}}))
    monkeypatch.setenv("MOMENTO_NBA001_INSPECT_FIXTURE", str(fixture))

    def fake(session_id, store=None):
        if session_id == "nba":
            return {"sport": "NBA", "quadrant_id": "quad-1", "session_id": session_id}
        if session_id == "mlb":
            return {"sport": "MLB", "quadrant_id": "quad-4", "session_id": session_id}
        raise SystimoError("SCOPE_REQUIRED", "unknown scope session", 401)

    monkeypatch.setattr("roller.systimo.scope.get_session", fake)
    client = _client()
    assert client.get("/momento/execution/nba/strategy").status_code == 401
    denied = client.get("/momento/execution/nba/strategy", headers={"x-momento-scope": "mlb"})
    assert denied.status_code == 403
    ok = client.get("/momento/execution/nba/strategy", headers={"x-momento-scope": "nba"})
    assert ok.status_code == 200
    assert "nba-001-v0" in ok.text
    assert "live_armed_confirmed" not in ok.text
    blocked = client.get("/momento/execution/nba/mlb-001", headers={"x-momento-scope": "nba"})
    assert blocked.status_code == 404
    runtime = client.get("/momento/execution/nba/runtime", headers={"x-momento-scope": "nba"}).json()
    assert runtime["runtime"] == "NOT_DEPLOYED"
    assert runtime["execution_authorized"] is False
    assert runtime["submits"] is False
    assert runtime["fills"] == "UNAVAILABLE"
    mlb = client.get("/vital/bots/mlb-001")
    assert mlb.status_code == 200
    assert mlb.json()["bot_id"] == "mlb-001"
