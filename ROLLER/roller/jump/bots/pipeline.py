"""Draft, create (DEMO), observe, promote. Jump is not the engine."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig
from roller.jump.bots import deploy
from roller.jump.bots.factory import factory_snapshot
from roller.jump.bots.source_iti import list_iti_commits, load_iti_commit
from roller.jump.bots.status import apply_observation, live_gate_ok
from roller.jump.bots.profile import update_profile
from roller.jump.bots.store import (
    append_event,
    create_draft,
    ensure_bot_one,
    list_bots,
    load_bot,
    public_bot,
    save_bot,
)
from roller.jump.bots.versions import BOT_ONE_ID, FACTORY_ID, LIVE_CONFIRMATION as JUMP_LIVE_CONFIRMATION
from roller.jump.errors import JumpError


def _refresh(bot: dict[str, Any], *, root=None, observe: bool = True) -> dict[str, Any]:
    from roller.jump.bots.engine import hydrate_research_engine

    if hydrate_research_engine(bot):
        save_bot(bot, root=root)
    if observe:
        apply_observation(bot)
        save_bot(bot, root=root)
    out = public_bot(bot)
    deploy = bot.get("deploy") if isinstance(bot.get("deploy"), dict) else {}
    if deploy.get("status"):
        out["deploy_status"] = deploy["status"]
    return out


def list_iti_commit_desk(*, cfg: RollerConfig | None = None) -> dict[str, Any]:
    """Committed `_ITI` folders only. Disk. Not Vital. Not a host observe."""
    items = list_iti_commits(cfg)
    return {"results": items, "n": len(items)}


def list_control_plane(*, root=None, cfg: RollerConfig | None = None, observe: bool = True) -> dict[str, Any]:
    ensure_bot_one(root=root)
    commits = list_iti_commits(cfg)
    if observe:
        try:
            from roller.vital.register import backfill_jump_demo_bots

            backfill_jump_demo_bots(jump_root=root)
        except Exception:
            pass
    bots = []
    for row in list_bots(root=root):
        raw = load_bot(str(row["bot_id"]), root=root)
        bots.append(_refresh(raw, root=root, observe=observe))
    return {
        "bots": bots,
        "factory": factory_snapshot(),
        "iti_commits": commits,
        "bot_one_id": BOT_ONE_ID,
    }


def get_bot(bot_id: str, *, root=None) -> dict[str, Any]:
    ensure_bot_one(root=root)
    bot = load_bot(bot_id, root=root)
    return _refresh(bot, root=root)


def draft_bot(body: dict[str, Any] | None = None, *, root=None, cfg: RollerConfig | None = None) -> dict[str, Any]:
    body = body or {}
    folder = str(body.get("iti_folder") or body.get("strategy_folder") or "").strip()
    iti = load_iti_commit(folder, cfg=cfg)
    name = str(body.get("name") or iti.get("strategy_name") or "Untitled bot")
    notes = str(body.get("notes") or "")
    return create_draft(name=name, iti=iti, notes=notes, root=root)


def _live_factory_held(*, root=None) -> bool:
    ensure_bot_one(root=root)
    one = apply_observation(load_bot(BOT_ONE_ID, root=root))
    return bool(one.get("live_armed_confirmed") and one.get("environment") == "PRODUCTION")


def create_bot(body: dict[str, Any] | None = None, *, root=None, cfg: RollerConfig | None = None) -> dict[str, Any]:
    body = body or {}
    draft_id = str(body.get("draft_id") or body.get("bot_id") or "").strip()
    if draft_id == BOT_ONE_ID:
        raise JumpError("DUPLICATE_LIVE_FACTORY", "Bot One already exists; do not recreate the live MLB factory")
    if draft_id:
        bot = load_bot(draft_id, root=root)
        folder = str(body.get("iti_folder") or body.get("strategy_folder") or "").strip()
        if folder:
            iti = load_iti_commit(folder, cfg=cfg)
            bot["strategy_folder"] = iti.get("folder")
            bot["strategy_fingerprint"] = iti.get("strategy_fingerprint")
            bot["iti_version"] = iti.get("iti_version")
            bot["slot_id"] = iti.get("slot_id")
            bot["engine"] = iti.get("engine")
            bot["engine_pointer"] = (iti.get("engine") or {}).get("engine_pointer")
            bot["strategy_pointer"] = (iti.get("engine") or {}).get("strategy_pointer")
            bot["sport"] = (iti.get("engine") or {}).get("sport")
            bot["factory_id"] = None
            bot["iti"] = {
                "folder": iti.get("folder"),
                "run_id": iti.get("run_id"),
                "slot_id": iti.get("slot_id"),
                "strategy_name": iti.get("strategy_name"),
                "entry_cents": iti.get("entry_cents"),
                "win_cents": iti.get("win_cents"),
                "loss_cents": iti.get("loss_cents"),
                "question": iti.get("question"),
                "BASE_GRADE": iti.get("BASE_GRADE"),
                "DEBASE_GRADE": iti.get("DEBASE_GRADE"),
                "metadata_sha256": iti.get("metadata_sha256"),
                "iti_is_not_live_signal": True,
            }
        if str(body.get("name") or "").strip():
            bot["name"] = str(body["name"]).strip()
        if "notes" in body:
            bot["notes"] = str(body.get("notes") or "")
    else:
        bot = draft_bot(body, root=root, cfg=cfg)
        bot = load_bot(str(bot["bot_id"]), root=root)
    if bot.get("kind") == "grandfathered":
        raise JumpError("DUPLICATE_LIVE_FACTORY", "grandfathered Bot One is not created through this path")
    if not bot.get("strategy_folder"):
        raise JumpError("DATA_REQUIRED", "ITI strategy folder is required")
    if str(body.get("confirmation") or "").strip() == JUMP_LIVE_CONFIRMATION:
        raise JumpError(
            "REJECTED",
            "ENABLE_LIVE_TRADING is the engine live gate, not a Jump create token",
        )
    desired = str(body.get("desired_environment") or body.get("environment") or "DEMO").strip().upper()
    if desired not in {"DEMO", "PRODUCTION"}:
        desired = "DEMO"
    settings_sent = isinstance(body.get("settings"), dict) or any(
        key in body
        for key in (
            "bankroll_cents",
            "sizing_mode",
            "allocation_bps",
            "amount_cents",
            "max_daily_entries",
            "max_daily_wins",
            "max_daily_losses",
            "max_daily_win_cents",
            "max_daily_loss_cents",
        )
    )
    if settings_sent:
        update_profile(str(bot["bot_id"]), body, root=root)
        bot = load_bot(str(bot["bot_id"]), root=root)
    bot["environment"] = "DEMO"
    bot["desired_environment"] = desired
    bot["live_armed_confirmed"] = False
    bot["status"] = "CREATED"
    bot["aws_runtime_id"] = None
    save_bot(bot, root=root)
    from roller.vital.register import register_iti_bot

    vital = register_iti_bot(bot, jump_root=root)
    bot = load_bot(str(bot["bot_id"]), root=root)
    bot["vital_bot_id"] = vital.get("bot_id")
    bot["activation"] = vital.get("activation") or bot.get("activation")
    bot["attach"] = vital.get("attach")
    bot["deploy"] = vital.get("deploy") or bot.get("deploy")
    save_bot(bot, root=root)
    append_event(
        str(bot["bot_id"]),
        {
            "kind": "created_demo",
            "activation": bot.get("activation"),
            "vital_bot_id": bot.get("vital_bot_id"),
            "unit_started": bool((bot.get("attach") or {}).get("unit_started")),
        },
        root=root,
    )
    out = _refresh(bot, root=root)
    out["activation"] = bot.get("activation")
    out["desired_environment"] = desired
    out["vital_bot_id"] = bot.get("vital_bot_id")
    out["attach"] = bot.get("attach")
    deploy = bot.get("deploy") if isinstance(bot.get("deploy"), dict) else {}
    out["deploy_status"] = deploy.get("status")
    return out


def patch_profile(bot_id: str, body: dict[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    ensure_bot_one(root=root)
    return update_profile(bot_id, body, root=root)


def promote_bot(bot_id: str, body: dict[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    body = body or {}
    if bot_id == BOT_ONE_ID:
        raise JumpError("DUPLICATE_LIVE_FACTORY", "Bot One is the existing live host; do not promote a second copy")
    if not live_gate_ok(body):
        raise JumpError(
            "LIVE_GATE_INCOMPLETE",
            "production requires mode=live, live.enabled=true, and confirmation ENABLE_LIVE_TRADING",
        )
    bot = load_bot(bot_id, root=root)
    if bot.get("kind") == "grandfathered":
        raise JumpError("DUPLICATE_LIVE_FACTORY", "grandfathered Bot One is observed, not promoted")
    if bot.get("environment") != "DEMO" or bot.get("status") == "DRAFT":
        raise JumpError("COMMIT_NOT_READY", "only a DEMO bot can be promoted")
    if bot.get("factory_id") == FACTORY_ID and _live_factory_held(root=root):
        raise JumpError(
            "DUPLICATE_LIVE_FACTORY",
            "Bot One already holds the live MLB factory; a second production factory is refused",
        )
    if bot.get("kind") == "iti" or (bot.get("engine") or {}).get("kind") == "research_iti":
        from roller.jump.bots.live_host import iti_live_toml, start_iti_live_unit
        from roller.vital.register import apply_iti_promote
        from roller.vital.research_engine import strategy_view

        frame = strategy_view(bot)
        if frame.get("spec_status") == "SPEC_MISMATCH":
            raise JumpError("REJECTED", "ITI prices do not match the committed ROLLER/SuperASI spec")
        try:
            iti_live_toml(bot)
        except JumpError:
            raise
        started = start_iti_live_unit({**bot, "bot_id": bot.get("vital_bot_id") or bot["bot_id"]})
        vital_id = str(bot.get("vital_bot_id") or "")
        if vital_id:
            apply_iti_promote(vital_id, started)
        if started.get("active"):
            bot["environment"] = "PRODUCTION"
            bot["status"] = "RUNNING"
            bot["activation"] = "RUNNING"
            bot["live_armed_confirmed"] = True
            bot["aws_runtime_id"] = started.get("aws_runtime_id")
            bot["deploy"] = {
                "status": "RUNNING",
                "unit": started.get("unit"),
                "kalshi_env": "production",
                "second_live_engine": False,
                "note": "isolated momento-live@ unit; not momento-live.service",
            }
            append_event(bot_id, {"kind": "promoted_iti_live", "unit": started.get("unit")}, root=root)
        else:
            bot["environment"] = "DEMO"
            bot["activation"] = "DEPLOY_REQUIRED"
            bot["live_armed_confirmed"] = False
            bot["aws_runtime_id"] = None
            bot["deploy"] = {
                "status": "DEPLOY_REQUIRED",
                "reason": started.get("reason"),
                "secret_missing": bool(started.get("secret_missing")),
            }
            append_event(bot_id, {"kind": "promote_blocked", "code": "DEPLOY_REQUIRED"}, root=root)
        save_bot(bot, root=root)
        out = _refresh(bot, root=root)
        out["activation"] = bot.get("activation")
        out["deploy_status"] = (bot.get("deploy") or {}).get("status")
        out["attach"] = bot.get("attach")
        return out
    try:
        promoted = deploy.promote_runtime(bot)
    except JumpError as exc:
        if exc.code != "DEPLOY_REQUIRED":
            raise
        append_event(bot_id, {"kind": "promote_blocked", "code": exc.code}, root=root)
        out = public_bot(bot)
        out["deploy_status"] = "DEPLOY_REQUIRED"
        return out
    bot["environment"] = "PRODUCTION"
    bot["status"] = "PRODUCTION"
    bot["live_armed_confirmed"] = True
    bot["aws_runtime_id"] = promoted.get("aws_runtime_id")
    bot["deploy"] = promoted
    append_event(bot_id, {"kind": "promoted", "environment": "PRODUCTION"}, root=root)
    return _refresh(bot, root=root)
