"""Vital bot identity. MLB 001 first. No crate move."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.vital.errors import VitalError
from roller.vital.models import factory_snapshot, resolve_bot_id
from roller.vital.mlb_001.boundary import boundary_record
from roller.vital.store import list_bot_ids, load_bot, pointers_path, read_json, seed_mlb_001
from roller.vital.versions import (
    BOT_ID,
    CAVEATS,
    HONESTY,
    LIVE_EXECUTION,
)


def public_bot(bot: dict[str, Any], *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out = dict(bot)
    if str(out.get("bot_id") or "") == BOT_ID or out.get("kind") == "grandfathered":
        out["factory"] = factory_snapshot()
    else:
        out["factory"] = None
    out["honesty"] = dict(HONESTY)
    out["caveats"] = list(CAVEATS)
    out["live_execution"] = LIVE_EXECUTION
    if extra:
        out.update(extra)
    return out


def ensure_mlb_001(*, root: Path | None = None) -> dict[str, Any]:
    return seed_mlb_001(root=root)


def get_bot(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    ensure_mlb_001(root=root)
    resolved = resolve_bot_id(bot_id)
    if resolved == BOT_ID:
        return load_bot(BOT_ID, root=root)
    try:
        return load_bot(resolved, root=root)
    except VitalError as exc:
        raise VitalError("BOT_NOT_FOUND", f"bot not found: {bot_id}") from exc


def list_bots(*, root: Path | None = None) -> list[dict[str, Any]]:
    ensure_mlb_001(root=root)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for bot_id in list_bot_ids(root=root):
        rec = load_bot(bot_id, root=root)
        out.append(rec)
        seen.add(bot_id)
    if BOT_ID not in seen:
        out.insert(0, load_bot(BOT_ID, root=root))
    return out


def get_bot_boundary(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    ensure_mlb_001(root=root)
    resolved = resolve_bot_id(bot_id)
    if resolved != BOT_ID:
        raise VitalError("BOT_NOT_FOUND", f"bot not found: {bot_id}")
    on_disk = read_json(pointers_path(BOT_ID, root=root))
    return on_disk if on_disk is not None else boundary_record()
