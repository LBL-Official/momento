"""nba-001 worker observe. RUNNING != HEALTHY != EXECUTING. Unread is never $0."""

from __future__ import annotations

import base64
import json
import sys
import time
import zlib
from pathlib import Path

import pytest

from roller.momento import nba_001_runtime as rt

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _z(text: str) -> str:
    return base64.b64encode(zlib.compress(text.encode())).decode()


def _fixture(tmp_path, monkeypatch, payload: dict) -> None:
    path = tmp_path / "inspect.json"
    path.write_text(json.dumps(payload))
    monkeypatch.setenv(rt.FIXTURE_ENV, str(path))


def _deployed(heartbeat_at: int, *, sha: str = "abc", active: str = "active") -> dict:
    status = {
        "schema": "nba_001_status_v1",
        "mode": "SHADOW",
        "heartbeat_at": heartbeat_at,
        "binary_sha256": "abc",
        "submits": False,
        "submission_adapter_linked": False,
        "blockers": {"EXIT_CAPACITY_UNBOUNDED": {}},
    }
    return {
        "ok": True,
        "unit_file_exists": True,
        "unit": {"ActiveState": active, "SubState": "running" if active == "active" else "dead", "LoadState": "loaded"},
        "binary_sha256": sha,
        "status_z": _z(json.dumps(status)),
        "journal_tail_z": _z('{"kind": "WORKER_START"}\nnot json\n{"kind": "SERIES_ROUTE"}'),
        "momento_live_active": "active",
    }


def test_inspect_script_is_read_only():
    script = rt.inspect_script()
    assert '"systemctl", "show"' in script
    for verb in ("start", "stop", "restart", "kill", "enable", "disable", "daemon-reload"):
        assert f"systemctl {verb}" not in script
        assert f'"systemctl", "{verb}"' not in script
    assert "VITAL_AWS_CONTROL" not in script


def test_unread_is_observation_unavailable(monkeypatch):
    monkeypatch.delenv(rt.FIXTURE_ENV, raising=False)
    monkeypatch.setenv(rt.DISABLE_ENV, "off")
    out = rt.observe()
    assert out["runtime"] == "OBSERVATION_UNAVAILABLE"
    assert out["heartbeat"] == "UNAVAILABLE"
    assert out["running"] == "UNAVAILABLE"
    assert out["executing"] is False


def test_missing_unit_is_not_deployed(tmp_path, monkeypatch):
    _fixture(tmp_path, monkeypatch, {"ok": True, "unit_file_exists": False, "unit": {"LoadState": "not-found"}})
    out = rt.observe()
    assert out["runtime"] == "NOT_DEPLOYED"
    assert out["running"] is False


def test_fresh_heartbeat_and_matching_binary_is_healthy(tmp_path, monkeypatch):
    _fixture(tmp_path, monkeypatch, _deployed(int(time.time()) - 10))
    out = rt.observe()
    assert out["runtime"] == "DEPLOYED"
    assert out["running"] is True
    assert out["heartbeat"] == "FRESH"
    assert out["healthy"] is True
    assert out["executing"] is False
    assert out["status"]["mode"] == "SHADOW"
    assert [row["kind"] for row in out["journal_tail"]] == ["WORKER_START", "SERIES_ROUTE"]


@pytest.mark.parametrize(
    "payload",
    [
        _deployed(int(time.time()) - 10_000),
        _deployed(int(time.time()) - 10, sha="different"),
        _deployed(int(time.time()) - 10, active="failed"),
    ],
)
def test_running_is_not_healthy(tmp_path, monkeypatch, payload):
    _fixture(tmp_path, monkeypatch, payload)
    out = rt.observe()
    assert out["healthy"] is False
    assert out["executing"] is False


def test_heartbeat_boundary(tmp_path, monkeypatch):
    now = int(time.time())
    monkeypatch.setattr(rt.time, "time", lambda: float(now))
    _fixture(tmp_path, monkeypatch, _deployed(now - rt.HEARTBEAT_FRESH_S))
    assert rt.observe()["heartbeat"] == "FRESH"
    _fixture(tmp_path, monkeypatch, _deployed(now - rt.HEARTBEAT_FRESH_S - 1))
    assert rt.observe()["heartbeat"] == "STALE"


def test_corrupt_status_blob_is_unavailable(tmp_path, monkeypatch):
    payload = _deployed(int(time.time()))
    payload["status_z"] = "not-base64!!"
    _fixture(tmp_path, monkeypatch, payload)
    out = rt.observe()
    assert out["status"] is None
    assert out["heartbeat"] == "UNAVAILABLE"
    assert out["healthy"] is False


def test_desk_runtime_surfaces_worker_and_stays_closed(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import terminal_api

    _fixture(tmp_path, monkeypatch, _deployed(int(time.time()) - 5))
    monkeypatch.setattr(
        "roller.systimo.scope.get_session",
        lambda session_id, store=None: {"sport": "NBA", "quadrant_id": "quad-1", "session_id": session_id},
    )
    client = TestClient(terminal_api.app)
    body = client.get("/momento/execution/nba/runtime", headers={"x-momento-scope": "nba"}).json()
    assert body["runtime"] == "DEPLOYED"
    assert body["mode"] == "SHADOW"
    assert body["healthy"] is True
    assert body["executing"] is False
    assert body["submits"] is False
    assert body["execution_authorized"] is False
    assert body["fills"] == "UNAVAILABLE"
    contract = client.get("/momento/execution/nba/contract", headers={"x-momento-scope": "nba"}).json()
    assert contract["contract_id"] == "nba-001-first78_67-v1"
    assert contract["submits"] is False
    policy = client.get("/momento/execution/nba/policy", headers={"x-momento-scope": "nba"}).json()
    assert policy["version"] == "nba-001-v1"
    v0 = client.get("/momento/execution/nba/policy_v0", headers={"x-momento-scope": "nba"}).json()
    assert v0["version"] == "nba-001-v0"
    for kind in ("funding", "status", "field_to_code"):
        doc = client.get(f"/momento/execution/nba/{kind}", headers={"x-momento-scope": "nba"})
        assert doc.status_code == 200, kind
