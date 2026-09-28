#!/usr/bin/env python3
"""Double-fork the warehouse finish pipeline under caffeinate.

Survives Cursor teardown and macOS idle sleep. Research only.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path("/Users/user/Desktop/Momento")
LOG_DIR = ROOT / "logs" / "warehouse-finish"
LOG = LOG_DIR / "daemon.log"
PIDFILE = LOG_DIR / "daemon.pid"
SCRIPT = ROOT / "scripts" / "warehouse_finish_pipeline.py"
PY = ROOT / "ROLLER" / ".venv" / "bin" / "python"


def daemonize() -> None:
    if os.fork() > 0:
        os._exit(0)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    os.umask(0o022)
    os.chdir(ROOT)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0)
    fd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    if devnull > 2:
        os.close(devnull)
    if fd > 2:
        os.close(fd)


def main() -> int:
    if not PY.is_file():
        print(f"missing {PY}", flush=True)
        return 1
    if not SCRIPT.is_file():
        print(f"missing {SCRIPT}", flush=True)
        return 1
    daemonize()
    PIDFILE.write_text(f"{os.getpid()}\n")
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    os.environ.setdefault("RUST_LOG", "info")
    os.environ["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    argv = [
        "/usr/bin/caffeinate",
        "-dimsu",
        str(PY),
        "-u",
        str(SCRIPT),
    ]
    print(f"DAEMON pid={os.getpid()} sid={os.getsid(0)} exec={' '.join(argv)}", flush=True)
    os.execv(argv[0], argv)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
