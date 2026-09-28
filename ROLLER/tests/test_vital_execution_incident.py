"""Vital execution incident regressions. No secrets. No second engine."""

from __future__ import annotations

import json
from pathlib import Path

from roller.jump.bots.demo_host import iti_demo_toml, safe_bot_id
from roller.jump.errors import JumpError
from roller.vital.mlb_001.identity import (
    BOT_ID,
    CONFIG_POINTER,
    ENGINE_POINTER,
    HOST_BINARY,
    SERVICE_NAME,
    STRATEGY_POINTER,
    UNIT_POINTER,
)
from roller.vital.observe import observe_bot
from roller.vital.reconcile import reconcile_bot
from roller.vital.research_engine import worker_view
from roller.vital.store import seed_mlb_001

_REPO = Path(__file__).resolve().parents[2]


def _isolate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    monkeypatch.delenv("VITAL_AWS_INSPECT_FIXTURE", raising=False)
    monkeypatch.delenv("VITAL_BOT_STATE_DIR", raising=False)
    monkeypatch.delenv("VITAL_BOT_RUNTIME_PATH", raising=False)
    monkeypatch.delenv("VITAL_AWS_CONTROL", raising=False)
    seed_mlb_001(root=tmp_path)


def test_mlb_001_pointers_stay_on_existing_engine():
    assert ENGINE_POINTER == "apps/trading-engine"
    assert STRATEGY_POINTER == "strategies/mlb"
    assert CONFIG_POINTER == "config/live.toml"
    assert UNIT_POINTER == "deploy/momento-live.service"
    assert HOST_BINARY == "/usr/local/bin/momento-trading-engine"
    assert SERVICE_NAME == "momento-live.service"
    for rel in (ENGINE_POINTER, STRATEGY_POINTER, CONFIG_POINTER, UNIT_POINTER):
        assert (_REPO / rel).exists()
    boundary = json.loads((_REPO / "research/vital/bots/mlb-001/pointers/boundary.json").read_text())
    assert boundary["moved"] is False
    assert boundary["second_engine"] is False
    assert boundary["pointers"]["worker"] == ENGINE_POINTER
    assert boundary["pointers"]["strategy"] == STRATEGY_POINTER


def test_live_and_demo_units_keep_kalshi_env_apart():
    live = (_REPO / "deploy/momento-live.service").read_text(encoding="utf-8")
    demo = (_REPO / "deploy/momento-demo@.service").read_text(encoding="utf-8")
    assert "MOMENTO_KALSHI_ENV=production" in live
    assert "MOMENTO_KALSHI_ENV=demo" in demo
    assert "momento-kalshi-live.json" in live
    assert "momento-kalshi-demo-%i.json" in demo
    assert "ExecStart=/usr/local/bin/momento-trading-engine\n" in live
    assert "ExecStart=/usr/local/bin/momento-trading-engine-demo" in demo
    assert "Conflicts=momento-live" not in demo
    fetch = (_REPO / "deploy/m-demo-fetch-secret.sh").read_text(encoding="utf-8")
    assert "momento/kalshi/demo" in fetch
    assert "demo fetch refuses a production secret id" in fetch


def test_desired_running_is_not_confirmed_when_host_unread(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    view = observe_bot(BOT_ID, root=tmp_path, persist=False)
    runtime = view["runtime"]
    assert runtime["desired"]["lifecycle"] in {"OBSERVATION_UNAVAILABLE", "RUNNING"}
    assert runtime["lifecycle"] == "OBSERVATION_UNAVAILABLE"
    assert runtime["confirmed"]["lifecycle"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert runtime["http_200_not_running"] is True


def test_inspect_runtime_present_is_not_empty_fill_body(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    fixture = tmp_path / "inspect.json"
    fixture.write_text(
        json.dumps(
            {
                "ok": True,
                "source": "fixture",
                "paths": {"runtime_exists": True, "snapshot_exists": True, "kill_exists": False},
                "ledger": {"ok": True, "open_mlb_positions": 0, "kill_switch": False},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VITAL_AWS_INSPECT_FIXTURE", str(fixture))
    view = reconcile_bot(BOT_ID, root=tmp_path, persist=True)
    host = view["source"]["host"]
    assert host["status"] == "CONFIRMED"
    assert host["fill_body"] == "OBSERVATION_UNAVAILABLE"
    assert view["fills"] is None
    assert view["trades"] is None
    assert view["summary"]["total_fills"]["value"] is None
    assert view["summary"]["total_trades"]["value"] is None
    observed = json.loads(
        (tmp_path / "bots" / BOT_ID / "execution" / "observed.json").read_text(encoding="utf-8")
    )
    assert observed["host"]["status"] == "CONFIRMED"
    assert observed["host"]["fill_body"] == "OBSERVATION_UNAVAILABLE"


def test_iti_demo_toml_refuses_factory_band():
    bot = {
        "bot_id": "mlb-002",
        "sport": "nba",
        "engine": {"sport": "nba", "prices": {"entry_cents": 80, "win_cents": 84, "loss_cents": 40}},
        "iti": {"entry_cents": 80, "win_cents": 84, "loss_cents": 40},
        "settings": {"bankroll_cents": 2000, "allocation_bps": 1250},
    }
    try:
        text = iti_demo_toml(bot)
    except JumpError as exc:
        assert exc.code == "DEPLOY_REQUIRED"
        return
    assert "max_entry_price_cents = 83" not in text
    assert "preferred_entry_price_cents = 80" not in text
    assert 'strategy_profile = "research_iti"' in text
    assert 'mode = "demo"' in text


def test_demo_safe_id_refuses_mlb_001():
    try:
        safe_bot_id("mlb-001")
    except JumpError as exc:
        assert exc.code == "DEPLOY_REQUIRED"
    else:
        raise AssertionError("mlb-001 must not be a demo unit id")


def test_iti_worker_names_demo_binary_not_factory():
    bot = {
        "bot_id": "mlb-002",
        "activation": "RUNNING_DEMO",
        "aws_runtime_id": "momento-demo@mlb-002.service",
        "engine": {"engine_pointer": "research_iti", "implementation": {"worker": "momento-demo@mlb-002.service"}},
        "attach": {"unit": {"active": True, "unit": "momento-demo@mlb-002.service"}},
    }
    view = worker_view(bot)
    assert view["binary"] == "momento-trading-engine-demo"
    assert view["vital_submits"] is False
    assert view["implementation"]["submit"] is False
