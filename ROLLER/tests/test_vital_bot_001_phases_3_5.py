"""Vital Bot Standard Phases 3–5. Control plane, worker contract, pipeline facts."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roller.vital.api import (
    handle_command,
    handle_configuration,
    handle_controls,
    handle_health,
    handle_heartbeat,
    handle_pipeline,
    handle_plane,
    handle_risk,
    handle_strategy,
    handle_worker,
)
from roller.vital.errors import VitalError
from roller.vital.mlb_001.pipeline import PATH, STAGES
from roller.vital.mlb_001.plane import REQUIRED_SURFACES, ROUTES
from roller.vital.naming import BOT_STANDARD_PHASE
from roller.vital.store import seed_mlb_001
from roller.vital.versions import BOT_ID, CONTROL_CONFIRMATION, LIVE_CONFIRMATION, LIVE_EXECUTION


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    monkeypatch.delenv("VITAL_AWS_CONTROL", raising=False)
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    monkeypatch.delenv("VITAL_BOT_STATE_DIR", raising=False)
    monkeypatch.delenv("JUMP_BOT_ONE_HOST_FETCH", raising=False)
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")


def test_bot_standard_phases_3_5_implemented():
    assert BOT_STANDARD_PHASE["1"] == "ACCEPTED"
    assert BOT_STANDARD_PHASE["2"] == "IMPLEMENTED"
    assert BOT_STANDARD_PHASE["3"] == "IMPLEMENTED"
    assert BOT_STANDARD_PHASE["4"] == "IMPLEMENTED"
    assert BOT_STANDARD_PHASE["5"] == "IMPLEMENTED"
    assert BOT_STANDARD_PHASE["6"] == "IMPLEMENTED"


def test_health_exposes_bot_standard_phases(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    body = handle_health(root=tmp_path)
    assert body["bot_standard_phases"] == dict(BOT_STANDARD_PHASE)
    assert body["live_execution"] is False


def test_plane_catalog_lists_required_surfaces(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    body = handle_plane(BOT_ID, root=tmp_path)
    assert body["bot_id"] == BOT_ID
    assert body["phase"] == 3
    assert body["frontend_owns_trading_logic"] is False
    assert body["live_execution"] is LIVE_EXECUTION
    assert body["auth_fail_closed"] is True
    for surface in REQUIRED_SURFACES:
        assert surface in body["surfaces"]
        assert surface in body["routes"] or surface in {"logs", "events", "controls"}
    assert "configuration" in body["routes"]
    assert "strategy" in body["routes"]
    assert "risk" in body["routes"]
    assert "heartbeat" in body["routes"]
    assert "controls" in body["routes"]
    assert body["routes"]["commands"] == ROUTES["commands"]


def test_configuration_has_no_secrets_and_does_not_arm_live(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    body = handle_configuration(BOT_ID, root=tmp_path)
    assert body["pointer"] == "config/live.toml"
    assert body["secrets"] is False
    assert body["editable"] is False
    assert body["live_arm_is_not_vital_start"] is True
    assert body["factory"]["signal"] == "80_to_81_yes_bid"
    assert body["live_gates"]["confirmation"] == LIVE_CONFIRMATION
    dumped = str(body)
    assert "BEGIN RSA PRIVATE KEY" not in dumped
    assert "momento-kalshi-live.json" not in dumped


def test_strategy_proposes_and_does_not_submit(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    body = handle_strategy(BOT_ID, root=tmp_path)
    assert body["pointer"] == "strategies/mlb"
    assert body["proposes"] is True
    assert body["submits"] is False
    assert body["locked"] is True
    assert body["does_not_retune"] is True
    assert body["signal"] == "80_to_81_yes_bid"
    assert body["constants"]["min_entry_cents"] == 80
    assert body["constants"]["confirm_cents"] == 81
    assert body["constants"]["max_entry_cents"] == 83
    assert body["constants"]["lock_cents"] == 89
    assert body["looking_for"].startswith("YES bid First 80")
    assert body["entry_rules"]["confirm_cents"] == 81
    assert body["entry_rules"]["band_cents"] == [80, 83]
    assert body["exit_rules"]["lock_cents"] == 89
    assert body["exit_rules"]["not_iti_reach"] is True
    assert body["order_rules"]["entry"] == "post-only maker"
    assert body["spec_status"] == "CONFIRMED"
    assert body["state"]["status"] == "OBSERVATION_UNAVAILABLE"


def test_risk_is_pointer_not_second_engine(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    body = handle_risk(BOT_ID, root=tmp_path)
    assert body["pointer"] == "crates/risk"
    assert body["engine"] == "Risk Decision Engine"
    assert body["second_engine"] is False
    assert body["submits"] is False
    assert body["limits"]["max_open_mlb_positions"] == 5
    assert body["state"]["status"] == "OBSERVATION_UNAVAILABLE"


def test_heartbeat_unread_is_not_running(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    body = handle_heartbeat(BOT_ID, root=tmp_path)
    assert body["http_200_not_running"] is True
    assert body["lifecycle"] == "OBSERVATION_UNAVAILABLE"
    assert body["live_ev"]["status"] == "UNAVAILABLE"
    assert body["sharpe"]["status"] == "UNAVAILABLE"
    assert body["heartbeat"]["status"] == "OBSERVATION_UNAVAILABLE"


def test_controls_fail_closed_without_gates(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    view = handle_controls(BOT_ID, root=tmp_path)
    assert view["fail_closed"] is True
    assert view["enabled"] is False
    assert view["dispatch_mode"] == "mock"
    assert view["start_is_not_live_arm"] is True
    assert view["kill_does_not_flatten"] is True
    assert "start" in view["actions"]
    body = handle_command(BOT_ID, {"action": "start", "confirmation": CONTROL_CONFIRMATION}, root=tmp_path)
    assert body["command_status"] == "CONTROL_DISABLED"
    assert body["http_200_not_running"] is True
    rejected = handle_command(BOT_ID, {"action": "start", "confirmation": LIVE_CONFIRMATION}, root=tmp_path)
    assert rejected["command_status"] == "REJECTED"
    assert rejected["live_confirmation_rejected"] is True


def test_worker_is_independent_existing_unit(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    body = handle_worker(BOT_ID, root=tmp_path)
    assert body["phase"] == 4
    assert body["independent_of_vital"] is True
    assert body["vital_ui_required"] is False
    assert body["vital_api_required"] is False
    assert body["jump_required"] is False
    assert body["vital_submits"] is False
    assert body["second_worker"] is False
    assert body["moved"] is False
    assert body["if_vital_down"] == "continues"
    assert body["unit"] == "momento-live.service"
    assert body["binary"] == "/usr/local/bin/momento-trading-engine"
    assert body["repo_pointer"] == "apps/trading-engine"
    assert body["submitter"] == body["binary"]
    assert body["observed"]["lifecycle"] == "OBSERVATION_UNAVAILABLE"


def test_pipeline_is_existing_path_without_invented_fills(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    body = handle_pipeline(BOT_ID, root=tmp_path)
    assert body["phase"] == 5
    assert body["path"] == PATH
    assert body["signal_locked"] == "80_to_81_yes_bid"
    assert body["does_not_retune"] is True
    assert body["does_not_invent_fills"] is True
    assert body["catalog_fills_are_not_trades"] is True
    assert body["fill_not_trade"] is True
    assert body["strategy_submits"] is False
    assert body["risk_submits"] is False
    assert body["vital_submits"] is False
    assert body["browser_submits"] is False
    ids = [row["id"] for row in body["stages"]]
    assert ids == [row["id"] for row in STAGES]
    assert ids == [
        "MARKET_DATA",
        "NORMALIZATION",
        "FEATURE_STATE",
        "SIGNAL",
        "RISK",
        "ORDER_DECISION",
        "EXECUTION",
        "FILL",
    ]
    for row in body["stages"]:
        assert row["invents_fills"] is False
        assert row["observation"]["status"] == "OBSERVATION_UNAVAILABLE"
    signal = next(row for row in body["stages"] if row["id"] == "SIGNAL")
    assert signal["submits"] is False
    assert signal["locked"] is True
    execution = next(row for row in body["stages"] if row["id"] == "EXECUTION")
    assert execution["submits"] is True
    assert execution["pointer"] == "apps/trading-engine"
    fill = next(row for row in body["stages"] if row["id"] == "FILL")
    assert fill["fill_is_not_trade"] is True


def test_unknown_bot_is_not_found_on_plane(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    with pytest.raises(VitalError) as missing:
        handle_plane("mlb-002", root=tmp_path)
    assert missing.value.code == "BOT_NOT_FOUND"
    with pytest.raises(VitalError):
        handle_worker("mlb-002", root=tmp_path)
    with pytest.raises(VitalError):
        handle_pipeline("not-a-bot", root=tmp_path)


def test_http_plane_worker_pipeline_routes(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    plane = client.get("/vital/bots/mlb-bot-one/plane").json()
    assert plane["bot_id"] == BOT_ID
    assert "configuration" in plane["routes"]
    assert client.get("/vital/bots/mlb-001/configuration").status_code == 200
    assert client.get("/vital/bots/mlb-001/strategy").status_code == 200
    assert client.get("/vital/bots/mlb-001/risk").status_code == 200
    assert client.get("/vital/bots/mlb-001/heartbeat").status_code == 200
    assert client.get("/vital/bots/mlb-001/controls").status_code == 200
    assert client.get("/vital/bots/mlb-001/boundary").status_code == 200
    worker = client.get("/vital/bots/mlb-001/worker").json()
    assert worker["independent_of_vital"] is True
    pipeline = client.get("/vital/bots/mlb-001/pipeline").json()
    assert pipeline["does_not_invent_fills"] is True
    missing = client.get("/vital/bots/mlb-002/plane")
    assert missing.status_code == 404


def test_execution_crates_still_untouched():
    repo = Path(__file__).resolve().parents[2]
    assert (repo / "apps" / "trading-engine" / "src" / "live.rs").is_file()
    assert (repo / "strategies" / "mlb").is_dir()
    assert (repo / "crates" / "risk").is_dir()
    assert (repo / "config" / "live.toml").is_file()
    assert (repo / "deploy" / "momento-live.service").is_file()
    assert not (repo / "ROLLER" / "roller" / "vital" / "bots").is_dir()
