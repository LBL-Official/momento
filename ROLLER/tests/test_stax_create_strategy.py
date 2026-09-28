"""STAX V1.1 — create a ROLLER strategy inside STAX.

Uses the real compile_draft + write_save path. Execution is mocked.
Does not scan the warehouse.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roller.research_library.saves import list_saves, load_save
from roller.stax.api import handle_create, handle_validate
from roller.stax.create_strategy import handle_create_strategy
from roller.stax.library import load_head
from roller.stax.models import ConstraintViolation, StaxError
from roller.stax.runner import run_stax
from tests.stax_fixtures import envelope, source


def nba_draft(
    *,
    price: int = 80,
    reach: int = 40,
    family: str = "first_touch",
    leagues: tuple[str, ...] = ("NBA",),
    date_from: str = "2025-10-10",
    date_to: str = "2026-06-13",
) -> dict:
    return {
        "universe": {
            "sports": ["basketball"],
            "leagues": list(leagues),
            "seasons": ["2025-26"],
            "dateFrom": date_from,
            "dateTo": date_to,
            "markets": ["kalshi"],
            "marketData": ["candles"],
            "dataSources": [],
        },
        "entryConditions": [
            {
                "id": "e1",
                "family": family,
                "priceCents": price,
                "touchN": 1,
                "periodWindows": [{"period": "Q3"}],
            }
        ],
        "exitConditions": [
            {
                "id": "p-loss",
                "kind": "path",
                "family": "reach",
                "priceCents": reach,
                "outcome": "loss",
            },
            {
                "id": "h-win",
                "kind": "terminal",
                "family": "hold_expiration_win",
                "outcome": "win",
            },
        ],
    }


def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("STAX_LIBRARY_ROOT", str(tmp_path / "stax"))
    monkeypatch.setenv("ROLLER_LIBRARY_DIR", str(tmp_path / "saves"))


def test_create_new_strategy_persists_roller_and_member(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    created = handle_create({"name": "NBA PATH STACK"}, root=tmp_path / "stax")
    stax_id = created["stax"]["stax_id"]
    out = handle_create_strategy(
        stax_id,
        {"name": "S01 FIRST TOUCH 80", "draft": nba_draft(price=80)},
        root=tmp_path / "stax",
    )
    assert out["persisted"] is True
    assert out["live_execution"] is False
    member = out["member"]
    assert member["member_id"] == "STXM-0001"
    assert member["question_hash"]
    assert member["universe"]["sport_family"] == "basketball"
    assert member["universe"]["league_set"] == ["NBA"]
    assert member["question"]["universe"]["leagues"] == ["NBA"]
    rec = load_save(out["roller"]["save_id"])
    assert rec is not None
    assert rec["id"] == out["roller"]["save_id"]
    assert rec["workflow_draft"]["entryConditions"][0]["priceCents"] == 80
    assert rec["hashes"]["question_hash"] == member["question_hash"]
    head = load_head(stax_id, root=tmp_path / "stax")
    assert len(head["working_members"]) == 1


def test_cancel_preview_does_not_persist(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    created = handle_create({"name": "NBA PATH STACK"}, root=tmp_path / "stax")
    stax_id = created["stax"]["stax_id"]
    before = list_saves()
    out = handle_create_strategy(
        stax_id,
        {"name": "ABANDONED", "draft": nba_draft(), "persist": False},
        root=tmp_path / "stax",
    )
    assert out["persisted"] is False
    assert out["valid"] is True
    assert list_saves() == before
    head = load_head(stax_id, root=tmp_path / "stax")
    assert head["working_members"] == []


def test_incompatible_league_rejected(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    created = handle_create({"name": "NBA PATH STACK"}, root=tmp_path / "stax")
    stax_id = created["stax"]["stax_id"]
    handle_create_strategy(stax_id, {"name": "S01", "draft": nba_draft()}, root=tmp_path / "stax")
    with pytest.raises(ConstraintViolation) as exc:
        handle_create_strategy(
            stax_id,
            {"name": "S02 NCAAB", "draft": nba_draft(leagues=("NCAAB",))},
            root=tmp_path / "stax",
        )
    assert exc.value.code == "STAX_CONSTRAINT_VIOLATION"
    assert "SPORT / LEAGUE / TIMEFRAME MUST MATCH" in exc.value.message
    head = load_head(stax_id, root=tmp_path / "stax")
    assert len(head["working_members"]) == 1
    assert len(list_saves()) == 1


def test_date_mismatch_rejected_no_expansion(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    created = handle_create({"name": "NBA PATH STACK"}, root=tmp_path / "stax")
    stax_id = created["stax"]["stax_id"]
    first = handle_create_strategy(
        stax_id,
        {"name": "S01", "draft": nba_draft(date_from="2025-10-10", date_to="2026-06-13")},
        root=tmp_path / "stax",
    )
    locked = first["member"]["universe"]
    with pytest.raises(ConstraintViolation) as exc:
        handle_create_strategy(
            stax_id,
            {
                "name": "S02 NARROW",
                "draft": nba_draft(date_from="2025-11-01", date_to="2026-06-13"),
            },
            root=tmp_path / "stax",
        )
    assert "timeframe" in exc.value.details
    head = load_head(stax_id, root=tmp_path / "stax")
    assert len(head["working_members"]) == 1
    assert head["universe"]["date_from"] == locked["date_from"]
    assert head["universe"]["date_to"] == locked["date_to"]


def test_multiple_creations_independent_ids(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    created = handle_create({"name": "NBA PATH STACK"}, root=tmp_path / "stax")
    stax_id = created["stax"]["stax_id"]
    rows = []
    for price, name in ((80, "S01"), (75, "S02"), (70, "S03")):
        rows.append(
            handle_create_strategy(
                stax_id,
                {"name": name, "draft": nba_draft(price=price)},
                root=tmp_path / "stax",
            )
        )
    ids = [r["member"]["member_id"] for r in rows]
    hashes = [r["member"]["question_hash"] for r in rows]
    saves = [r["roller"]["save_id"] for r in rows]
    assert ids == ["STXM-0001", "STXM-0002", "STXM-0003"]
    assert len(set(hashes)) == 3
    assert len(set(saves)) == 3
    assert all(r["member"]["universe"]["league_set"] == ["NBA"] for r in rows)


def test_reorder_keeps_member_id(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    created = handle_create({"name": "NBA PATH STACK"}, root=tmp_path / "stax")
    stax_id = created["stax"]["stax_id"]
    for price in (80, 75, 70):
        handle_create_strategy(
            stax_id,
            {"name": f"P{price}", "draft": nba_draft(price=price)},
            root=tmp_path / "stax",
        )
    got = handle_validate(
        stax_id,
        {"order": ["STXM-0003", "STXM-0001", "STXM-0002"]},
        root=tmp_path / "stax",
    )
    members = got["members"]
    assert [m["member_id"] for m in members] == ["STXM-0003", "STXM-0001", "STXM-0002"]
    assert members[0]["position"] == 1
    assert members[0]["member_id"] == "STXM-0003"
    assert members[0]["display_id"] == "STX01-S01"


def test_add_existing_still_works(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    created = handle_create({"name": "NBA PATH STACK"}, root=tmp_path / "stax")
    stax_id = created["stax"]["stax_id"]
    first = handle_create_strategy(stax_id, {"name": "S01", "draft": nba_draft(price=80)}, root=tmp_path / "stax")
    existing = source(name="EXISTING", question_hash="existing-qh")
    existing["question"]["universe"] = first["member"]["question"]["universe"]
    got = handle_validate(stax_id, {"add": existing}, root=tmp_path / "stax")
    assert [m["member_id"] for m in got["members"]] == ["STXM-0001", "STXM-0002"]
    assert got["members"][1]["label"] == "EXISTING"
    assert got["members"][1]["question_hash"] == "existing-qh"


def test_execution_three_independent_envelopes(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    created = handle_create({"name": "NBA PATH STACK"}, root=tmp_path / "stax")
    stax_id = created["stax"]["stax_id"]
    for price in (80, 75, 70):
        handle_create_strategy(
            stax_id,
            {"name": f"P{price}", "draft": nba_draft(price=price)},
            root=tmp_path / "stax",
        )

    def execute_question(payload):
        qh = (payload.get("question") or {}).get("entry_conditions", [{}])[0].get("price_e4")
        return envelope(games=[f"G-{qh}"], dataset_version="ds-create", question_hash=str(qh))

    out = run_stax(stax_id, root=tmp_path / "stax", execute_question=execute_question)
    assert out["status"] == "COMPLETE"
    assert out["strategy_count"] == 3
    assert len({id(r["envelope"]) for r in out["results"]}) == 3
    assert [r["summary"]["n"] for r in out["results"]] == [1, 1, 1]
    assert out.get("aggregation_method") == "NONE"


def test_one_data_required_is_partial(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    created = handle_create({"name": "NBA PATH STACK"}, root=tmp_path / "stax")
    stax_id = created["stax"]["stax_id"]
    for price in (80, 75, 70):
        handle_create_strategy(
            stax_id,
            {"name": f"P{price}", "draft": nba_draft(price=price)},
            root=tmp_path / "stax",
        )

    def execute_question(payload):
        price = (payload.get("question") or {}).get("entry_conditions", [{}])[0].get("price_e4")
        if price == 7500:
            raise RuntimeError("DATA_REQUIRED: object unavailable")
        return envelope(games=[f"G-{price}"], dataset_version="ds-create")

    out = run_stax(stax_id, root=tmp_path / "stax", execute_question=execute_question)
    assert out["status"] == "PARTIAL"
    assert out["failed_count"] == 1
    assert out["completed_count"] == 2
    assert len(out["results"]) == 3
    failed = next(r for r in out["results"] if r["status"] != "COMPLETE")
    assert failed["member_id"] == "STXM-0002"
    assert failed["summary"]["n"] is None
    complete = [r for r in out["results"] if r["status"] == "COMPLETE"]
    assert [r["summary"]["n"] for r in complete] == [1, 1]


def test_duplicate_definition_warns_unless_allowed(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    created = handle_create({"name": "NBA PATH STACK"}, root=tmp_path / "stax")
    stax_id = created["stax"]["stax_id"]
    handle_create_strategy(stax_id, {"name": "S01", "draft": nba_draft(price=80)}, root=tmp_path / "stax")
    with pytest.raises(StaxError) as exc:
        handle_create_strategy(stax_id, {"name": "S01-DUP", "draft": nba_draft(price=80)}, root=tmp_path / "stax")
    assert exc.value.code == "STAX_DUPLICATE_DEFINITION"
    assert len(load_head(stax_id, root=tmp_path / "stax")["working_members"]) == 1
    allowed = handle_create_strategy(
        stax_id,
        {"name": "S01-DUP", "draft": nba_draft(price=80), "allow_duplicate": True},
        root=tmp_path / "stax",
    )
    assert allowed["duplicate"] is True
    assert [m["member_id"] for m in allowed["members"]] == ["STXM-0001", "STXM-0002"]
    assert allowed["members"][0]["question_hash"] == allowed["members"][1]["question_hash"]


def test_http_create_strategy_route(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    created = client.post("/stax", json={"name": "NBA PATH STACK"}).json()
    stax_id = created["stax"]["stax_id"]
    preview = client.post(
        f"/stax/{stax_id}/strategies",
        json={"name": "S01", "draft": nba_draft(), "persist": False},
    )
    assert preview.status_code == 200
    assert preview.json()["persisted"] is False
    saved = client.post(f"/stax/{stax_id}/strategies", json={"name": "S01", "draft": nba_draft()})
    assert saved.status_code == 200
    body = saved.json()
    assert body["member"]["member_id"] == "STXM-0001"
    assert body["roller"]["save_id"]
    dup = client.post(f"/stax/{stax_id}/strategies", json={"name": "S01", "draft": nba_draft()})
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "STAX_DUPLICATE_DEFINITION"
