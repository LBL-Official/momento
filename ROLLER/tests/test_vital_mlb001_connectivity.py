"""Incident B — Vital observes momento-live.service. No invented RUNNING."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from roller.jump.dashboard.host_state import load_host_state
from roller.jump.vital_client import jump_heartbeat_from_vital, vital_observe
from roller.vital.api import handle_bots_get, handle_status
from roller.vital.aws import (
    clear_ssm_cache,
    host_fetch_enabled,
    inspect_mlb_001,
    inspect_script,
    instance_id,
)
from roller.vital.control import control_enabled
from roller.vital.observe import observe_bot, overlay_confirmed_lifecycle
from roller.vital.store import read_json, runtime_path, seed_mlb_001, write_json
from roller.vital.unit_observe import journal_unit
from roller.vital.versions import BOT_ID, DOCUMENTED_INSTANCE_ID, SERVICE_NAME

_OFFICIAL_INSPECT = {
    "ok": True,
    "source": "ssm",
    "host": {"instance_verified": True},
    "service": {
        "name": "momento-live.service",
        "active": "active",
        "started_at": "Wed 2026-09-16 20:00:11 UTC",
    },
    "process": {"main_pid": 1101134},
    "version": {
        "binary_sha256": "610dd470b1769a0385c81942ec634362ce8607b2db6f8f44156cf7757a147250",
        "binary_exists": True,
    },
    "environment": {
        "env_names": ["MOMENTO_KALSHI_ENV"],
        "kalshi_env_name": "MOMENTO_KALSHI_ENV",
        "label": "production",
    },
    "paths": {"runtime_exists": True, "snapshot_exists": True, "kill_exists": False},
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
    "logs": [
        "momento heartbeat reconciliation=ambiguous open_slots=0 unknown_orders=0 order_submission=blocked"
    ],
}


def _isolate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    monkeypatch.delenv("VITAL_AWS_CONTROL", raising=False)
    monkeypatch.delenv("VITAL_BOT_STATE_DIR", raising=False)
    monkeypatch.delenv("VITAL_BOT_RUNTIME_PATH", raising=False)
    monkeypatch.delenv("VITAL_AWS_INSPECT_FIXTURE", raising=False)
    monkeypatch.delenv("VITAL_AWS_SSM_RUNNER", raising=False)
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    monkeypatch.delenv("JUMP_BOT_ONE_HOST_FETCH", raising=False)


def _write_runner(tmp_path: Path, payload: dict) -> Path:
    runner = tmp_path / "ssm_runner.sh"
    runner.write_text(
        "#!/bin/sh\ncat <<'EOF'\n" + json.dumps(payload) + "\nEOF\n",
        encoding="utf-8",
    )
    runner.chmod(0o755)
    return runner


def test_mlb_001_targets_documented_instance_and_factory_unit(monkeypatch):
    monkeypatch.delenv("VITAL_AWS_INSTANCE_ID", raising=False)
    assert DOCUMENTED_INSTANCE_ID == "i-0f0849d5829476c31"
    assert instance_id() == "i-0f0849d5829476c31"
    assert SERVICE_NAME == "momento-live.service"
    script = inspect_script()
    assert 'service = "momento-live.service"' in script
    assert "momento-demo@mlb-001" not in script


def test_production_inspect_is_not_demo_unit():
    assert journal_unit({"bot_id": BOT_ID, "kind": "grandfathered"}) == SERVICE_NAME
    assert journal_unit({"bot_id": "mlb-005", "environment": "DEMO"}) == "momento-demo@mlb-005.service"
    assert journal_unit({"bot_id": "mlb-006", "environment": "PRODUCTION"}) == "momento-live@mlb-006.service"


def test_official_inspect_json_including_runtime_presence_parses(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    runner = _write_runner(tmp_path, _OFFICIAL_INSPECT)
    monkeypatch.delenv("VITAL_BOT_STATE_DIR", raising=False)
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "ssm")
    monkeypatch.setenv("VITAL_AWS_SSM_RUNNER", str(runner))
    monkeypatch.setenv("VITAL_AWS_INSTANCE_ID", DOCUMENTED_INSTANCE_ID)
    clear_ssm_cache()
    body = inspect_mlb_001(refresh=True)
    assert body["ok"] is True
    assert body["source"] == "ssm"
    assert body["service"]["value"]["name"] == SERVICE_NAME
    assert body["process"]["value"]["main_pid"] == 1101134
    assert body["paths"]["runtime_exists"] is True
    beat = body["heartbeat"]["value"]
    assert beat["reconciliation"] == "Ambiguous"
    assert beat["open_slots"] == 0
    assert beat["reservations_n"] == 0
    assert beat["unknown_orders"] == 0
    assert beat["order_submission"] == "blocked"
    dumped = json.dumps(body)
    assert "BEGIN RSA" not in dumped
    assert "api_key=" not in dumped


def test_local_unset_plus_ssm_ok_observes_from_ssm(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    runner = _write_runner(tmp_path, _OFFICIAL_INSPECT)
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "ssm")
    monkeypatch.setenv("VITAL_AWS_SSM_RUNNER", str(runner))
    monkeypatch.setenv("VITAL_AWS_INSTANCE_ID", DOCUMENTED_INSTANCE_ID)
    clear_ssm_cache()
    view = observe_bot(BOT_ID, root=tmp_path, persist=True)
    assert view["inspect"]["source"] == "ssm"
    assert view["runtime"]["lifecycle"] == "RUNNING"
    observed = view["runtime"]["observed"]
    assert observed["source"] == "ssm"
    assert observed["observed_at"]
    assert observed["instance_id"] == DOCUMENTED_INSTANCE_ID
    assert observed["service"] == SERVICE_NAME
    assert observed["lifecycle_guess"] == "RUNNING"
    disk = read_json(runtime_path(BOT_ID, "observed", root=tmp_path))
    assert disk["observed_at"] == observed["observed_at"]
    assert view["runtime"]["desired"]["lifecycle"] == "OBSERVATION_UNAVAILABLE"
    assert view["runtime"]["confirmed"]["lifecycle"]["value"] == "RUNNING"
    assert view["runtime"]["desired"]["lifecycle"] != observed["lifecycle_guess"]
    assert view["runtime"]["reconciliation"]["value"] == "Ambiguous"
    assert view["runtime"]["open_slots"]["value"] == 0


def test_host_fetch_default_enables_ssm_without_control(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    runner = _write_runner(tmp_path, _OFFICIAL_INSPECT)
    monkeypatch.delenv("VITAL_AWS_HOST_FETCH", raising=False)
    monkeypatch.setenv("VITAL_AWS_SSM_RUNNER", str(runner))
    monkeypatch.setenv("VITAL_AWS_INSTANCE_ID", DOCUMENTED_INSTANCE_ID)
    monkeypatch.delenv("VITAL_AWS_CONTROL", raising=False)
    assert host_fetch_enabled() is True
    assert control_enabled() is False
    clear_ssm_cache()
    body = inspect_mlb_001(refresh=True)
    assert body["source"] == "ssm"
    assert body["ok"] is True


def test_missing_and_stale_host_are_observation_unavailable(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    unread = handle_status(BOT_ID, root=tmp_path)
    assert unread["lifecycle"] == "OBSERVATION_UNAVAILABLE"
    assert unread["confirmed"]["lifecycle"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert "RUNNING" not in json.dumps(unread["confirmed"])
    write_json(
        runtime_path(BOT_ID, "observed", root=tmp_path),
        {"ok": True, "source": "ssm", "lifecycle_guess": "RUNNING", "status": "OBSERVED"},
    )
    write_json(
        runtime_path(BOT_ID, "confirmed", root=tmp_path),
        {"lifecycle": {"status": "CONFIRMED", "value": "RUNNING"}, "health": {"status": "CONFIRMED", "value": "HEALTHY"}},
    )
    stale = overlay_confirmed_lifecycle({"bot_id": BOT_ID, "status": "RUNNING"}, root=tmp_path)
    assert stale["status"] == "OBSERVATION_UNAVAILABLE"
    assert stale["observation_freshness"] == "STALE"
    listed = handle_bots_get(BOT_ID, root=tmp_path)
    assert listed["status"] == "OBSERVATION_UNAVAILABLE"
    write_json(
        runtime_path(BOT_ID, "observed", root=tmp_path),
        {
            "ok": True,
            "source": "ssm",
            "lifecycle_guess": "RUNNING",
            "status": "OBSERVED",
            "observed_at": (datetime.now(timezone.utc) - timedelta(seconds=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    aged = overlay_confirmed_lifecycle({"bot_id": BOT_ID, "status": "RUNNING"}, root=tmp_path)
    assert aged["status"] == "OBSERVATION_UNAVAILABLE"
    assert aged["observation_freshness"] == "STALE"


def test_fresh_observed_at_overlays_confirmed_running(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    write_json(
        runtime_path(BOT_ID, "observed", root=tmp_path),
        {
            "ok": True,
            "source": "ssm",
            "lifecycle_guess": "RUNNING",
            "status": "OBSERVED",
            "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "instance_id": DOCUMENTED_INSTANCE_ID,
            "service": SERVICE_NAME,
        },
    )
    write_json(
        runtime_path(BOT_ID, "confirmed", root=tmp_path),
        {"lifecycle": {"status": "CONFIRMED", "value": "RUNNING"}, "health": {"status": "CONFIRMED", "value": "HEALTHY"}},
    )
    rec = overlay_confirmed_lifecycle({"bot_id": BOT_ID, "status": "CREATED"}, root=tmp_path)
    assert rec["status"] == "RUNNING"
    assert rec["observation_freshness"] == "FRESH"


def test_jump_reads_vital_and_does_not_ssm_bot_one(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    fixture = tmp_path / "inspect.json"
    fixture.write_text(
        json.dumps(
            {
                "ok": True,
                "source": "fixture",
                "instance_id": DOCUMENTED_INSTANCE_ID,
                "service": {"value": {"name": SERVICE_NAME, "active": "active"}, "status": "CONFIRMED"},
                "heartbeat": {
                    "value": {
                        "kill_switch": False,
                        "live_armed_confirmed": True,
                        "open_mlb_positions": 0,
                        "reconciliation": "Ambiguous",
                        "reservations_n": 0,
                        "unknown_orders": 0,
                        "open_slots": 0,
                        "order_submission": "blocked",
                    },
                    "status": "CONFIRMED",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VITAL_AWS_INSPECT_FIXTURE", str(fixture))
    vital = observe_bot(BOT_ID, root=tmp_path, persist=False)
    jump = vital_observe("mlb-bot-one", root=tmp_path)
    assert jump["runtime"]["lifecycle"] == vital["runtime"]["lifecycle"] == "RUNNING"
    assert jump["runtime"]["reconciliation"]["value"] == "Ambiguous"
    assert jump["runtime"]["open_slots"]["value"] == 0
    hb = jump_heartbeat_from_vital(jump["runtime"], bot_id="mlb-bot-one")
    assert hb["source"] == "vital"
    assert hb["fields"]["reconciliation"] == "Ambiguous"
    assert hb["fields"]["open_slots"] == 0
    assert hb["fields"]["order_submission"] == "blocked"
    host = load_host_state()
    assert host.get("ssm_skipped") is True
    assert host.get("ok") is not True


def test_control_stays_disabled_in_connectivity_suite(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.delenv("VITAL_AWS_CONTROL", raising=False)
    assert control_enabled() is False
    assert os.environ.get("VITAL_AWS_CONTROL") in {None, ""}


def test_no_secrets_in_connectivity_fixtures():
    dumped = json.dumps(_OFFICIAL_INSPECT)
    for token in ("KALSHI_API_KEY", "PRIVATE_KEY", "secret_key", "api_key=", "BEGIN RSA"):
        assert token not in dumped
    assert "momento-kalshi-live.json" not in dumped
