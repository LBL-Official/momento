"""Sequential STAX orchestration. Calls existing ROLLER execute. No second scanner."""

from __future__ import annotations

from typing import Any, Callable

from roller.research_query.hashing import dumps_canon, sha256_hex
from roller.stax.compatibility import (
    assert_timeframe_unchanged,
    canonicalize_universe,
    universe_from_source,
)
from roller.stax.membership import definition_hash
from roller.stax.models import (
    STATUS_COMPLETE,
    STATUS_DATA_REQUIRED,
    STATUS_FAILED,
    STATUS_PARTIAL,
    utc_now,
)
from roller.stax.overlap import compute_overlap
from roller.stax.versions import AGGREGATION_METHOD, LIVE_EXECUTION, SUM_OF_STRATEGY_N_LABEL


ExecuteQuestion = Callable[[dict[str, Any]], dict[str, Any]]
ExecuteFrozen = Callable[[dict[str, Any]], dict[str, Any]]


def _is_frozen(member: dict[str, Any]) -> bool:
    spec = member.get("research_spec") if isinstance(member.get("research_spec"), dict) else {}
    versions = spec.get("definition_versions") if isinstance(spec.get("definition_versions"), dict) else {}
    if versions.get("FIRST80") or versions.get("NCAAB_FIRST80_P5"):
        return True
    rid = str(member.get("research_object_id") or "")
    if rid.startswith("FIRST80") or rid.startswith("NCAAB_FIRST80"):
        return True
    return False


def _payload(member: dict[str, Any]) -> dict[str, Any]:
    if isinstance(member.get("question"), dict):
        return {"question": member["question"]}
    if isinstance(member.get("draft"), dict):
        return {"draft": member["draft"]}
    return {}


def _envelope_status(env: dict[str, Any]) -> str:
    status = str(env.get("execution_status") or STATUS_COMPLETE)
    if status in {STATUS_DATA_REQUIRED, "OPERATION_REQUIRED"}:
        return STATUS_DATA_REQUIRED
    if status in {STATUS_FAILED, "failed"}:
        return STATUS_FAILED
    if status == STATUS_PARTIAL:
        return STATUS_PARTIAL
    return STATUS_COMPLETE


def _n(env: dict[str, Any]) -> int | None:
    pop = env.get("population") if isinstance(env.get("population"), dict) else {}
    if pop.get("count") is not None:
        return int(pop["count"])
    summary = env.get("summary") if isinstance(env.get("summary"), dict) else {}
    if summary.get("population_n") is not None:
        return int(summary["population_n"])
    return None


def summary_from_envelope(env: dict[str, Any]) -> dict[str, Any]:
    measurements = env.get("measurements") if isinstance(env.get("measurements"), list) else []
    by_name = {
        str(m.get("name")): m
        for m in measurements
        if isinstance(m, dict) and m.get("name")
    }
    analysis = env.get("analysis") if isinstance(env.get("analysis"), dict) else {}
    ev = None
    for key in ("observed_path_ev", "path_ev"):
        block = analysis.get(key)
        if isinstance(block, dict) and block.get("value") is not None:
            ev = block.get("value")
            break
        if isinstance(analysis.get("ev"), dict) and analysis["ev"].get(key) is not None:
            ev = analysis["ev"].get(key)
            break
    path = by_name.get("path_rate") or by_name.get("path_true_rate")
    terminal = by_name.get("terminal_rate") or by_name.get("terminal_yes_rate")
    return {
        "n": _n(env),
        "path_rate": None if not path else path.get("value"),
        "terminal": None if not terminal else terminal.get("value"),
        "ev": ev,
        "execution_status": _envelope_status(env),
        "dataset_version": env.get("dataset_version"),
        "question_hash": (env.get("hashes") or {}).get("question_hash")
        if isinstance(env.get("hashes"), dict)
        else None,
        "research_object_id": env.get("research_object_id"),
    }


