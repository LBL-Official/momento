"""Momento LS — direct live-service observe. Not Vital."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from roller.ls.api import handle_health, handle_observe
from roller.ls.host import WRITE_FORBIDDEN, assert_readonly, compose_snapshot, inspect_script, unread
from roller.ls.identity import BASELINE_SHA256, INSTANCE_ID, SERVICE_NAME

LS_DIR = Path(__file__).resolve().parents[1] / "roller" / "ls"


def _raw(*, binary: str = BASELINE_SHA256, recon: str = "Healthy", submit: str = "enabled") -> dict:
    return {
        "ok": True,
        "source": "fixture",
        "service": {
            "name": SERVICE_NAME,
            "active": "active",
            "n_restarts": 0,
            "restart": "always",
            "restart_prevent_exit_status": "78",
        },
        "process": {"main_pid": 1112917, "exe": "/usr/local/bin/momento-trading-engine"},
        "hashes": {
            "binary": binary,
            "unit": "unit-sha",
            "live_toml": "toml-sha",
            "persist": "persist-sha",
        },
        "ledger": {
            "ok": True,
            "kill_switch": False,
            "live_armed": True,
            "reconciliation": recon,
            "order_submission": submit,
            "open_slots": 0,
            "max_open_slots": 5,
            "heartbeat_markets": 12,
        },
        "activity": {
            "mlb_yes_bid_n": 40,
            "first80_n": 0,
            "first81_n": 0,
            "submit_to_ack_n": 0,
            "error_n": 1,
            "last_error": "fill_apply_failed leftover",
            "recent_errors": ["fill_apply_failed leftover"],
            "last_mlb_ticker": "KXMLBGAME-26SEP16NYYBOS-NYY",
            "last_mlb_bid_cents": 46,
        },
        "gates": {"ok": True, "armed": True},
        "logs": ["momento heartbeat reconciliation=Healthy order_submission=enabled"],
    }


def test_package_does_not_import_vital():
    for path in LS_DIR.glob("*.py"):
        text = path.read_text()
        assert "roller.vital" not in text
        assert "/vital/" not in text


def test_inspect_script_is_readonly():
    script = inspect_script()
    assert 'service = "momento-live.service"' in script
    assert "live-runtime.json" in script
    assert "sha256" in script
    assert "yes_bid_update ticker=kxmlbgame" in script.lower()
    assert "First80Observed" in script
    assert "fill_apply_failed" in script
    assert "RestartPreventExitStatus" in script
    assert WRITE_FORBIDDEN.search(script) is None
    assert_readonly(script)


def test_write_verbs_are_refused():
    for command in (
        "systemctl start momento-live.service",
        "systemctl stop momento-live.service",
        "systemctl restart momento-live.service",
        "systemctl kill momento-live.service",
        "touch /var/lib/momento/state/KILL",
        "echo 1 > /var/lib/momento/state/KILL",
    ):
        with pytest.raises(PermissionError):
            assert_readonly(command)


def test_unread_is_not_running():
    body = unread("host unread")
    assert body["ok"] is False
    assert body["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["submits"] is False
    assert "RUNNING" not in json.dumps(body)


def test_health_is_observe_only():
    body = handle_health()
    assert body["ok"] is True
    assert body["product"] == "Momento LS"
    assert body["submits"] is False
    assert body["service"] == SERVICE_NAME
    assert body["instance_id"] == INSTANCE_ID


def test_compose_authorized_and_hashes():
    snap = compose_snapshot(_raw())
    assert snap["ok"] is True
    assert snap["product"] == "Momento LS"
    assert snap["submits"] is False
    assert snap["hashes"]["binary"] == BASELINE_SHA256
    assert snap["hashes"]["baseline_match"] is True
    assert snap["gates"]["authorized_to_submit"] is True
    assert snap["updates"]["mlb_yes_bid_n"] == 40
    assert snap["updates"]["first80_n"] == 0
    assert snap["errors"]["n"] == 1
    assert snap["errors"]["last"] == "fill_apply_failed leftover"


def test_compose_ambiguous_is_not_authorized():
    snap = compose_snapshot(_raw(recon="Ambiguous"))
    assert snap["gates"]["reconciliation"] == "Ambiguous"
    assert snap["gates"]["authorized_to_submit"] is False


def test_baseline_mismatch_is_flagged():
    snap = compose_snapshot(_raw(binary="deadbeef" * 8))
    assert snap["hashes"]["baseline_match"] is False
    assert snap["hashes"]["binary"] != BASELINE_SHA256


def test_observe_reads_fixture(monkeypatch, tmp_path):
    fixture = tmp_path / "inspect.json"
    fixture.write_text(json.dumps(_raw()), encoding="utf-8")
    monkeypatch.setenv("MOMENTO_LS_INSPECT_FIXTURE", str(fixture))
    snap = handle_observe()
    assert snap["ok"] is True
    assert snap["hashes"]["baseline_match"] is True
    assert snap["updates"]["last_mlb_bid_cents"] == 46
