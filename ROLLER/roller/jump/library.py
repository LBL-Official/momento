"""Empty Jump disk library. Not a run store until Jump A."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_ENV = "JUMP_LIBRARY_ROOT"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_library_root() -> Path:
    env = os.environ.get(_ENV)
    if env:
        return Path(env)
    return repo_root() / "research" / "jump" / "library"


def list_items(*, root: Path | None = None) -> list[dict[str, Any]]:
    base = root or default_library_root()
    if not base.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for child in sorted(base.iterdir()):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            out.append({"id": child.name})
    return out
