"""Vital live-service integration proof. L1–L8 stay independent. No production order."""

from __future__ import annotations

import json

import pytest

from roller.vital.api import handle_demo_lifecycle, handle_health, handle_integration, handle_integration_handshake
from roller.vital.demo_control import demo_unit_name, stop_script
from roller.vital.errors import VitalError
from roller.vital.integration_proof import (
    DEFAULT_WINDOW_S,
    DEMO_SUCCESS_FIXTURE,
    PROOF_ID,
    collect_demo_exchange,
    evaluate_demo_chain,
    evaluate_l1,
    evaluate_l8,
    evaluate_liveness_window,
    evaluate_proof,
    persist_demo_control_proof,
    persist_demo_strategy_proof,
    record_liveness_sample,
)
from roller.vital.store import save_bot, seed_mlb_001
from roller.vital.versions import BOT_ID, CONTROL_CONFIRMATION, LIVE_CONFIRMATION, LIVE_EXECUTION


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    monkeypatch.delenv("VITAL_AWS_CONTROL", raising=False)
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    monkeypatch.delenv("VITAL_AWS_INSPECT_FIXTURE", raising=False)
    monkeypatch.delenv("VITAL_DEMO_INSPECT_FIXTURE", raising=False)


def _factory_inspect() -> dict:
    return {
        "ok": True,
        "source": "fixture",
        "service": {
            "name": "momento-live.service",
            "active": "active",
            "started_at": "Wed 2026-09-16 20:00:11 UTC",
            "working_directory": "/var/lib/momento",
            "n_restarts": 0,
        },
        "process": {
            "main_pid": 1101134,
            "exe": "/usr/local/bin/momento-trading-engine",
            "cwd": "/var/lib/momento",
            "exe_matches": True,
            "cwd_matches": True,
        },
        "version": {"binary_sha256": "abc123"},
        "environment": {"kalshi_env": "production", "label": "production"},
        "heartbeat": {
            "value": {
                "kill_switch": False,
                "live_armed": True,
                "live_armed_confirmed": True,
                "updated_at": "2026-09-16T20:10:00Z",
                "reservations_n": 0,
                "order_submission": "idle",
            },
            "status": "CONFIRMED",
        },
        "gates": {"ok": True, "armed": True},
        "logs": ["momento heartbeat open_slots=0"],
    }


def _demo_control_proof() -> dict:
    return {
        "ok": True,
        "status": "CONFIRMED",
        "bot_id": "mlb-002",
        "unit": "momento-demo@mlb-002.service",
        "lifecycle": "CONFIRMED",
        "steps": [
            {"action": "inspect", "lifecycle": "RUNNING_DEMO", "ok": True, "active": True},
            {"action": "stop", "ok": True, "unit": "momento-demo@mlb-002.service"},
            {"action": "inspect", "lifecycle": "STOPPED", "ok": True, "active": False},
            {"action": "start", "ok": True, "unit": "momento-demo@mlb-002.service"},
            {"action": "inspect", "lifecycle": "RUNNING_DEMO", "ok": True, "active": True},
        ],
    }


def _demo_strategy_proof() -> dict:
    return {
        "ok": True,
        "bot": {
            "bot_id": "mlb-002",
            "engine": {"prices": {"entry_cents": 20, "win_cents": 60, "loss_cents": 10}},
            "iti": {"entry_cents": 20, "win_cents": 60, "loss_cents": 10},
        },
        "inspect": {
            "ok": True,
            "heartbeat": True,
            "config": {"strategy_profile": "research_iti", "iti_entry_cents": "20"},
            "logs": ["momento signal generated", "risk approved", "demo_submit ack"],
        },
        "written": {"strategy_profile": "research_iti"},
        "observed": {"strategy_profile": "research_iti"},
        "loaded": {"ok": True},
        "vital_test_id": "vital-test-001",
        "strategy_id": "test-vital-strategy-001",
        "signal_id": "sig-1",
        "intent_id": "int-1",
        "order_id": "ord-1",
        "fill_id": "fill-1",
        "risk_decision": "approved",
        "demo_order_attempt": True,
        "demo_exchange_response": "ack",
        "deterministic_fixture": {
            "source": DEMO_SUCCESS_FIXTURE,
            "http_status": 201,
        },
        "correlation": {
            "vital_test_id": "vital-test-001",
            "strategy_id": "test-vital-strategy-001",
            "signal_id": "sig-1",
            "intent_id": "int-1",
            "order_id": "ord-1",
        },
    }


