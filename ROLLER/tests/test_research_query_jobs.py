"""Execute is a background job. /health stays reachable while it runs."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

ROLLER_ROOT = Path(__file__).resolve().parents[1]


def _client() -> TestClient:
    import sys

    sys.path.insert(0, str(ROLLER_ROOT / "scripts"))
    import terminal_api

    return TestClient(terminal_api.app)


def test_execute_returns_202_and_health_stays_ok(monkeypatch):
    def slow(_payload):
        time.sleep(0.35)
        return {
            "execution_status": "COMPLETE",
            "population": {"count": 1, "trades": [{"ticker": "T"}]},
            "summary": {"population_n": 1},
            "identity": {"terminal_missing": 0},
            "hashes": {"question_hash": "abc"},
            "compile": {"execution_path": "generic_query"},
        }

    monkeypatch.setattr("roller.research_query.execute.execute_question", slow)
    client = _client()
    started = time.perf_counter()
    posted = client.post("/research-query/execute", json={"draft": {"universe": {}}})
    assert posted.status_code == 202
    job_id = posted.json()["job_id"]
    assert job_id
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["reachable_during_execute"] is True
    assert time.perf_counter() - started < 0.8

    deadline = time.time() + 3
    body = None
    while time.time() < deadline:
        polled = client.get(f"/research-query/jobs/{job_id}")
        assert polled.status_code == 200
        body = polled.json()
        if body["status"] in {"complete", "failed"}:
            break
        time.sleep(0.05)
    assert body is not None
    assert body["status"] == "complete"
    assert body["result"]["summary"]["population_n"] == 1
    assert body["result"]["hashes"]["question_hash"] == "abc"


def test_failed_job_is_not_empty_population(monkeypatch):
    def boom(_payload):
        raise RuntimeError("warehouse down")

    monkeypatch.setattr("roller.research_query.execute.execute_question", boom)
    client = _client()
    posted = client.post("/research-query/execute", json={"draft": {"universe": {}}})
    assert posted.status_code == 202
    job_id = posted.json()["job_id"]
    deadline = time.time() + 3
    body = None
    while time.time() < deadline:
        polled = client.get(f"/research-query/jobs/{job_id}")
        assert polled.status_code == 200
        body = polled.json()
        if body["status"] in {"complete", "failed"}:
            break
        time.sleep(0.05)
    assert body is not None
    assert body["status"] == "failed"
    assert body.get("result") is None
    assert (body.get("error") or {}).get("message")
    assert body.get("population", {}).get("count") != 0


def test_missing_job_is_404():
    client = _client()
    res = client.get("/research-query/jobs/not-a-real-job")
    assert res.status_code == 404
