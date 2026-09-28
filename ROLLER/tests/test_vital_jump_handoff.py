"""Jump create registers a Vital mlb-00N bot and attaches DEMO autonomously."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from roller.jump.bots.pipeline import create_bot
from roller.jump.bots.versions import LIVE_CONFIRMATION
from roller.jump.errors import JumpError
from roller.vital.activate import handle_activate
from roller.vital.api import handle_bots_list
from roller.vital.bankroll import handle_bankroll
from roller.vital.errors import VitalError
from roller.vital.naming import next_mlb_bot_id, next_sport_bot_id
from roller.vital.store import load_bot, metadata_path
from roller.vital.versions import BOT_ID, DEMO_ACTIVATION_CONFIRMATION


def _write_iti(phase_b: Path, *, name: str = "Src", **extra) -> str:
    folder = phase_b / name / f"{name}_ITI"
    folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "artifact": "jump_iti",
        "iti_version": "jump_a_iti_v1.0.0",
        "run_id": "run-test",
        "slot_id": "ITI-12",
        "strategy_name": f"{name}_ITI",
        "entry_cents": 65,
        "win_cents": 97,
        "loss_cents": 40,
        "BASE_GRADE": "D",
        "DEBASE_GRADE": "F",
        "source_folder": extra.get("source_folder") or "MLB",
        "question": extra.get("question")
        or {
            "universe": {"sports": ["MLB"], "leagues": ["MLB"], "seasons": ["2025-2026"]},
            "terminal": "BOTH",
        },
    }
    meta.update(extra)
    (folder / "metadata.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return f"{name}/{name}_ITI"


def _isolate(monkeypatch, tmp_path: Path) -> Path:
    phase_b = tmp_path / "phase_b"
    phase_b.mkdir()
    monkeypatch.setenv("JUMP_BOTS_ROOT", str(tmp_path / "bots"))
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path / "vital"))
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    monkeypatch.delenv("JUMP_BOT_DEMO_READY", raising=False)
    monkeypatch.delenv("JUMP_BOT_DEMO_SSM", raising=False)
    monkeypatch.delenv("JUMP_BOT_ONE_HOST_FETCH", raising=False)
    monkeypatch.delenv("VITAL_AWS_CONTROL", raising=False)
    monkeypatch.setattr("roller.jump.bots.source_iti._phase_b_root", lambda cfg=None: phase_b)
    monkeypatch.setattr(
        "roller.jump.bots.demo_host.start_iti_demo_unit",
        lambda bot: {
            "ok": False,
            "active": False,
            "secret_missing": True,
            "unit_started": False,
            "aws_runtime_id": None,
            "reason": "demo secret not present on host",
        },
    )
    monkeypatch.setattr(
        "roller.jump.bots.demo_host.start_demo_unit",
        lambda bot: (_ for _ in ()).throw(AssertionError("factory start_demo_unit must not run for ITI")),
    )
    monkeypatch.setattr(
        "roller.jump.bots.deploy.create_demo_runtime",
        lambda bot: (_ for _ in ()).throw(AssertionError("factory create_demo_runtime must not run for ITI")),
    )
    monkeypatch.setattr(
        "roller.jump.bots.live_host.start_iti_live_unit",
        lambda bot: {
            "ok": False,
            "active": False,
            "secret_missing": True,
            "unit_started": False,
            "aws_runtime_id": None,
            "reason": "production secret not present on host",
        },
    )
    return phase_b


def test_next_mlb_bot_id_skips_001():
    assert next_mlb_bot_id([]) == "mlb-002"
    assert next_mlb_bot_id(["mlb-001"]) == "mlb-002"
    assert next_mlb_bot_id(["mlb-001", "mlb-002"]) == "mlb-003"
    assert next_mlb_bot_id(["mlb-001", "not-a-bot"]) == "mlb-002"
    assert next_sport_bot_id("nba", []) == "nba-001"
    assert next_sport_bot_id("atp", ["atp-001"]) == "atp-002"
    assert next_sport_bot_id("wta", []) == "wta-001"


def test_create_registers_vital_demo_unit(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    created = create_bot(
        {
            "name": "Handoff",
            "iti_folder": folder,
            "desired_environment": "DEMO",
            "settings": {
                "sizing_mode": "FIXED_CENTS",
                "amount_cents": 100,
                "max_daily_entries": 3,
            },
        },
        root=tmp_path / "bots",
    )
    assert created["environment"] == "DEMO"
    assert created["desired_environment"] == "DEMO"
    assert created["activation"] == "DEPLOY_REQUIRED"
    assert created["deploy_status"] == "DEPLOY_REQUIRED"
    assert created["status"] not in {"RUNNING", "RUNNING_DEMO"}
    assert created.get("aws_runtime_id") in {None, ""}
    assert created["attach"]["unit_started"] is False
    assert created["attach"]["kalshi_demo"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert created["attach"]["aws"]["factory_toml_refused"] is True
    assert created["vital_bot_id"] == "mlb-002"
    with pytest.raises(JumpError) as live:
        create_bot(
            {"name": "Live token", "iti_folder": folder, "confirmation": LIVE_CONFIRMATION},
            root=tmp_path / "bots",
        )
    assert live.value.code == "REJECTED"
    vital = load_bot("mlb-002", root=tmp_path / "vital")
    assert vital["jump_bot_id"] == created["bot_id"]
    assert vital["kind"] == "iti"
    assert vital["activation"] == "DEPLOY_REQUIRED"
    assert vital["attach"]["unit_started"] is False
    assert (tmp_path / "vital" / "bots" / "mlb-002" / "source" / "attach.json").is_file()
    assert vital["sport"] == "mlb"
    assert vital["engine"]["kind"] == "research_iti"
    assert vital["engine"]["prices"]["entry_cents"] == 65
    assert vital["engine"]["implementation"]["not_mlb_factory"] is True
    assert vital["engine_pointer"] == "research_iti"
    assert (tmp_path / "vital" / "bots" / "mlb-002" / "source" / "engine.json").is_file()
    assert vital["settings"]["amount_cents"] == 100
    listed = handle_bots_list(root=tmp_path / "vital")
    ids = [row["bot_id"] for row in listed["bots"]]
    assert BOT_ID in ids
    assert "mlb-002" in ids
    book = handle_bankroll(root=tmp_path / "vital")
    bot_ids = [row["bot_id"] for row in book["bots"]]
    assert "mlb-002" in bot_ids
    assert created["bot_id"] not in bot_ids
    demo = next(row for row in book["bots"] if row["bot_id"] == "mlb-002")
    assert demo["environment"] == "DEMO"
    assert demo["allocation"]["desired"]["value"]["unit_cents"] == 100
    assert demo["allocation"]["observed"]["status"] == "CONFIRMED"
    assert demo["allocation"]["observed"]["value"]["unit_cents"] == 100


def test_activate_gates(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    demo = create_bot({"name": "Demo", "iti_folder": folder, "desired_environment": "DEMO"}, root=tmp_path / "bots")
    prod = create_bot(
        {"name": "Prod desired", "iti_folder": folder, "desired_environment": "PRODUCTION"},
        root=tmp_path / "bots",
    )
    assert prod["environment"] == "DEMO"
    assert prod["desired_environment"] == "PRODUCTION"
    retried = handle_activate(demo["vital_bot_id"], {}, root=tmp_path / "vital")
    assert retried["activation"] == "DEPLOY_REQUIRED"
    assert retried["status"] != "RUNNING"
    with pytest.raises(VitalError) as live:
        handle_activate(demo["vital_bot_id"], {"confirmation": LIVE_CONFIRMATION}, root=tmp_path / "vital")
    assert live.value.code == "REJECTED"
    with pytest.raises(VitalError) as one:
        handle_activate(BOT_ID, {"confirmation": DEMO_ACTIVATION_CONFIRMATION}, root=tmp_path / "vital")
    assert one.value.code == "REJECTED"
    promoted = handle_activate(
        prod["vital_bot_id"],
        {"confirmation": DEMO_ACTIVATION_CONFIRMATION},
        root=tmp_path / "vital",
    )
    assert promoted["activation"] == "PROMOTE_REQUIRED"
    implemented = handle_activate(
        demo["vital_bot_id"],
        {"confirmation": DEMO_ACTIVATION_CONFIRMATION},
        root=tmp_path / "vital",
    )
    assert implemented["activation"] == "DEPLOY_REQUIRED"
    assert implemented["http_200_not_running"] is True
    assert implemented["status"] != "RUNNING"
    assert implemented["attach"]["unit_started"] is False


def test_activate_implements_engine_without_mlb_binary(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    created = create_bot({"name": "Hosted", "iti_folder": folder}, root=tmp_path / "bots")
    called = {}

    def _runtime(bot):
        called["bot_id"] = bot["bot_id"]
        return {
            "aws_runtime_id": f"momento-demo@{bot['bot_id']}.service",
            "environment": "DEMO",
            "status": "CREATED",
            "active": False,
        }

    monkeypatch.setattr("roller.jump.bots.deploy.create_demo_runtime", _runtime)
    started = handle_activate(
        created["vital_bot_id"],
        {"confirmation": DEMO_ACTIVATION_CONFIRMATION},
        root=tmp_path / "vital",
    )
    assert called == {}
    assert started["activation"] == "DEPLOY_REQUIRED"
    assert started["status"] != "RUNNING"
    assert started["engine"]["implementation"]["worker"] == "OPERATION_REQUIRED"
    assert started.get("aws_runtime_id") in {None, ""}
    assert metadata_path("mlb-001", root=tmp_path / "vital").is_file()


def test_backfill_existing_jump_demo_once(monkeypatch, tmp_path):
    from roller.jump.bots.store import create_draft, load_bot as jump_load
    from roller.jump.bots.store import save_bot as jump_save
    from roller.vital.register import backfill_jump_demo_bots

    _isolate(monkeypatch, tmp_path)
    first = create_draft(
        name="Existing one",
        iti={
            "folder": "a/a_ITI",
            "source_folder": "MLB",
            "strategy_name": "a_ITI",
            "strategy_fingerprint": "a" * 64,
            "entry_cents": 65,
            "win_cents": 85,
            "loss_cents": 40,
            "question": {"universe": {"sports": ["MLB"], "leagues": ["MLB"]}, "terminal": "BOTH"},
        },
        root=tmp_path / "bots",
    )
    second = create_draft(
        name="Existing two",
        iti={
            "folder": "b/b_ITI",
            "source_folder": "MLB",
            "strategy_name": "b_ITI",
            "strategy_fingerprint": "b" * 64,
            "entry_cents": 65,
            "win_cents": 85,
            "loss_cents": 40,
            "question": {"universe": {"sports": ["MLB"], "leagues": ["MLB"]}, "terminal": "BOTH"},
        },
        root=tmp_path / "bots",
    )
    for row in (first, second):
        bot = jump_load(row["bot_id"], root=tmp_path / "bots")
        bot["status"] = "CREATED"
        jump_save(bot, root=tmp_path / "bots")
    filled = backfill_jump_demo_bots(vital_root=tmp_path / "vital", jump_root=tmp_path / "bots")
    ids = {row["bot_id"] for row in filled}
    assert ids == {"mlb-002", "mlb-003"}
    again = backfill_jump_demo_bots(vital_root=tmp_path / "vital", jump_root=tmp_path / "bots")
    assert {row["bot_id"] for row in again} == ids
    listed = handle_bots_list(root=tmp_path / "vital")
    assert {row["bot_id"] for row in listed["bots"] if row["bot_id"] != BOT_ID} == ids
    mapped = {
        jump_load(first["bot_id"], root=tmp_path / "bots")["vital_bot_id"],
        jump_load(second["bot_id"], root=tmp_path / "bots")["vital_bot_id"],
    }
    assert mapped == ids
    one = load_bot(BOT_ID, root=tmp_path / "vital")
    assert one["kind"] == "grandfathered"
    assert one.get("jump_bot_id") in {None, ""}


def test_create_registers_atp_research_engine(monkeypatch, tmp_path):
    from roller.vital.api import handle_plane, handle_strategy, handle_worker

    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(
        phase_b,
        name="ATP CROSS 65",
        source_folder="ATP",
        question={
            "universe": {"sports": ["ATP"], "leagues": ["ATP"], "seasons": ["2025-2026"]},
            "terminal": "BOTH",
        },
    )
    created = create_bot({"name": "ATP engine", "iti_folder": folder}, root=tmp_path / "bots")
    assert created["vital_bot_id"] == "atp-001"
    assert created["engine"]["sport"] == "atp"
    assert created["factory"] is None
    vital = load_bot("atp-001", root=tmp_path / "vital")
    assert vital["sport"] == "atp"
    assert vital["engine"]["prices"]["entry_cents"] == 65
    view = handle_strategy("atp-001", root=tmp_path / "vital")
    assert view["not_mlb_factory"] is True
    assert view["not_80_81"] is True
    assert view["prices"]["win_cents"] == 97
    assert view["implementation"]["worker"] in {"OPERATION_REQUIRED", "momento-demo@atp-001.service"}
    plane = handle_plane("atp-001", root=tmp_path / "vital")
    assert plane["bot_id"] == "atp-001"
    assert plane["factory"] is None
    assert plane["engine_pointer"] == "research_iti"
    worker = handle_worker("atp-001", root=tmp_path / "vital")
    assert worker["kind"] == "research_iti"
    assert worker["submitter"] is None
    assert worker["implementation"]["worker"] == "OPERATION_REQUIRED"


def test_existing_factory_stamp_gets_research_engine(monkeypatch, tmp_path):
    from roller.jump.bots.store import load_bot as jump_load
    from roller.jump.bots.store import save_bot as jump_save
    from roller.vital.register import register_iti_bot
    from roller.vital.store import save_bot

    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    created = create_bot({"name": "Old stamp", "iti_folder": folder}, root=tmp_path / "bots")
    vital_id = created["vital_bot_id"]
    jump = jump_load(created["bot_id"], root=tmp_path / "bots")
    jump["factory_id"] = "mlb_factory_v1"
    jump["factory_version"] = "mlb_factory_v1.0.0"
    jump.pop("engine", None)
    jump["engine_pointer"] = "apps/trading-engine"
    jump["strategy_pointer"] = "strategies/mlb"
    jump_save(jump, root=tmp_path / "bots")
    vital = load_bot(vital_id, root=tmp_path / "vital")
    vital.pop("engine", None)
    vital["engine_pointer"] = "apps/trading-engine"
    vital["strategy_pointer"] = "strategies/mlb"
    save_bot(vital, root=tmp_path / "vital")
    again = register_iti_bot(
        jump_load(created["bot_id"], root=tmp_path / "bots"),
        vital_root=tmp_path / "vital",
        jump_root=tmp_path / "bots",
    )
    assert again["bot_id"] == vital_id
    assert again["engine"]["kind"] == "research_iti"
    assert again["engine_pointer"] == "research_iti"
    assert again["strategy_pointer"] != "strategies/mlb"
    assert (tmp_path / "vital" / "bots" / vital_id / "source" / "engine.json").is_file()
    jump2 = jump_load(created["bot_id"], root=tmp_path / "bots")
    assert jump2.get("factory_id") in {None, ""}
    assert jump2["engine"]["kind"] == "research_iti"


def test_iti_toml_is_not_factory_80_83():
    from roller.jump.bots.demo_host import iti_demo_toml, demo_toml

    bot = {
        "bot_id": "mlb-002",
        "sport": "mlb",
        "engine": {"sport": "mlb", "prices": {"entry_cents": 20, "win_cents": 60, "loss_cents": 10}},
        "settings": {"sizing_mode": "FIXED_CENTS", "amount_cents": 100, "bankroll_cents": 5000, "allocation_bps": 1250},
    }
    text = iti_demo_toml(bot)
    assert 'mode = "demo"' in text
    assert 'strategy_profile = "research_iti"' in text
    assert "iti_entry_cents = 20" in text
    assert "iti_win_cents = 60" in text
    assert "iti_loss_cents = 10" in text
    assert "max_entry_price_cents = 59" in text
    assert "min_entry_price_cents = 20" in text
    assert "max_entry_price_cents = 83" not in text
    assert "preferred_entry_price_cents = 80" not in text
    factory = demo_toml({"settings": {}})
    assert 'mode = "paper"' in factory
    assert "max_entry_price_cents = 83" in factory


def test_create_starts_iti_unit_when_ssm_active(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    started = {"n": 0, "factory": 0}

    def _iti(bot):
        started["n"] += 1
        unit = f"momento-demo@{bot['bot_id']}.service"
        return {
            "ok": True,
            "active": True,
            "unit_started": True,
            "aws_runtime_id": unit,
            "unit": unit,
            "state_dir": f"/var/lib/momento/demo/{bot['bot_id']}/state",
        }

    def _factory(bot):
        started["factory"] += 1
        return {"ok": True, "active": True}

    monkeypatch.setattr("roller.jump.bots.demo_host.start_iti_demo_unit", _iti)
    monkeypatch.setattr("roller.jump.bots.demo_host.start_demo_unit", _factory)
    monkeypatch.setattr(
        "roller.vital.demo_attach._observe_demo_book",
        lambda: {
            "status": "CONFIRMED",
            "ok": True,
            "read_only": True,
            "submits": False,
            "environment": "DEMO",
            "balance_cents": 5000,
            "fill_n": 2,
            "position_n": 0,
            "detail": None,
            "http_200_not_running": True,
        },
    )
    monkeypatch.setattr(
        "roller.vital.demo_attach.inspect_aws_demo",
        lambda: {
            "status": "CONFIRMED",
            "session": "CONFIRMED",
            "demo_secret": "CONFIRMED",
            "unit_started": False,
            "factory_toml_refused": True,
            "momento_live_untouched": True,
            "region": "us-east-1",
            "detail": None,
        },
    )
    created = create_bot({"name": "Live attach", "iti_folder": folder}, root=tmp_path / "bots")
    assert started["n"] == 1
    assert started["factory"] == 0
    assert created["activation"] == "RUNNING_DEMO"
    assert created["deploy_status"] == "RUNNING_DEMO"
    assert created["status"] == "RUNNING_DEMO"
    assert created["status"] != "RUNNING"
    assert created["aws_runtime_id"] == "momento-demo@mlb-002.service"
    assert created["attach"]["kalshi_demo"]["balance_cents"] == 5000
    assert created["attach"]["aws"]["session"] == "CONFIRMED"
    assert created["attach"]["unit_started"] is True
    vital = load_bot("mlb-002", root=tmp_path / "vital")
    assert vital["activation"] == "RUNNING_DEMO"
    assert vital["engine"]["implementation"]["worker"] == "momento-demo@mlb-002.service"
    assert vital["engine"]["implementation"]["submit"] is False
    from roller.vital.bots import ensure_mlb_001

    one = ensure_mlb_001(root=tmp_path / "vital")
    assert one["kind"] == "grandfathered"
    assert one.get("aws_runtime_id") != created["aws_runtime_id"]


def test_missing_secret_is_not_running(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    created = create_bot({"name": "No secret", "iti_folder": folder}, root=tmp_path / "bots")
    assert created["activation"] == "DEPLOY_REQUIRED"
    assert created["status"] != "RUNNING_DEMO"
    assert created.get("aws_runtime_id") in {None, ""}
    assert created["attach"]["unit_started"] is False
    from roller.vital.bots import ensure_mlb_001

    one = ensure_mlb_001(root=tmp_path / "vital")
    assert one["bot_id"] == BOT_ID
    assert one.get("activation") != created["activation"] or one["kind"] == "grandfathered"


def test_iti_ledger_reads_unit_runtime_only(monkeypatch, tmp_path):
    from roller.vital.reconcile import execution_view

    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    created = create_bot({"name": "Ledger", "iti_folder": folder}, root=tmp_path / "bots")
    unit_root = tmp_path / "demo-state"
    monkeypatch.setenv("JUMP_BOT_DEMO_STATE_ROOT", str(unit_root))
    (unit_root / "mlb-002" / "state").mkdir(parents=True)
    (unit_root / "mlb-002" / "state" / "live-runtime.json").write_text("{}", encoding="utf-8")
    view = execution_view(created["vital_bot_id"], root=tmp_path / "vital")
    assert view["status"] == "OBSERVATION_UNAVAILABLE"
    assert view["trades_status"] == "OBSERVATION_UNAVAILABLE"
    assert view["trades"] is None
    assert view["kalshi"].get("fill_n") is None
    assert view["kalshi"].get("source") == "isolated_unit"
    assert "$0" not in str(view.get("detail") or "")


def test_iti_strategy_frame_matches_committed_prices(monkeypatch, tmp_path):
    from roller.vital.api import handle_strategy

    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    created = create_bot({"name": "Frame", "iti_folder": folder}, root=tmp_path / "bots")
    view = handle_strategy(created["vital_bot_id"], root=tmp_path / "vital")
    assert view["kind"] == "research_iti"
    assert view["prices"]["entry_cents"] == 65
    assert view["prices"]["win_cents"] == 97
    assert view["prices"]["loss_cents"] == 40
    assert view["entry_rules"]["kind"] == "FIRST_TOUCH"
    assert view["exit_rules"]["kind"] == "REACH"
    assert view["exit_rules"]["not_89_lock"] is True
    assert view["spec_status"] == "CONFIRMED"
    assert view["candle_path_not_fill"] is True
    assert "80" not in str(view["entry_rules"]["entry_cents"])


def test_vital_promote_starts_isolated_live_unit(monkeypatch, tmp_path):
    from roller.vital.bots import ensure_mlb_001
    from roller.vital.api import handle_promote_post
    from roller.vital.store import load_bot as vital_load

    phase_b = _isolate(monkeypatch, tmp_path)
    ensure_mlb_001(root=tmp_path / "vital")
    folder = _write_iti(phase_b)
    created = create_bot({"name": "Promote", "iti_folder": folder}, root=tmp_path / "bots")

    def _start(bot):
        ident = bot.get("vital_bot_id") or bot["bot_id"]
        assert ident == "mlb-002"
        return {
            "ok": True,
            "active": True,
            "unit_started": True,
            "aws_runtime_id": "momento-live@mlb-002.service",
            "unit": "momento-live@mlb-002.service",
        }

    monkeypatch.setattr("roller.jump.bots.live_host.start_iti_live_unit", _start)
    body = handle_promote_post(
        created["vital_bot_id"],
        {"mode": "live", "live_enabled": True, "confirmation": LIVE_CONFIRMATION},
        root=tmp_path / "vital",
    )
    assert body["http_200_not_running"] is True
    assert body["submits"] is False
    vital = vital_load("mlb-002", root=tmp_path / "vital")
    assert vital["environment"] == "PRODUCTION"
    assert vital["activation"] == "RUNNING"
    assert vital["aws_runtime_id"] == "momento-live@mlb-002.service"
    one = vital_load(BOT_ID, root=tmp_path / "vital")
    assert one["kind"] == "grandfathered"
    assert one.get("aws_runtime_id") != vital["aws_runtime_id"]


def test_vital_promote_refuses_mlb_001(monkeypatch, tmp_path):
    from roller.vital.api import handle_promote_post

    _isolate(monkeypatch, tmp_path)
    with pytest.raises(VitalError) as exc:
        handle_promote_post(
            BOT_ID,
            {"mode": "live", "live_enabled": True, "confirmation": LIVE_CONFIRMATION},
            root=tmp_path / "vital",
        )
    assert exc.value.code == "REJECTED"
