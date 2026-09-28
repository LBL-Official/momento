"""Vital Phase 6 — auditable control. Fail-closed. Kill ≠ stop. Start ≠ live arm."""

from __future__ import annotations

import json

from roller.vital.api import handle_command
from roller.vital.store import list_events, seed_mlb_001
from roller.vital.versions import BOT_ID, CONTROL_CONFIRMATION, LIVE_CONFIRMATION


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    monkeypatch.delenv("VITAL_AWS_CONTROL", raising=False)
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")


def test_control_disabled_without_gates(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    body = handle_command(BOT_ID, {"action": "start", "confirmation": CONTROL_CONFIRMATION}, root=tmp_path)
    assert body["command_status"] == "CONTROL_DISABLED"
    assert body["command_id"]
    assert body["requested_at"]
    assert body["desired_state"] == "RUNNING"
    assert body["http_200_not_running"] is True
    assert body["lifecycle_after"] == "OBSERVATION_UNAVAILABLE"
    kinds = [row.get("kind") for row in list_events(BOT_ID, root=tmp_path)]
    assert "command" in kinds


def test_live_confirmation_is_rejected(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("VITAL_AWS_CONTROL", "1")
    seed_mlb_001(root=tmp_path)
    body = handle_command(BOT_ID, {"action": "start", "confirmation": LIVE_CONFIRMATION}, root=tmp_path)
    assert body["command_status"] == "REJECTED"
    assert body["live_confirmation_rejected"] is True
    assert body["start_is_not_live_arm"] is True


def test_kill_is_not_stop(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    body = handle_command(BOT_ID, {"action": "kill", "confirmation": CONTROL_CONFIRMATION}, root=tmp_path)
    assert "systemctl stop" not in body["host_effect"]
    assert "KILL" in body["host_effect"]
    assert body["kill_is_not_stop"] is True
    assert body["desired_state"] == "KILLED"


def test_mock_dispatch_still_requires_independent_confirm(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("VITAL_AWS_CONTROL", "1")
    monkeypatch.setenv("VITAL_AWS_CONTROL_DISPATCH", "mock")
    seed_mlb_001(root=tmp_path)
    body = handle_command(BOT_ID, {"action": "stop", "confirmation": CONTROL_CONFIRMATION}, root=tmp_path)
    assert body["command_status"] in {"CONFIRMING", "CONFIRMED"}
    assert body["dispatch"]["mode"] == "mock"
    if body["command_status"] == "CONFIRMING":
        assert body["lifecycle_after"] != "STOPPED" or body["confirmed_runtime"]["lifecycle"]["status"] != "CONFIRMED"


def test_mock_confirm_when_observe_matches(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    fixture = tmp_path / "inspect.json"
    fixture.write_text(
        json.dumps(
            {
                "ok": True,
                "service": {"value": {"active": "inactive"}, "status": "CONFIRMED"},
                "heartbeat": {"value": {"kill_switch": False}, "status": "CONFIRMED"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VITAL_AWS_INSPECT_FIXTURE", str(fixture))
    monkeypatch.setenv("VITAL_AWS_CONTROL", "1")
    monkeypatch.setenv("VITAL_AWS_CONTROL_DISPATCH", "mock")
    seed_mlb_001(root=tmp_path)
    body = handle_command(BOT_ID, {"action": "stop", "confirmation": CONTROL_CONFIRMATION}, root=tmp_path)
    assert body["desired_state"] == "STOPPED"
    assert body["command_status"] == "CONFIRMED"
    assert body["lifecycle_after"] == "STOPPED"


def test_ssm_dispatch_uses_allowlisted_script(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    wrapper = tmp_path / "run_control"
    wrapper.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "print(json.dumps({'ok': True, 'script': sys.argv[3], 'instance': sys.argv[1]}))\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    monkeypatch.setenv("VITAL_AWS_CONTROL", "1")
    monkeypatch.setenv("VITAL_AWS_CONTROL_DISPATCH", "ssm")
    monkeypatch.setenv("VITAL_AWS_INSTANCE_ID", "i-0f0849d5829476c31")
    monkeypatch.setenv("VITAL_AWS_CONTROL_RUNNER", str(wrapper))
    body = handle_command(BOT_ID, {"action": "restart", "confirmation": CONTROL_CONFIRMATION}, root=tmp_path)
    assert body["dispatch"]["mode"] == "ssm"
    assert body["dispatch"]["ok"] is True
    assert body["dispatch"]["script"] == "systemctl restart momento-live.service"
    assert body["command_status"] in {"CONFIRMING", "CONFIRMED"}
    assert body["http_200_not_running"] is True


def test_ssm_dispatch_failure_is_failed_not_running(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    wrapper = tmp_path / "run_control"
    wrapper.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "print(json.dumps({'ok': False, 'reason': 'instance unreachable'}))\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    monkeypatch.setenv("VITAL_AWS_CONTROL", "1")
    monkeypatch.setenv("VITAL_AWS_CONTROL_DISPATCH", "ssm")
    monkeypatch.setenv("VITAL_AWS_INSTANCE_ID", "i-0f0849d5829476c31")
    monkeypatch.setenv("VITAL_AWS_CONTROL_RUNNER", str(wrapper))
    body = handle_command(BOT_ID, {"action": "start", "confirmation": CONTROL_CONFIRMATION}, root=tmp_path)
    assert body["command_status"] == "FAILED"
    assert body["dispatch"]["ok"] is False
    assert body["lifecycle_after"] != "RUNNING" or body["confirmed_runtime"]["lifecycle"]["status"] != "CONFIRMED"
    assert "RUNNING" not in str(body.get("detail") or "")


def test_armed_control_defaults_to_ssm_not_mock(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    wrapper = tmp_path / "run_control"
    wrapper.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "print(json.dumps({'ok': True, 'script': sys.argv[3]}))\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    monkeypatch.setenv("VITAL_AWS_CONTROL", "1")
    monkeypatch.delenv("VITAL_AWS_CONTROL_DISPATCH", raising=False)
    monkeypatch.setenv("VITAL_AWS_INSTANCE_ID", "i-0f0849d5829476c31")
    monkeypatch.setenv("VITAL_AWS_CONTROL_RUNNER", str(wrapper))
    body = handle_command(BOT_ID, {"action": "stop", "confirmation": CONTROL_CONFIRMATION}, root=tmp_path)
    assert body["dispatch_mode"] == "ssm"
    assert body["dispatch"]["mode"] == "ssm"


def test_unknown_action_rejected(monkeypatch, tmp_path):
    from roller.vital.errors import VitalError

    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    try:
        handle_command(BOT_ID, {"action": "flatten"}, root=tmp_path)
    except VitalError as exc:
        assert exc.code == "REJECTED"
    else:
        raise AssertionError("flatten must be rejected")
