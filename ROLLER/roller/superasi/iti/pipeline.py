"""ITI orchestrator. Calls warehouse + SuperASI. Does not edit them."""

from __future__ import annotations

import threading
import time
from typing import Any

from roller.config import RollerConfig
from roller.jump.errors import JumpError
from roller.superasi.iti.catalog import build_catalog, plan_prices
from roller.superasi.iti.source import load_source
from roller.superasi.iti.store import create_job, latest_job, load_job, public_job, save_job
from roller.superasi.iti.timings import write_timing_facts
from roller.superasi.iti.versions import (
    DEFAULT_ORCHESTRATOR,
    ORCHESTRATOR_BASELINE,
    ORCHESTRATOR_OPTIMIZED,
)
from roller.labs.schema import sanitize_folder, sanitize_name
from roller.superasi.models import SuperasiError

_CLOSED = {"INVALID", "DATA_REQUIRED", "OPERATION_REQUIRED"}
_TERMINAL = frozenset({"COMPLETE", "SKIPPED", "INVALID", "DATA_REQUIRED", "OPERATION_REQUIRED", "CANCELLED"})
_RESUME = frozenset({"PENDING", "RUNNING", "FAILED"})
_ACTIVE_RUNS: set[str] = set()
_ACTIVE_LOCK = threading.Lock()


def compile_question(question: dict[str, Any], cfg: RollerConfig | None = None) -> dict[str, Any]:
    from roller.warehouse.frontend_contract import compile_frontend_research

    return compile_frontend_research({"question": question}, cfg)


def execute_question(question: dict[str, Any], cfg: RollerConfig | None = None) -> dict[str, Any]:
    from roller.warehouse.frontend_contract import execute_frontend_research

    return execute_frontend_research({"question": question}, cfg)


def save_variant_lab(
    *,
    name: str,
    payload: dict[str, Any],
    question: dict[str, Any],
    folder: str,
    cfg: RollerConfig | None = None,
) -> dict[str, Any]:
    from roller.labs.store import save_lab

    return save_lab(name=name, payload=payload, folder=folder, question=question, cfg=cfg)


def run_base_variant(*, lab_id: str, cfg: RollerConfig | None = None, monte_carlo_paths: int | None = None) -> dict[str, Any]:
    from roller.superasi.base.pipeline import run_base
    from roller.superasi.base.versions import DESK_PATHS

    return run_base(lab_id=lab_id, cfg=cfg, monte_carlo_paths=int(monte_carlo_paths or DESK_PATHS))


def run_debase_variant(
    *,
    result_id: str,
    cfg: RollerConfig | None = None,
    monte_carlo_paths: int | None = None,
) -> dict[str, Any]:
    from roller.superasi.debase.pipeline import run_debase
    from roller.superasi.debase.versions import DESK_PATHS

    return run_debase(result_id=result_id, cfg=cfg, monte_carlo_paths=int(monte_carlo_paths or DESK_PATHS))


def _population(payload: dict[str, Any]) -> int | None:
    contract = payload.get("results_contract") if isinstance(payload.get("results_contract"), dict) else {}
    stats = contract.get("statistics") if isinstance(contract.get("statistics"), dict) else {}
    if stats.get("population") is not None:
        return int(stats["population"])
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    if result.get("population") is not None:
        return int(result["population"])
    if contract.get("population") is not None:
        return int(contract["population"])
    return None


def _result_hash(payload: dict[str, Any]) -> str | None:
    contract = payload.get("results_contract") if isinstance(payload.get("results_contract"), dict) else {}
    repro = contract.get("reproducibility") if isinstance(contract.get("reproducibility"), dict) else {}
    if repro.get("result_hash"):
        return str(repro["result_hash"])
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    if result.get("result_hash"):
        return str(result["result_hash"])
    return None


def _lab_folder(question: dict[str, Any]) -> str:
    universe = question.get("universe") if isinstance(question.get("universe"), dict) else {}
    leagues = list(universe.get("leagues") or [])
    return sanitize_folder(str(leagues[0] if leagues else "NBA"))


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _can_reuse_control(slot: dict[str, Any], snapshot: dict[str, Any], *, enabled: bool) -> bool:
    if not enabled:
        return False
    if slot.get("slot_id") != "ITI-00":
        return False
    if slot.get("status") == "SKIPPED":
        return False
    if not snapshot:
        return False
    if slot.get("question_sha256") != snapshot.get("question_sha256"):
        return False
    if not snapshot.get("lab_id"):
        return False
    if not snapshot.get("phase_a_result_id"):
        return False
    if not snapshot.get("phase_b_result_id"):
        return False
    return True


