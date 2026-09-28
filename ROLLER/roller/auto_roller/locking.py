"""Single-writer lock. Two Auto Roller jobs must not publish together."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from roller.config import RollerConfig


def lock_path(cfg: RollerConfig | None = None) -> Path:
    cfg = cfg or RollerConfig()
    return cfg.root / "data" / ".cache" / "auto_roller" / "auto_roller.lock"


@contextmanager
def job_lock(cfg: RollerConfig | None = None):
    path = lock_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = path.open("a+")
    try:
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        fh.close()
        raise RuntimeError(f"AUTO ROLLER lock held: {path}") from exc
    fh.seek(0)
    fh.truncate()
    fh.write(str(os.getpid()))
    fh.flush()
    try:
        yield path
    finally:
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()
