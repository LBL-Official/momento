"""Jump B — Bot Creation. Control plane only. No credentials. No order submit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roller.jump.bots.factory import FACTORY, factory_snapshot
from roller.jump.bots.pipeline import create_bot, draft_bot, get_bot, list_control_plane, promote_bot
from roller.jump.bots.source_iti import list_iti_commits, load_iti_commit
from roller.jump.bots.store import load_bot
from roller.jump.bots.versions import BOT_ONE_ID, FACTORY_ID, LIVE_CONFIRMATION
from roller.jump.errors import JumpError
from roller.jump.versions import CODE_VERSION, PHASE_STATUS

_BANNED = ("KALSHI_API_KEY", "PRIVATE_KEY", "secret_key", "api_key=")
_LIVE_GATE = {"mode": "live", "live_enabled": True, "confirmation": LIVE_CONFIRMATION}


def _write_iti(phase_b: Path, *, name: str = "Src", artifact: str = "jump_iti", **extra) -> str:
    folder = phase_b / name / f"{name}_ITI"
    folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "artifact": artifact,
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
        "created_at": "2026-09-13T00:00:00Z",
    }
    meta.update(extra)
    (folder / "metadata.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return f"{name}/{name}_ITI"


def _isolate(monkeypatch, tmp_path: Path) -> Path:
    phase_b = tmp_path / "phase_b"
    phase_b.mkdir()
    bots = tmp_path / "bots"
    monkeypatch.setenv("JUMP_BOTS_ROOT", str(bots))
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    monkeypatch.delenv("JUMP_BOT_ONE_PROBE", raising=False)
    monkeypatch.delenv("JUMP_BOT_DEMO_READY", raising=False)
    monkeypatch.delenv("JUMP_BOT_DEMO_RUNNING", raising=False)
    monkeypatch.delenv("JUMP_BOT_DEMO_SSM", raising=False)
    monkeypatch.delenv("JUMP_BOT_ONE_HOST_FETCH", raising=False)
    monkeypatch.delenv("JUMP_BOT_PROMOTE_READY", raising=False)
    monkeypatch.delenv("MOMENTO_KALSHI_ENV", raising=False)
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path / "vital"))
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    monkeypatch.delenv("VITAL_AWS_INSPECT_FIXTURE", raising=False)
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


def test_health_b_and_c_implemented():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    jump = client.get("/jump/health").json()
    assert jump["phases"] == {"A": "MOVED_TO_SUPERASI", "B": "IMPLEMENTED", "C": "IMPLEMENTED"}
    assert jump["code_version"] == CODE_VERSION
    assert PHASE_STATUS["B"] == "IMPLEMENTED"
    assert PHASE_STATUS["C"] == "IMPLEMENTED"
    assert jump["live_execution"] is False
    caps = client.get("/health").json()["capabilities"]
    assert "jump_bots" in caps


def test_factory_snapshot_matches_live_desk():
    snap = factory_snapshot()
    assert snap["factory_id"] == FACTORY_ID
    assert snap["bankroll_cents"] == 5000
    assert snap["allocation_bps"] == 1250
    assert snap["per_game_cents"] == 625
    assert snap["max_open_mlb_positions"] == 5
    assert snap["min_entry_cents"] == 80
    assert snap["max_entry_cents"] == 83
    assert snap["confirm_cents"] == 81
    assert snap["lock_cents"] == 89
    assert snap["editable"] is False
    assert FACTORY["signal"] == "80_to_81_yes_bid"


def test_no_credentials_in_jump_bots():
    root = Path(__file__).resolve().parents[1] / "roller" / "jump" / "bots"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in _BANNED:
            assert token not in text, f"{path} contains {token}"


def test_bot_one_first_and_status_unset_without_probe(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    body = list_control_plane(root=tmp_path / "bots")
    assert body["bots"][0]["bot_id"] == BOT_ONE_ID
    one = body["bots"][0]
    assert one["kind"] == "grandfathered"
    assert one["status"] == "OBSERVATION_UNAVAILABLE"
    assert one["environment"] is None
    assert one["live_armed_confirmed"] is False
    assert one["factory"]["max_entry_cents"] == 83


def test_bot_one_probe_does_not_invent_running(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv(
        "JUMP_BOT_ONE_PROBE",
        json.dumps({"status": "RUNNING", "environment": "PRODUCTION", "live_armed_confirmed": False}),
    )
    one = get_bot(BOT_ONE_ID, root=tmp_path / "bots")
    assert one["status"] == "OBSERVATION_UNAVAILABLE"
    assert one["live_armed_confirmed"] is False


def test_missing_iti_folder_is_data_required(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    with pytest.raises(JumpError) as exc:
        draft_bot({"iti_folder": "missing/missing_ITI"}, root=tmp_path / "bots")
    assert exc.value.code == "DATA_REQUIRED"


def test_non_iti_artifact_is_data_required(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b, artifact="phase_b")
    with pytest.raises(JumpError) as exc:
        load_iti_commit(folder)
    assert exc.value.code == "DATA_REQUIRED"


def test_create_always_demo_and_not_running_without_host(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    created = create_bot(
        {"name": "Demo bot", "iti_folder": folder, "environment": "PRODUCTION"},
        root=tmp_path / "bots",
    )
    assert created["environment"] == "DEMO"
    assert created["desired_environment"] == "PRODUCTION"
    assert created["status"] == "CREATED"
    assert created["live_armed_confirmed"] is False
    assert created["activation"] == "DEPLOY_REQUIRED"
    assert created["deploy_status"] == "DEPLOY_REQUIRED"
    assert created["vital_bot_id"] == "mlb-002"
    assert created["status"] != "RUNNING"
    assert created.get("aws_runtime_id") in {None, ""}
    assert created["attach"]["unit_started"] is False
    assert created["strategy_fingerprint"]
    assert created["factory"] is None
    assert created["engine"]["kind"] == "research_iti"
    assert created["engine"]["sport"] == "mlb"
    assert created["engine"]["implementation"]["not_80_81"] is True


def test_create_demo_ready_still_not_assumed_running(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    monkeypatch.setenv("JUMP_BOT_DEMO_READY", "1")
    created = create_bot({"name": "Demo bot", "iti_folder": folder}, root=tmp_path / "bots")
    assert created["environment"] == "DEMO"
    assert created["status"] == "CREATED"
    assert created["activation"] == "DEPLOY_REQUIRED"
    assert created.get("aws_runtime_id") in {None, ""}
    assert created.get("deploy_status") != "RUNNING"


def test_later_iti_save_does_not_mutate_bot(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    draft = draft_bot({"name": "Frozen", "iti_folder": folder}, root=tmp_path / "bots")
    fingerprint = draft["strategy_fingerprint"]
    _write_iti(phase_b, run_id="run-later", slot_id="ITI-00")
    bot = load_bot(draft["bot_id"], root=tmp_path / "bots")
    assert bot["strategy_fingerprint"] == fingerprint
    assert bot["slot_id"] == "ITI-12"


def test_production_without_confirmation_rejected(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    monkeypatch.setenv("JUMP_BOT_DEMO_READY", "1")
    created = create_bot({"name": "Demo bot", "iti_folder": folder}, root=tmp_path / "bots")
    with pytest.raises(JumpError) as exc:
        promote_bot(created["bot_id"], {"mode": "live", "live_enabled": True}, root=tmp_path / "bots")
    assert exc.value.code == "LIVE_GATE_INCOMPLETE"
    bot = get_bot(created["bot_id"], root=tmp_path / "bots")
    assert bot["environment"] == "DEMO"


def test_second_live_factory_rejected_while_bot_one_live(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    monkeypatch.setenv("JUMP_BOT_DEMO_READY", "1")
    monkeypatch.setenv("JUMP_BOT_PROMOTE_READY", "1")
    fixture = tmp_path / "vital_inspect.json"
    fixture.write_text(
        json.dumps(
            {
                "ok": True,
                "service": {"value": {"active": "active"}, "status": "CONFIRMED"},
                "heartbeat": {"value": {"live_armed_confirmed": True, "kill_switch": False}, "status": "CONFIRMED"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VITAL_AWS_INSPECT_FIXTURE", str(fixture))

    def _start(bot):
        ident = bot.get("vital_bot_id") or bot["bot_id"]
        assert ident != "mlb-001"
        return {
            "ok": True,
            "active": True,
            "unit_started": True,
            "aws_runtime_id": f"momento-live@{ident}.service",
            "unit": f"momento-live@{ident}.service",
        }

    monkeypatch.setattr("roller.jump.bots.live_host.start_iti_live_unit", _start)
    created = create_bot({"name": "Second", "iti_folder": folder}, root=tmp_path / "bots")
    promoted = promote_bot(created["bot_id"], _LIVE_GATE, root=tmp_path / "bots")
    assert promoted["environment"] == "PRODUCTION"
    assert promoted["activation"] == "RUNNING"
    assert promoted["aws_runtime_id"] == "momento-live@mlb-002.service"
    assert "momento-live.service" not in str(promoted["aws_runtime_id"])
    one = get_bot(BOT_ONE_ID, root=tmp_path / "bots")
    assert one["bot_id"] == BOT_ONE_ID
    assert one["factory"]["max_entry_cents"] == 83


def test_promote_secret_missing_stays_demo(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    created = create_bot({"name": "Secret missing", "iti_folder": folder}, root=tmp_path / "bots")
    promoted = promote_bot(created["bot_id"], _LIVE_GATE, root=tmp_path / "bots")
    assert promoted["environment"] == "DEMO"
    assert promoted["activation"] == "DEPLOY_REQUIRED"
    assert promoted.get("aws_runtime_id") in {None, ""}
    assert get_bot(BOT_ONE_ID, root=tmp_path / "bots")["bot_id"] == BOT_ONE_ID


def test_iti_live_toml_is_not_factory_80_83(monkeypatch, tmp_path):
    from roller.jump.bots.live_host import iti_live_toml
    from roller.jump.bots.store import load_bot as jump_load

    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    created = create_bot({"name": "Toml", "iti_folder": folder}, root=tmp_path / "bots")
    text = iti_live_toml(jump_load(created["bot_id"], root=tmp_path / "bots"))
    assert 'mode = "live"' in text
    assert 'strategy_profile = "research_iti"' in text
    assert "enabled = true" in text
    assert "ENABLE_LIVE_TRADING" in text
    assert "max_entry_price_cents = 83" not in text
    assert "preferred_entry_price_cents = 80" not in text
    assert "iti_entry_cents = 65" in text
    assert "iti_win_cents = 97" in text
    assert "iti_loss_cents = 40" in text


def test_promote_spec_mismatch_is_rejected(monkeypatch, tmp_path):
    from roller.jump.bots.store import load_bot as jump_load
    from roller.jump.bots.store import save_bot

    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    created = create_bot({"name": "Mismatch", "iti_folder": folder}, root=tmp_path / "bots")
    bot = jump_load(created["bot_id"], root=tmp_path / "bots")
    bot["engine"]["prices"]["entry_cents"] = 50
    bot["engine"]["prices"]["entry_e4"] = 500000
    save_bot(bot, root=tmp_path / "bots")
    with pytest.raises(JumpError) as exc:
        promote_bot(created["bot_id"], _LIVE_GATE, root=tmp_path / "bots")
    assert exc.value.code == "REJECTED"
    assert get_bot(created["bot_id"], root=tmp_path / "bots")["environment"] == "DEMO"


def test_promote_bot_one_rejected(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    with pytest.raises(JumpError) as exc:
        promote_bot(BOT_ONE_ID, _LIVE_GATE, root=tmp_path / "bots")
    assert exc.value.code == "DUPLICATE_LIVE_FACTORY"


def test_list_iti_commits_is_generic_and_skips_corrupt(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    hold = _write_iti(
        phase_b,
        name="HoldYes",
        win_cents=None,
        source_folder="NBA",
        question={"universe": {"sports": ["NBA"], "leagues": ["NBA"]}, "win_hold": True},
    )
    path = _write_iti(phase_b, name="PathOnly")
    bad = phase_b / "Broken" / "Broken_ITI"
    bad.mkdir(parents=True)
    (bad / "metadata.json").write_text("{not-json", encoding="utf-8")
    rows = list_iti_commits()
    folders = {row["folder"] for row in rows}
    assert hold in folders
    assert path in folders
    assert not any("Broken" in folder for folder in folders)
    hold_row = next(row for row in rows if row["folder"] == hold)
    assert hold_row["sport"] == "nba"
    assert hold_row["win_cents"] is None


def test_http_iti_commits_does_not_observe_host(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b, name="Src")

    def boom(*_args, **_kwargs):
        raise AssertionError("Make Bot ITI list must not observe Vital/SSM")

    monkeypatch.setattr("roller.jump.bots.pipeline.apply_observation", boom)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    commits = client.get("/jump/iti-commits").json()
    assert commits["n"] == 1
    assert commits["results"][0]["folder"] == folder
    listed = client.get("/jump/bots").json()
    assert [row["folder"] for row in listed["iti_commits"]] == [folder]


def test_http_create_demo_and_production_reject(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    listed = client.get("/jump/bots").json()
    assert listed["bots"][0]["bot_id"] == BOT_ONE_ID
    assert listed["factory"]["allocation_bps"] == 1250

    missing = client.post("/jump/bots/draft", json={"iti_folder": "nope/nope_ITI"})
    assert missing.status_code == 400
    assert missing.json()["detail"]["code"] == "DATA_REQUIRED"

    created = client.post("/jump/bots", json={"name": "HTTP demo", "iti_folder": folder}).json()
    assert created["environment"] == "DEMO"
    assert created["desired_environment"] == "DEMO"
    assert created["status"] == "CREATED"
    assert created["activation"] == "DEPLOY_REQUIRED"
    assert created["vital_bot_id"] == "mlb-002"

    live = client.post("/jump/bots", json={"name": "Live token", "iti_folder": folder, "confirmation": LIVE_CONFIRMATION})
    assert live.status_code == 400
    assert live.json()["detail"]["code"] == "REJECTED"

    rejected = client.post(f"/jump/bots/{created['bot_id']}/production", json={"mode": "live"})
    assert rejected.status_code == 400
    assert rejected.json()["detail"]["code"] == "LIVE_GATE_INCOMPLETE"

    missing_bot = client.get("/jump/bots/does-not-exist")
    assert missing_bot.status_code == 404


def test_profile_patch_and_avatar(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    created = create_bot({"name": "Named", "iti_folder": folder}, root=tmp_path / "bots")
    from roller.jump.bots.profile import update_profile

    updated = update_profile(
        created["bot_id"],
        {
            "bio": "Maker desk",
            "purpose": "ITI lineage MLB factory",
            "handle": "named.desk",
            "bankroll_cents": 5000,
            "avatar_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
            "avatar_ext": "png",
        },
        root=tmp_path / "bots",
    )
    assert updated["profile"]["bio"] == "Maker desk"
    assert updated["profile"]["purpose"] == "ITI lineage MLB factory"
    assert updated["profile"]["handle"] == "named.desk"
    assert updated["settings"]["bankroll_cents"] == 5000
    assert updated["avatar_url"]
    from roller.jump.bots.profile import read_avatar

    data, media = read_avatar(created["bot_id"], root=tmp_path / "bots")
    assert media == "image/png"
    assert data.startswith(b"\x89PNG")


def test_bot_one_bankroll_override_refused(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    from roller.jump.bots.profile import update_profile
    from roller.jump.bots.store import ensure_bot_one
    from roller.jump.errors import JumpError

    ensure_bot_one(root=tmp_path / "bots")
    with pytest.raises(JumpError) as exc:
        update_profile(BOT_ONE_ID, {"bankroll_cents": 2000000}, root=tmp_path / "bots")
    assert exc.value.code == "OPERATION_REQUIRED"


def test_demo_fetch_script_comment_does_not_block_unit():
    from roller.jump.bots.demo_host import _fetch_script, _unit_text

    fetch = _fetch_script()
    unit = _unit_text()
    assert "momento/kalshi/demo" in fetch
    assert 'SECRET_ID="${JUMP_BOT_DEMO_SECRET_ID:-momento/kalshi/demo}"' in fetch
    assert "Conflicts=momento-live" not in unit
    assert "MOMENTO_KALSHI_ENV=demo" in unit
    assert "ExecStart=/usr/local/bin/momento-trading-engine-demo" in unit
    assert "ExecStart=/usr/local/bin/momento-trading-engine\n" not in unit
    assert "momento-kalshi-demo-%i.json" in unit
    assert "MOMENTO_KALSHI_SECRET_FILE=/dev/shm/momento-kalshi-demo.json\n" not in unit
    assert "MOMENTO_KALSHI_SECRET_FILE:?demo fetch requires" in fetch
    assert "momento-kalshi-demo-*.json" in fetch


def test_mocked_ssm_create_is_running_demo(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    monkeypatch.setenv("JUMP_BOT_DEMO_SSM", "1")

    def _start(bot):
        return {
            "ok": True,
            "active": True,
            "aws_runtime_id": f"momento-demo@{bot['bot_id']}.service",
            "unit": f"momento-demo@{bot['bot_id']}.service",
            "state_dir": f"/var/lib/momento/demo/{bot['bot_id']}/state",
        }

    monkeypatch.setattr("roller.jump.bots.demo_host.start_iti_demo_unit", _start)
    monkeypatch.setattr(
        "roller.jump.bots.deploy.observe_demo_unit",
        lambda bot_id: {"active": True, "aws_runtime_id": f"momento-demo@{bot_id}.service", "reason": None},
    )
    created = create_bot({"name": "Hosted", "iti_folder": folder}, root=tmp_path / "bots")
    assert created["activation"] == "RUNNING_DEMO"
    assert created["status"] == "RUNNING_DEMO"
    assert created["aws_runtime_id"] == "momento-demo@mlb-002.service"
    from roller.vital.activate import handle_activate
    from roller.vital.versions import DEMO_ACTIVATION_CONFIRMATION

    started = handle_activate(
        created["vital_bot_id"],
        {"confirmation": DEMO_ACTIVATION_CONFIRMATION},
        root=tmp_path / "vital",
    )
    assert started["activation"] == "RUNNING_DEMO"
    assert started["environment"] == "DEMO"
    assert started["live_armed_confirmed"] is False
    assert started["aws_runtime_id"] == "momento-demo@mlb-002.service"
    assert started["engine"]["implementation"]["worker"] == "momento-demo@mlb-002.service"
    assert started["attach"]["unit_started"] is True


def test_http_profile_and_trades_unavailable(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    folder = _write_iti(phase_b)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    created = client.post("/jump/bots", json={"name": "HTTP profile", "iti_folder": folder}).json()
    patched = client.patch(
        f"/jump/bots/{created['bot_id']}/profile",
        json={"bio": "from http", "purpose": "demo identity"},
    )
    assert patched.status_code == 200
    assert patched.json()["profile"]["bio"] == "from http"
    trades = client.get(f"/jump/bots/{created['bot_id']}/trades").json()
    assert trades["status"] == "OBSERVATION_UNAVAILABLE"
    assert trades["trades"] is None
    assert trades["day_pnl"]["value"] is None
