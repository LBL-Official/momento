"""Vital live desk: Kalshi observe honesty, diagnose, start-if-armed."""

from __future__ import annotations

from roller.vital.api import handle_diagnose, handle_kalshi_observe, handle_start_if_armed
from roller.vital.errors import VitalError
from roller.vital.store import seed_mlb_001
from roller.vital.versions import BOT_ID, CONTROL_CONFIRMATION, LIVE_CONFIRMATION


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.delenv("VITAL_AWS_CONTROL", raising=False)
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")


def test_observe_rejects_live_confirmation(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    try:
        handle_kalshi_observe(BOT_ID, {"confirmation": LIVE_CONFIRMATION}, root=tmp_path)
    except VitalError as exc:
        assert exc.code == "REJECTED"
        return
    raise AssertionError("ENABLE_LIVE_TRADING must not be an observe token")


def test_diagnose_does_not_invent_fills(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    monkeypatch.setattr(
        "roller.vital.mlb_001.diagnose.observe_bot",
        lambda *args, **kwargs: {
            "runtime": {
                "lifecycle": "OBSERVATION_UNAVAILABLE",
                "service": {"value": {"active": "inactive"}, "status": "CONFIRMED"},
            }
        },
    )
    body = handle_diagnose(BOT_ID, root=tmp_path)
    assert body["bot_id"] == BOT_ID
    assert body["invented_fills"] is False
    assert body["http_200_not_running"] is True
    assert body["host_confirmed"] is True
    assert body["kalshi"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert "$0" not in str(body)


def test_start_if_armed_fails_closed_without_control(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    monkeypatch.setattr(
        "roller.vital.mlb_001.diagnose._live_toml_armed",
        lambda: {"ok": True, "armed": True, "reason": None, "path": "config/live.toml"},
    )
    monkeypatch.setattr(
        "roller.vital.mlb_001.diagnose.observe_bot",
        lambda *args, **kwargs: {
            "runtime": {
                "lifecycle": "OBSERVATION_UNAVAILABLE",
                "service": {"value": {"active": "inactive"}, "status": "CONFIRMED"},
            }
        },
    )
    body = handle_start_if_armed(BOT_ID, {"confirmation": CONTROL_CONFIRMATION}, root=tmp_path)
    assert body["started"] is False
    assert body["command_status"] == "CONTROL_DISABLED"
    assert body["host_confirmed"] is True
    assert body["http_200_not_running"] is True


def test_start_if_armed_dispatches_when_armed_and_down(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    monkeypatch.setenv("VITAL_AWS_CONTROL", "1")
    monkeypatch.setattr(
        "roller.vital.mlb_001.diagnose._live_toml_armed",
        lambda: {"ok": True, "armed": True, "reason": None, "path": "config/live.toml"},
    )
    monkeypatch.setattr(
        "roller.vital.mlb_001.diagnose.observe_bot",
        lambda *args, **kwargs: {
            "runtime": {
                "lifecycle": "STOPPED",
                "service": {"value": {"active": "inactive"}, "status": "CONFIRMED"},
            }
        },
    )
    monkeypatch.setattr(
        "roller.vital.mlb_001.diagnose.control_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "roller.vital.mlb_001.diagnose.submit_command",
        lambda *args, **kwargs: {
            "command_status": "DISPATCHED",
            "action": "start",
            "http_200_not_running": True,
        },
    )
    body = handle_start_if_armed(BOT_ID, {"confirmation": CONTROL_CONFIRMATION}, root=tmp_path)
    assert body["started"] is True
    assert body["command_status"] == "DISPATCHED"
    assert body["host_confirmed"] is True
    assert body["http_200_not_running"] is True
    assert body["lifecycle"] != "RUNNING"


def test_start_if_armed_refuses_unread_host(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    monkeypatch.setenv("VITAL_AWS_CONTROL", "1")
    monkeypatch.setattr(
        "roller.vital.mlb_001.diagnose._live_toml_armed",
        lambda: {"ok": True, "armed": True, "reason": None, "path": "config/live.toml"},
    )
    monkeypatch.setattr(
        "roller.vital.mlb_001.diagnose.observe_bot",
        lambda *args, **kwargs: {
            "runtime": {
                "lifecycle": "OBSERVATION_UNAVAILABLE",
                "service": {"status": "OBSERVATION_UNAVAILABLE"},
            }
        },
    )
    monkeypatch.setattr("roller.vital.mlb_001.diagnose.control_enabled", lambda: True)
    body = handle_start_if_armed(BOT_ID, {"confirmation": CONTROL_CONFIRMATION}, root=tmp_path)
    assert body["started"] is False
    assert body["command_status"] == "REJECTED"
    assert body["host_confirmed"] is False
    assert "unread" in (body.get("detail") or "")
