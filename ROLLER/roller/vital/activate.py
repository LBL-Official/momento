"""Vital demo activate / retry attach. Not ENABLE_LIVE_TRADING. MLB 001 is refused."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.vital.bots import get_bot
from roller.vital.demo_attach import attach_demo, attach_result
from roller.vital.errors import VitalError
from roller.vital.store import append_event, save_bot
from roller.vital.versions import BOT_ID, DEMO_ACTIVATION_CONFIRMATION, LIVE_CONFIRMATION


def handle_activate(bot_id: str, body: dict[str, Any] | None = None, *, root: Path | None = None) -> dict[str, Any]:
    body = body or {}
    token = str(body.get("confirmation") or "").strip()
    if token == LIVE_CONFIRMATION:
        raise VitalError(
            "REJECTED",
            "ENABLE_LIVE_TRADING is the engine live gate, not a Vital demo activate token",
        )
    bot = get_bot(bot_id, root=root)
    resolved = str(bot.get("bot_id") or bot_id)
    if resolved == BOT_ID or bot.get("kind") == "grandfathered":
        raise VitalError("REJECTED", "MLB 001 uses the existing control plane; this path is for Jump ITI bots")
    if bot.get("kind") != "iti":
        raise VitalError("BOT_NOT_FOUND", f"bot not found: {bot_id}")
    desired = str(bot.get("desired_environment") or "DEMO").upper()
    if desired == "PRODUCTION":
        bot["activation"] = "PROMOTE_REQUIRED"
        save_bot(bot, root=root)
        append_event(resolved, {"kind": "activate_promote_required"}, root=root)
        return {
            "bot_id": resolved,
            "jump_bot_id": bot.get("jump_bot_id"),
            "environment": "DEMO",
            "desired_environment": "PRODUCTION",
            "activation": "PROMOTE_REQUIRED",
            "status": bot.get("status") or "CREATED",
            "http_200_not_running": True,
            "live_armed_confirmed": False,
            "detail": "PRODUCTION desired still requires the existing Jump promote gate",
        }
    if token and token != DEMO_ACTIVATION_CONFIRMATION:
        raise VitalError("REJECTED", f"demo attach accepts empty confirmation or {DEMO_ACTIVATION_CONFIRMATION}")
    attached = attach_demo(bot, vital_root=root)
    out = attach_result(attached)
    out["detail"] = (
        "Vital re-attached DEMO. RUNNING_DEMO only after the isolated unit is active. "
        "Kalshi Demo book observe is separate. Browser does not submit."
    )
    return out
