"""Dashboard notes/expand and read-only event logs. Not a trading log."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from roller.jump.bots.store import default_bots_root, events_path, list_bots
from roller.jump.library import repo_root

_ENV = "JUMP_DASHBOARD_ROOT"


def default_dashboard_root() -> Path:
    env = os.environ.get(_ENV)
    if env:
        return Path(env)
    return repo_root() / "research" / "jump" / "dashboard"


def notes_path(*, root: Path | None = None) -> Path:
    return (root or default_dashboard_root()) / "notes.json"


def load_notes(*, root: Path | None = None) -> dict[str, Any]:
    path = notes_path(root=root)
    if not path.is_file():
        return {"expand_open": False, "selected_bot_id": None, "notes": ""}
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"expand_open": False, "selected_bot_id": None, "notes": ""}
    if not isinstance(rec, dict):
        return {"expand_open": False, "selected_bot_id": None, "notes": ""}
    return rec


def read_events(bot_id: str, *, bots_root: Path | None = None) -> list[dict[str, Any]]:
    path = events_path(bot_id, root=bots_root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            rec["bot_id"] = bot_id
            rows.append(rec)
    return rows


def list_logs(*, bots_root: Path | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bot in list_bots(root=bots_root):
        rows.extend(read_events(str(bot["bot_id"]), bots_root=bots_root))
    rows.sort(key=lambda row: str(row.get("ts") or ""), reverse=True)
    return rows
