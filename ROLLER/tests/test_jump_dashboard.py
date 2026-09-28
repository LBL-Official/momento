"""Jump C — operating dashboard. No invented $0. No credentials."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from roller.jump.bots.versions import BOT_ONE_ID
from roller.jump.dashboard.api import handle_dashboard, handle_logs
from roller.jump.dashboard.heartbeat import load_probe_heartbeat, parse_heartbeat_payload
from roller.jump.dashboard.rollup import rollup_tracks
from roller.jump.versions import CODE_VERSION, PHASE_STATUS

_BANNED = ("KALSHI_API_KEY", "PRIVATE_KEY", "secret_key", "api_key=")


def _isolate(monkeypatch, tmp_path: Path) -> Path:
    bots = tmp_path / "bots"
    monkeypatch.setenv("JUMP_BOTS_ROOT", str(bots))
    monkeypatch.setenv("JUMP_DASHBOARD_ROOT", str(tmp_path / "dashboard"))
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    monkeypatch.delenv("JUMP_BOT_ONE_PROBE", raising=False)
    monkeypatch.delenv("JUMP_BOT_ONE_STATE_DIR", raising=False)
    monkeypatch.delenv("JUMP_BOT_ONE_RUNTIME_PATH", raising=False)
    monkeypatch.delenv("JUMP_BOT_ONE_SNAPSHOT_PATH", raising=False)
    monkeypatch.delenv("JUMP_BOT_ONE_HOST_FETCH", raising=False)
    monkeypatch.delenv("JUMP_BOT_DEMO_READY", raising=False)
    monkeypatch.delenv("JUMP_BOT_DEMO_RUNNING", raising=False)
    monkeypatch.delenv("JUMP_BOT_DEMO_SSM", raising=False)
    monkeypatch.delenv("JUMP_BOT_PROMOTE_READY", raising=False)
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path / "vital"))
    monkeypatch.delenv("VITAL_AWS_INSPECT_FIXTURE", raising=False)
    monkeypatch.delenv("VITAL_BOT_STATE_DIR", raising=False)
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    return bots


def test_health_c_implemented():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    jump = TestClient(terminal_api.app).get("/jump/health").json()
    assert jump["phases"] == {"A": "MOVED_TO_SUPERASI", "B": "IMPLEMENTED", "C": "IMPLEMENTED"}
    assert jump["code_version"] == CODE_VERSION
    assert PHASE_STATUS["C"] == "IMPLEMENTED"
    assert "JUMP C = NOT_STARTED" not in jump["caveats"]
    assert "jump_dashboard" in TestClient(terminal_api.app).get("/health").json()["capabilities"]


def test_no_credentials_in_dashboard():
    root = Path(__file__).resolve().parents[1] / "roller" / "jump" / "dashboard"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in _BANNED:
            assert token not in text, f"{path} contains {token}"


def test_bot_one_first_and_unavailable_without_probe(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    body = handle_dashboard(root=tmp_path / "bots")
    assert body["tracks"][0]["bot_id"] == BOT_ONE_ID
    assert body["header"]["bankroll"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["header"]["bankroll"]["value"] is None
    assert body["header"]["day_pnl"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["header"]["day_pnl"]["value"] is None
    assert body["tracks"][0]["actual"]["pnl"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["tracks"][0]["actual"]["pnl"]["value"] is None
    assert body["tracks"][0]["actual"]["sharpe"]["status"] == "UNAVAILABLE"
    assert body["tracks"][0]["expected"]["pnl"]["status"] == "UNAVAILABLE"
    assert body["tracks"][0]["activity"]["value"] == "OBSERVATION_UNAVAILABLE"
    assert "$0" not in json.dumps(body["header"])
    assert body["header"]["bankroll"]["value"] != 0


def _vital_running(tmp_path: Path, **fields) -> Path:
    fixture = tmp_path / "vital_inspect.json"
    heartbeat = {"kill_switch": False, "live_armed_confirmed": True, **fields}
    fixture.write_text(
        json.dumps(
            {
                "ok": True,
                "source": "fixture",
                "service": {"value": {"name": "momento-live.service", "active": "active"}, "status": "CONFIRMED"},
                "heartbeat": {"value": heartbeat, "status": "CONFIRMED"},
            }
        ),
        encoding="utf-8",
    )
    return fixture


def test_probe_shows_only_confirmed_keys(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("VITAL_AWS_INSPECT_FIXTURE", str(_vital_running(tmp_path, bankroll_cents=5000, open_mlb_positions=2)))
    body = handle_dashboard(root=tmp_path / "bots")
    one = body["tracks"][0]
    assert one["actual"]["bankroll"] == {"value": 5000, "status": "CONFIRMED"}
    assert one["actual"]["open_mlb_positions"] == {"value": 2, "status": "CONFIRMED"}
    assert one["actual"]["sharpe"]["status"] == "UNAVAILABLE"
    assert one["actual"]["pnl"]["value"] is None
    assert one["actual"]["pnl"]["status"] in {"UNAVAILABLE", "OBSERVATION_UNAVAILABLE"}
    assert one["actual"]["last_trade"]["status"] == "UNAVAILABLE"
    assert one["expected"]["day_ev"]["status"] == "UNAVAILABLE"
    assert one["activity"]["value"] == "ACTIVE"
    assert body["header"]["bankroll"]["value"] == 5000
    assert body["header"]["day_sharpe"]["status"] == "UNAVAILABLE"


def test_rollup_does_not_sum_unavailable_to_zero(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    body = handle_dashboard(root=tmp_path / "bots")
    rollup = body["rollup"]
    assert rollup["actual"]["bankroll"]["status"] == "UNAVAILABLE"
    assert rollup["actual"]["bankroll"]["value"] is None
    assert rollup["actual"]["pnl"]["status"] == "UNAVAILABLE"
    assert rollup["expected"]["day_ev"]["status"] == "UNAVAILABLE"
    mixed = rollup_tracks(
        [
            {"actual": {"bankroll": {"value": 5000, "status": "CONFIRMED"}}, "expected": {}},
            {"actual": {"bankroll": {"value": None, "status": "UNAVAILABLE"}}, "expected": {}},
        ]
    )
    assert mixed["actual"]["bankroll"]["status"] == "UNAVAILABLE"
    assert mixed["actual"]["bankroll"]["value"] is None


def test_missing_heartbeat_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("JUMP_BOT_ONE_PROBE", raising=False)
    parsed = parse_heartbeat_payload({"live_armed_confirmed": True, "bankroll_cents": 5000})
    assert "open_mlb_positions" not in parsed["fields"]
    assert parsed["fields"]["bankroll_cents"] == 5000
    unset = load_probe_heartbeat()
    assert unset["status"] == "OBSERVATION_UNAVAILABLE"


def test_probe_pnl_keys_reach_header_and_track(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv(
        "JUMP_BOT_ONE_PROBE",
        json.dumps(
            {
                "status": "PRODUCTION",
                "live_armed_confirmed": True,
                "bankroll_cents": 5000,
                "day_pnl_cents": -3177,
                "week_pnl_cents": -3177,
                "open_mlb_positions": 0,
            }
        ),
    )
    body = handle_dashboard(root=tmp_path / "bots")
    assert body["header"]["day_pnl"]["value"] is None
    assert body["header"]["day_pnl"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["header"]["week_pnl"]["value"] is None
    one = body["tracks"][0]
    assert one["actual"]["pnl"]["value"] is None
    assert one["actual"]["week_pnl"]["value"] is None
    assert one["actual"]["sharpe"]["status"] == "UNAVAILABLE"
    assert one["expected"]["day_ev"]["status"] == "UNAVAILABLE"
    assert one["expected"]["day_ev"]["value"] is None
    assert body["rollup"]["actual"]["day_pnl"]["value"] is None
    assert body["rollup"]["expected"]["day_ev"]["status"] == "UNAVAILABLE"


def test_local_ledger_is_not_jump_c_truth(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    runtime = {
        "tracker": {
            "positions": [
                {
                    "strategy_id": 1,
                    "lifecycle": "Settled",
                    "filled_quantity": {"qty": 3},
                    "fill_history": [
                        {
                            "premium": {"cents": 240},
                            "fee": {"amount": {"cents": 5}, "kind": "Entry"},
                            "exchange_ts": "2026-08-26T16:00:00Z",
                        }
                    ],
                    "settlement_proceeds": {"cents": 300},
                }
            ]
        }
    }
    (state / "live-runtime.json").write_text(json.dumps(runtime), encoding="utf-8")
    (state / "weekly-snapshot.json").write_text(
        json.dumps({"bankroll": {"cents": 5000}, "week_start_utc": "2026-08-24T11:00:00Z"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("JUMP_BOT_ONE_STATE_DIR", str(state))
    from roller.jump.dashboard.heartbeat import load_bot_one_heartbeat

    observed = load_bot_one_heartbeat(now=datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc))
    assert observed["source"] == "vital"
    assert "day_pnl_cents" not in observed["fields"]
    body = handle_dashboard(root=tmp_path / "bots")
    assert body["tracks"][0]["expected"]["week_ev"]["status"] == "UNAVAILABLE"
    assert body["tracks"][0]["actual"]["origin_pnl"]["value"] is None
    assert body["header"]["origin_pnl"]["value"] is None
    assert body["header"]["day_pnl"]["value"] is None
    assert body["header"]["day_pnl"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["header"]["source"] == "vital"


def test_bot_one_runtime_comes_from_vital_not_ssm(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    called = {"ssm": False}

    def _boom(*_args, **_kwargs):
        called["ssm"] = True
        raise AssertionError("Jump must not SSM Bot One")

    monkeypatch.setattr("roller.jump.dashboard.host_state.fetch_ssm_ledger", _boom)
    monkeypatch.setenv("JUMP_BOT_ONE_HOST_FETCH", "ssm")
    body = handle_dashboard(root=tmp_path / "bots")
    assert called["ssm"] is False
    assert body["tracks"][0]["observation"]["source"] == "vital"
    assert body["tracks"][0]["bot_status"] == "OBSERVATION_UNAVAILABLE"
    assert body["heartbeat"]["status"] == "OBSERVATION_UNAVAILABLE"


def test_unread_ledger_is_not_zero(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("JUMP_BOT_ONE_STATE_DIR", str(tmp_path / "missing-state"))
    body = handle_dashboard(root=tmp_path / "bots")
    assert body["header"]["day_pnl"]["value"] is None
    assert body["header"]["day_pnl"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["rollup"]["actual"]["day_pnl"]["value"] is None


def test_http_dashboard_and_logs(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    body = client.get("/jump/dashboard").json()
    assert body["tracks"][0]["bot_id"] == BOT_ONE_ID
    assert body["tracks"][0]["expected"]["sharpe"]["status"] == "UNAVAILABLE"
    logs = client.get("/jump/dashboard/logs").json()
    assert logs["honesty"]["control_events_only"] is True
    local = handle_logs(root=tmp_path / "bots")
    assert local["source"] == "jump_b_events_jsonl"


def test_fill_list_and_weekly_count():
    from datetime import datetime, timezone

    from roller.jump.dashboard.ledger import list_mlb_fills, summarize_mlb_ledger

    runtime = {
        "tracker": {
            "positions": [
                {
                    "strategy_id": 1,
                    "lifecycle": "Settled",
                    "filled_quantity": {"qty": 3},
                    "ticker": "KXMLBGAME-TEST",
                    "fill_history": [
                        {
                            "premium": {"cents": 240},
                            "fee": {"amount": {"cents": 5}, "kind": "Entry"},
                            "exchange_ts": "2026-08-26T16:00:00Z",
                            "side": "yes",
                        }
                    ],
                    "settlement_proceeds": {"cents": 300},
                }
            ]
        }
    }
    now = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    fills = list_mlb_fills(runtime, {"week_start_utc": "2026-08-24T11:00:00Z"}, now)
    assert fills["ok"] is True
    assert fills["fields"]["trade_n"] == 1
    assert fills["fields"]["weekly_trade_n"] == 1
    assert fills["trades"][0]["premium_cents"] == 240
    assert fills["trades"][0]["market"] == "KXMLBGAME-TEST"
    summary = summarize_mlb_ledger(runtime, {"week_start_utc": "2026-08-24T11:00:00Z", "bankroll": {"cents": 5000}}, now)
    assert summary["fields"]["trade_n"] == 1
    assert summary["fields"]["day_pnl_cents"] == 55


def test_fill_market_prefers_ticker_over_numeric_id():
    from datetime import datetime, timezone

    from roller.jump.dashboard.ledger import list_mlb_fills

    runtime = {
        "tracker": {
            "positions": [
                {
                    "strategy_id": 1,
                    "lifecycle": "Settled",
                    "filled_quantity": {"qty": 3},
                    "market_id": "1" * 39,
                    "ticker": "KXMLBGAME-TEST",
                    "fill_history": [
                        {
                            "premium": {"cents": 240},
                            "fee": {"amount": {"cents": 5}, "kind": "Entry"},
                            "exchange_ts": "2026-08-26T16:00:00Z",
                            "market_id": "1" * 39,
                            "side": "yes",
                        }
                    ],
                    "settlement_proceeds": {"cents": 300},
                }
            ]
        }
    }
    fills = list_mlb_fills(runtime, {"week_start_utc": "2026-08-24T11:00:00Z"}, datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc))
    assert fills["ok"] is True
    assert fills["trades"][0]["market"] == "KXMLBGAME-TEST"


def test_rollup_does_not_add_demo_to_live():
    from roller.jump.dashboard.rollup import rollup_tracks

    body = rollup_tracks(
        [
            {
                "kind": "grandfathered",
                "environment": "PRODUCTION",
                "actual": {"day_pnl": {"value": 55, "status": "CONFIRMED"}, "bankroll": {"value": 5000, "status": "CONFIRMED"}},
                "expected": {},
            },
            {
                "kind": "iti",
                "environment": "DEMO",
                "actual": {"day_pnl": {"value": 100, "status": "CONFIRMED"}, "bankroll": {"value": 5000, "status": "CONFIRMED"}},
                "expected": {},
            },
        ]
    )
    assert body["live"]["actual"]["day_pnl"]["value"] == 55
    assert body["demo"]["actual"]["day_pnl"]["value"] == 100
    assert body["actual"]["day_pnl"]["value"] == 55
    assert body["honesty"]["demo_not_added_to_live"] is True


def _write_catalog(tmp_path: Path, rows: list[dict]) -> None:
    catalog = tmp_path / "catalog"
    catalog.mkdir(parents=True, exist_ok=True)
    (catalog / "origin.json").write_text(
        json.dumps({"bot_one_first_fill_ts": "2026-08-24T23:18:58Z", "source": "test"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (catalog / "trades.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_fill_result_sum_is_not_origin_pnl(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _write_catalog(
        tmp_path,
        [
            {
                "jump_trade_id": "origin-win",
                "bot_id": BOT_ONE_ID,
                "environment": "PRODUCTION",
                "exchange_ts": "2026-08-25T02:57:07Z",
                "result": 100,
            },
            {
                "jump_trade_id": "full-premium-loss",
                "bot_id": BOT_ONE_ID,
                "environment": "PRODUCTION",
                "exchange_ts": "2026-09-10T18:00:00Z",
                "result": -26235,
            },
        ],
    )
    frozen = datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc)
    body = handle_dashboard(root=tmp_path / "bots", now=frozen)
    one = body["tracks"][0]
    assert one["actual"]["trades"] == {"value": 2, "status": "CONFIRMED"}
    assert one["activity"]["value"] == "HAS_FILLS"
    assert one["track_amount"] == {"value": 5000, "status": "CONFIRMED"}
    assert one["actual"]["origin_pnl"]["value"] is None
    assert one["actual"]["pnl"]["value"] is None
    assert body["header"]["origin_pnl"]["value"] is None
    assert body["header"]["origin_pnl"]["status"] == "OBSERVATION_UNAVAILABLE"
    dumped = json.dumps(body["header"]) + json.dumps(one["actual"])
    assert "-26235" not in dumped
    assert "26235" not in dumped


def test_origin_pnl_is_bankroll_minus_factory(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _write_catalog(
        tmp_path,
        [
            {
                "jump_trade_id": "origin-win",
                "bot_id": BOT_ONE_ID,
                "environment": "PRODUCTION",
                "exchange_ts": "2026-08-25T02:57:07Z",
                "result": -26235,
            }
        ],
    )
    (tmp_path / "catalog" / "bankroll.json").write_text(
        json.dumps(
            {
                "origin_bankroll_cents": 5000,
                "origin_source": "mlb_factory_v1",
                "books": {
                    "PRODUCTION": {"current_cents": 3500, "origin_cents": 5000, "source": "kalshi_get_balance"},
                    "DEMO": {"current_cents": 4800, "origin_cents": 5000, "source": "kalshi_get_balance"},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    frozen = datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc)
    body = handle_dashboard(root=tmp_path / "bots", now=frozen)
    one = body["tracks"][0]
    assert one["actual"]["origin_pnl"] == {"value": -1500, "status": "CONFIRMED"}
    assert one["actual"]["pnl"] == {"value": -1500, "status": "CONFIRMED"}
    assert one["actual"]["bankroll"] == {"value": 3500, "status": "CONFIRMED"}
    assert body["header"]["origin_pnl"] == {"value": -1500, "status": "CONFIRMED"}
    assert body["header"]["bankroll"] == {"value": 3500, "status": "CONFIRMED"}
    assert body["rollup"]["actual"]["pnl"]["value"] == -1500
    assert body["rollup"]["actual"]["origin_pnl"]["value"] == -1500
    assert body["honesty"]["fill_result_sum_is_not_account_pnl"] is True


def test_kalshi_history_confirms_day_week_not_fill_sum(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _write_catalog(
        tmp_path,
        [
            {
                "jump_trade_id": "origin-win",
                "bot_id": BOT_ONE_ID,
                "environment": "PRODUCTION",
                "exchange_ts": "2026-08-25T02:57:07Z",
                "result": -500,
            }
        ],
    )
    (tmp_path / "catalog" / "bankroll.json").write_text(
        json.dumps(
            {
                "origin_bankroll_cents": 5000,
                "books": {"PRODUCTION": {"current_cents": 2533, "origin_cents": 5000}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "catalog" / "bankroll_history.jsonl").write_text(
        json.dumps({"environment": "PRODUCTION", "observed_at": "2026-09-06T12:00:00Z", "current_cents": 4000})
        + "\n"
        + json.dumps({"environment": "PRODUCTION", "observed_at": "2026-09-12T20:00:00Z", "current_cents": 2600})
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "catalog" / "kalshi_book.json").write_text(
        json.dumps(
            {
                "books": {
                    "PRODUCTION": {
                        "observed_at": "2026-09-13T15:00:00Z",
                        "source": "kalshi_book",
                        "positions": [{"ticker": "KXMLBGAME-X", "exchange_index": 3, "open": True}],
                    }
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    frozen = datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc)
    body = handle_dashboard(root=tmp_path / "bots", now=frozen)
    assert body["header"]["origin_pnl"] == {"value": -2467, "status": "CONFIRMED"}
    assert body["header"]["day_pnl"] == {"value": -67, "status": "CONFIRMED"}
    assert body["header"]["week_pnl"] == {"value": -1467, "status": "CONFIRMED"}
    assert body["header"]["day_sharpe"]["value"] is None
    assert body["tracks"][0]["actual"]["positions"] == {"value": 1, "status": "CONFIRMED"}


def test_unread_empty_catalog_stays_unavailable(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    body = handle_dashboard(root=tmp_path / "bots")
    assert body["tracks"][0]["actual"]["pnl"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["tracks"][0]["actual"]["pnl"]["value"] is None
    assert body["header"]["origin_pnl"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["header"]["origin_pnl"]["value"] is None
    assert "$0" not in json.dumps(body["header"])


def test_dashboard_read_does_not_hit_ssm(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _write_catalog(
        tmp_path,
        [
            {
                "jump_trade_id": "origin-win",
                "bot_id": BOT_ONE_ID,
                "environment": "PRODUCTION",
                "exchange_ts": "2026-08-25T02:57:07Z",
                "result": 100,
            }
        ],
    )
    monkeypatch.setenv("JUMP_BOT_ONE_HOST_FETCH", "ssm")

    def _boom(*_args, **_kwargs):
        raise AssertionError("dashboard GET must not SSM")

    monkeypatch.setattr("roller.jump.dashboard.host_state.fetch_ssm_ledger", _boom)
    monkeypatch.setattr("roller.jump.bots.demo_host.fetch_ssm_demo_ledger", _boom)
    monkeypatch.setattr("roller.jump.bots.demo_host.observe_demo_unit", _boom)
    monkeypatch.setattr("roller.jump.catalog.kalshi.fetch_connection", _boom)
    frozen = datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc)
    body = handle_dashboard(root=tmp_path / "bots", now=frozen)
    assert body["tracks"][0]["actual"]["origin_pnl"]["value"] is None
    assert body["tracks"][0]["activity"]["value"] == "HAS_FILLS"
    assert body["header"]["day_sharpe"] == {"value": None, "status": "UNAVAILABLE"}
    assert body["header"]["week_sharpe"] == {"value": None, "status": "UNAVAILABLE"}


def test_bot_one_lifecycle_stays_running_not_production(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("VITAL_AWS_INSPECT_FIXTURE", str(_vital_running(tmp_path, bankroll_cents=5000)))
    body = handle_dashboard(root=tmp_path / "bots")
    one = body["tracks"][0]
    assert one["bot_status"] == "RUNNING"
    assert one["vital_bot_id"] == "mlb-001"
    assert one["observation"]["source"] == "vital"
    assert one["activity"]["value"] == "ACTIVE"


def test_demo_sports_shard_is_not_top_level(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    (tmp_path / "catalog").mkdir(parents=True, exist_ok=True)
    (tmp_path / "catalog" / "bankroll.json").write_text(
        json.dumps(
            {
                "origin_bankroll_cents": 5000,
                "books": {
                    "PRODUCTION": {
                        "current_cents": 1512,
                        "top_level_cents": 3931,
                        "origin_cents": 5000,
                        "exchange_index": 3,
                        "source": "kalshi_balance_breakdown",
                    },
                    "DEMO": {
                        "current_cents": 2000,
                        "top_level_cents": 2000,
                        "mlb_shard_cents": 0,
                        "exchange_index": 3,
                        "origin_cents": 2000,
                        "source": "kalshi_get_balance",
                        "balance_breakdown": [
                            {"exchange_index": 0, "balance": 20},
                            {"exchange_index": 3, "balance": 0},
                        ],
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    body = handle_dashboard(root=tmp_path / "bots")
    demo = body["header"]["books"]["DEMO"]
    assert demo["top_level_cents"] == {"value": 2000, "status": "CONFIRMED"}
    assert demo["sports_shard_cents"] == {"value": 0, "status": "CONFIRMED"}
    assert body["header"]["books"]["PRODUCTION"]["sports_shard_cents"] == {"value": 1512, "status": "CONFIRMED"}
    assert body["header"]["bankroll"] == {"value": 1512, "status": "CONFIRMED"}
    dumped = json.dumps(demo)
    assert demo["sports_shard_cents"]["value"] != demo["top_level_cents"]["value"]
    assert "2000" in dumped
