"""Vital Phase 5 — desired/observed/confirmed. No invented zeros."""

from __future__ import annotations

import json

from roller.vital.api import handle_bot_health, handle_host_observe, handle_positions, handle_status
from roller.vital.observe import occupancy_trap, observe_bot, trading_health
from roller.vital.store import seed_mlb_001
from roller.vital.versions import BOT_ID


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    monkeypatch.delenv("VITAL_BOT_STATE_DIR", raising=False)
    monkeypatch.delenv("JUMP_BOT_ONE_HOST_FETCH", raising=False)
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")


def test_unread_host_is_unknown_not_running(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    status = handle_status(BOT_ID, root=tmp_path)
    assert status["lifecycle"] == "OBSERVATION_UNAVAILABLE"
    assert status["health"] == "UNKNOWN"
    assert status["confirmed"]["lifecycle"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert status["http_200_not_running"] is True
    health = handle_bot_health(BOT_ID, root=tmp_path)
    assert health["live_ev"]["status"] == "UNAVAILABLE"
    assert health["sharpe"]["status"] == "UNAVAILABLE"
    assert health["live_ev"]["value"] is None


def test_fixture_running_confirms_health(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    fixture = tmp_path / "inspect.json"
    fixture.write_text(
        json.dumps(
            {
                "ok": True,
                "source": "fixture",
                "instance_verified": True,
                "service": {"value": {"name": "momento-live.service", "active": "active"}, "status": "CONFIRMED"},
                "process": {"value": {"main_pid": 9}, "status": "CONFIRMED"},
                "version": {"value": {"binary_sha256": "def"}, "status": "CONFIRMED"},
                "environment": {"value": {"label": "production"}, "status": "OBSERVED"},
                "heartbeat": {
                    "value": {
                        "bankroll_cents": 4875,
                        "open_mlb_positions": 1,
                        "kill_switch": False,
                        "day_pnl_cents": -125,
                    },
                    "status": "CONFIRMED",
                },
                "logs": ["ok"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VITAL_AWS_INSPECT_FIXTURE", str(fixture))
    seed_mlb_001(root=tmp_path)
    view = observe_bot(BOT_ID, root=tmp_path)
    assert view["runtime"]["lifecycle"] == "RUNNING"
    assert view["runtime"]["health"] == "HEALTHY"
    assert view["runtime"]["confirmed"]["lifecycle"]["value"] == "RUNNING"
    assert view["runtime"]["bankroll_cents"]["value"] == 4875
    assert view["runtime"]["live_ev"]["status"] == "UNAVAILABLE"
    assert view["runtime"]["sharpe"]["value"] is None


def test_kill_switch_is_not_hidden(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    fixture = tmp_path / "inspect.json"
    fixture.write_text(
        json.dumps(
            {
                "ok": True,
                "service": {"value": {"active": "active"}, "status": "CONFIRMED"},
                "heartbeat": {"value": {"kill_switch": True, "open_mlb_positions": 1}, "status": "CONFIRMED"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VITAL_AWS_INSPECT_FIXTURE", str(fixture))
    seed_mlb_001(root=tmp_path)
    health = handle_bot_health(BOT_ID, root=tmp_path)
    assert health["health"] == "DEGRADED"
    assert health["kill_switch"]["value"] is True


def test_observe_persists_running_onto_bot(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    fixture = tmp_path / "inspect.json"
    fixture.write_text(
        json.dumps(
            {
                "ok": True,
                "service": {"value": {"name": "momento-live.service", "active": "active"}, "status": "CONFIRMED"},
                "heartbeat": {
                    "value": {
                        "kill_switch": False,
                        "live_armed_confirmed": True,
                        "open_mlb_positions": 0,
                    },
                    "status": "CONFIRMED",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VITAL_AWS_INSPECT_FIXTURE", str(fixture))
    seed_mlb_001(root=tmp_path)
    view = observe_bot(BOT_ID, root=tmp_path)
    assert view["runtime"]["live_armed"]["value"] is True
    assert view["runtime"]["open_mlb_positions"]["value"] == 0
    from roller.vital.store import load_bot

    rec = load_bot(BOT_ID, root=tmp_path)
    assert rec["status"] == "RUNNING"
    assert rec["activation"] == "RUNNING"
    assert rec["live_armed_confirmed"] is True
    observed = view["runtime"]["observed"]
    assert observed["observed_at"]
    assert observed["service"] == "momento-live.service"
    assert observed["source"] == "fixture"


def test_kalshi_book_fills_unread_host_positions():
    from roller.vital.observe import _overlay_runtime_book

    runtime = {"open_mlb_positions": {"status": "OBSERVATION_UNAVAILABLE", "value": None}}
    _overlay_runtime_book(runtime, {"positions": {"status": "CONFIRMED", "value": 0}})
    assert runtime["open_mlb_positions"]["status"] == "CONFIRMED"
    assert runtime["open_mlb_positions"]["value"] == 0


def test_unread_positions_are_not_empty_flat(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    body = handle_positions(BOT_ID, root=tmp_path)
    assert body["positions"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["positions"]["value"] is None
    assert body["live_ev"]["status"] == "UNAVAILABLE"


def test_host_observe_is_read_only_refresh(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    body = handle_host_observe(BOT_ID, root=tmp_path)
    assert body["refreshed"] is True
    assert body["read_only"] is True
    assert body["submits"] is False
    assert body["http_200_not_running"] is True
    assert body["lifecycle"] == "OBSERVATION_UNAVAILABLE"
    assert body["runtime"]["lifecycle"] == "OBSERVATION_UNAVAILABLE"


def test_occupancy_trap_ghost_cap_only_at_max_with_zero_fills():
    trap = occupancy_trap(open_slots=5, open_mlb_positions=0, max_open_slots=5)
    assert trap["status"] == "CONFIRMED"
    assert trap["value"]["trapped"] is True
    clear = occupancy_trap(open_slots=0, open_mlb_positions=0, max_open_slots=5)
    assert clear["status"] == "CONFIRMED"
    assert clear["value"]["trapped"] is False
    real = occupancy_trap(open_slots=5, open_mlb_positions=2, max_open_slots=5)
    assert real["value"]["trapped"] is False
    unread = occupancy_trap()
    assert unread["status"] == "OBSERVATION_UNAVAILABLE"
    assert unread["value"] is None


def test_observe_exports_activity_and_does_not_invent_unread_counts(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    fixture = tmp_path / "inspect.json"
    fixture.write_text(
        json.dumps(
            {
                "ok": True,
                "source": "fixture",
                "service": {"value": {"name": "momento-live.service", "active": "active"}, "status": "CONFIRMED"},
                "heartbeat": {
                    "value": {
                        "kill_switch": False,
                        "open_mlb_positions": 0,
                        "open_slots": 5,
                        "max_open_slots": 5,
                        "reconciliation": "Ambiguous",
                        "order_submission": "blocked",
                        "mlb_yes_bid_n": 12,
                        "first80_n": 0,
                        "first81_n": 0,
                        "submit_to_ack_n": 0,
                        "last_mlb_ticker": "KXMLBGAME-26SEP161340NYYMIN-MIN",
                        "last_mlb_bid_cents": 36,
                        "last_mlb_ask_cents": 37,
                    },
                    "status": "CONFIRMED",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VITAL_AWS_INSPECT_FIXTURE", str(fixture))
    seed_mlb_001(root=tmp_path)
    view = observe_bot(BOT_ID, root=tmp_path, persist=False)
    runtime = view["runtime"]
    assert runtime["occupancy_trap"]["value"]["trapped"] is True
    assert runtime["mlb_yes_bid_n"]["value"] == 12
    assert runtime["first80_n"]["value"] == 0
    assert runtime["last_mlb_ticker"]["value"].startswith("KXMLBGAME")
    assert runtime["submit_to_ack_n"]["value"] == 0
    unread = occupancy_trap()
    assert unread["status"] == "OBSERVATION_UNAVAILABLE"


def test_trading_health_clear_is_not_process_authorization(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    fixture = tmp_path / "inspect.json"
    fixture.write_text(
        json.dumps(
            {
                "ok": True,
                "source": "fixture",
                "service": {"value": {"name": "momento-live.service", "active": "active"}, "status": "CONFIRMED"},
                "heartbeat": {
                    "value": {
                        "kill_switch": False,
                        "reconciliation": "Healthy",
                        "order_submission": "enabled",
                        "unknown_orders": 0,
                    },
                    "status": "CONFIRMED",
                },
                "logs": ["momento recon_cleared reason=no_unknown_no_live_uncertain order_submission=enabled"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VITAL_AWS_INSPECT_FIXTURE", str(fixture))
    seed_mlb_001(root=tmp_path)
    view = observe_bot(BOT_ID, root=tmp_path, persist=False)
    runtime = view["runtime"]
    health = runtime["trading_health"]["value"]
    assert runtime["health"] == "HEALTHY"
    assert health["status"] == "CLEAR"
    assert health["authorized_to_submit"] is True
    assert health["auto_flatten"] is False
    assert health["process_up_is_not_authorization"] is True
    assert health["flags"] == []
    bot_health = handle_bot_health(BOT_ID, root=tmp_path)
    assert bot_health["trading_health"]["value"]["status"] == "CLEAR"


def test_trading_health_flags_ambiguous_without_flattening(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    fixture = tmp_path / "inspect.json"
    fixture.write_text(
        json.dumps(
            {
                "ok": True,
                "source": "fixture",
                "service": {"value": {"name": "momento-live.service", "active": "active"}, "status": "CONFIRMED"},
                "heartbeat": {
                    "value": {
                        "kill_switch": False,
                        "reconciliation": "Ambiguous",
                        "order_submission": "blocked",
                        "unknown_orders": 0,
                    },
                    "status": "CONFIRMED",
                },
                "logs": [
                    "momento recon_cleared reason=no_unknown_no_live_uncertain order_submission=enabled",
                    "momento heartbeat reconciliation=ambiguous unknown_orders=0 order_submission=blocked",
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VITAL_AWS_INSPECT_FIXTURE", str(fixture))
    seed_mlb_001(root=tmp_path)
    view = observe_bot(BOT_ID, root=tmp_path, persist=False)
    runtime = view["runtime"]
    health = runtime["trading_health"]["value"]
    ids = {row["id"] for row in health["flags"]}
    assert runtime["health"] == "HEALTHY"
    assert health["status"] == "FLAGGED"
    assert health["authorized_to_submit"] is False
    assert health["auto_flatten"] is False
    assert "recon_ambiguous" in ids
    assert "order_submission_blocked" in ids
    assert "sticky_blocked_after_recon_cleared" in ids
    ambiguous = next(row for row in health["flags"] if row["id"] == "recon_ambiguous")
    assert ambiguous["unknowns"] == 0


def test_trading_health_stale_heartbeat_and_venue_auth():
    from datetime import datetime, timezone

    now = datetime(2026, 9, 16, 21, 40, tzinfo=timezone.utc)
    stale = trading_health(
        fields={"reconciliation": "Healthy", "order_submission": "enabled", "unknown_orders": 0},
        inspect={"ok": True, "logs": ["momento venue_error=timeout"]},
        observed_at="2026-09-16T21:30:00Z",
        now=now,
    )
    ids = {row["id"] for row in stale["value"]["flags"]}
    assert stale["value"]["status"] == "FLAGGED"
    assert "heartbeat_stale" in ids
    assert "venue_auth_error" in ids
    unread = trading_health(inspect={"ok": False})
    assert unread["status"] == "OBSERVATION_UNAVAILABLE"
    assert unread["value"] is None
