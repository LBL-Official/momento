"""Fresh ROLLER → SuperASI A+B → Jump A ITI stress. Facts only. Not Jump C."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from roller.config import RollerConfig

os.environ.setdefault("ROLLER_QUERY_RESULT_CACHE", "1")
os.environ.setdefault(
    "ROLLER_QUERY_RESULT_CACHE_DIR",
    str(_ROOT / "data" / ".cache" / "research_query"),
)
from roller.jump.iti.catalog import build_catalog, question_sha256, shift_price_e4, step_cents
from roller.jump.iti.pipeline import start_run
from roller.jump.iti.rank import recommend_slot_id
from roller.jump.iti.store import commit_slot, load_job
from roller.jump.iti.stress_question import STRATEGY_NAME, STRESS_QUESTION
from roller.jump.iti.timings import timings_path
from roller.jump.iti.versions import ORCHESTRATOR_BASELINE, ORCHESTRATOR_OPTIMIZED
from roller.jump.library import repo_root
from roller.jump.versions import PHASE_STATUS
from roller.labs.store import save_lab
from roller.superasi.base.pipeline import run_base
from roller.superasi.debase.pipeline import run_debase
from roller.warehouse.frontend_contract import compile_frontend_research, execute_frontend_research
from roller.warehouse.layout import warehouse_root

STRESS_DIR = repo_root() / "research" / "jump" / "stress"


def warehouse_present(cfg: RollerConfig | None = None) -> bool:
    cfg = cfg or RollerConfig()
    root = warehouse_root(cfg, "NBA", "2025-2026")
    return (root / "games" / "games.parquet").is_file()


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _write_facts(name: str, payload: dict[str, Any]) -> Path:
    STRESS_DIR.mkdir(parents=True, exist_ok=True)
    dest = STRESS_DIR / name
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return dest


def assert_catalog(question: dict[str, Any]) -> list[dict[str, Any]]:
    assert step_cents(6500) == 3
    assert step_cents(8500) == 4
    assert step_cents(4000) == 2
    assert shift_price_e4(6500, -3) == 5600
    assert shift_price_e4(6500, 3) == 7400
    assert shift_price_e4(8500, -3) == 7300
    assert shift_price_e4(4000, 3) == 4600
    slots = build_catalog(question)
    assert len(slots) == 25
    control = slots[0]
    assert control["slot_id"] == "ITI-00"
    assert control["question_sha256"] == question_sha256(question)
    skipped = [s for s in slots if s["status"] == "SKIPPED"]
    assert not skipped, f"unexpected catalog skips: {skipped}"
    return slots


def assert_job(job: dict[str, Any], *, source: dict[str, Any], expect_reuse: bool) -> None:
    assert job["status"] == "COMPLETE"
    assert len(job["slots"]) == 25
    executed = [s["slot_id"] for s in job["slots"] if s.get("executed")]
    skipped = [s for s in job["slots"] if s.get("status") == "SKIPPED"]
    assert not skipped
    control = next(s for s in job["slots"] if s["slot_id"] == "ITI-00")
    assert control["question_sha256"] == question_sha256(STRESS_QUESTION)
    if expect_reuse:
        assert control.get("reused_source") is True, control
        assert "ITI-00" not in executed
        assert control.get("BASE_GRADE") == source.get("BASE_GRADE")
        assert control.get("DEBASE_GRADE") == source.get("DEBASE_GRADE")
        assert control.get("result_hash") == source.get("result_hash")
        assert control.get("population") == source.get("population"), (
            control.get("population"),
            source.get("population"),
        )
    else:
        assert control.get("reused_source") in {None, False}
        assert control.get("population") == source.get("population"), (
            control.get("population"),
            source.get("population"),
        )
        assert control.get("result_hash") == source.get("result_hash")
    ranked = recommend_slot_id(list(job["slots"]))
    assert job.get("recommended_slot_id") == ranked
    assert PHASE_STATUS["A"] == "IMPLEMENTED"


def run_source(*, cfg: RollerConfig, monte_carlo_paths: int) -> dict[str, Any]:
    started = time.perf_counter()
    stages: dict[str, int] = {}
    t = time.perf_counter()
    compiled = compile_frontend_research({"question": STRESS_QUESTION}, cfg)
    stages["compile_ms"] = _ms(t)
    if compiled.get("status") != "READY":
        raise SystemExit(f"compile status {compiled.get('status')}: {compiled}")
    t = time.perf_counter()
    executed = execute_frontend_research({"question": STRESS_QUESTION}, cfg)
    stages["execute_ms"] = _ms(t)
    if executed.get("status") != "READY":
        raise SystemExit(f"execute status {executed.get('status')}: {executed}")
    result = executed.get("result") if isinstance(executed.get("result"), dict) else {}
    contract = executed.get("results_contract") if isinstance(executed.get("results_contract"), dict) else {}
    stats = contract.get("statistics") if isinstance(contract.get("statistics"), dict) else {}
    population = stats.get("population")
    if population is None:
        population = result.get("population")
    result_hash = result.get("result_hash") or (contract.get("reproducibility") or {}).get("result_hash")
    t = time.perf_counter()
    lab = save_lab(
        name=STRATEGY_NAME,
        payload=executed,
        folder="NBA",
        question=STRESS_QUESTION,
        cfg=cfg,
    )
    stages["lab_ms"] = _ms(t)
    t = time.perf_counter()
    base = run_base(lab_id=str(lab["lab_id"]), cfg=cfg, monte_carlo_paths=monte_carlo_paths)
    stages["base_ms"] = _ms(t)
    inspect_a = base.get("inspect") if isinstance(base.get("inspect"), dict) else base
    t = time.perf_counter()
    debase = run_debase(
        result_id=str(inspect_a.get("result_id") or base.get("result_id")),
        cfg=cfg,
        monte_carlo_paths=monte_carlo_paths,
    )
    stages["debase_ms"] = _ms(t)
    inspect_b = debase.get("inspect") if isinstance(debase.get("inspect"), dict) else debase
    facts = {
        "strategy_name": STRATEGY_NAME,
        "lab_id": lab.get("lab_id"),
        "phase_a_result_id": inspect_a.get("result_id") or base.get("result_id"),
        "debase_result_id": inspect_b.get("result_id") or debase.get("result_id"),
        "population": int(population) if population is not None else None,
        "result_hash": result_hash,
        "BASE_GRADE": inspect_b.get("BASE_GRADE") or inspect_a.get("BASE_GRADE"),
        "DEBASE_GRADE": inspect_b.get("DEBASE_GRADE"),
        "question_sha256": question_sha256(STRESS_QUESTION),
        "monte_carlo_paths": monte_carlo_paths,
        "source_ms": _ms(started),
        "stages_ms": stages,
    }
    path = _write_facts("source.json", facts)
    print(json.dumps({"phase": "source", "path": str(path), **facts}, indent=2, default=str), flush=True)
    return facts


def run_iti(
    *,
    debase_result_id: str,
    source: dict[str, Any],
    orchestrator: str,
    cfg: RollerConfig,
    monte_carlo_paths: int,
    commit: bool,
) -> dict[str, Any]:
    expect_reuse = orchestrator == ORCHESTRATOR_OPTIMIZED
    job = start_run(
        debase_result_id=debase_result_id,
        cfg=cfg,
        background=False,
        monte_carlo_paths=monte_carlo_paths,
        orchestrator=orchestrator,
        reuse_control=expect_reuse,
    )
    raw = load_job(job["run_id"])
    assert_job(raw, source=source, expect_reuse=expect_reuse)
    commit_out = None
    if commit:
        pick = str(raw.get("recommended_slot_id") or "ITI-00")
        parent = Path(cfg.root) / "superasi_labs" / "phase_b" / source.get("folder", debase_result_id)
        if not parent.is_dir():
            parent = Path(cfg.root) / "superasi_labs" / "phase_b" / debase_result_id
        before = {}
        if parent.is_dir():
            for path in parent.iterdir():
                if path.is_file():
                    before[path.name] = path.read_bytes()
        commit_out = commit_slot(raw["run_id"], pick, cfg=cfg)
        if parent.is_dir():
            for name, data in before.items():
                assert (parent / name).read_bytes() == data
        raw = load_job(raw["run_id"])
    facts = {
        "orchestrator": orchestrator,
        "run_id": raw["run_id"],
        "status": raw["status"],
        "job_ms": raw.get("job_ms"),
        "recommended_slot_id": raw.get("recommended_slot_id"),
        "committed_slot_id": raw.get("committed_slot_id"),
        "commit_path": raw.get("commit_path") or (commit_out or {}).get("path"),
        "timings_path": str(timings_path(raw["run_id"])),
        "slots": [
            {
                "slot_id": s.get("slot_id"),
                "status": s.get("status"),
                "reused_source": s.get("reused_source"),
                "population": s.get("population"),
                "result_hash": s.get("result_hash"),
                "BASE_GRADE": s.get("BASE_GRADE"),
                "DEBASE_GRADE": s.get("DEBASE_GRADE"),
                "compile_ms": s.get("compile_ms"),
                "execute_ms": s.get("execute_ms"),
                "lab_ms": s.get("lab_ms"),
                "base_ms": s.get("base_ms"),
                "debase_ms": s.get("debase_ms"),
                "slot_ms": s.get("slot_ms"),
            }
            for s in raw.get("slots") or []
        ],
    }
    path = _write_facts(f"iti_{orchestrator}.json", facts)
    print(json.dumps({"phase": f"iti_{orchestrator}", "path": str(path), **{k: facts[k] for k in facts if k != "slots"}}, indent=2, default=str), flush=True)
    print(json.dumps({"slots": facts["slots"]}, indent=2, default=str), flush=True)
    return facts


def compare_runs(baseline: dict[str, Any], optimized: dict[str, Any]) -> dict[str, Any]:
    base_slots = {s["slot_id"]: s for s in baseline.get("slots") or []}
    opt_slots = {s["slot_id"]: s for s in optimized.get("slots") or []}
    mismatches = []
    for slot_id, left in base_slots.items():
        right = opt_slots.get(slot_id) or {}
        if slot_id == "ITI-00":
            if not right.get("reused_source"):
                mismatches.append({"slot_id": slot_id, "field": "reused_source", "expected": True, "got": right.get("reused_source")})
            continue
        for field in ("population", "BASE_GRADE", "DEBASE_GRADE"):
            if left.get(field) != right.get(field):
                mismatches.append({"slot_id": slot_id, "field": field, "baseline": left.get(field), "optimized": right.get(field)})
    out = {
        "baseline_job_ms": baseline.get("job_ms"),
        "optimized_job_ms": optimized.get("job_ms"),
        "mismatch_n": len(mismatches),
        "mismatches": mismatches,
    }
    path = _write_facts("compare.json", out)
    print(json.dumps({"phase": "compare", "path": str(path), **out}, indent=2, default=str), flush=True)
    if mismatches:
        raise SystemExit(f"optimized slots diverged from baseline: {mismatches}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Jump A full-path stress. Does not start Jump C.")
    parser.add_argument("--pass", dest="phase", choices=("source", "baseline", "optimized", "all"), default="all")
    parser.add_argument("--source-id", default="")
    parser.add_argument("--monte-carlo-paths", type=int, default=100_000)
    parser.add_argument("--skip-commit", action="store_true")
    args = parser.parse_args()
    if PHASE_STATUS["A"] != "IMPLEMENTED":
        raise SystemExit("Jump A must remain IMPLEMENTED")
    cfg = RollerConfig()
    if not warehouse_present(cfg):
        raise SystemExit("NBA warehouse games.parquet is absent")
    assert_catalog(STRESS_QUESTION)
    source = None
    if args.source_id:
        existing = STRESS_DIR / "source.json"
        if existing.is_file():
            source = json.loads(existing.read_text(encoding="utf-8"))
        source = {**(source or {}), "debase_result_id": args.source_id}
    if args.phase in {"source", "all"}:
        source = run_source(cfg=cfg, monte_carlo_paths=args.monte_carlo_paths)
    if source is None or not source.get("debase_result_id"):
        raise SystemExit("source SuperASI Final Result is required")
    source["folder"] = source.get("debase_result_id")
    baseline = None
    optimized = None
    if args.phase in {"baseline", "all"}:
        baseline = run_iti(
            debase_result_id=str(source["debase_result_id"]),
            source=source,
            orchestrator=ORCHESTRATOR_BASELINE,
            cfg=cfg,
            monte_carlo_paths=args.monte_carlo_paths,
            commit=not args.skip_commit,
        )
    if args.phase in {"optimized", "all"}:
        optimized = run_iti(
            debase_result_id=str(source["debase_result_id"]),
            source=source,
            orchestrator=ORCHESTRATOR_OPTIMIZED,
            cfg=cfg,
            monte_carlo_paths=args.monte_carlo_paths,
            commit=False,
        )
    if baseline and optimized:
        compare_runs(baseline, optimized)
    return 0


if __name__ == "__main__":
    sys.exit(main())
