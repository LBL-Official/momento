"""Vital Phase 2 — skeleton health. No credentials. No AWS writes."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from roller.vital import api as vapi
from roller.vital.versions import BOT_ID, CODE_VERSION, LIVE_EXECUTION, PHASE_STATUS

_BANNED = ("KALSHI_API_KEY", "PRIVATE_KEY", "secret_key", "api_key=")


def test_health_handler_seeds_mlb_001(tmp_path):
    body = vapi.handle_health(root=tmp_path)
    assert body["status"] == "ok"
    assert body["product"] == "Vital"
    assert body["code_version"] == CODE_VERSION
    assert body["bot_id"] == BOT_ID
    assert body["live_execution"] is False
    assert body["http_200_not_running"] is True
    assert body["phases"] == dict(PHASE_STATUS)
    assert body["honesty"]["live_ev"] == "UNAVAILABLE"
    assert body["integration_proof"]["id"] == "LIVE_SERVICE_INTEGRATION"
    assert body["honesty"]["running_not_healthy"] is True
    assert (tmp_path / "bots" / BOT_ID / "metadata" / "bot.json").is_file()


def test_bots_list_and_alias(tmp_path):
    listed = vapi.handle_bots_list(root=tmp_path)
    assert listed["n"] == 1
    assert listed["bots"][0]["bot_id"] == BOT_ID
    assert listed["bots"][0]["kind"] == "grandfathered"
    assert listed["bots"][0]["status"] == "OBSERVATION_UNAVAILABLE"
    one = vapi.handle_bots_get("mlb-bot-one", root=tmp_path)
    assert one["bot_id"] == BOT_ID
    assert one["factory"]["bankroll_cents"] == 5000
    assert one["factory"]["signal"] == "80_to_81_yes_bid"


def test_unknown_bot_is_not_found(tmp_path):
    from roller.vital.errors import VitalError

    try:
        vapi.handle_bots_get("not-a-bot", root=tmp_path)
    except VitalError as exc:
        assert exc.code == "BOT_NOT_FOUND"
    else:
        raise AssertionError("expected BOT_NOT_FOUND")


def test_health_lists_vital_shell():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    body = TestClient(terminal_api.app).get("/health").json()
    assert "vital_shell" in body["capabilities"]
    assert "vital_bots" in body["capabilities"]


def test_vital_health_endpoint():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    body = TestClient(terminal_api.app).get("/vital/health").json()
    assert body["product"] == "Vital"
    assert body["code_version"] == CODE_VERSION
    assert body["live_execution"] is LIVE_EXECUTION
    bots = TestClient(terminal_api.app).get("/vital/bots").json()
    assert any(row["bot_id"] == BOT_ID for row in bots["bots"])
    alias = TestClient(terminal_api.app).get("/vital/bots/mlb-bot-one").json()
    assert alias["bot_id"] == BOT_ID


def test_no_credentials_in_vital_package():
    root = Path(__file__).resolve().parents[1] / "roller" / "vital"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in _BANNED:
            assert token not in text, f"{path} contains {token}"
    disk = Path(__file__).resolve().parents[2] / "research" / "vital"
    if disk.is_dir():
        for path in disk.rglob("*"):
            if path.suffix not in {".json", ".jsonl", ".md", ".py"}:
                continue
            text = path.read_text(encoding="utf-8")
            for token in _BANNED:
                assert token not in text, f"{path} contains {token}"
            assert "BEGIN RSA PRIVATE KEY" not in text
            assert "momento-kalshi-live.json" not in text or path.name.endswith(".md")


def test_execution_crates_untouched():
    repo = Path(__file__).resolve().parents[2]
    assert (repo / "apps" / "trading-engine").is_dir()
    assert (repo / "strategies" / "mlb").is_dir()
    assert (repo / "config" / "live.toml").is_file()
    assert (repo / "deploy" / "momento-live.service").is_file()
