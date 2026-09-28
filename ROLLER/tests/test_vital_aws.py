"""Vital Phase 4 — read-only AWS adapter. No write verbs."""

from __future__ import annotations

import json

import pytest

from roller.vital.aws import (
    WRITE_FORBIDDEN,
    _heartbeat_from_inspect,
    _normalize_ssm,
    assert_readonly,
    host_fetch_enabled,
    inspect_mlb_001,
    inspect_script,
    unread,
)
from roller.vital.aws import clear_ssm_cache


def test_inspect_script_is_readonly():
    script = inspect_script()
    assert '"systemctl", "is-active"' in script
    assert '"systemctl", "show"' in script
    assert "live-runtime.json" in script
    assert "live_armed_confirmed" in script
    assert 'service = "momento-live.service"' in script
    assert "momento-demo@mlb-001" not in script
    assert "reconciliation" in script
    assert "open_slots" in script
    assert "reservations_n" in script
    assert "WorkingDirectory" in script
    assert "/proc/" in script
    assert "MOMENTO_KALSHI_ENV=" in script
    assert "heartbeat_n" in script
    assert "yes_bid_update ticker=KXMLBGAME" in script
    assert "First80Observed" in script
    assert "submit_to_ack" in script
    assert WRITE_FORBIDDEN.search(script) is None
    assert_readonly(script)


def test_write_verbs_are_refused():
    for command in (
        "systemctl start momento-live.service",
        "systemctl stop momento-live.service",
        "systemctl restart momento-live.service",
        "systemctl kill momento-live.service",
        "touch /var/lib/momento/state/KILL",
        "install -m 644 /dev/null /var/lib/momento/state/KILL",
        "echo 1 > /var/lib/momento/state/KILL",
    ):
        with pytest.raises(PermissionError):
            assert_readonly(command)


