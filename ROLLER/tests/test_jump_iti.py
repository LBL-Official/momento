"""Jump A — Ian Taleb Index. Catalog, rank, orchestrator stress. No credentials."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from roller.config import RollerConfig
from roller.jump.errors import JumpError
from roller.jump.iti.catalog import (
    SLOT_SPEC,
    build_catalog,
    question_sha256,
    step_cents,
    shift_price_e4,
)
from roller.jump.iti.pipeline import start_run
from roller.jump.iti.rank import recommend_slot_id
from roller.jump.iti.source import load_source
from roller.jump.iti.store import commit_slot, create_job, save_job
from roller.jump.iti.stress_question import STRESS_QUESTION
from roller.jump.iti.timings import timings_path
from roller.jump.iti.versions import SLOT_COUNT
from roller.jump.versions import PHASE_STATUS
from roller.warehouse.layout import warehouse_root
def _question(entry=6500, win=8500, loss=4100) -> dict:
    return {
        "universe": {"sports": ["NBA"], "leagues": ["NBA"], "seasons": ["2025-2026"]},
        "entry_conditions": [
            {
                "id": "e1",
                "ordinal": "FIRST_TOUCH",
                "price_e4": entry,
                "operation": "CROSS",
                "period": "Q4",
            }
        ],
        "path_conditions": [
            {"id": "w1", "op": "REACH", "price_e4": win, "outcome": "win"},
            {"id": "l1", "op": "DROP_TO", "price_e4": loss, "outcome": "loss"},
        ],
        "terminal": "BOTH",
        "requested_dimensions": [],
        "accept_limitations": False,
    }


def _write_debase(root: Path, name: str, question: dict | None) -> str:
    dest = root / name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"Roller[{name}].csv").write_text("PARENT_ROLLER\n", encoding="utf-8")
    (dest / f"SuperasiABase[{name}].csv").write_text("PARENT_ABASE\n", encoding="utf-8")
    (dest / f"SuperasiBDeBase[{name}].csv").write_text("PARENT_DEBASE\n", encoding="utf-8")
    rec = {
        "result_id": name,
        "folder": name,
        "strategy_name": name,
        "source_lab_id": "",
        "question": question,
        "roller_filename": f"Roller[{name}].csv",
        "abase_filename": f"SuperasiABase[{name}].csv",
        "debase_filename": f"SuperasiBDeBase[{name}].csv",
    }
    (dest / "metadata.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    return name


def test_step_cents_rounding():
    assert step_cents(6500) == 3
    assert step_cents(2000) == 1
    assert step_cents(8000) == 4
    assert shift_price_e4(6500, -3) == 5600
    assert shift_price_e4(6500, 3) == 7400
    assert shift_price_e4(2000, -3) == 1700
    assert shift_price_e4(8000, 3) == 9200


def test_catalog_is_25_and_control_hash_unchanged():
    q = _question()
    slots = build_catalog(q)
    assert len(SLOT_SPEC) == SLOT_COUNT
    assert len(slots) == 25
    assert [s["slot_id"] for s in slots] == [spec[0] for spec in SLOT_SPEC]
    control = slots[0]
    assert control["slot_id"] == "ITI-00"
    assert control["status"] == "PENDING"
    assert control["question_sha256"] == question_sha256(q)
    assert control["question"] == q


def test_inversion_skipped_not_replaced():
    slots = build_catalog(_question(entry=6500, win=6800, loss=6200))
    assert len(slots) == 25
    skipped = [s for s in slots if s["status"] == "SKIPPED"]
    assert skipped
    assert all(s["skip_reason"] in {"win_le_entry", "loss_ge_entry"} for s in skipped)
    assert slots[0]["status"] == "PENDING"
    assert {s["slot_id"] for s in skipped} <= {s["slot_id"] for s in slots}


def test_missing_question_is_data_required(tmp_path, monkeypatch):
    phase_b = tmp_path / "phase_b"
    monkeypatch.setattr("roller.superasi.debase.store.phase_b_root", lambda _cfg=None: phase_b)
    _write_debase(phase_b, "Bare", {"terminal": "BOTH"})
    with pytest.raises(JumpError) as ei:
        load_source(debase_result_id="Bare")
    assert ei.value.code == "DATA_REQUIRED"


def test_ranking_debase_first():
    slots = [
        {"slot_id": "ITI-00", "status": "COMPLETE", "DEBASE_GRADE": "B", "BASE_GRADE": "A+"},
        {"slot_id": "ITI-04", "status": "COMPLETE", "DEBASE_GRADE": "A", "BASE_GRADE": "F"},
        {"slot_id": "ITI-05", "status": "SKIPPED", "DEBASE_GRADE": "A+", "BASE_GRADE": "A+"},
    ]
    assert recommend_slot_id(slots) == "ITI-04"


def test_ranking_control_last_on_tie():
    slots = [
        {"slot_id": "ITI-00", "status": "COMPLETE", "DEBASE_GRADE": "B", "BASE_GRADE": "B"},
        {"slot_id": "ITI-10", "status": "COMPLETE", "DEBASE_GRADE": "B", "BASE_GRADE": "B"},
    ]
    assert recommend_slot_id(slots) == "ITI-10"


def test_orchestrator_stress_skips_do_not_execute(tmp_path, monkeypatch):
    phase_b = tmp_path / "phase_b"
    jump_lib = tmp_path / "jump"
    monkeypatch.setattr("roller.superasi.debase.store.phase_b_root", lambda _cfg=None: phase_b)
    executed: list[str] = []

    def compile_ok(question, cfg=None):
        return {"status": "READY"}

    def execute_ok(question, cfg=None):
        return {
            "status": "READY",
            "results_contract": {"statistics": {"population": 12}, "population": 12},
            "result": {"population": 12},
        }

    def save_lab(**kwargs):
        return {"lab_id": f"lab-{kwargs['name'][-6:]}"}

    def run_base(*, lab_id, cfg=None, monte_carlo_paths=None):
        return {"inspect": {"result_id": f"A-{lab_id}", "BASE_GRADE": "C"}}

    def run_debase(*, result_id, cfg=None, monte_carlo_paths=None):
        return {"inspect": {"result_id": f"B-{result_id}", "BASE_GRADE": "C", "DEBASE_GRADE": "C"}}

    monkeypatch.setattr("roller.jump.iti.pipeline.compile_question", compile_ok)
    monkeypatch.setattr("roller.jump.iti.pipeline.execute_question", execute_ok)
    monkeypatch.setattr("roller.jump.iti.pipeline.save_variant_lab", save_lab)
    monkeypatch.setattr("roller.jump.iti.pipeline.run_base_variant", run_base)
    monkeypatch.setattr("roller.jump.iti.pipeline.run_debase_variant", run_debase)

    _write_debase(phase_b, "Narrow", _question(entry=6500, win=6800, loss=6200))
    job = start_run(
        debase_result_id="Narrow",
        root=jump_lib,
        background=False,
        executed_ids=executed,
        orchestrator="baseline",
    )
    assert job["status"] == "COMPLETE"
    assert len(job["slots"]) == 25
    skipped = [s for s in job["slots"] if s["status"] == "SKIPPED"]
    completed = [s for s in job["slots"] if s["status"] == "COMPLETE"]
    assert skipped
    assert completed
    assert set(executed) == {s["slot_id"] for s in completed}
    assert all(s["slot_id"] not in executed for s in skipped)


def test_commit_writes_nested_csvs_and_leaves_parent(tmp_path, monkeypatch):
    phase_b = tmp_path / "phase_b"
    jump_lib = tmp_path / "jump"
    monkeypatch.setattr("roller.superasi.debase.store.phase_b_root", lambda _cfg=None: phase_b)
    _write_debase(phase_b, "Src", _question())
    slots = build_catalog(_question())
    slots[0]["status"] = "COMPLETE"
    slots[0]["lab_id"] = "lab1"
    slots[0]["phase_a_result_id"] = "a1"
    slots[0]["phase_b_result_id"] = "b1"
    slots[0]["BASE_GRADE"] = "C"
    slots[0]["DEBASE_GRADE"] = "C"
    source = {
        "debase_result_id": "Src",
        "source_folder": "Src",
        "source_lab_id": "",
        "strategy_name": "Src",
    }
    job = create_job(source=source, slots=slots, root=jump_lib)
    job["status"] = "COMPLETE"
    save_job(job, root=jump_lib)

    monkeypatch.setattr(
        "roller.jump.iti.store.get_lab_csv_bytes",
        lambda *_a, **_k: ("Roller[x].csv", b"LAB"),
    )
    monkeypatch.setattr(
        "roller.jump.iti.store.get_base_csv_bytes",
        lambda *_a, **_k: ("SuperasiABase[x].csv", b"ABASE"),
    )
    monkeypatch.setattr(
        "roller.jump.iti.store.get_debase_csv_bytes",
        lambda *_a, **_k: ("SuperasiBDeBase[x].csv", b"DEBASE"),
    )
    out = commit_slot(job["run_id"], "ITI-00", root=jump_lib)
    dest = Path(out["path"])
    assert dest.name == "Src_ITI"
    assert (dest / "Roller[Src_ITI]" / "Roller[Src_ITI].csv").read_bytes() == b"LAB"
    assert (dest / "SuperasiABase[Src_ITI]" / "SuperasiABase[Src_ITI].csv").read_bytes() == b"ABASE"
    assert (dest / "SuperasiBDeBase[Src_ITI]" / "SuperasiBDeBase[Src_ITI].csv").read_bytes() == b"DEBASE"
    parent = phase_b / "Src"
    assert (parent / "Roller[Src].csv").read_text(encoding="utf-8") == "PARENT_ROLLER\n"
    assert (parent / "SuperasiABase[Src].csv").read_text(encoding="utf-8") == "PARENT_ABASE\n"
    assert (parent / "SuperasiBDeBase[Src].csv").read_text(encoding="utf-8") == "PARENT_DEBASE\n"


def test_commit_incomplete_slot_fails_closed(tmp_path):
    slots = build_catalog(_question())
    job = create_job(
        source={
            "debase_result_id": "Src",
            "source_folder": "Src",
            "source_lab_id": "",
            "strategy_name": "Src",
        },
        slots=slots,
        root=tmp_path / "jump",
    )
    job["status"] = "RUNNING"
    save_job(job, root=tmp_path / "jump")
    with pytest.raises(JumpError) as ei:
        commit_slot(job["run_id"], "ITI-00", root=tmp_path / "jump")
    assert ei.value.code == "SLOT_NOT_COMPLETE"


def test_commit_complete_slot_while_catalog_running(tmp_path, monkeypatch):
    phase_b = tmp_path / "phase_b"
    jump_lib = tmp_path / "jump"
    monkeypatch.setattr("roller.superasi.debase.store.phase_b_root", lambda _cfg=None: phase_b)
    _write_debase(phase_b, "Src", _question())
    slots = build_catalog(_question())
    slots[0]["status"] = "COMPLETE"
    slots[0]["lab_id"] = "lab1"
    slots[0]["phase_a_result_id"] = "a1"
    slots[0]["phase_b_result_id"] = "b1"
    slots[0]["BASE_GRADE"] = "C"
    slots[0]["DEBASE_GRADE"] = "C"
    job = create_job(
        source={
            "debase_result_id": "Src",
            "source_folder": "Src",
            "source_lab_id": "",
            "strategy_name": "Src",
        },
        slots=slots,
        root=jump_lib,
    )
    job["status"] = "RUNNING"
    save_job(job, root=jump_lib)
    monkeypatch.setattr(
        "roller.jump.iti.store.get_lab_csv_bytes",
        lambda *_a, **_k: ("Roller[x].csv", b"LAB"),
    )
    monkeypatch.setattr(
        "roller.jump.iti.store.get_base_csv_bytes",
        lambda *_a, **_k: ("SuperasiABase[x].csv", b"ABASE"),
    )
    monkeypatch.setattr(
        "roller.jump.iti.store.get_debase_csv_bytes",
        lambda *_a, **_k: ("SuperasiBDeBase[x].csv", b"DEBASE"),
    )
    out = commit_slot(job["run_id"], "ITI-00", root=jump_lib)
    assert out["slot_id"] == "ITI-00"
    assert Path(out["path"]).name == "Src_ITI"


def test_start_run_returns_existing_complete_job(tmp_path, monkeypatch):
    phase_b = tmp_path / "phase_b"
    jump_lib = tmp_path / "jump"
    monkeypatch.setattr("roller.superasi.debase.store.phase_b_root", lambda _cfg=None: phase_b)
    executed = _patch_orchestrator(monkeypatch, [])
    _write_debase(phase_b, "Once", _question())
    first = start_run(
        debase_result_id="Once",
        root=jump_lib,
        background=False,
        executed_ids=executed,
        orchestrator="baseline",
    )
    assert first["status"] == "COMPLETE"
    first_n = len(executed)
    executed.clear()
    second = start_run(
        debase_result_id="Once",
        root=jump_lib,
        background=False,
        executed_ids=executed,
        orchestrator="baseline",
    )
    assert second["run_id"] == first["run_id"]
    assert executed == []
    assert first_n > 0


def test_start_run_resumes_and_skips_complete_slots(tmp_path, monkeypatch):
    phase_b = tmp_path / "phase_b"
    jump_lib = tmp_path / "jump"
    monkeypatch.setattr("roller.superasi.debase.store.phase_b_root", lambda _cfg=None: phase_b)
    _write_debase(phase_b, "Resume", _question())
    slots = build_catalog(_question())
    for slot in slots[:-1]:
        if slot["status"] == "PENDING":
            slot["status"] = "COMPLETE"
            slot["lab_id"] = "lab-done"
    leftover = [s["slot_id"] for s in slots if s["status"] == "PENDING"]
    assert leftover
    job = create_job(
        source={
            "debase_result_id": "Resume",
            "source_folder": "Resume",
            "source_lab_id": "",
            "strategy_name": "Resume",
        },
        slots=slots,
        root=jump_lib,
    )
    job["status"] = "FAILED"
    save_job(job, root=jump_lib)
    executed = _patch_orchestrator(monkeypatch, [])
    out = start_run(
        debase_result_id="Resume",
        root=jump_lib,
        background=False,
        executed_ids=executed,
        orchestrator="baseline",
    )
    assert out["run_id"] == job["run_id"]
    assert out["status"] == "COMPLETE"
    assert set(executed) == set(leftover)


def test_no_credentials_in_jump():
    root = Path(__file__).resolve().parents[1] / "roller" / "jump"
    banned = ("KALSHI_API_KEY", "PRIVATE_KEY", "secret_key", "api_key=")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path} contains {token}"


def test_health_lists_jump_iti():
    import sys

    from fastapi.testclient import TestClient

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    body = TestClient(terminal_api.app).get("/health").json()
    assert "jump_iti" in body["capabilities"]
    jump = TestClient(terminal_api.app).get("/jump/health").json()
    assert jump["phases"]["A"] == "MOVED_TO_SUPERASI"
    assert jump["phases"]["B"] == "IMPLEMENTED"
    assert jump["phases"]["C"] == "IMPLEMENTED"
    assert PHASE_STATUS["B"] == "IMPLEMENTED"
    assert PHASE_STATUS["C"] == "IMPLEMENTED"
    listed = TestClient(terminal_api.app).get("/jump/iti").json()
    assert "results" in listed


def test_source_reads_population_from_risk_row():
    from roller.jump.iti.source import _summary_field

    csv = (
        "record_type,population,result_hash\n"
        "row,1,abc\n"
        "risk,23,hash-src\n"
        "weekly,23,hash-src\n"
    ).encode("utf-8")
    assert _summary_field(csv, "population") == "23"
    assert _summary_field(csv, "result_hash") == "hash-src"


def test_catalog_658540_steps_and_no_inversion():
    assert step_cents(6500) == 3
    assert step_cents(8500) == 4
    assert step_cents(4000) == 2
    assert shift_price_e4(6500, -3) == 5600
    assert shift_price_e4(8500, -3) == 7300
    assert shift_price_e4(4000, 3) == 4600
    slots = build_catalog(STRESS_QUESTION)
    assert len(slots) == 25
    assert slots[0]["question_sha256"] == question_sha256(STRESS_QUESTION)
    assert slots[0]["entry_cents"] == 65
    assert slots[0]["win_cents"] == 85
    assert slots[0]["loss_cents"] == 40
    assert slots[1]["entry_cents"] == 56
    assert not [s for s in slots if s["status"] == "SKIPPED"]


def _patch_orchestrator(monkeypatch, executed: list[str]):
    def compile_ok(question, cfg=None):
        return {"status": "READY"}

    def execute_ok(question, cfg=None):
        return {
            "status": "READY",
            "results_contract": {
                "statistics": {"population": 12},
                "population": 12,
                "reproducibility": {"result_hash": "h12"},
            },
            "result": {"population": 12, "result_hash": "h12"},
        }

    def save_lab(**kwargs):
        return {"lab_id": f"lab-{kwargs['name'][-6:]}"}

    def run_base(*, lab_id, cfg=None, monte_carlo_paths=None):
        return {"inspect": {"result_id": f"A-{lab_id}", "BASE_GRADE": "C"}}

    def run_debase(*, result_id, cfg=None, monte_carlo_paths=None):
        return {"inspect": {"result_id": f"B-{result_id}", "BASE_GRADE": "C", "DEBASE_GRADE": "C"}}

    monkeypatch.setattr("roller.jump.iti.pipeline.compile_question", compile_ok)
    monkeypatch.setattr("roller.jump.iti.pipeline.execute_question", execute_ok)
    monkeypatch.setattr("roller.jump.iti.pipeline.save_variant_lab", save_lab)
    monkeypatch.setattr("roller.jump.iti.pipeline.run_base_variant", run_base)
    monkeypatch.setattr("roller.jump.iti.pipeline.run_debase_variant", run_debase)
    return executed


def test_timing_facts_written(tmp_path, monkeypatch):
    phase_b = tmp_path / "phase_b"
    jump_lib = tmp_path / "jump"
    monkeypatch.setattr("roller.superasi.debase.store.phase_b_root", lambda _cfg=None: phase_b)
    _patch_orchestrator(monkeypatch, [])
    _write_debase(phase_b, "Timed", _question())
    job = start_run(
        debase_result_id="Timed",
        root=jump_lib,
        background=False,
        orchestrator="baseline",
    )
    path = timings_path(job["run_id"], root=jump_lib)
    assert path.is_file()
    facts = json.loads(path.read_text(encoding="utf-8"))
    assert facts["run_id"] == job["run_id"]
    assert facts["status"] == "COMPLETE"
    assert facts["orchestrator"] == "baseline"
    assert facts["job_ms"] is not None
    assert len(facts["slots"]) == 25
    control = facts["slots"][0]
    assert control["compile_ms"] is not None
    assert control["execute_ms"] is not None
    assert control["result_hash"] == "h12"


def test_optimized_skips_precompile(tmp_path, monkeypatch):
    phase_b = tmp_path / "phase_b"
    jump_lib = tmp_path / "jump"
    monkeypatch.setattr("roller.superasi.debase.store.phase_b_root", lambda _cfg=None: phase_b)
    compiles: list[int] = []

    def compile_ok(question, cfg=None):
        compiles.append(1)
        return {"status": "READY"}

    _patch_orchestrator(monkeypatch, [])
    monkeypatch.setattr("roller.jump.iti.pipeline.compile_question", compile_ok)
    _write_debase(phase_b, "NoCompile", _question())
    job = start_run(
        debase_result_id="NoCompile",
        root=jump_lib,
        background=False,
        orchestrator="optimized",
        reuse_control=False,
    )
    assert job["status"] == "COMPLETE"
    assert compiles == []
    assert job["orchestrator"] == "optimized"


def test_optimized_reuses_control(tmp_path, monkeypatch):
    phase_b = tmp_path / "phase_b"
    jump_lib = tmp_path / "jump"
    monkeypatch.setattr("roller.superasi.debase.store.phase_b_root", lambda _cfg=None: phase_b)
    executed: list[str] = []

    def execute_ok(question, cfg=None):
        return {
            "status": "READY",
            "results_contract": {
                "statistics": {"population": 9},
                "reproducibility": {"result_hash": "h9"},
            },
            "result": {"population": 9, "result_hash": "h9"},
        }

    _patch_orchestrator(monkeypatch, executed)
    monkeypatch.setattr("roller.jump.iti.pipeline.execute_question", execute_ok)
    dest = phase_b / "Reuse"
    dest.mkdir(parents=True)
    q = _question()
    (dest / "Roller[Reuse].csv").write_text("PARENT\n", encoding="utf-8")
    (dest / "SuperasiABase[Reuse].csv").write_text("A\n", encoding="utf-8")
    (dest / "SuperasiBDeBase[Reuse].csv").write_text("B\n", encoding="utf-8")
    rec = {
        "result_id": "Reuse",
        "folder": "Reuse",
        "strategy_name": "Reuse",
        "source_lab_id": "lab-source",
        "phase_a_result_id": "phase-a-source",
        "BASE_GRADE": "B",
        "DEBASE_GRADE": "A",
        "result_hash": "hash-src",
        "population": 77,
        "question": q,
        "roller_filename": "Roller[Reuse].csv",
        "abase_filename": "SuperasiABase[Reuse].csv",
        "debase_filename": "SuperasiBDeBase[Reuse].csv",
    }
    (dest / "metadata.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    job = start_run(
        debase_result_id="Reuse",
        root=jump_lib,
        background=False,
        executed_ids=executed,
        orchestrator="optimized",
        reuse_control=True,
    )
    control = next(s for s in job["slots"] if s["slot_id"] == "ITI-00")
    assert control["reused_source"] is True
    assert control["BASE_GRADE"] == "B"
    assert control["DEBASE_GRADE"] == "A"
    assert control["result_hash"] == "hash-src"
    assert control["population"] == 77
    assert "ITI-00" not in executed
    assert job["status"] == "COMPLETE"


def test_optimized_pipelines_superasi(tmp_path, monkeypatch):
    phase_b = tmp_path / "phase_b"
    jump_lib = tmp_path / "jump"
    monkeypatch.setattr("roller.superasi.debase.store.phase_b_root", lambda _cfg=None: phase_b)
    in_base = threading.Event()
    overlapped: list[bool] = []

    def execute_ok(question, cfg=None):
        if in_base.is_set():
            overlapped.append(True)
        return {
            "status": "READY",
            "results_contract": {"statistics": {"population": 4}, "reproducibility": {"result_hash": "h4"}},
            "result": {"population": 4, "result_hash": "h4"},
        }

    def run_base(*, lab_id, cfg=None, monte_carlo_paths=None):
        in_base.set()
        time.sleep(0.12)
        in_base.clear()
        return {"inspect": {"result_id": f"A-{lab_id}", "BASE_GRADE": "C"}}

    _patch_orchestrator(monkeypatch, [])
    monkeypatch.setattr("roller.jump.iti.pipeline.execute_question", execute_ok)
    monkeypatch.setattr("roller.jump.iti.pipeline.run_base_variant", run_base)
    _write_debase(phase_b, "Pipe", _question())
    job = start_run(
        debase_result_id="Pipe",
        root=jump_lib,
        background=False,
        orchestrator="optimized",
        reuse_control=False,
    )
    assert job["status"] == "COMPLETE"
    assert overlapped


def test_nba_warehouse_compiles_stress_question():
    cfg = RollerConfig()
    if not (warehouse_root(cfg, "NBA", "2025-2026") / "games" / "games.parquet").is_file():
        pytest.skip("NBA warehouse absent")
    from roller.warehouse.frontend_contract import compile_frontend_research

    compiled = compile_frontend_research({"question": STRESS_QUESTION}, cfg)
    assert compiled.get("status") in {"READY", "DATA_REQUIRED", "OPERATION_REQUIRED", "INVALID"}