def _reuse_control(slot: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    slot["status"] = "COMPLETE"
    slot["executed"] = False
    slot["reused_source"] = True
    slot["lab_id"] = snapshot.get("lab_id")
    slot["phase_a_result_id"] = snapshot.get("phase_a_result_id")
    slot["phase_b_result_id"] = snapshot.get("phase_b_result_id")
    slot["BASE_GRADE"] = snapshot.get("BASE_GRADE")
    slot["DEBASE_GRADE"] = snapshot.get("DEBASE_GRADE")
    slot["result_hash"] = snapshot.get("result_hash")
    slot["population"] = snapshot.get("population")
    slot["compile_ms"] = 0
    slot["execute_ms"] = 0
    slot["lab_ms"] = 0
    slot["base_ms"] = 0
    slot["debase_ms"] = 0
    slot["slot_ms"] = _elapsed_ms(started)
    return slot


def _process_warehouse(
    slot: dict[str, Any],
    *,
    strategy: str,
    cfg: RollerConfig | None,
    executed_ids: list[str],
    skip_precompile: bool,
) -> dict[str, Any]:
    if slot.get("status") == "SKIPPED":
        return slot
    question = slot["question"]
    if not skip_precompile:
        compile_started = time.perf_counter()
        compiled = compile_question(question, cfg)
        slot["compile_ms"] = _elapsed_ms(compile_started)
        status = str(compiled.get("status") or "")
        if status in _CLOSED:
            slot["status"] = status
            slot["skip_reason"] = f"compile_{status.lower()}"
            return slot
        if status != "READY":
            slot["status"] = "SKIPPED"
            slot["skip_reason"] = f"compile_{status.lower() or 'not_ready'}"
            return slot
    executed_ids.append(str(slot["slot_id"]))
    execute_started = time.perf_counter()
    payload = execute_question(question, cfg)
    slot["execute_ms"] = _elapsed_ms(execute_started)
    exec_status = str(payload.get("status") or "")
    if exec_status in _CLOSED:
        slot["status"] = exec_status
        slot["skip_reason"] = f"execute_{exec_status.lower()}"
        slot["executed"] = True
        return slot
    if exec_status != "READY" and payload.get("result") is None:
        slot["status"] = "SKIPPED"
        slot["skip_reason"] = f"execute_{exec_status.lower() or 'not_ready'}"
        slot["executed"] = True
        return slot
    slot["executed"] = True
    slot["population"] = _population(payload)
    slot["result_hash"] = _result_hash(payload)
    slot.update(plan_prices(question))
    lab_started = time.perf_counter()
    lab = save_variant_lab(
        name=sanitize_name(f"{strategy} {slot['slot_id']}"),
        payload=payload,
        question=question,
        folder=_lab_folder(question),
        cfg=cfg,
    )
    slot["lab_ms"] = _elapsed_ms(lab_started)
    slot["lab_id"] = lab.get("lab_id")
    return slot


def _process_superasi(
    slot: dict[str, Any],
    *,
    cfg: RollerConfig | None,
    monte_carlo_paths: int | None,
) -> dict[str, Any]:
    if slot.get("status") != "PENDING" or not slot.get("lab_id"):
        return slot
    base_started = time.perf_counter()
    base = run_base_variant(lab_id=str(slot["lab_id"]), cfg=cfg, monte_carlo_paths=monte_carlo_paths)
    slot["base_ms"] = _elapsed_ms(base_started)
    inspect_a = base.get("inspect") if isinstance(base.get("inspect"), dict) else base
    slot["phase_a_result_id"] = inspect_a.get("result_id") or base.get("result_id")
    slot["BASE_GRADE"] = inspect_a.get("BASE_GRADE")
    debase_started = time.perf_counter()
    debase = run_debase_variant(
        result_id=str(slot["phase_a_result_id"]),
        cfg=cfg,
        monte_carlo_paths=monte_carlo_paths,
    )
    slot["debase_ms"] = _elapsed_ms(debase_started)
    inspect_b = debase.get("inspect") if isinstance(debase.get("inspect"), dict) else debase
    slot["phase_b_result_id"] = inspect_b.get("result_id") or debase.get("result_id")
    slot["DEBASE_GRADE"] = inspect_b.get("DEBASE_GRADE")
    slot["BASE_GRADE"] = inspect_b.get("BASE_GRADE") or slot.get("BASE_GRADE")
    slot["status"] = "COMPLETE"
    return slot


def _process_slot(
    slot: dict[str, Any],
    *,
    strategy: str,
    cfg: RollerConfig | None,
    monte_carlo_paths: int | None,
    executed_ids: list[str],
    skip_precompile: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    if slot.get("status") in _TERMINAL:
        slot["slot_ms"] = slot.get("slot_ms") or _elapsed_ms(started)
        return slot
    if slot.get("status") in {"FAILED", "RUNNING"}:
        slot["status"] = "PENDING"
        slot["skip_reason"] = None
    if slot.get("lab_id") and slot.get("status") == "PENDING":
        slot = _process_superasi(slot, cfg=cfg, monte_carlo_paths=monte_carlo_paths)
        slot["slot_ms"] = _elapsed_ms(started)
        return slot
    slot = _process_warehouse(
        slot,
        strategy=strategy,
        cfg=cfg,
        executed_ids=executed_ids,
        skip_precompile=skip_precompile,
    )
    if slot.get("status") != "PENDING" or not slot.get("lab_id"):
        slot["slot_ms"] = _elapsed_ms(started)
        return slot
    slot = _process_superasi(slot, cfg=cfg, monte_carlo_paths=monte_carlo_paths)
    slot["slot_ms"] = _elapsed_ms(started)
    return slot


def _finish_job(job: dict[str, Any], *, root, started: float) -> dict[str, Any]:
    job["job_ms"] = _elapsed_ms(started)
    saved = save_job(job, root=root)
    write_timing_facts(saved, root=root)
    return saved


def run_job(
    run_id: str,
    *,
    root=None,
    cfg: RollerConfig | None = None,
    monte_carlo_paths: int | None = None,
    executed_ids: list[str] | None = None,
    orchestrator: str | None = None,
    reuse_control: bool | None = None,
) -> dict[str, Any]:
    job_started = time.perf_counter()
    job = load_job(run_id, root=root)
    if job.get("cancel_requested"):
        job["status"] = "CANCELLED"
        return _finish_job(job, root=root, started=job_started)
    mode = str(orchestrator or job.get("orchestrator") or DEFAULT_ORCHESTRATOR)
    if mode not in {ORCHESTRATOR_BASELINE, ORCHESTRATOR_OPTIMIZED}:
        raise JumpError("INVALID_ORCHESTRATOR", f"unknown ITI orchestrator: {mode}")
    skip_precompile = mode == ORCHESTRATOR_OPTIMIZED
    pipeline_superasi = mode == ORCHESTRATOR_OPTIMIZED
    reuse = bool(reuse_control) if reuse_control is not None else mode == ORCHESTRATOR_OPTIMIZED
    snapshot = job.get("source_snapshot") if isinstance(job.get("source_snapshot"), dict) else {}
    job["orchestrator"] = mode
    job["status"] = "RUNNING"
    save_job(job, root=root)
    seen = executed_ids if executed_ids is not None else []
    strategy = str(job.get("strategy_name") or "Untitled")
    lock = threading.Lock()
    pending: threading.Thread | None = None
    pending_error: list[BaseException] = []

    def persist(index: int, slot: dict[str, Any], *, done: bool) -> None:
        with lock:
            latest = load_job(run_id, root=root)
            job.update(latest)
            job["slots"][index] = slot
            if done:
                job["progress_done"] = max(int(job.get("progress_done") or 0), index + 1)
            save_job(job, root=root)

    def run_superasi_thread(index: int, slot: dict[str, Any], slot_started: float) -> None:
        try:
            finished = _process_superasi(slot, cfg=cfg, monte_carlo_paths=monte_carlo_paths)
            finished["slot_ms"] = _elapsed_ms(slot_started)
            persist(index, finished, done=True)
        except (JumpError, SuperasiError) as exc:
            slot["status"] = getattr(exc, "code", None) or "FAILED"
            slot["skip_reason"] = str(exc)
            slot["slot_ms"] = _elapsed_ms(slot_started)
            persist(index, slot, done=True)
            pending_error.append(exc)
        except Exception as exc:
            slot["status"] = "FAILED"
            slot["skip_reason"] = str(exc)
            slot["slot_ms"] = _elapsed_ms(slot_started)
            persist(index, slot, done=True)
            pending_error.append(exc)

    for index, slot in enumerate(job.get("slots") or []):
        latest = load_job(run_id, root=root)
        job.update(latest)
        if latest.get("cancel_requested"):
            if pending is not None:
                pending.join()
            job = load_job(run_id, root=root)
            job["status"] = "CANCELLED"
            return _finish_job(job, root=root, started=job_started)
        slot = job["slots"][index]
        if slot.get("status") in _TERMINAL:
            job["progress_done"] = max(int(job.get("progress_done") or 0), index + 1)
            save_job(job, root=root)
            continue
        if slot.get("status") in {"FAILED", "RUNNING"}:
            slot["status"] = "PENDING"
            slot["skip_reason"] = None
        slot_started = time.perf_counter()
        try:
            if _can_reuse_control(slot, snapshot, enabled=reuse):
                job["slots"][index] = _reuse_control(slot, snapshot)
                job["progress_done"] = index + 1
                save_job(job, root=root)
                continue
            if not pipeline_superasi:
                job["slots"][index] = _process_slot(
                    slot,
                    strategy=strategy,
                    cfg=cfg,
                    monte_carlo_paths=monte_carlo_paths,
                    executed_ids=seen,
                    skip_precompile=skip_precompile,
                )
                job["progress_done"] = index + 1
                save_job(job, root=root)
                continue
            if slot.get("lab_id") and slot.get("status") == "PENDING":
                persist(index, slot, done=False)
                if pending is not None:
                    pending.join()
                    pending = None
                pending = threading.Thread(
                    target=run_superasi_thread,
                    args=(index, slot, slot_started),
                    daemon=True,
                    name=f"jump-iti-sa-{index}",
                )
                pending.start()
                continue
            warehoused = _process_warehouse(
                slot,
                strategy=strategy,
                cfg=cfg,
                executed_ids=seen,
                skip_precompile=skip_precompile,
            )
            if warehoused.get("status") != "PENDING" or not warehoused.get("lab_id"):
                warehoused["slot_ms"] = _elapsed_ms(slot_started)
                persist(index, warehoused, done=True)
                continue
            persist(index, warehoused, done=False)
            if pending is not None:
                pending.join()
                pending = None
            pending = threading.Thread(
                target=run_superasi_thread,
                args=(index, warehoused, slot_started),
                daemon=True,
                name=f"jump-iti-sa-{index}",
            )
            pending.start()
        except (JumpError, SuperasiError) as exc:
            job["slots"][index]["status"] = getattr(exc, "code", None) or "FAILED"
            job["slots"][index]["skip_reason"] = str(exc)
            job["slots"][index]["slot_ms"] = _elapsed_ms(slot_started)
            job["progress_done"] = index + 1
            save_job(job, root=root)
        except Exception as exc:
            job["slots"][index]["status"] = "FAILED"
            job["slots"][index]["skip_reason"] = str(exc)
            job["slots"][index]["slot_ms"] = _elapsed_ms(slot_started)
            job["progress_done"] = index + 1
            save_job(job, root=root)
    if pending is not None:
        pending.join()
    job = load_job(run_id, root=root)
    if job.get("status") != "CANCELLED":
        job["status"] = "COMPLETE"
    return _finish_job(job, root=root, started=job_started)


def start_run(
    *,
    debase_result_id: str,
    root=None,
    cfg: RollerConfig | None = None,
    background: bool = True,
    monte_carlo_paths: int | None = None,
    executed_ids: list[str] | None = None,
    orchestrator: str | None = None,
    reuse_control: bool | None = None,
) -> dict[str, Any]:
    mode = str(orchestrator or DEFAULT_ORCHESTRATOR)
    if mode not in {ORCHESTRATOR_BASELINE, ORCHESTRATOR_OPTIMIZED}:
        raise JumpError("INVALID_ORCHESTRATOR", f"unknown ITI orchestrator: {mode}")
    latest = latest_job(debase_result_id=debase_result_id, root=root)
    run_id = ""
    if latest:
        status = str(latest.get("status") or "")
        if status == "COMPLETE":
            return latest
        if status in _RESUME:
            run_id = str(latest.get("run_id") or "")
    if run_id:
        job = load_job(run_id, root=root)
        job["orchestrator"] = mode
        job["cancel_requested"] = False
        if job.get("status") == "FAILED":
            job["status"] = "PENDING"
        save_job(job, root=root)
    else:
        source = load_source(debase_result_id=debase_result_id, cfg=cfg)
        slots = build_catalog(source["question"])
        job = create_job(source=source, slots=slots, root=root)
        job["orchestrator"] = mode
        save_job(job, root=root)
        run_id = str(job["run_id"])
    kwargs = {
        "run_id": run_id,
        "root": root,
        "cfg": cfg,
        "monte_carlo_paths": monte_carlo_paths,
        "executed_ids": executed_ids,
        "orchestrator": mode,
        "reuse_control": reuse_control,
    }
    with _ACTIVE_LOCK:
        if run_id in _ACTIVE_RUNS:
            return public_job(load_job(run_id, root=root))
        _ACTIVE_RUNS.add(run_id)

    def _guarded(**kw: Any) -> dict[str, Any]:
        try:
            return run_job(**kw)
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE_RUNS.discard(str(kw["run_id"]))

    if background:
        thread = threading.Thread(
            target=_guarded,
            kwargs=kwargs,
            daemon=True,
            name=f"jump-iti-{run_id[:8]}",
        )
        thread.start()
        return public_job(load_job(run_id, root=root))
    try:
        finished = run_job(**kwargs)
        return public_job(finished)
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_RUNS.discard(run_id)