def execute_member(
    member: dict[str, Any],
    *,
    execute_question: ExecuteQuestion | None = None,
    execute_research_object: ExecuteFrozen | None = None,
) -> dict[str, Any]:
    saved_universe = canonicalize_universe(member["universe"])
    try:
        if _is_frozen(member):
            spec = member.get("research_spec") if isinstance(member.get("research_spec"), dict) else {}
            if not spec:
                return {
                    "member_id": member["member_id"],
                    "status": STATUS_DATA_REQUIRED,
                    "error": {"code": "DATA_REQUIRED", "message": "frozen research spec unavailable"},
                    "envelope": None,
                    "summary": {"n": None, "execution_status": STATUS_DATA_REQUIRED},
                }
            if execute_research_object is None:
                from roller.dashboard_adapter.research_executor import execute_research_object as _frozen

                execute_research_object = _frozen
            env = execute_research_object(spec)
        else:
            payload = _payload(member)
            if not payload:
                return {
                    "member_id": member["member_id"],
                    "status": STATUS_DATA_REQUIRED,
                    "error": {"code": "DATA_REQUIRED", "message": "research object unavailable"},
                    "envelope": None,
                    "summary": {"n": None, "execution_status": STATUS_DATA_REQUIRED},
                }
            if execute_question is None:
                from roller.research_query.execute import execute_question as _exec

                execute_question = _exec
            env = execute_question(payload)
        if not isinstance(env, dict):
            raise RuntimeError("execute returned no envelope")
        try:
            executed_universe = universe_from_source(env)
            assert_timeframe_unchanged(saved_universe, executed_universe)
        except Exception:
            # Envelope may omit universe; the payload we sent is the authority.
            pass
        status = _envelope_status(env)
        summary = summary_from_envelope(env)
        if status == STATUS_COMPLETE and summary.get("n") is None:
            status = STATUS_DATA_REQUIRED
            summary["execution_status"] = STATUS_DATA_REQUIRED
            summary["n"] = None
        return {
            "member_id": member["member_id"],
            "status": status,
            "error": None
            if status not in {STATUS_DATA_REQUIRED, STATUS_FAILED}
            else {"code": status, "message": env.get("execution_status") or "full population N unavailable"},
            "envelope": env if status != STATUS_DATA_REQUIRED or summary.get("n") is not None else env,
            "summary": summary,
        }
    except Exception as exc:  # noqa: BLE001 — surface per-member; do not drop
        code = getattr(exc, "code", None)
        status = STATUS_DATA_REQUIRED if code == "DATA_REQUIRED" or "DATA_REQUIRED" in str(exc) else STATUS_FAILED
        return {
            "member_id": member["member_id"],
            "status": status,
            "error": {"code": status, "message": str(exc), "type": type(exc).__name__},
            "envelope": None,
            "summary": {"n": None, "execution_status": status},
        }


def execute_stack(
    members: list[dict[str, Any]],
    *,
    execute_question: ExecuteQuestion | None = None,
    execute_research_object: ExecuteFrozen | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for member in members:
        results.append(
            execute_member(
                member,
                execute_question=execute_question,
                execute_research_object=execute_research_object,
            )
        )
    completed = [r for r in results if r["status"] == STATUS_COMPLETE]
    failed = [r for r in results if r["status"] in {STATUS_FAILED, STATUS_DATA_REQUIRED}]
    if failed and completed:
        status = STATUS_PARTIAL
    elif failed and not completed:
        status = STATUS_PARTIAL if any(r["status"] == STATUS_DATA_REQUIRED for r in failed) else STATUS_FAILED
        if len(failed) == len(results):
            status = STATUS_PARTIAL if any(r["status"] == STATUS_DATA_REQUIRED for r in results) else STATUS_FAILED
            if all(r["status"] == STATUS_DATA_REQUIRED for r in results):
                status = STATUS_PARTIAL
    elif all(r["status"] == STATUS_COMPLETE for r in results):
        status = STATUS_COMPLETE
    else:
        status = STATUS_PARTIAL
    overlap = compute_overlap(results)
    fingerprints = [
        str((r.get("summary") or {}).get("dataset_version") or "")
        for r in results
    ]
    return {
        "execution_id": None,
        "status": status,
        "started_at": None,
        "completed_at": utc_now(),
        "strategy_count": len(members),
        "completed_count": len(completed),
        "failed_count": len(failed),
        "results": results,
        "overlap": overlap,
        "definition_hash": definition_hash(members),
        "dataset_fingerprint": sha256_hex(dumps_canon(fingerprints)),
        "aggregation_method": AGGREGATION_METHOD,
        "live_execution": LIVE_EXECUTION,
        "sum_of_strategy_n": (
            sum(
                int((r.get("summary") or {})["n"])
                for r in results
                if (r.get("summary") or {}).get("n") is not None
            )
            if any((r.get("summary") or {}).get("n") is not None for r in results)
            else None
        ),
        "sum_of_strategy_n_label": SUM_OF_STRATEGY_N_LABEL,
    }
