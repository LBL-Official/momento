"""STAX library + HTTP handlers."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from roller.stax.api import handle_create, handle_export, handle_run
from tests.stax_fixtures import envelope, source


def test_create_requires_name(tmp_path):
    import pytest
    from roller.stax.models import StaxError

    with pytest.raises(StaxError) as exc:
        handle_create({"members": [source()]}, root=tmp_path)
    assert exc.value.code == "STAX_NAME_REQUIRED"


def test_run_and_export_package(tmp_path, monkeypatch):
    monkeypatch.setenv("STAX_LIBRARY_ROOT", str(tmp_path))
    created = handle_create({"name": "NBA Q3 Path Research", "members": [source(), source(name="B", question_hash="b")]}, root=tmp_path)
    stax_id = created["stax"]["stax_id"]

    def execute_question(_payload):
        return envelope(games=["G1", "G2"], dataset_version="ds-1")

    from roller.stax import runner

    out = runner.run_stax(stax_id, root=tmp_path, execute_question=execute_question)
    assert out["status"] == "COMPLETE"
    pkg = handle_export(stax_id, root=tmp_path)
    assert pkg["schema_version"] == "stax_result_package_v1"
    assert pkg["live_execution"] is False
    assert pkg["aggregation_method"] == "NONE"
    assert len(pkg["members"]) == 2
    assert pkg["members"][0]["member_id"].startswith("STXM-")
    assert pkg["stax_id"] == stax_id


def test_http_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("STAX_LIBRARY_ROOT", str(tmp_path))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    health = client.get("/health").json()
    assert "stax" in health["capabilities"]
    created = client.post("/stax", json={"name": "NBA PATH RESEARCH", "members": [source()]}).json()
    stax_id = created["stax"]["stax_id"]
    listed = client.get("/stax").json()
    assert listed["n"] >= 1
    got = client.get(f"/stax/{stax_id}")
    assert got.status_code == 200
    bad = client.post("/stax", json={"name": "x", "timeframe_mode": "ROLLING"})
    assert bad.status_code == 400


def test_run_ignores_client_execution_controls(tmp_path, monkeypatch):
    monkeypatch.setenv("STAX_LIBRARY_ROOT", str(tmp_path))
    created = handle_create({"name": "NBA PATH RESEARCH", "members": [source()]}, root=tmp_path)
    stax_id = created["stax"]["stax_id"]

    def execute_question(payload):
        assert "execution_path" not in payload
        assert payload.get("dataset") is None
        return envelope(games=["G1", "G2"], dataset_version="ds-server")

    from roller.stax import runner

    monkeypatch.setattr(
        runner,
        "execute_stack",
        lambda members, **kwargs: __import__("roller.stax.executor", fromlist=["execute_stack"]).execute_stack(
            members, execute_question=execute_question
        ),
    )

    # persist_run calls execute_stack from executor, not runner.execute_stack.
    monkeypatch.setattr(
        "roller.stax.runner.execute_stack",
        lambda members, **kwargs: __import__("roller.stax.executor", fromlist=["execute_stack"]).execute_stack(
            members, execute_question=execute_question
        ),
    )

    out = handle_run(
        stax_id,
        {
            "execution_path": "frozen_reference",
            "dataset": "hacked",
            "N": 999,
            "population_n": 999,
            "version_id": "9.9.9",
            "version": "9.9.9",
            "reference_match": "FIRST80_Q3",
            "members": [
                {
                    **source(),
                    "execution_path": "frozen_reference",
                    "n": 999,
                    "dataset": "hacked",
                    "version_id": "9.9.9",
                    "reference_match": "FIRST80_Q3",
                }
            ],
        },
        root=tmp_path,
    )
    assert out["version"] == "1.0.0"
    assert out["version"] != "9.9.9"
    assert out["results"][0]["summary"]["n"] == 2
    assert "execution_path" not in out["members"][0]
    assert out["members"][0].get("dataset_version") != "hacked"
