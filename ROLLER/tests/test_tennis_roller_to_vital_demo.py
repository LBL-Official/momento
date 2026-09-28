"""ROLLER tennis (ATP/WTA) → ITI engine → Jump create → Vital demo bot.

Does not submit. Does not start momento-live.service. Does not convert ITI to 80/81.
Mixed tennis without a tour stays DATA_REQUIRED.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from roller.jump.bots.engine import build_research_engine, sport_slug_from_iti
from roller.jump.bots.pipeline import create_bot
from roller.jump.errors import JumpError
from roller.vital.api import handle_desk, handle_parameters, handle_strategy
from roller.vital.bankroll import handle_bankroll
from roller.vital.store import load_bot
from roller.vital.versions import BOT_ID
from roller.warehouse.frontend_contract import compile_frontend_research, execute_frontend_research, question_from_draft

ROLLER_ROOT = Path(__file__).resolve().parents[1]
ATP_WAREHOUSE = ROLLER_ROOT / "data" / "atp" / "2025_2026" / "derived" / "warehouse"
ATP_LIVE = (ATP_WAREHOUSE / "manifest.json").is_file()


def _write_iti(phase_b: Path, *, name: str, sport: str, question: dict, **extra) -> str:
    folder = phase_b / name / f"{name}_ITI"
    folder.mkdir(parents=True, exist_ok=True)
    league = sport.upper()
    meta = {
        "artifact": "jump_iti",
        "iti_version": "jump_a_iti_v1.0.0",
        "run_id": "run-tennis-pipeline",
        "slot_id": "ITI-00",
        "strategy_name": f"{name}_ITI",
        "entry_cents": extra.pop("entry_cents", 65),
        "win_cents": extra.pop("win_cents", 85),
        "loss_cents": extra.pop("loss_cents", 40),
        "BASE_GRADE": extra.pop("BASE_GRADE", "D"),
        "DEBASE_GRADE": extra.pop("DEBASE_GRADE", "F"),
        "source_folder": league,
        "question": question,
    }
    meta.update(extra)
    (folder / "metadata.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        lambda bot: (_ for _ in ()).throw(AssertionError("factory start_demo_unit must not run for tennis ITI")),
    )
    monkeypatch.setattr(
        "roller.jump.bots.deploy.create_demo_runtime",
        lambda bot: (_ for _ in ()).throw(AssertionError("factory create_demo_runtime must not run for tennis ITI")),
    )
    return phase_b


def _atp_draft() -> dict:
    return {
        "universe": {
            "sports": ["tennis"],
            "leagues": ["ATP"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
            "dateFrom": "2025-07-01",
            "dateTo": "2025-07-31",
        },
        "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 65}],
        "exitConditions": [
            {"id": "win", "kind": "path", "family": "reach", "priceCents": 85, "outcome": "win"},
            {"id": "loss", "kind": "path", "family": "reach", "priceCents": 40, "outcome": "loss"},
        ],
    }


def test_tennis_without_tour_is_data_required():
    try:
        sport_slug_from_iti({"question": {"universe": {"sports": ["tennis"], "leagues": []}}})
    except JumpError as exc:
        assert exc.code == "DATA_REQUIRED"
    else:
        raise AssertionError("mixed tennis must fail closed")


def test_mixed_tours_are_data_required():
    try:
        sport_slug_from_iti(
            {"question": {"universe": {"sports": ["tennis"], "leagues": ["ATP", "WTA"]}}}
        )
    except JumpError as exc:
        assert exc.code == "DATA_REQUIRED"
    else:
        raise AssertionError("ATP+WTA must fail closed")


def test_atp_compile_creates_vital_demo_bot(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    question, errors = question_from_draft(_atp_draft())
    assert question is not None
    assert not errors
    compiled = compile_frontend_research({"question": question.to_dict()})
    assert compiled["status"] == "READY"
    assert compiled["observation_basis"] == "TRADABLE_YES_BID"
    assert compiled["capability"].get("unavailable_sport") != "ATP"
    packed = question.to_dict()
    folder = _write_iti(phase_b, name="ATP CROSS 65 REACH 85 40", sport="atp", question=packed)
    engine = build_research_engine(
        {
            "folder": folder,
            "entry_cents": 65,
            "win_cents": 85,
            "loss_cents": 40,
            "question": packed,
        }
    )
    assert engine["sport"] == "atp"
    assert engine["implementation"]["not_80_81"] is True
    assert engine["implementation"]["submit"] is False
    created = create_bot({"name": "ATP desk", "iti_folder": folder}, root=tmp_path / "bots")
    assert created["vital_bot_id"] == "atp-001"
    assert created["engine"]["sport"] == "atp"
    assert created["factory"] is None
    vital = load_bot("atp-001", root=tmp_path / "vital")
    assert vital["sport"] == "atp"
    assert vital["environment"] == "DEMO"
    assert vital["engine"]["implementation"]["not_mlb_factory"] is True
    strategy = handle_strategy("atp-001", root=tmp_path / "vital")
    assert strategy["not_80_81"] is True
    assert strategy["prices"]["entry_cents"] == 65
    params = handle_parameters("atp-001", root=tmp_path / "vital")
    sport_row = next(row for row in params["parameters"] if row["key"] == "sport")
    assert sport_row["value"] == "atp"
    books = handle_bankroll(root=tmp_path / "vital")
    assert books["account"] is not None or books.get("honesty", {}).get("demo_not_added_to_live") is True
    desk = handle_desk("atp-001", "full", root=tmp_path / "vital")
    assert desk["selected_id"] == "atp-001"
    assert desk["focus"]["bot"]["sport"] == "atp"
    assert desk["focus"]["strategy"]["not_80_81"] is True
    factory = load_bot(BOT_ID, root=tmp_path / "vital")
    assert factory["kind"] == "grandfathered"
    assert factory.get("sport") in {None, "mlb", "MLB"} or factory.get("kind") == "grandfathered"


def test_wta_compile_creates_wta_001(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    draft = _atp_draft()
    draft["universe"]["leagues"] = ["WTA"]
    question, errors = question_from_draft(draft)
    assert question is not None
    assert not errors
    assert question.universe.leagues == ("WTA",)
    folder = _write_iti(phase_b, name="WTA CROSS 65", sport="wta", question=question.to_dict())
    created = create_bot({"name": "WTA desk", "iti_folder": folder}, root=tmp_path / "bots")
    assert created["vital_bot_id"] == "wta-001"
    assert created["engine"]["sport"] == "wta"
    desk = handle_desk("wta-001", "list", root=tmp_path / "vital")
    assert desk["selected_id"] == "wta-001"
    ids = {row["bot_id"] for row in desk["bots"]}
    assert BOT_ID in ids
    assert "wta-001" in ids


@pytest.mark.skipif(not ATP_LIVE, reason="ATP Phase 8 warehouse absent")
def test_atp_warehouse_execute_feeds_vital_question(monkeypatch, tmp_path):
    phase_b = _isolate(monkeypatch, tmp_path)
    question, errors = question_from_draft(_atp_draft())
    assert question is not None
    assert not errors
    executed = execute_frontend_research({"question": question.to_dict()}, include_reference=True)
    assert executed["status"] == "READY"
    assert executed["difference_count"] == 0
    contract = executed["results_contract"]
    assert contract["observation_basis"] == "TRADABLE_YES_BID"
    assert contract["population"] >= 1
    folder = _write_iti(
        phase_b,
        name="ATP WAREHOUSE CROSS 65",
        sport="atp",
        question=question.to_dict(),
        population=contract["population"],
    )
    created = create_bot({"name": "ATP warehouse", "iti_folder": folder}, root=tmp_path / "bots")
    assert created["vital_bot_id"] == "atp-001"
    strategy = handle_strategy("atp-001", root=tmp_path / "vital")
    assert strategy["question"]["universe"]["leagues"] == ["ATP"] or strategy["question"]["universe"]["sports"]
    assert strategy["implementation"]["submit"] is False
    assert strategy["candle_path_not_fill"] is True
