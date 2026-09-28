"""AUTO ROLLER VERIFY — guardian of the optimized engine.

Level 1–3: warehouse / index integrity.
Level 4–5: reference vs optimized + frozen goldens.
A hash/N change is FAILED. Goldens are not auto-updated.
"""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path
from typing import Any

from roller.auto_roller.history import new_run_id, now_utc, write_run
from roller.auto_roller.locking import job_lock
from roller.auto_roller.report import write_report
from roller.config import RollerConfig
from roller.research_query.hashing import CODE_VERSION
from roller.research_query.indexes.builder import index_root
from roller.research_query.indexes.manifest import MANIFEST_NAME
from roller.research_query.indexes.reader import IndexUnavailable, verify_index_checksums
from roller.research_query.models import BASIS_LAST_TRADE, BASIS_TRADABLE, OPERATION_SEMANTICS_VERSION
from roller.warehouse.catalog import catalog
from roller.warehouse.gap_audit import run_audit


INDEX_LEAVES = (
    ("NBA", "2025-2026", BASIS_TRADABLE),
    ("NCAAB", "2025-2026", BASIS_TRADABLE),
    ("WNBA", "2025", BASIS_TRADABLE),
    ("WNBA", "2026", BASIS_TRADABLE),
    ("MLB", "2025-2026", BASIS_LAST_TRADE),
    ("MLB", "2025-2026", BASIS_TRADABLE),
    ("ATP", "2025-2026", BASIS_TRADABLE),
    ("WTA", "2025-2026", BASIS_TRADABLE),
    ("ATP", "2025-2026", BASIS_LAST_TRADE),
    ("WTA", "2025-2026", BASIS_LAST_TRADE),
)


def _check_indexes(
    cfg: RollerConfig,
    *,
    checksums: bool = True,
    leaves: tuple[tuple[str, str, str], ...] | None = None,
    root_for: Any | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    resolve = root_for or (
        lambda sport, season, basis: index_root(cfg, sport, season, league=sport, basis=basis)
    )
    for sport, season, basis in leaves or INDEX_LEAVES:
        root = resolve(sport, season, basis)
        man = root / MANIFEST_NAME
        if not man.is_file():
            out.append({"leaf": f"{sport}/{season}/{basis}", "ok": False, "reason": "index_absent"})
            continue
        try:
            if checksums:
                verify_index_checksums(root)
            bars = root / "bars.parquet"
            out.append(
                {
                    "leaf": f"{sport}/{season}/{basis}",
                    "ok": bars.is_file(),
                    "reason": None if bars.is_file() else "bars_missing",
                }
            )
        except IndexUnavailable as exc:
            out.append({"leaf": f"{sport}/{season}/{basis}", "ok": False, "reason": str(exc)})
        except Exception as exc:  # noqa: BLE001 — report, do not hide
            out.append({"leaf": f"{sport}/{season}/{basis}", "ok": False, "reason": str(exc)})
    return out


def _semantic_sentinels() -> list[dict[str, Any]]:
    from roller.research_query import cache as rq_cache
    from roller.research_query.execute import execute_question
    from roller.research_query.reference_engine import execute_reference, identities
    from tests.mlb_golden import GOLDEN_DRAFT, load_golden

    checks: list[dict[str, Any]] = []
    golden = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "research_query_increment1_goldens.json"
    # parents[2] is roller/ — wrong. auto_roller is roller/auto_roller so parents[2]=ROLLER
    golden = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "research_query_increment1_goldens.json"
    if not golden.is_file():
        checks.append({"name": "increment2_goldens_file", "ok": False, "reason": "missing fixture"})
        return checks
    by_id = {q["query_id"]: q for q in json.loads(golden.read_text())["queries"]}
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
            "dataSources": ["nba_api"],
        },
        "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 60, "period": "Q2"}],
        "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
    }
    rq_cache.clear()
    opt = execute_question({"draft": draft})
    rq_cache.clear()
    ref = execute_reference({"draft": draft}, clear_cache=True)
    expect = by_id["first_60_q2"]["population_n"]
    same = identities(ref) == identities(opt)
    n_ok = ref["summary"]["population_n"] == expect == opt["summary"]["population_n"]
    checks.append(
        {
            "name": "increment2_first_60_q2",
            "ok": bool(same and n_ok),
            "reference_n": ref["summary"]["population_n"],
            "optimized_n": opt["summary"]["population_n"],
            "expected_n": expect,
            "mode_ref": (ref.get("performance") or {}).get("execution_mode"),
            "mode_opt": (opt.get("performance") or {}).get("execution_mode"),
        }
    )
    exp = load_golden()["expected"]
    rq_cache.clear()
    mlb_opt = execute_question({"draft": GOLDEN_DRAFT})
    rq_cache.clear()
    mlb_ref = execute_reference({"draft": GOLDEN_DRAFT}, clear_cache=True)
    mlb_ok = (
        mlb_ref["summary"]["population_n"] == exp["n"] == 554
        and mlb_opt["summary"]["population_n"] == 554
        and identities(mlb_ref) == identities(mlb_opt)
    )
    checks.append(
        {
            "name": "mlb_554",
            "ok": bool(mlb_ok),
            "reference_n": mlb_ref["summary"]["population_n"],
            "optimized_n": mlb_opt["summary"]["population_n"],
            "expected_n": 554,
        }
    )
    return checks


