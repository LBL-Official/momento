"""Bot identity profile. Not a trading engine. Does not write live.toml."""

from __future__ import annotations

import base64
import re
from typing import Any

from roller.jump.bots.factory import FACTORY
from roller.jump.bots.store import (
    append_event,
    avatar_path,
    bot_dir,
    ensure_identity,
    load_bot,
    public_bot,
    save_bot,
)
from roller.jump.errors import JumpError

_HANDLE = re.compile(r"^[a-z0-9._]{1,32}$")
_AVATAR_EXT = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
_MAX_AVATAR = 512 * 1024


def _handle_from_name(name: str, bot_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", (name or "").lower())[:24]
    return slug or str(bot_id).replace("-", "")[:12] or "bot"


def update_profile(bot_id: str, body: dict[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    body = body or {}
    bot = ensure_identity(load_bot(bot_id, root=root))
    profile = dict(bot.get("profile") or {})
    settings = dict(bot.get("settings") or {})

    if "name" in body or "display_name" in body:
        name = str(body.get("display_name") or body.get("name") or "").strip()
        if name:
            bot["name"] = name
            profile["display_name"] = name

    if "handle" in body:
        handle = str(body.get("handle") or "").strip().lstrip("@").lower()
        if handle and not _HANDLE.match(handle):
            raise JumpError("INVALID_PROFILE", "handle must be 1–32 characters: a-z, 0-9, . or _")
        if handle:
            profile["handle"] = handle

    if "bio" in body:
        profile["bio"] = str(body.get("bio") or "")[:500]
    if "purpose" in body:
        profile["purpose"] = str(body.get("purpose") or "")[:500]
    if "notes" in body:
        bot["notes"] = str(body.get("notes") or "")

    incoming_settings = body.get("settings") if isinstance(body.get("settings"), dict) else {}
    if "bankroll_cents" in body or "bankroll_cents" in incoming_settings:
        raw = body.get("bankroll_cents", incoming_settings.get("bankroll_cents"))
        try:
            cents = int(raw)
        except (TypeError, ValueError) as exc:
            raise JumpError("INVALID_PROFILE", "bankroll_cents must be an integer") from exc
        if cents <= 0:
            raise JumpError("INVALID_PROFILE", "bankroll_cents must be positive")
        production = bot.get("environment") == "PRODUCTION" or bot.get("kind") == "grandfathered"
        current = int(settings.get("bankroll_cents") or FACTORY["bankroll_cents"])
        if production and cents != current:
            raise JumpError(
                "OPERATION_REQUIRED",
                "demo bankroll override is not applied to production or Bot One",
            )
        settings["bankroll_cents"] = cents

    production = bot.get("environment") == "PRODUCTION" or bot.get("kind") == "grandfathered"
    sizing = incoming_settings if incoming_settings else body
    if any(key in body or key in incoming_settings for key in ("sizing_mode", "allocation_bps", "amount_cents", "max_position_budget_cents")):
        if production:
            raise JumpError(
                "OPERATION_REQUIRED",
                "demo allocation override is not applied to production or Bot One",
            )
        mode = str(sizing.get("sizing_mode") or settings.get("sizing_mode") or "FIXED_CENTS").strip().upper()
        if mode not in {"FIXED_CENTS", "PCT_CURRENT", "PCT_WEEKLY"}:
            raise JumpError("INVALID_PROFILE", "sizing_mode must be FIXED_CENTS, PCT_CURRENT, or PCT_WEEKLY")
        settings["sizing_mode"] = mode
        if "allocation_bps" in body or "allocation_bps" in incoming_settings:
            try:
                bps = int(sizing.get("allocation_bps"))
            except (TypeError, ValueError) as exc:
                raise JumpError("INVALID_PROFILE", "allocation_bps must be an integer") from exc
            if bps < 1 or bps > 10_000:
                raise JumpError("INVALID_PROFILE", "allocation_bps must be 1..=10000")
            settings["allocation_bps"] = bps
        if mode == "FIXED_CENTS":
            raw = sizing.get("amount_cents", sizing.get("max_position_budget_cents"))
            try:
                amount = int(raw)
            except (TypeError, ValueError) as exc:
                raise JumpError("INVALID_PROFILE", "FIXED_CENTS requires amount_cents") from exc
            if amount <= 0:
                raise JumpError("INVALID_PROFILE", "amount_cents must be positive")
            settings["amount_cents"] = amount
            settings["max_position_budget_cents"] = amount
    for key in (
        "max_daily_entries",
        "max_daily_wins",
        "max_daily_losses",
        "max_daily_win_cents",
        "max_daily_loss_cents",
    ):
        if key not in body and key not in incoming_settings:
            continue
        if production:
            raise JumpError(
                "OPERATION_REQUIRED",
                "demo limit override is not applied to production or Bot One",
            )
        raw = body.get(key, incoming_settings.get(key))
        if raw is None or raw == "":
            settings[key] = None
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise JumpError("INVALID_PROFILE", f"{key} must be an integer") from exc
        if value <= 0:
            raise JumpError("INVALID_PROFILE", f"{key} must be > 0")
        settings[key] = value

    avatar_b64 = body.get("avatar_base64") or body.get("avatar")
    ext = str(body.get("avatar_ext") or "png").strip().lower().lstrip(".")
    if avatar_b64:
        if ext not in _AVATAR_EXT:
            raise JumpError("INVALID_PROFILE", "avatar_ext must be png, jpg, or webp")
        try:
            raw = base64.b64decode(str(avatar_b64), validate=True)
        except (ValueError, TypeError) as exc:
            raise JumpError("INVALID_PROFILE", "avatar_base64 is not valid base64") from exc
        if len(raw) > _MAX_AVATAR:
            raise JumpError("INVALID_PROFILE", "avatar must be 512 KiB or smaller")
        folder = bot_dir(bot_id, root=root)
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"avatar.{ext}"
        (folder / filename).write_bytes(raw)
        profile["avatar"] = filename

    if not profile.get("handle"):
        profile["handle"] = _handle_from_name(str(bot.get("name") or ""), bot_id)
    if not profile.get("display_name"):
        profile["display_name"] = str(bot.get("name") or "Untitled bot")

    bot["profile"] = profile
    bot["settings"] = settings
    save_bot(bot, root=root)
    append_event(bot_id, {"kind": "profile_updated"}, root=root)
    return public_bot(ensure_identity(bot))


def read_avatar(bot_id: str, *, root=None) -> tuple[bytes, str]:
    bot = load_bot(bot_id, root=root)
    path = avatar_path(bot, root=root)
    if path is None or not path.is_file():
        raise JumpError("BOT_NOT_FOUND", f"avatar not found: {bot_id}")
    ext = path.suffix.lstrip(".").lower()
    return path.read_bytes(), _AVATAR_EXT.get(ext, "application/octet-stream")


def default_handle(name: str, bot_id: str) -> str:
    return _handle_from_name(name, bot_id)
