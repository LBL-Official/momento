"""Jump product shell. Health only. No credentials."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from roller.jump import api as japi
from roller.jump.versions import CODE_VERSION, PHASE_STATUS


def test_health_handler_phases_not_started(tmp_path):
    body = japi.handle_health(root=tmp_path)
    assert body["status"] == "ok"
    assert body["product"] == "Jump"
    assert body["code_version"] == CODE_VERSION
    assert body["phases"] == dict(PHASE_STATUS)
    assert body["library_n"] == 0
    assert body["live_execution"] is False
    assert body["honesty"]["risk_not"] == "candle_path_not_fill"


def test_health_lists_jump_shell():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    body = TestClient(terminal_api.app).get("/health").json()
    assert "jump_shell" in body["capabilities"]


def test_jump_health_endpoint():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    body = TestClient(terminal_api.app).get("/jump/health").json()
    assert body["phases"] == {"A": "MOVED_TO_SUPERASI", "B": "IMPLEMENTED", "C": "IMPLEMENTED"}
    assert body["code_version"] == CODE_VERSION
    assert "jump_iti" in TestClient(terminal_api.app).get("/health").json()["capabilities"]
    assert "jump_bots" in TestClient(terminal_api.app).get("/health").json()["capabilities"]
    assert body["live_execution"] is False


def test_no_new_credential_paths():
    root = Path(__file__).resolve().parents[1] / "roller" / "jump"
    banned = ("KALSHI_API_KEY", "PRIVATE_KEY", "secret_key", "api_key=")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path} contains {token}"