def run_verify(
    cfg: RollerConfig | None = None,
    *,
    semantic: bool = True,
    checksums: bool = True,
    missed_schedule: bool = False,
    leaves: tuple[tuple[str, str, str], ...] | None = None,
    root_for: Any | None = None,
) -> dict[str, Any]:
    cfg = cfg or RollerConfig()
    started = now_utc()
    t0 = time.perf_counter()
    run_id = new_run_id()
    errors: list[str] = []
    warnings: list[str] = []
    if missed_schedule:
        warnings.append("MISSED_SCHEDULE")
    try:
        with job_lock(cfg):
            indexes = _check_indexes(cfg, checksums=checksums, leaves=leaves, root_for=root_for)
            audit = run_audit(cfg)
            sentinels: list[dict[str, Any]] = []
            if semantic:
                sentinels = _semantic_sentinels()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{exc}\n{traceback.format_exc()}")
        indexes, audit, sentinels = [], {}, []
    failed = [c for c in indexes if not c.get("ok")] + [c for c in sentinels if not c.get("ok")]
    status = "FAILED" if errors or failed else "COMPLETE"
    finished = now_utc()
    record = {
        "run_id": run_id,
        "job_type": "verify",
        "display": "AUTO ROLLER VERIFY",
        "started_at": started,
        "finished_at": finished,
        "duration_s": round(time.perf_counter() - t0, 3),
        "status": status,
        "code_version": CODE_VERSION,
        "operation_semantics_version": OPERATION_SEMANTICS_VERSION,
        "indexes": indexes,
        "sentinels": sentinels,
        "gaps_found": sum(
            1
            for s in (audit.get("sports") or [])
            for d in (s.get("datasets") or {}).values()
            if d.get("status") in {"MISSING", "PARTIAL", "INVALID"}
        ),
        "errors": errors,
        "warnings": warnings,
    }
    path = write_run(record, cfg)
    report_path = write_report(f"verify_{run_id}.json", record, cfg)
    record["report_path"] = str(report_path)
    record["history_path"] = str(path)
    return record


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="python -m roller.auto_roller.verify")
    p.add_argument("--fast", action="store_true", help="Level 1–3 only (no warehouse sentinels)")
    p.add_argument("--missed-schedule", action="store_true")
    args = p.parse_args(argv)
    rec = run_verify(semantic=not args.fast, missed_schedule=args.missed_schedule)
    print(json.dumps({k: rec[k] for k in rec if k not in {"indexes"}}, indent=2))
    return 0 if rec["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
