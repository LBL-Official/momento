"""Jump B bot registry. Identity and events. Not the trading engine."""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.jump.bots.factory import FACTORY, factory_snapshot
from roller.jump.bots.versions import (
    BOT_ONE_ID,
    BOTS_VERSION,
    CAVEATS,
    ENGINE_POINTER,
    FACTORY_ID,
    FACTORY_VERSION,
    HONESTY,
    SERVICE_NAME,
    STRATEGY_POINTER,
)
from roller.jump.errors import JumpError
from roller.jump.library import repo_root

_ENV = "JUMP_BOTS_ROOT"


def default_bots_root() -> Path:
    env = os.environ.get(_ENV)
    if env:
        return Path(env)
    return repo_root() / "research" / "jump" / "bots"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def bot_dir(bot_id: str, *, root: Path | None = None) -> Path:
    return (root or default_bots_root()) / bot_id


def bot_path(bot_id: str, *, root: Path | None = None) -> Path:
    return bot_dir(bot_id, root=root) / "metadata.json"


def events_path(bot_id: str, *, root: Path | None = None) -> Path:
    return bot_dir(bot_id, root=root) / "events.jsonl"


def _handle_from_name(name: str, bot_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", (name or "").lower())[:24]
    return slug or str(bot_id).replace("-", "")[:12] or "bot"


def default_profile(name: str, bot_id: str) -> dict[str, Any]:
    return {
        "display_name": name,
        "handle": _handle_from_name(name, bot_id),
        "bio": "",
        "purpose": "",
        "avatar": None,
    }


DEMO_FALLBACK_BANKROLL_CENTS = 2000
DEMO_UNIT_CENTS = 100


def _production_like(bot: dict[str, Any]) -> bool:
    return (
        str(bot.get("environment") or "").upper() == "PRODUCTION"
        or bot.get("kind") == "grandfathered"
        or str(bot.get("bot_id") or "") == BOT_ONE_ID
    )


def _observed_demo_bankroll_cents() -> int | None:
    try:
        from roller.jump.catalog.bankroll import book_for, current_cents
        from roller.jump.catalog.store import load_bankroll
    except Exception:
        return None
    book = book_for(load_bankroll(), "DEMO")
    if not book:
        return None
    top = book.get("top_level_cents")
    try:
        if top is not None:
            value = int(top)
            return value if value > 0 else None
    except (TypeError, ValueError):
        pass
    current = current_cents(book)
    return current if current is not None and current > 0 else None


def default_settings() -> dict[str, Any]:
    return {
        "bankroll_cents": int(FACTORY["bankroll_cents"]),
        "sizing_mode": "PCT_WEEKLY",
        "allocation_bps": int(FACTORY["allocation_bps"]),
    }


def demo_default_settings(*, observed_bankroll: int | None = None) -> dict[str, Any]:
    bankroll = observed_bankroll if observed_bankroll is not None and observed_bankroll > 0 else None
    if bankroll is None:
        bankroll = _observed_demo_bankroll_cents()
    source = "demo_book" if bankroll is not None else "unread_fallback"
    if bankroll is None:
        bankroll = DEMO_FALLBACK_BANKROLL_CENTS
    return {
        "bankroll_cents": int(bankroll),
        "bankroll_source": source,
        "sizing_mode": "FIXED_CENTS",
        "amount_cents": DEMO_UNIT_CENTS,
        "max_position_budget_cents": DEMO_UNIT_CENTS,
        "allocation_bps": int(FACTORY["allocation_bps"]),
    }


def apply_demo_dollar_defaults(bot: dict[str, Any]) -> dict[str, Any]:
    """Force the current $1 demo unit. Does not change production / Bot One."""
    if _production_like(bot):
        return bot
    settings = dict(bot.get("settings") or {})
    settings.update(demo_default_settings())
    bot["settings"] = settings
    return bot


def ensure_identity(bot: dict[str, Any]) -> dict[str, Any]:
    bot_id = str(bot.get("bot_id") or "")
    name = str(bot.get("name") or "Untitled bot")
    profile = dict(bot["profile"]) if isinstance(bot.get("profile"), dict) else {}
    defaults = default_profile(name, bot_id)
    for key, value in defaults.items():
        profile.setdefault(key, value)
    settings = dict(bot["settings"]) if isinstance(bot.get("settings"), dict) else {}
    if _production_like(bot):
        factory = default_settings()
        for key, value in factory.items():
            settings.setdefault(key, value)
    else:
        demo = demo_default_settings()
        for key, value in demo.items():
            settings.setdefault(key, value)
    bot["profile"] = profile
    bot["settings"] = settings
    return bot


def avatar_path(bot: dict[str, Any], *, root: Path | None = None) -> Path | None:
    filename = ((bot.get("profile") or {}) if isinstance(bot.get("profile"), dict) else {}).get("avatar")
    if not filename:
        return None
    name = Path(str(filename)).name
    if name.startswith(".") or "/" in str(filename) or "\\" in str(filename):
        return None
    path = bot_dir(str(bot["bot_id"]), root=root) / name
    return path if path.is_file() else None


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="jump_bot_", dir=str(path.parent))) / "metadata.json"
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    tmp.parent.rmdir()


