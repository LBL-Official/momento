#!/usr/bin/env python3
"""Detach the overnight PBP ingest from the Cursor process group.

Uses a new session + caffeinate so macOS idle sleep and Cursor shell
teardown cannot kill the download. Restarts the ingest if it exits
before the 1352-game target is on disk (resumable).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/Users/user/Desktop/Momento")
PY = Path("/tmp/momento-nba-venv/bin/python")
INGEST = ROOT / "apps/nba-data/scripts/nba_pbp_overnight_ingest.py"
WAREHOUSE = ROOT / "Backtesting Suite/Data/NBA/2025-2026/warehouse"
LOG = WAREHOUSE / "manifests/nba/pbp_ingest.nohup.log"
WATCH_LOG = WAREHOUSE / "manifests/nba/pbp_ingest.watchdog.log"
PID_PATH = WAREHOUSE / "manifests/nba/pbp_ingest.watchdog.pid"
PBP_DIR = WAREHOUSE / "raw/nba_stats/pbp_v3"
TARGET = 1352
MAX_RESTARTS = 30


def wlog(msg: str) -> None:
    line = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + msg
    print(line, flush=True)
    WATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with WATCH_LOG.open("a") as f:
        f.write(line + "\n")


def pbp_count() -> int:
    if not PBP_DIR.exists():
        return 0
    return sum(1 for p in PBP_DIR.glob("*.json") if p.stat().st_size > 200)


def already_running() -> bool:
    if not PID_PATH.exists():
        return False
    try:
        pid = int(PID_PATH.read_text().strip())
    except ValueError:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return pid != os.getpid()


def main() -> int:
    if already_running():
        wlog(f"watchdog already running pid={PID_PATH.read_text().strip()}")
        return 0
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(os.getpid()))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    restarts = 0
    wlog(f"watchdog start pid={os.getpid()} target={TARGET} on_disk={pbp_count()}")
    try:
        while pbp_count() < TARGET and restarts <= MAX_RESTARTS:
            n = pbp_count()
            wlog(f"spawn ingest on_disk={n} restart={restarts}")
            with LOG.open("a") as logf:
                proc = subprocess.Popen(
                    ["caffeinate", "-dims", str(PY), "-u", str(INGEST)],
                    stdout=logf,
                    stderr=logf,
                    stdin=subprocess.DEVNULL,
                    cwd=str(ROOT),
                    start_new_session=True,
                )
                wlog(f"ingest pid={proc.pid} caffeinate-wrapped")
                rc = proc.wait()
            n2 = pbp_count()
            wlog(f"ingest exit rc={rc} on_disk={n2}")
            if n2 >= TARGET:
                wlog("target reached")
                return 0
            restarts += 1
            time.sleep(min(60, 5 * restarts))
        wlog(f"watchdog stop on_disk={pbp_count()} restarts={restarts}")
        return 0 if pbp_count() >= TARGET else 1
    finally:
        try:
            PID_PATH.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    # Daemonize: fork twice, new session, so Cursor shell teardown cannot reap us.
    if os.environ.get("PBP_WATCHDOG_INNER") != "1":
        env = os.environ.copy()
        env["PBP_WATCHDOG_INNER"] = "1"
        WATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
        with WATCH_LOG.open("a") as wf:
            child = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve())],
                stdin=subprocess.DEVNULL,
                stdout=wf,
                stderr=wf,
                cwd="/",
                env=env,
                start_new_session=True,
            )
        print(f"detached watchdog pid={child.pid}", flush=True)
        raise SystemExit(0)
    raise SystemExit(main())
