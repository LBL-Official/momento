"""Read-only warehouse resolution. Never mkdir. Never write."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PACKAGE_ROOT.parents[1]


def data_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit)
    env = os.environ.get("MOMENTO_RESEARCH_DATA_DIR")
    if env:
        return Path(env)
    return REPO_ROOT / "Backtesting Suite" / "Data"


def derived_root(root: Path, league: str, season: str) -> Path:
    sport = "nba" if league.upper() == "NBA" else "ncaab"
    return Path(root) / league.upper() / season / "warehouse" / "derived" / sport / "terminal_efficiency"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())
