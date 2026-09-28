#!/usr/bin/env python3
"""Queue 2024-25 NBA PBP ingest to start after 2025-26 finishes.

Does not interrupt the running 2025-26 watchdog. Polls until that season's
PBP files hit the matched-game target, waits for the 2025-26 ingest process
to exit so we do not double-hit stats.nba.com, then runs 2024-25 (full NBA
schedule — no Kalshi warehouse exists for that season yet).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/Users/user/Desktop/Momento")
PY = Path("/tmp/momento-nba-venv/bin/python")
INGEST = ROOT / "apps/nba-data/scripts/nba_pbp_overnight_ingest.py"
DATA = ROOT / "Backtesting Suite/Data/NBA"
QUEUE_PATH = DATA / "pbp_ingest_queue.json"
LOG = DATA / "pbp_ingest_queue.log"
PID_PATH = DATA / "pbp_ingest_queue.pid"

SEASONS = [
    {
        "warehouse_season": "2025-2026",
        "stats_season": "2025-26",
        "wait_pbp_dir": str(DATA / "2025-2026/warehouse/raw/nba_stats/pbp_v3"),
        "wait_target": 1352,
        "run": False,
    },
    {
        "warehouse_season": "2024-2025",
        "stats_season": "2024-25",
        "wait_pbp_dir": str(DATA / "2024-2025/warehouse/raw/nba_stats/pbp_v3"),
        "wait_target": None,
        "run": True,
    },
]
MAX_RESTARTS = 40
POLL_S = 20


def qlog(msg: str) -> None:
    line = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + msg
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def pbp_count(path: str) -> int:
    p = Path(path)
    if not p.exists():
        return 0
    return sum(1 for f in p.glob("*.json") if f.stat().st_size > 200)


def ingest_running() -> bool:
    try:
        out = subprocess.check_output(["pgrep", "-f", "nba_pbp_overnight_ingest.py"], text=True)
    except subprocess.CalledProcessError:
        return False
    pids = [int(x) for x in out.split() if x.strip().isdigit()]
    return any(pid != os.getpid() for pid in pids)


def write_queue(state: dict) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(QUEUE_PATH)


def run_season(item: dict) -> int:
    wh = item["warehouse_season"]
    st = item["stats_season"]
    pbp_dir = Path(item["wait_pbp_dir"])
    log_path = DATA / wh / "warehouse/manifests/nba/pbp_ingest.nohup.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    restarts = 0
    while restarts <= MAX_RESTARTS:
        status_path = DATA / wh / "warehouse/manifests/nba/pbp_ingest_status.json"
        on_disk = pbp_count(str(pbp_dir))
        target = item["wait_target"]
        if status_path.exists():
            try:
                status = json.loads(status_path.read_text())
                if status.get("done") is True:
                    qlog(f"{wh} already done on_disk={on_disk}")
                    return 0
                if target is None and status.get("targets"):
                    target = int(status["targets"])
            except Exception:
                pass
        if target is not None and on_disk >= target:
            qlog(f"{wh} target reached on_disk={on_disk} target={target}")
            return 0
        qlog(f"spawn {wh} stats={st} on_disk={on_disk} restart={restarts}")
        with log_path.open("a") as logf:
            proc = subprocess.Popen(
                [
                    "caffeinate",
                    "-dims",
                    str(PY),
                    "-u",
                    str(INGEST),
                    "--warehouse-season",
                    wh,
                    "--stats-season",
                    st,
                ],
                stdout=logf,
                stderr=logf,
                stdin=subprocess.DEVNULL,
                cwd=str(ROOT),
                start_new_session=True,
            )
            rc = proc.wait()
        on_disk = pbp_count(str(pbp_dir))
        qlog(f"{wh} ingest exit rc={rc} on_disk={on_disk}")
        if status_path.exists():
            try:
                status = json.loads(status_path.read_text())
                if status.get("done") is True or (
                    status.get("remaining") == 0 and int(status.get("targets") or 0) > 0
                ):
                    return 0
            except Exception:
                pass
        restarts += 1
        time.sleep(min(60, 5 * restarts))
    qlog(f"{wh} gave up after {restarts} restarts")
    return 1


def main() -> int:
    if PID_PATH.exists():
        try:
            old = int(PID_PATH.read_text().strip())
            os.kill(old, 0)
            if old != os.getpid():
                qlog(f"queue runner already pid={old}")
                return 0
        except (ValueError, OSError):
            pass
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(os.getpid()))
    state = {
        "queued": [s["warehouse_season"] for s in SEASONS],
        "current": None,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "2024-2025 has no Kalshi warehouse yet; PBP is full NBA stats schedule.",
    }
    write_queue(state)
    try:
        for item in SEASONS:
            wh = item["warehouse_season"]
            state["current"] = wh
            write_queue(state)
            if not item["run"]:
                target = item["wait_target"]
                qlog(f"waiting for {wh} pbp>={target}")
                while pbp_count(item["wait_pbp_dir"]) < target:
                    time.sleep(POLL_S)
                    n = pbp_count(item["wait_pbp_dir"])
                    if n % 50 < 5:
                        qlog(f"wait {wh} on_disk={n}/{target}")
                qlog(f"{wh} files complete; waiting for ingest process to exit")
                while ingest_running():
                    time.sleep(POLL_S)
                qlog(f"{wh} ingest idle; next season")
                continue
            rc = run_season(item)
            if rc != 0:
                state["failed"] = wh
                write_queue(state)
                return rc
        state["current"] = None
        state["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        write_queue(state)
        qlog("queue complete")
        return 0
    finally:
        try:
            PID_PATH.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    if os.environ.get("PBP_QUEUE_INNER") != "1":
        env = os.environ.copy()
        env["PBP_QUEUE_INNER"] = "1"
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as wf:
            child = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve())],
                stdin=subprocess.DEVNULL,
                stdout=wf,
                stderr=wf,
                cwd="/",
                env=env,
                start_new_session=True,
            )
        print(f"detached queue runner pid={child.pid}", flush=True)
        raise SystemExit(0)
    raise SystemExit(main())