def append_event(bot_id: str, event: dict[str, Any], *, root: Path | None = None) -> None:
    path = events_path(bot_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _utc_now(), **event}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def load_bot(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    path = bot_path(bot_id, root=root)
    if not path.is_file():
        raise JumpError("BOT_NOT_FOUND", f"bot not found: {bot_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_bot(bot: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    bot_id = str(bot["bot_id"])
    bot["updated_at"] = _utc_now()
    _write_json(bot_path(bot_id, root=root), bot)
    return bot


def public_bot(bot: dict[str, Any]) -> dict[str, Any]:
    out = dict(ensure_identity(bot))
    if out.get("kind") == "grandfathered" or str(out.get("bot_id") or "") == BOT_ONE_ID:
        out["factory"] = factory_snapshot()
    else:
        out["factory"] = None
        out["engine"] = out.get("engine")
    out["honesty"] = dict(HONESTY)
    out["caveats"] = list(CAVEATS)
    if avatar_path(out, root=None) is not None or (
        isinstance(out.get("profile"), dict) and out["profile"].get("avatar")
    ):
        out["avatar_url"] = f"/jump/bots/{out['bot_id']}/avatar"
    else:
        out["avatar_url"] = None
    return out


def bot_one_record() -> dict[str, Any]:
    return {
        "bot_id": BOT_ONE_ID,
        "name": "MLB Bot 001",
        "kind": "grandfathered",
        "factory_id": FACTORY_ID,
        "factory_version": FACTORY_VERSION,
        "strategy_folder": None,
        "strategy_fingerprint": None,
        "iti_version": None,
        "slot_id": None,
        "environment": None,
        "status": "OBSERVATION_UNAVAILABLE",
        "aws_runtime_id": SERVICE_NAME,
        "notes": "Existing MLB desk. Predates Jump. Not created through ITI.",
        "engine_pointer": ENGINE_POINTER,
        "strategy_pointer": STRATEGY_POINTER,
        "live_armed_confirmed": False,
        "bots_version": BOTS_VERSION,
        "profile": default_profile("MLB Bot 001", BOT_ONE_ID),
        "settings": default_settings(),
        "created_at": "2026-08-01T00:00:00Z",
        "updated_at": _utc_now(),
    }


def ensure_bot_one(*, root: Path | None = None) -> dict[str, Any]:
    path = bot_path(BOT_ONE_ID, root=root)
    if path.is_file():
        rec = load_bot(BOT_ONE_ID, root=root)
        rec["kind"] = "grandfathered"
        rec["factory_id"] = FACTORY_ID
        rec["engine_pointer"] = ENGINE_POINTER
        rec["strategy_pointer"] = STRATEGY_POINTER
        return rec
    rec = bot_one_record()
    save_bot(rec, root=root)
    append_event(BOT_ONE_ID, {"kind": "seeded", "status": rec["status"]}, root=root)
    return rec


def list_bots(*, root: Path | None = None) -> list[dict[str, Any]]:
    ensure_bot_one(root=root)
    base = root or default_bots_root()
    if not base.is_dir():
        return [public_bot(ensure_bot_one(root=root))]
    items: list[dict[str, Any]] = []
    for child in sorted(base.iterdir()):
        if child.name.startswith(".") or not child.is_dir():
            continue
        if not (child / "metadata.json").is_file():
            continue
        rec = json.loads((child / "metadata.json").read_text(encoding="utf-8"))
        from roller.jump.bots.engine import hydrate_research_engine

        if hydrate_research_engine(rec):
            save_bot(rec, root=root)
        items.append(public_bot(rec))
    items.sort(key=lambda row: (0 if row.get("bot_id") == BOT_ONE_ID else 1, str(row.get("created_at") or "")))
    return items


def create_draft(
    *,
    name: str,
    iti: dict[str, Any],
    notes: str = "",
    root: Path | None = None,
) -> dict[str, Any]:
    bot_id = uuid.uuid4().hex
    engine = iti.get("engine") if isinstance(iti.get("engine"), dict) else None
    if engine is None:
        from roller.jump.bots.engine import build_research_engine

        engine = build_research_engine(iti)
    bot = {
        "bot_id": bot_id,
        "name": name.strip() or iti.get("strategy_name") or "Untitled bot",
        "kind": "iti",
        "factory_id": None,
        "factory_version": None,
        "engine": engine,
        "engine_pointer": engine.get("engine_pointer"),
        "strategy_pointer": engine.get("strategy_pointer"),
        "sport": engine.get("sport"),
        "strategy_folder": iti.get("folder"),
        "strategy_fingerprint": iti.get("strategy_fingerprint") or engine.get("engine_fingerprint"),
        "iti_version": iti.get("iti_version"),
        "slot_id": iti.get("slot_id"),
        "iti": {
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
        },
        "environment": "DEMO",
        "status": "DRAFT",
        "aws_runtime_id": None,
        "notes": notes,
        "live_armed_confirmed": False,
        "bots_version": BOTS_VERSION,
        "profile": default_profile(name.strip() or iti.get("strategy_name") or "Untitled bot", bot_id),
        "settings": demo_default_settings(),
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }
    save_bot(bot, root=root)
    append_event(bot_id, {"kind": "draft", "strategy_folder": bot["strategy_folder"]}, root=root)
    return public_bot(bot)
