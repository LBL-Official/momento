"""AUTO ROLLER INGEST — wrap existing ingest. Do not invent a Kalshi client.

Idempotent. Lock held. Does not publish invalid parquet. Does not start a
second NCAAB download-all. Does not run mlb.ingest while Foundation ingest.lock
is held.
"""

from __future__ import annotations

import json
import subprocess
import time
import traceback
from pathlib import Path
from typing import Any

from roller.auto_roller.history import new_run_id, now_utc, write_run
from roller.auto_roller.locking import job_lock
from roller.auto_roller.report import write_report
from roller.config import RollerConfig
from roller.paths import momento_root
from roller.research_query.hashing import CODE_VERSION
from roller.warehouse.gap_audit import run_audit


def _foundation_lock_held() -> bool:
    from roller.config import RollerConfig

    lock = (
        momento_root(RollerConfig().root)
        / "Backtesting Suite"
        / "Foundation"
        / "Ingest"
        / "locks"
        / "ingest.lock"
    )
    return lock.is_file()


def _pgrep(pattern: str) -> bool:
    r = subprocess.run(["pgrep", "-f", pattern], capture_output=True)
    return r.returncode == 0


def run_ingest(
    cfg: RollerConfig | None = None,
    *,
    rebuild_indexes: bool = True,
    missed_schedule: bool = False,
) -> dict[str, Any]:
    cfg = cfg or RollerConfig()
    started = now_utc()
    t0 = time.perf_counter()
    run_id = new_run_id()
    errors: list[str] = []
    warnings: list[str] = []
    actions: list[dict[str, Any]] = []
    if missed_schedule:
        warnings.append("MISSED_SCHEDULE")
    try:
        with job_lock(cfg):
            if _foundation_lock_held() or _pgrep("momento-research-ingest"):
                warnings.append("FOUNDATION_INGEST_ACTIVE")
                actions.append(
                    {
                        "step": "mlb_canonical",
                        "status": "SKIPPED",
                        "reason": "ingest.lock or backfill running — will not overlap",
                    }
                )
            if _pgrep("ncaab-data download-all") or _pgrep("ncaab-ingest"):
                warnings.append("NCAAB_INGEST_ACTIVE")
                actions.append(
                    {
                        "step": "ncaab",
                        "status": "SKIPPED",
                        "reason": "existing NCAAB LaunchAgent/process running",
                    }
                )
            if rebuild_indexes and not errors:
                cmd = [
                    str(cfg.root / ".venv" / "bin" / "python"),
                    "-m",
                    "roller.research_query.indexes",
                    "build-all",
                ]
                if not Path(cmd[0]).is_file():
                    cmd[0] = "python3"
                # Index rebuild is the safe idempotent publish of derived facts.
                proc = subprocess.run(
                    cmd,
                    cwd=str(cfg.root),
                    capture_output=True,
                    text=True,
                    timeout=3600,
                )
                actions.append(
                    {
                        "step": "rq_index_build_all",
                        "status": "INGESTED" if proc.returncode == 0 else "FAILED",
                        "returncode": proc.returncode,
                        "stderr_tail": (proc.stderr or "")[-2000:],
                    }
                )
                if proc.returncode != 0:
                    errors.append("index rebuild failed")
            audit = run_audit(cfg)
            actions.append({"step": "gap_audit", "status": "COMPLETE"})
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{exc}\n{traceback.format_exc()}")
        audit = {}
    status = "FAILED" if errors else ("PARTIAL" if warnings else "ALREADY_CURRENT")
    if any(a.get("status") == "INGESTED" for a in actions) and not errors:
        status = "INGESTED" if not warnings else "PARTIAL"
    finished = now_utc()
    record = {
        "run_id": run_id,
        "job_type": "ingest",
        "display": "AUTO ROLLER INGEST",
        "started_at": started,
        "finished_at": finished,
        "duration_s": round(time.perf_counter() - t0, 3),
        "status": status,
        "code_version": CODE_VERSION,
        "actions": actions,
        "errors": errors,
        "warnings": warnings,
        "gaps_found": sum(
            1
            for s in (audit.get("sports") or [])
            for d in (s.get("datasets") or {}).values()
            if d.get("status") == "MISSING"
        ),
    }
    path = write_run(record, cfg)
    report_path = write_report(f"ingest_{run_id}.json", record, cfg)
    record["report_path"] = str(report_path)
    record["history_path"] = str(path)
    return record


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="python -m roller.auto_roller.ingest")
    p.add_argument("--skip-indexes", action="store_true")
    p.add_argument("--missed-schedule", action="store_true")
    args = p.parse_args(argv)
    rec = run_ingest(rebuild_indexes=not args.skip_indexes, missed_schedule=args.missed_schedule)
    print(json.dumps(rec, indent=2))
    return 0 if rec["status"] not in {"FAILED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