def _window_samples(pid: int = 1101134) -> list[dict]:
    return [
        {
            "observed_at": "2026-09-16T20:00:00Z",
            "pid": pid,
            "service_active": "active",
            "binary_sha256": "abc123",
            "started_at": "Wed 2026-09-16 20:00:11 UTC",
            "heartbeat_updated_at": "2026-09-16T20:00:00Z",
            "live_armed": True,
            "kill_switch": False,
            "n_restarts": 0,
        },
        {
            "observed_at": "2026-09-16T20:30:00Z",
            "pid": pid,
            "service_active": "active",
            "binary_sha256": "abc123",
            "started_at": "Wed 2026-09-16 20:00:11 UTC",
            "heartbeat_updated_at": "2026-09-16T20:30:00Z",
            "live_armed": True,
            "kill_switch": False,
            "n_restarts": 0,
        },
    ]


def test_unread_inspect_is_not_running(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    body = evaluate_proof(BOT_ID, bot={"bot_id": BOT_ID, "kind": "grandfathered"}, inspect={"ok": False, "reason": "host unread"}, root=tmp_path)
    assert body["accepted"] is False
    assert body["levels"]["L1_PROCESS"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["lifecycle_claim"] != "RUNNING"
    assert body["collapsed_to_running"] is False
    assert body["levels"]["L8_EXCHANGE"]["status"] == "NOT_CLAIMED"
    assert "RUNNING" not in json.dumps(body["levels"]["L1_PROCESS"])


def test_l1_running_does_not_collapse_signaling_unread(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    body = evaluate_proof(
        BOT_ID,
        bot={"bot_id": BOT_ID, "kind": "grandfathered"},
        inspect=_factory_inspect(),
        root=tmp_path,
    )
    assert body["levels"]["L1_PROCESS"]["status"] == "CONFIRMED"
    assert body["chain"]["SIGNALING"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["lifecycle_claim"] != "RUNNING"
    assert body["collapsed_to_running"] is False
    assert body["accepted"] is False
    assert body["strategy_status"] in {"LOADED", "OBSERVATION_UNAVAILABLE"}
    assert body["strategy_status"] != "TRADING"
    assert body["strategy_status"] != "LIVE"


def test_liveness_samples_are_rate_limited(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    inspect = _factory_inspect()
    first = record_liveness_sample(BOT_ID, inspect, root=tmp_path, observed_at="2026-09-16T20:00:00Z")
    second = record_liveness_sample(BOT_ID, inspect, root=tmp_path, observed_at="2026-09-16T20:00:10Z")
    third = record_liveness_sample(BOT_ID, inspect, root=tmp_path, observed_at="2026-09-16T20:01:10Z")
    assert first is not None
    assert second is None
    assert third is not None


def test_l2_one_sample_is_unavailable(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    inspect = _factory_inspect()
    record_liveness_sample(BOT_ID, inspect, root=tmp_path, observed_at="2026-09-16T20:00:00Z")
    window = evaluate_liveness_window(
        [{"observed_at": "2026-09-16T20:00:00Z", "pid": 1}],
        min_span_s=DEFAULT_WINDOW_S,
    )
    assert window["status"] == "OBSERVATION_UNAVAILABLE"
    assert window["window_met"] is False


def test_l2_window_confirms_monotonicity():
    window = evaluate_liveness_window(_window_samples(), min_span_s=DEFAULT_WINDOW_S)
    assert window["window_met"] is True
    assert window["status"] == "CONFIRMED"
    assert window["pid_stable"]["status"] == "CONFIRMED"
    assert window["heartbeat_advancing"]["status"] == "CONFIRMED"
    assert window["unexpected_restarts"]["status"] == "CONFIRMED"


def test_l2_pid_change_is_failed():
    rows = _window_samples()
    rows[1]["pid"] = 99
    window = evaluate_liveness_window(rows, min_span_s=DEFAULT_WINDOW_S)
    assert window["status"] == "FAILED"
    assert window["pid_stable"]["status"] == "FAILED"
    assert window["unexpected_restarts"]["status"] == "FAILED"


def test_production_l8_is_never_claimed(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    body = evaluate_proof(
        BOT_ID,
        bot={"bot_id": BOT_ID, "kind": "grandfathered"},
        inspect=_factory_inspect(),
        root=tmp_path,
    )
    assert body["levels"]["L8_EXCHANGE"]["status"] == "NOT_CLAIMED"
    assert body["production_test_order"] is False
    assert body["architecture"]["no_second_engine"]["status"] == "CONFIRMED"
    assert LIVE_EXECUTION is False


def test_demo_stop_refuses_factory_unit():
    script = stop_script("mlb-002")
    assert "momento-demo@mlb-002.service" in script
    assert "systemctl stop momento-live.service" not in script
    assert demo_unit_name("mlb-002") == "momento-demo@mlb-002.service"
    with pytest.raises(VitalError):
        stop_script("mlb-001")
    with pytest.raises(VitalError):
        demo_unit_name("mlb-001")


def test_demo_lifecycle_fail_closed(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    save_bot(
        {
            "bot_id": "mlb-002",
            "kind": "iti",
            "environment": "DEMO",
            "engine": {"prices": {"entry_cents": 20, "win_cents": 60, "loss_cents": 10}},
        },
        root=tmp_path,
    )
    with pytest.raises(VitalError) as factory:
        handle_demo_lifecycle(BOT_ID, {"confirmation": CONTROL_CONFIRMATION}, root=tmp_path)
    assert factory.value.code == "REJECTED"
    with pytest.raises(VitalError) as disabled:
        handle_demo_lifecycle("mlb-002", {"confirmation": CONTROL_CONFIRMATION}, root=tmp_path)
    assert disabled.value.code == "CONTROL_DISABLED"
    monkeypatch.setenv("VITAL_AWS_CONTROL", "1")
    with pytest.raises(VitalError) as live:
        handle_demo_lifecycle("mlb-002", {"confirmation": LIVE_CONFIRMATION}, root=tmp_path)
    assert live.value.code == "REJECTED"


def test_handshake_factory_is_loaded_not_live(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    fixture = tmp_path / "inspect.json"
    fixture.write_text(json.dumps(_factory_inspect()), encoding="utf-8")
    monkeypatch.setenv("VITAL_AWS_INSPECT_FIXTURE", str(fixture))
    with pytest.raises(VitalError):
        handle_integration_handshake(BOT_ID, {"confirmation": LIVE_CONFIRMATION}, root=tmp_path)
    body = handle_integration_handshake(BOT_ID, {}, root=tmp_path)
    assert body["wrote_live_toml"] is False
    assert body["strategy_status"] in {"LOADED", "OBSERVATION_UNAVAILABLE"}
    assert body["strategy_status"] != "LIVE"
    assert body["strategy_status"] != "TRADING"
    assert body["production_test_order"] is False


def test_full_acceptance_requires_all_suites(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    inspect = _factory_inspect()
    for row in _window_samples():
        record_liveness_sample(BOT_ID, inspect, root=tmp_path, observed_at=row["observed_at"])
        # overwrite sample fields that record_liveness_sample derives
    from roller.vital.store import write_json
    from roller.vital.integration_proof import liveness_path

    path = liveness_path(BOT_ID, root=tmp_path)
    path.write_text("\n".join(json.dumps(row) for row in _window_samples()) + "\n", encoding="utf-8")
    persist_demo_control_proof(_demo_control_proof(), root=tmp_path)
    persist_demo_strategy_proof(_demo_strategy_proof(), root=tmp_path)
    body = evaluate_proof(
        BOT_ID,
        bot={"bot_id": BOT_ID, "kind": "grandfathered"},
        inspect=inspect,
        root=tmp_path,
    )
    assert body["suites"]["A_PRODUCTION_READ"]["status"] == "CONFIRMED"
    assert body["suites"]["B_DEMO_CONTROL"]["status"] == "CONFIRMED"
    assert body["suites"]["C_DEMO_STRATEGY"]["status"] == "CONFIRMED"
    assert body["suites"]["D_PRODUCTION_STRATEGY_LOAD"]["status"] == "CONFIRMED"
    assert body["suites"]["D_PRODUCTION_STRATEGY_LOAD"]["strategy_status"] == "LOADED"
    assert body["levels"]["L8_EXCHANGE"]["status"] == "NOT_CLAIMED"
    assert body["accepted"] is True
    assert body["architecture"]["existing_engine_untouched"]["status"] == "CONFIRMED"


def test_l1_identity_fields():
    body = evaluate_l1(_factory_inspect(), factory=True)
    assert body["pid_executable"]["status"] == "CONFIRMED"
    assert body["working_directory"]["status"] == "CONFIRMED"
    assert body["kalshi_env"]["value"] == "production"
    assert body["kill"]["status"] == "NOT_TRIPPED"
    assert body["enable_live_trading"]["status"] == "CONFIRMED"


def test_demo_503_stays_unknown_and_does_not_become_ack():
    exchange = collect_demo_exchange(
        ["momento demo_submit_refused=HTTP 503 service unavailable"],
        {"demo_order_attempt": True},
    )
    assert exchange["http_status"] == 503
    assert exchange["order_state"] == "UNKNOWN"
    assert exchange["fail_closed"] is True
    assert exchange["retry"] is False
    assert exchange["live_acknowledged"] is False
    l8 = evaluate_l8(
        factory=False,
        demo_proof={
            "correlation": {"strategy_id": "mlb-005"},
            "inspect": {"logs": ["momento demo_submit_refused=HTTP 503"]},
            "exchange_http": 503,
            "order_state": "UNKNOWN",
        },
    )
    assert l8["status"] == "OBSERVATION_UNAVAILABLE"
    assert l8["order_state"] == "UNKNOWN"
    assert l8["fail_closed"] is True
    assert l8["retry"] is False


def test_demo_503_does_not_use_live_ack_even_with_fixture():
    bot = {"engine": {"prices": {"entry_cents": 21, "win_cents": 61, "loss_cents": 11}}}
    inspect = {
        "ok": True,
        "heartbeat": True,
        "config": {"strategy_profile": "research_iti", "iti_entry_cents": "21"},
        "logs": ["yes_bid_update ticker=KXMLB", "momento demo_risk_rejected=none", "momento demo_submit_refused=HTTP 503"],
    }
    proof = {
        "desired": {"profile": "research_iti"},
        "written": {"strategy_profile": "research_iti"},
        "observed": {"strategy_profile": "research_iti"},
        "loaded": {"ok": True},
        "risk_decision": "approved",
        "demo_order_attempt": True,
        "exchange_http": 503,
        "order_state": "UNKNOWN",
        "deterministic_fixture": {"source": DEMO_SUCCESS_FIXTURE, "http_status": 201},
    }
    chain = evaluate_demo_chain(bot, inspect, proof)
    assert chain["ACKNOWLEDGED"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert "503" in str(chain["ACKNOWLEDGED"].get("detail") or "")
    assert chain["FILLED"]["status"] == "OBSERVATION_UNAVAILABLE"
    from roller.vital.integration_proof import _suite_c_status

    assert _suite_c_status(chain, proof) == "CONFIRMED"


def test_invented_signal_id_does_not_confirm_signaling():
    bot = {"engine": {"prices": {"entry_cents": 21, "win_cents": 61, "loss_cents": 11}}}
    inspect = {
        "ok": True,
        "heartbeat": True,
        "config": {"strategy_profile": "research_iti", "iti_entry_cents": "21"},
        "logs": ["momento-trading-engine start strategy_profile=research_iti"],
    }
    proof = {
        "desired": {"profile": "research_iti"},
        "written": {"strategy_profile": "research_iti"},
        "observed": {"strategy_profile": "research_iti"},
        "loaded": {"ok": True},
        "signal_id": "mlb-005-yes-bid-observe",
        "intent_id": "mlb-005-risk-decision",
        "risk_decision": "observed rejects",
    }
    chain = evaluate_demo_chain(bot, inspect, proof)
    assert chain["SIGNALING"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert chain["RISK_APPROVED"]["status"] == "OBSERVATION_UNAVAILABLE"


def test_live_503_without_fixture_does_not_confirm_suite_c():
    bot = {"engine": {"prices": {"entry_cents": 21, "win_cents": 61, "loss_cents": 11}}}
    inspect = {
        "ok": True,
        "heartbeat": True,
        "config": {"strategy_profile": "research_iti", "iti_entry_cents": "21"},
        "logs": [
            "momento demo_risk_rejected=DailyTradeLimit",
            "momento demo_submit_refused=malformed venue response: unexpected HTTP 503",
        ],
    }
    proof = {
        "desired": {"profile": "research_iti"},
        "written": {"strategy_profile": "research_iti"},
        "observed": {"strategy_profile": "research_iti"},
        "loaded": {"ok": True},
        "demo_order_attempt": True,
        "exchange_http": 503,
        "order_state": "UNKNOWN",
    }
    chain = evaluate_demo_chain(bot, inspect, proof)
    from roller.vital.integration_proof import _suite_c_status

    assert chain["ACKNOWLEDGED"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert _suite_c_status(chain, proof) == "OBSERVATION_UNAVAILABLE"


def test_health_exposes_proof_token(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    body = handle_health(root=tmp_path)
    assert body["integration_proof"]["id"] == PROOF_ID
    assert "RUNNING ≠ HEALTHY ≠ EXECUTING" in body["caveats"]


def test_handle_integration_does_not_claim_running(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    seed_mlb_001(root=tmp_path)
    body = handle_integration(BOT_ID, root=tmp_path)
    assert body["proof_id"] == PROOF_ID
    assert body["accepted"] is False
    assert body["http_200_not_running"] is True
    assert body["levels"]["L8_EXCHANGE"]["status"] == "NOT_CLAIMED"
