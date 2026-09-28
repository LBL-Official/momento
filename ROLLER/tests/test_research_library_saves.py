"""Named result snapshots persist on disk, not in the browser quota."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from roller.research_library.saves import load_save, write_save


def test_write_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLLER_LIBRARY_DIR", str(tmp_path))
    meta = write_save(
        {
            "name": "Q1/Q2 leading 55/90",
            "folder": "Experimental",
            "question": "first touch 80",
            "result": {
                "execution_status": "COMPLETE",
                "summary": {"population_n": 788},
                "population": {"count": 788, "trades": [{"ticker": "T"}] * 788},
            },
        }
    )
    assert meta["message"] == "RESULT SAVED"
    assert meta["population_n"] == 788
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    listed = client.get("/research-library/saves").json()
    assert listed["n"] >= 1
    got = client.get(f"/research-library/saves/{meta['id']}")
    assert got.status_code == 200
    assert got.json()["result"]["population"]["count"] == 788
    assert len(got.json()["result"]["population"]["trades"]) == 788


def test_save_reload_preserves_question_and_state_hash(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLLER_LIBRARY_DIR", str(tmp_path))
    hashes = {
        "question_hash": "qh-save-lock",
        "state_hash": "st-save-lock",
        "entry_hash": "en-save-lock",
    }
    meta = write_save(
        {
            "name": "hash lock",
            "hashes": hashes,
            "result": {
                "execution_status": "COMPLETE",
                "hashes": hashes,
                "summary": {"population_n": 3},
                "population": {"count": 3, "trades": [{"ticker": "T"}] * 3},
            },
        }
    )
    loaded = load_save(meta["id"])
    assert loaded is not None
    assert loaded["hashes"]["question_hash"] == "qh-save-lock"
    assert loaded["hashes"]["state_hash"] == "st-save-lock"
    from_result_only = write_save(
        {
            "name": "hash from result",
            "result": {
                "execution_status": "COMPLETE",
                "hashes": {"question_hash": "qh-from-result", "state_hash": "st-from-result"},
                "population": {"count": 1, "trades": [{"ticker": "T"}]},
            },
        }
    )
    reloaded = load_save(from_result_only["id"])
    assert reloaded is not None
    assert reloaded["hashes"]["question_hash"] == "qh-from-result"
    assert reloaded["hashes"]["state_hash"] == "st-from-result"
