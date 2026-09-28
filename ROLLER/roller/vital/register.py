"""Register Jump ITI bots onto the Vital disk tree.

Create attaches Kalshi Demo observe + AWS inspect. It does not start a host
unit and does not invent RUNNING. MLB 001 is never rewritten.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.vital.models import utc_now
from roller.vital.naming import next_sport_bot_id
from roller.vital.store import (
    allocation_history_path,
    allocation_path,
    append_event,
    append_jsonl,
    default_vital_root,
    ensure_bot_tree,
    limits_history_path,
    limits_path,
    list_bot_ids,
    load_bot,
    metadata_path,
    save_bot,
    write_json,
)
from roller.vital.demo_attach import attach_demo_if_needed
from roller.vital.versions import BOT_ID

ACTIVATION_CONFIRM_REQUIRED = "CONFIRM_REQUIRED"


def _settings_snapshot(jump_bot: dict[str, Any]) -> dict[str, Any]:
    settings = jump_bot.get("settings") if isinstance(jump_bot.get("settings"), dict) else {}
    return {
        "sizing_mode": str(settings.get("sizing_mode") or "FIXED_CENTS").upper(),
        "amount_cents": settings.get("amount_cents"),
        "allocation_bps": settings.get("allocation_bps"),
        "bankroll_cents": settings.get("bankroll_cents"),
        "max_daily_entries": settings.get("max_daily_entries"),
        "max_daily_wins": settings.get("max_daily_wins"),
        "max_daily_losses": settings.get("max_daily_losses"),
        "max_daily_win_cents": settings.get("max_daily_win_cents"),
        "max_daily_loss_cents": settings.get("max_daily_loss_cents"),
    }


def _write_desired_policy(bot_id: str, jump_bot: dict[str, Any], *, root: Path | None) -> None:
    snap = _settings_snapshot(jump_bot)
    alloc = {
        "bot_id": bot_id,
        "recorded_at": utc_now(),
        "kind": "allocation_desired",
        "mode": snap["sizing_mode"],
        "amount_cents": snap["amount_cents"],
        "allocation_bps": snap["allocation_bps"],
    }
    write_json(allocation_path(bot_id, root=root), alloc)
    append_jsonl(allocation_history_path(bot_id, root=root), alloc)
    limits = {
        "bot_id": bot_id,
        "recorded_at": utc_now(),
        "kind": "limits_desired",
        "max_daily_entries": snap["max_daily_entries"],
        "max_daily_wins": snap["max_daily_wins"],
        "max_daily_losses": snap["max_daily_losses"],
        "max_daily_win_cents": snap["max_daily_win_cents"],
        "max_daily_loss_cents": snap["max_daily_loss_cents"],
    }
    write_json(limits_path(bot_id, root=root), limits)
    append_jsonl(limits_history_path(bot_id, root=root), limits)


def _sync_existing_engine(
    rec: dict[str, Any],
    engine: dict[str, Any],
    jump_bot: dict[str, Any],
    *,
    root: Path | None,
) -> dict[str, Any]:
    """Write the research engine onto an already-registered Vital bot. Keeps bot_id."""
    pointer = str(rec.get("engine_pointer") or "")
    needs = (
        not isinstance(rec.get("engine"), dict)
        or pointer in {"", "apps/trading-engine"}
        or rec.get("strategy_pointer") == "strategies/mlb"
    )
    if not needs:
        return rec
    rec["engine"] = engine
    rec["engine_pointer"] = engine.get("engine_pointer") or "research_iti"
    rec["strategy_pointer"] = engine.get("strategy_pointer") or jump_bot.get("strategy_folder")
    rec["sport"] = engine.get("sport") or jump_bot.get("sport")
    if isinstance(jump_bot.get("iti"), dict):
        rec["iti"] = jump_bot["iti"]
    dest = ensure_bot_tree(str(rec["bot_id"]), root=root)
    write_json(dest / "source" / "engine.json", engine)
    save_bot(rec, root=root)
    append_event(
        str(rec["bot_id"]),
        {"kind": "implemented_research_engine", "engine_pointer": rec["engine_pointer"]},
        root=root,
    )
    return rec


def register_iti_bot(
    jump_bot: dict[str, Any],
    *,
    vital_root: Path | None = None,
    jump_root: Path | None = None,
) -> dict[str, Any]:
    """Write research/vital/bots/mlb-00N for a Jump ITI bot. Idempotent per jump_bot_id."""
    from roller.jump.bots.store import save_bot as jump_save
    from roller.jump.bots.versions import BOT_ONE_ID

    jump_id = str(jump_bot.get("bot_id") or "")
    if not jump_id or jump_id in {BOT_ID, BOT_ONE_ID} or jump_bot.get("kind") == "grandfathered":
        return jump_bot
    root = vital_root or default_vital_root()
    from roller.jump.bots.engine import build_research_engine, hydrate_research_engine

    jump_dirty = hydrate_research_engine(jump_bot)
    iti = jump_bot.get("iti") if isinstance(jump_bot.get("iti"), dict) else {}
    engine = jump_bot.get("engine") if isinstance(jump_bot.get("engine"), dict) else {}
    if not engine:
        engine = build_research_engine({**iti, "folder": jump_bot.get("strategy_folder") or iti.get("folder")})
        jump_bot["engine"] = engine
        jump_dirty = True
    if jump_dirty:
        jump_save(jump_bot, root=jump_root)

    existing = str(jump_bot.get("vital_bot_id") or "").strip()
    if existing and metadata_path(existing, root=root).is_file():
        rec = _sync_existing_engine(load_bot(existing, root=root), engine, jump_bot, root=root)
        return attach_demo_if_needed(rec, vital_root=root, jump_root=jump_root, jump_bot=jump_bot)
    for bot_id in list_bot_ids(root=root):
        if bot_id == BOT_ID:
            continue
        rec = load_bot(bot_id, root=root)
        if str(rec.get("jump_bot_id") or "") == jump_id:
            if not jump_bot.get("vital_bot_id"):
                jump_bot["vital_bot_id"] = bot_id
                jump_save(jump_bot, root=jump_root)
            rec = _sync_existing_engine(rec, engine, jump_bot, root=root)
            return attach_demo_if_needed(rec, vital_root=root, jump_root=jump_root, jump_bot=jump_bot)
    sport = str(engine.get("sport") or jump_bot.get("sport") or "").strip().lower()
    vital_id = next_sport_bot_id(sport, list_bot_ids(root=root))
    rec = {
        "bot_id": vital_id,
        "name": jump_bot.get("name") or vital_id,
        "kind": "iti",
        "environment": "DEMO",
        "desired_environment": str(jump_bot.get("desired_environment") or "DEMO").upper(),
        "jump_bot_id": jump_id,
        "status": "CREATED",
        "health": "UNKNOWN",
        "activation": ACTIVATION_CONFIRM_REQUIRED,
        "sport": sport,
        "engine": engine,
        "engine_pointer": engine.get("engine_pointer") or "research_iti",
        "strategy_pointer": engine.get("strategy_pointer") or jump_bot.get("strategy_folder") or iti.get("folder"),
        "iti_lineage": jump_bot.get("strategy_folder") or iti.get("folder"),
        "strategy_fingerprint": jump_bot.get("strategy_fingerprint") or engine.get("engine_fingerprint"),
        "slot_id": jump_bot.get("slot_id") or iti.get("slot_id"),
        "iti": iti,
        "settings": _settings_snapshot(jump_bot),
        "live_armed_confirmed": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    dest = ensure_bot_tree(vital_id, root=root)
    write_json(dest / "source" / "engine.json", engine)
    save_bot(rec, root=root)
    _write_desired_policy(vital_id, jump_bot, root=root)
    append_event(
        vital_id,
        {
            "kind": "registered_from_jump",
            "jump_bot_id": jump_id,
            "activation": ACTIVATION_CONFIRM_REQUIRED,
        },
        root=root,
    )
    jump_bot["vital_bot_id"] = vital_id
    jump_save(jump_bot, root=jump_root)
    return attach_demo_if_needed(rec, vital_root=root, jump_root=jump_root, jump_bot=jump_bot)


def apply_iti_promote(
    vital_id: str,
    started: dict[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Persist isolated live unit result. MLB 001 is never rewritten."""
    if vital_id == BOT_ID:
        from roller.vital.errors import VitalError

        raise VitalError("REJECTED", "mlb-001 is observed, not promoted")
    bot = load_bot(vital_id, root=root)
    active = bool(started.get("active") or started.get("unit_started"))
    bot["desired_environment"] = "PRODUCTION"
    if active:
        bot["environment"] = "PRODUCTION"
        bot["status"] = "RUNNING"
        bot["activation"] = "RUNNING"
        bot["aws_runtime_id"] = started.get("aws_runtime_id") or started.get("unit")
        bot["live_armed_confirmed"] = True
        bot["deploy"] = {
            "status": "RUNNING",
            "unit": started.get("unit") or started.get("aws_runtime_id"),
            "kalshi_env": "production",
        }
    else:
        bot["environment"] = "DEMO"
        bot["status"] = bot.get("status") or "CREATED"
        bot["activation"] = "DEPLOY_REQUIRED"
        bot["aws_runtime_id"] = None
        bot["live_armed_confirmed"] = False
        bot["deploy"] = {
            "status": "DEPLOY_REQUIRED",
            "reason": started.get("reason"),
            "secret_missing": bool(started.get("secret_missing")),
        }
    bot["updated_at"] = utc_now()
    save_bot(bot, root=root)
    append_event(
        vital_id,
        {
            "kind": "iti_live_promote",
            "active": active,
            "unit": started.get("unit"),
            "reason": started.get("reason"),
        },
        root=root,
    )
    return bot


def backfill_jump_demo_bots(*, vital_root: Path | None = None, jump_root: Path | None = None) -> list[dict[str, Any]]:
    """Register created Jump DEMO ITI bots that are missing a Vital stub."""
    from roller.jump.bots.store import list_bots as jump_list
    from roller.jump.bots.store import load_bot as jump_load
    from roller.jump.bots.versions import BOT_ONE_ID

    out: list[dict[str, Any]] = []
    try:
        rows = jump_list(root=jump_root)
    except Exception:
        return out
    for row in rows:
        bot_id = str(row.get("bot_id") or "")
        if not bot_id or bot_id in {BOT_ID, BOT_ONE_ID} or row.get("kind") == "grandfathered":
            continue
        if str(row.get("environment") or "").upper() != "DEMO":
            continue
        if str(row.get("status") or "") == "DRAFT":
            continue
        try:
            raw = jump_load(bot_id, root=jump_root)
        except Exception:
            continue
        out.append(register_iti_bot(raw, vital_root=vital_root, jump_root=jump_root))
    return out
