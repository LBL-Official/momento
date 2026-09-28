"""Systimo library root under research/systimo/."""

from __future__ import annotations

import os
from pathlib import Path

from roller.paths import find_root, momento_root


def library_root(start: Path | None = None) -> Path:
    env = os.environ.get("SYSTIMO_ROOT")
    if env:
        return Path(env).resolve()
    return momento_root(find_root(start)) / "research" / "systimo"


def registry_dir(root: Path | None = None) -> Path:
    return (root or library_root()) / "registry"


def state_dir(root: Path | None = None) -> Path:
    return (root or library_root()) / "state"


def queries_dir(root: Path | None = None) -> Path:
    return (root or library_root()) / "queries"


def artifacts_dir(root: Path | None = None) -> Path:
    return (root or library_root()) / "artifacts"


def actions_dir(root: Path | None = None) -> Path:
    return (root or library_root()) / "actions"


def agents_dir(root: Path | None = None) -> Path:
    return (root or library_root()) / "agents"


def generated_dir(root: Path | None = None) -> Path:
    return (root or library_root()) / "generated"