def test_unread_is_observation_unavailable():
    body = unread(reason="host state path unset")
    assert body["ok"] is False
    assert body["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["host"]["value"] is None
    assert body["service"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert "RUNNING" not in json.dumps(body)


def test_armed_kill_enum_is_not_tripped():
    from roller.vital.aws import _normalize_ssm

    body = _normalize_ssm(
        {
            "ok": True,
            "host": {"instance_verified": True},
            "service": {"name": "momento-live.service", "active": "active"},
            "process": {"main_pid": 1},
            "version": {"binary_sha256": "abc"},
            "environment": {},
            "ledger": {
                "ok": True,
                "kill_switch": False,
                "live_armed": True,
                "live_armed_confirmed": True,
                "open_mlb_positions": 0,
            },
            "gates": {"ok": True, "armed": True},
            "logs": ["momento heartbeat kill_switch=not_tripped"],
        }
    )
    assert body["heartbeat"]["value"]["kill_switch"] is False
    assert body["heartbeat"]["value"]["live_armed"] is True


def test_ssm_inspect_attaches_host_ledger():
    beat = _heartbeat_from_inspect(
        {
            "ledger": {
                "ok": True,
                "kill_switch": False,
                "live_armed": True,
                "live_armed_confirmed": True,
                "open_mlb_positions": 0,
                "bankroll_cents": 5000,
                "reconciliation": "Ambiguous",
                "reservations_n": 0,
                "unknown_orders": 0,
                "open_slots": 0,
                "order_submission": "blocked",
            },
            "gates": {"ok": True, "armed": True},
        }
    )
    assert beat["status"] == "CONFIRMED"
    assert beat["value"]["live_armed"] is True
    assert beat["value"]["open_mlb_positions"] == 0
    assert beat["value"]["bankroll_cents"] == 5000
    assert beat["value"]["reconciliation"] == "Ambiguous"
    assert beat["value"]["reservations_n"] == 0
    assert beat["value"]["unknown_orders"] == 0
    assert beat["value"]["open_slots"] == 0
    assert beat["value"]["order_submission"] == "blocked"


def test_local_ledger_inspect(monkeypatch, tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    runtime = {"tracker": {"positions": []}, "risk": {"kill_switch": False}}
    (state / "live-runtime.json").write_text(json.dumps(runtime), encoding="utf-8")
    (state / "weekly-snapshot.json").write_text(
        json.dumps({"bankroll": {"cents": 5000}, "week_start_utc": "2026-09-08T07:00:00Z"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("VITAL_BOT_STATE_DIR", str(state))
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    monkeypatch.delenv("VITAL_AWS_INSPECT_FIXTURE", raising=False)
    body = inspect_mlb_001()
    assert body["ok"] is True
    assert body["source"] == "local_path"
    assert body["instance_verified"] is False
    assert body["heartbeat"]["status"] in {"CONFIRMED", "OBSERVATION_UNAVAILABLE"}


def test_fixture_inspect(monkeypatch, tmp_path):
    fixture = tmp_path / "inspect.json"
    fixture.write_text(
        json.dumps(
            {
                "ok": True,
                "source": "fixture",
                "instance_verified": True,
                "host": {"value": {"instance_id": "i-test", "verified": True}, "status": "CONFIRMED"},
                "service": {"value": {"name": "momento-live.service", "active": "active"}, "status": "CONFIRMED"},
                "process": {"value": {"main_pid": 12}, "status": "CONFIRMED"},
                "version": {"value": {"binary_sha256": "abc"}, "status": "CONFIRMED"},
                "environment": {"value": {"label": "production"}, "status": "OBSERVED"},
                "heartbeat": {"value": {"bankroll_cents": 5000, "kill_switch": False}, "status": "CONFIRMED"},
                "logs": ["heartbeat bankroll_cents=5000"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VITAL_AWS_INSPECT_FIXTURE", str(fixture))
    clear_ssm_cache()
    body = inspect_mlb_001()
    assert body["ok"] is True
    assert body["service"]["value"]["active"] == "active"


def test_unread_journal_activity_is_omitted_not_zero():
    beat = _heartbeat_from_inspect(
        {
            "ledger": {
                "ok": True,
                "kill_switch": False,
                "open_mlb_positions": 0,
            },
            "gates": {"ok": True, "armed": True},
        }
    )
    assert beat["status"] == "CONFIRMED"
    assert "mlb_yes_bid_n" not in beat["value"]
    assert "first80_n" not in beat["value"]
    assert "submit_to_ack_n" not in beat["value"]


def test_host_fetch_default_on_explicit_off(monkeypatch):
    monkeypatch.delenv("VITAL_AWS_HOST_FETCH", raising=False)
    assert host_fetch_enabled() is True
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    assert host_fetch_enabled() is False
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "false")
    assert host_fetch_enabled() is False
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "ssm")
    assert host_fetch_enabled() is True


def test_official_inspect_json_parses_ledger_counts():
    body = _normalize_ssm(
        {
            "ok": True,
            "host": {"instance_verified": True},
            "service": {"name": "momento-live.service", "active": "active"},
            "process": {"main_pid": 1101134},
            "version": {"binary_sha256": "abc"},
            "environment": {"kalshi_env_name": "MOMENTO_KALSHI_ENV", "label": "production"},
            "paths": {"runtime_exists": True},
            "ledger": {
                "ok": True,
                "kill_switch": False,
                "live_armed": True,
                "live_armed_confirmed": True,
                "open_mlb_positions": 0,
                "reconciliation": "Ambiguous",
                "reservations_n": 0,
                "unknown_orders": 0,
                "open_slots": 0,
                "order_submission": "blocked",
            },
            "activity": {
                "ok": True,
                "mlb_yes_bid_n": 12,
                "first80_n": 0,
                "first81_n": 0,
                "submit_to_ack_n": 0,
                "submit_refused_n": 0,
                "last_mlb_ticker": "KXMLBGAME-26SEP161340NYYMIN-MIN",
                "last_mlb_bid_cents": 36,
                "last_mlb_ask_cents": 37,
            },
            "gates": {"ok": True, "armed": True},
            "logs": ["momento heartbeat reconciliation=ambiguous open_slots=0"],
        }
    )
    assert body["ok"] is True
    assert body["source"] == "ssm"
    assert body["service"]["value"]["name"] == "momento-live.service"
    assert body["heartbeat"]["value"]["reconciliation"] == "Ambiguous"
    assert body["heartbeat"]["value"]["open_slots"] == 0
    assert body["heartbeat"]["value"]["reservations_n"] == 0
    assert body["heartbeat"]["value"]["unknown_orders"] == 0
    assert body["heartbeat"]["value"]["mlb_yes_bid_n"] == 12
    assert body["heartbeat"]["value"]["last_mlb_ticker"] == "KXMLBGAME-26SEP161340NYYMIN-MIN"
    assert body["heartbeat"]["value"]["first80_n"] == 0


def test_ssm_failure_is_unavailable(monkeypatch):
    monkeypatch.delenv("VITAL_BOT_STATE_DIR", raising=False)
    monkeypatch.delenv("VITAL_BOT_RUNTIME_PATH", raising=False)
    monkeypatch.delenv("VITAL_AWS_INSPECT_FIXTURE", raising=False)
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "ssm")
    monkeypatch.setenv("VITAL_AWS_INSTANCE_ID", "not-an-instance")
    clear_ssm_cache()
    body = inspect_mlb_001()
    assert body["ok"] is False
    assert body["status"] == "OBSERVATION_UNAVAILABLE"
