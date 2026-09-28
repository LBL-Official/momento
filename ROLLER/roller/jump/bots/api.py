"""Jump B HTTP handlers. Control plane only. Browser is not the engine."""

from __future__ import annotations

from typing import Any

from roller.jump.bots.pipeline import (
    create_bot,
    draft_bot,
    get_bot,
    list_control_plane,
    list_iti_commit_desk,
    patch_profile,
    promote_bot,
)
from roller.jump.bots.profile import read_avatar
from roller.jump.bots.trades import bot_trades


def handle_list(*, root=None, cfg=None) -> dict[str, Any]:
    return list_control_plane(root=root, cfg=cfg, observe=False)


def handle_iti_commits(*, cfg=None) -> dict[str, Any]:
    return list_iti_commit_desk(cfg=cfg)


def handle_get(bot_id: str, *, root=None) -> dict[str, Any]:
    return get_bot(bot_id, root=root)


def handle_draft(body: dict[str, Any] | None = None, *, root=None, cfg=None) -> dict[str, Any]:
    return draft_bot(body, root=root, cfg=cfg)


def handle_create(body: dict[str, Any] | None = None, *, root=None, cfg=None) -> dict[str, Any]:
    return create_bot(body, root=root, cfg=cfg)


def handle_production(bot_id: str, body: dict[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    return promote_bot(bot_id, body, root=root)


def handle_profile(bot_id: str, body: dict[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    return patch_profile(bot_id, body, root=root)


def handle_avatar(bot_id: str, *, root=None) -> tuple[bytes, str]:
    return read_avatar(bot_id, root=root)


def handle_trades(bot_id: str, *, root=None) -> dict[str, Any]:
    return bot_trades(bot_id, root=root)
