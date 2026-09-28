#!/usr/bin/env python3
"""Finish unfinished Momento warehouses, then link with existing ROLLER logic.

Research only. Does not submit orders. Does not start W9. Does not change
live FIRST01 / 80/81/83/89 / Risk.

Kalshi download uses the sport CLIs (resumable COMPLETE jobs skipped).
PBP uses the existing sport ingest scripts. Linking uses:
  - basketball: scripts/update_roller.py → identity + canonicalize_pbp/candles/markets
  - tennis: python -m roller.tennis.ingest (Kalshi↔MCP identity join)
  - MLB: existing mlb_canonical_catchup.sh after Foundation backfill
         (this script does not start a second backfill and does not run
         roller.mlb.ingest while ingest.lock is held)

Does not invent yes_bid, L2, tip-from-open, or official W from PBP.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/Users/user/Desktop/Momento")
ROLLER = ROOT / "ROLLER"
PY = ROLLER / ".venv" / "bin" / "python"
DATA = ROOT / "Backtesting Suite" / "Data"
LOG_DIR = ROOT / "logs" / "warehouse-finish"
STATUS = LOG_DIR / "status.json"
PIPELINE_LOG = LOG_DIR / "pipeline.log"

BIN = {
    "NBA": ROOT / "target" / "release" / "nba-data",
    "NCAAB": ROOT / "target" / "release" / "ncaab-data",
    "WNBA": ROOT / "target" / "release" / "wnba-data",
    "ATP": ROOT / "target" / "release" / "momento-tennis-data",
    "WTA": ROOT / "target" / "release" / "momento-tennis-data",
}

PBP = {
    "WNBA": ROOT / "apps" / "wnba-data" / "scripts" / "wnba_pbp_espn_ingest.py",
    "NCAAB": ROOT / "apps" / "ncaab-data" / "scripts" / "ncaab_pbp_espn_ingest.py",
    "MLB": ROOT / "apps" / "mlb-data" / "scripts" / "mlb_pbp_statsapi_ingest.py",
}


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with PIPELINE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def write_status(payload: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATUS.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATUS)


def running(pattern: str) -> bool:
    # pgrep -f can match its own argv. Require a real worker in the listing.
    r = subprocess.run(["pgrep", "-fl", pattern], capture_output=True, text=True)
    for line in (r.stdout or "").splitlines():
        if "pgrep" in line.split():
            continue
        if pattern in line:
            return True
    return False


def foundation_lock_held() -> bool:
    return (ROOT / "Backtesting Suite" / "Foundation" / "Ingest" / "locks" / "ingest.lock").is_file()


def run(argv: list[str], *, cwd: Path | None = None, timeout: int | None = None) -> int:
    log("RUN " + " ".join(argv))
    proc = subprocess.run(argv, cwd=str(cwd or ROOT), timeout=timeout)
    log(f"EXIT {proc.returncode} {' '.join(argv[:6])}")
    return proc.returncode


def rust_download(sport: str, extra: list[str]) -> int:
    bin_path = BIN[sport]
    if not bin_path.is_file():
        log(f"MISSING_BINARY {bin_path}")
        return 1
    argv = [
        "/usr/bin/caffeinate",
        "-dimsu",
        str(bin_path),
        "download-all",
        "--season",
        "2025-2026",
        "--max-workers",
        "4",
        "--rps",
        "4",
        "--data-dir",
        str(DATA),
        *extra,
    ]
    return run(argv)


def pgrep_tennis(tour: str) -> bool:
    return running(f"momento-tennis-data download-all --tour {tour}")


def start_tennis_if_needed(tour: str) -> None:
    if pgrep_tennis(tour):
        log(f"TENNIS_{tour.upper()}_ALREADY_RUNNING")
        return
    pidfile = ROOT / "logs" / "tennis" / f"{tour}-ingest.pid"
    log_path = ROOT / "logs" / "tennis" / f"{tour}-ingest.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        "/usr/bin/caffeinate",
        "-dimsu",
        str(BIN["ATP"]),
        "download-all",
        "--tour",
        tour,
        "--season",
        "2025-2026",
        "--max-workers",
        "4",
        "--rps",
        "4",
        "--data-dir",
        str(DATA),
    ]
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"\nWAREHOUSE_FINISH_START ts={datetime.now(timezone.utc).isoformat()} tour={tour}\n")
        proc = subprocess.Popen(
            argv,
            cwd=str(ROOT),
            stdout=fh,
            stderr=fh,
            start_new_session=True,
        )
    pidfile.write_text(f"{proc.pid}\n")
    log(f"TENNIS_{tour.upper()}_PID {proc.pid}")


def wait_tennis() -> None:
    log("WAIT_TENNIS_START")
    while pgrep_tennis("atp") or pgrep_tennis("wta") or running("momento-tennis-data"):
        time.sleep(60)
    log("WAIT_TENNIS_DONE")


def link_basketball() -> int:
    worst = 0
    jobs = [
        (["NBA"], "2025-2026"),
        (["WNBA"], "2025"),
        (["WNBA"], "2026"),
        (["NCAAB"], "2025-2026"),
    ]
    for sports, season in jobs:
        argv = [
            str(PY),
            "-u",
            str(ROLLER / "scripts" / "update_roller.py"),
            "--root",
            str(ROLLER),
            "--season",
            season,
            "--skip-validate",
        ]
        for sport in sports:
            argv.extend(["--sport", sport])
        rc = run(argv, cwd=ROLLER)
        worst = rc if rc != 0 else worst
    return worst


def link_tennis() -> int:
    return run(
        [
            str(PY),
            "-u",
            "-m",
            "roller.tennis.ingest",
            "--window-end",
            utc_today(),
        ],
        cwd=ROLLER,
    )


def rebuild_indexes(leagues: list[str]) -> int:
    worst = 0
    for league in leagues:
        bases = ["TRADABLE_YES_BID"]
        if league in {"MLB", "ATP", "WTA"}:
            bases.append("LAST_TRADE_PRINT")
        season = "2025" if league == "WNBA" else "2025-2026"
        # WNBA 2026 is a second campaign on the same warehouse tree.
        seasons = ["2025", "2026"] if league == "WNBA" else [season]
        for seas in seasons:
            for basis in bases:
                argv = [
                    str(PY),
                    "-u",
                    "-m",
                    "roller.research_query.indexes",
                    "build",
                    "--league",
                    league,
                    "--season",
                    seas,
                    "--basis",
                    basis,
                ]
                rc = run(argv, cwd=ROLLER)
                if rc != 0:
                    worst = rc
    return worst


def main() -> int:
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    os.environ.setdefault("RUST_LOG", "info")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = utc_today()
    write_status(
        {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "phase": "start",
            "window_end": today,
            "mlb_backfill_already_running": running("momento-research-ingest backfill"),
            "foundation_lock": foundation_lock_held(),
        }
    )
    log(f"WAREHOUSE_FINISH_START window_end={today}")
    log(
        "FACTS basketball_kalshi_pending=0 atp_pending_candles~1317 "
        "mlb_backfill=leave_running nba_pbp=complete"
    )

    # 1. Tennis Kalshi — ATP is unfinished; WTA rediscover is cheap.
    start_tennis_if_needed("atp")
    start_tennis_if_needed("wta")

    # 2. PBP catch-up (different hosts than Kalshi tennis).
    if running("mlb_pbp_statsapi_ingest"):
        log("MLB_PBP_ALREADY_RUNNING")
        mlb_pbp_rc = 0
    else:
        mlb_pbp_rc = run(
            [
                str(PY),
                "-u",
                str(PBP["MLB"]),
                "--window-start",
                "2025-04-16",
                "--window-end",
                today,
            ]
        )
    wnba_pbp_rc = run([str(PY), "-u", str(PBP["WNBA"])])
    ncaab_pbp_rc = run([str(PY), "-u", str(PBP["NCAAB"])])

    # 3. Wait for tennis ticker ingest, then identity-join into ROLLER.
    wait_tennis()
    tennis_rc = link_tennis()

    # 4. Basketball: warehouse Kalshi already COMPLETE. Write missing
    #    kalshi_markets.csv and refresh PBP/candle canonical via existing update.
    hoop_rc = link_basketball()

    # 5. Observation indexes so Confirm & Run stays indexed. Not FIRST80.
    idx_rc = rebuild_indexes(["NBA", "NCAAB", "WNBA", "ATP", "WTA"])

    record = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "phase": "done",
        "window_end": today,
        "exit": {
            "mlb_pbp": mlb_pbp_rc,
            "wnba_pbp": wnba_pbp_rc,
            "ncaab_pbp": ncaab_pbp_rc,
            "tennis_ingest": tennis_rc,
            "basketball_update": hoop_rc,
            "indexes": idx_rc,
        },
        "skipped": [
            "second MLB Foundation backfill (already running)",
            "roller.mlb.ingest while ingest.lock held (catchup owns it)",
            "NBA/NCAAB/WNBA Kalshi download-all (dry-run pending=0)",
            "NBA PBP (1352/1352 COMPLETE)",
            "NBA/NCAAB 2026-2027 (season not started; NOT_APPLICABLE)",
        ],
        "live_trading_changed": False,
        "w9_started": False,
    }
    write_status(record)
    log("WAREHOUSE_FINISH_DONE " + json.dumps(record["exit"]))
    if any(v not in (0, 2) for v in record["exit"].values()):
        # ESPN PBP returns 2 when unmatched/ambiguous remain; that is not a crash.
        hard = {k: v for k, v in record["exit"].items() if v not in (0, 2)}
        if hard:
            log("HARD_FAILURES " + json.dumps(hard))
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
