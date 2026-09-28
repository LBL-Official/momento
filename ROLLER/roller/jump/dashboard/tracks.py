"""Map Jump B bots to dashboard tracks. One bot = one track. No invented numbers."""

from __future__ import annotations

from typing import Any

from roller.jump.bots.factory import FACTORY
from roller.jump.bots.versions import BOT_ONE_ID
from roller.jump.dashboard.heartbeat import confirmed, field_metric, unavailable


def _activity(bot: dict[str, Any]) -> dict[str, Any]:
    status = str(bot.get("status") or "")
    live_armed = bool(bot.get("live_armed_confirmed"))
    if status in {"RUNNING_DEMO", "RUNNING"}:
        return {"value": "ACTIVE", "status": "CONFIRMED"}
    if status == "PRODUCTION" and live_armed:
        return {"value": "ACTIVE", "status": "CONFIRMED"}
    if status == "OBSERVATION_UNAVAILABLE" or not bot.get("observation", {}).get("observed"):
        if status in {"DRAFT", "CREATED", "DEMO"}:
            return {"value": status, "status": "CONFIRMED"}
        return {"value": "OBSERVATION_UNAVAILABLE", "status": "OBSERVATION_UNAVAILABLE"}
    return {"value": status or "NON-ACTIVE", "status": "CONFIRMED"}


def activity_for_track(track: dict[str, Any], *, has_fills: bool) -> dict[str, Any]:
    packed = _activity(
        {
            "status": track.get("bot_status") or (track.get("observation") or {}).get("status"),
            "live_armed_confirmed": track.get("live_armed_confirmed"),
            "observation": track.get("observation") or {},
        }
    )
    if packed.get("value") == "ACTIVE":
        return packed
    if has_fills:
        return {"value": "HAS_FILLS", "status": "CONFIRMED"}
    return packed


def _track_amount(bot: dict[str, Any]) -> dict[str, Any]:
    factory = bot.get("factory") if isinstance(bot.get("factory"), dict) else {}
    raw = factory.get("bankroll_cents")
    if raw is None:
        settings = bot.get("settings") if isinstance(bot.get("settings"), dict) else {}
        raw = settings.get("bankroll_cents")
    if raw is None and (factory.get("factory_id") or bot.get("factory_id")):
        raw = FACTORY["bankroll_cents"]
    if raw is None:
        return unavailable("OBSERVATION_UNAVAILABLE")
    try:
        cents = int(raw)
    except (TypeError, ValueError):
        return unavailable("OBSERVATION_UNAVAILABLE")
    return confirmed(cents)


def _sport(bot: dict[str, Any]) -> dict[str, Any]:
    engine = bot.get("engine") if isinstance(bot.get("engine"), dict) else {}
    if engine.get("sport"):
        return confirmed(str(engine["sport"]).upper())
    if bot.get("sport"):
        return confirmed(str(bot["sport"]).upper())
    factory = bot.get("factory") or {}
    if factory.get("factory_id") or bot.get("factory_id"):
        return confirmed("MLB")
    return unavailable()


def _market(bot: dict[str, Any]) -> dict[str, Any]:
    slot = bot.get("slot_id") or (bot.get("iti") or {}).get("slot_id")
    if slot:
        return confirmed(str(slot))
    return unavailable("UNAVAILABLE")


def _lineage(bot: dict[str, Any]) -> dict[str, Any]:
    iti = bot.get("iti") or {}
    if not iti and not bot.get("strategy_folder"):
        return {
            "kind": bot.get("kind") or "grandfathered",
            "label": "grandfathered",
            "research_not_live": True,
        }
    return {
        "kind": "iti",
        "folder": bot.get("strategy_folder") or iti.get("folder"),
        "slot_id": bot.get("slot_id") or iti.get("slot_id"),
        "BASE_GRADE": iti.get("BASE_GRADE"),
        "DEBASE_GRADE": iti.get("DEBASE_GRADE"),
        "entry_cents": iti.get("entry_cents"),
        "win_cents": iti.get("win_cents"),
        "loss_cents": iti.get("loss_cents"),
        "research_not_live": True,
        "iti_is_not_live_signal": True,
    }


def track_from_bot(bot: dict[str, Any], heartbeat: dict[str, Any] | None = None) -> dict[str, Any]:
    fields = dict((heartbeat or {}).get("fields") or {})
    observation = bot.get("observation") or {}
    if observation.get("aws_runtime_id") and "aws_runtime_id" not in fields:
        fields["aws_runtime_id"] = observation["aws_runtime_id"]
    missing = "OBSERVATION_UNAVAILABLE" if not (heartbeat or {}).get("observed") and str(bot.get("bot_id")) == BOT_ONE_ID else "UNAVAILABLE"
    day_pnl = field_metric(fields, "day_pnl_cents", missing=missing)
    week_pnl = field_metric(fields, "week_pnl_cents", missing=missing)
    actual = {
        "bankroll": field_metric(fields, "bankroll_cents", missing=missing),
        "pnl": day_pnl,
        "sharpe": unavailable(),
        "day_pnl": day_pnl,
        "week_pnl": week_pnl,
        "day_sharpe": unavailable(),
        "week_sharpe": unavailable(),
        "open_mlb_positions": field_metric(fields, "open_mlb_positions", missing=missing),
        "open_desk_positions": field_metric(fields, "open_desk_positions", missing=missing),
        "last_trade": field_metric(fields, "last_trade", missing="UNAVAILABLE"),
        "positions": field_metric(fields, "open_mlb_positions", missing="UNAVAILABLE"),
        "orders": unavailable(),
        "kill_switch": field_metric(fields, "kill_switch", missing="UNAVAILABLE"),
        "trades": field_metric(fields, "trade_n", missing=missing),
        "weekly_trades": field_metric(fields, "weekly_trade_n", missing=missing),
        "origin_pnl": unavailable(missing),
    }
    expected = {
        "pnl": unavailable(),
        "sharpe": unavailable(),
        "day_ev": unavailable(),
        "week_ev": unavailable(),
        "day_pnl": unavailable(),
        "week_pnl": unavailable(),
    }
    return {
        "track_id": bot.get("bot_id"),
        "bot_id": bot.get("bot_id"),
        "name": bot.get("name"),
        "kind": bot.get("kind"),
        "environment": bot.get("environment"),
        "bot_status": bot.get("status"),
        "activity": _activity(bot),
        "sport": _sport(bot),
        "market": _market(bot),
        "track_amount": _track_amount(bot),
        "factory": bot.get("factory"),
        "lineage": _lineage(bot),
        "notes": bot.get("notes") or "",
        "profile": bot.get("profile") or {},
        "settings": bot.get("settings") or {},
        "avatar_url": bot.get("avatar_url"),
        "deploy_status": bot.get("deploy_status"),
        "observation": observation,
        "live_armed_confirmed": bool(bot.get("live_armed_confirmed")),
        "vital_bot_id": bot.get("vital_bot_id") or ("mlb-001" if str(bot.get("bot_id")) == BOT_ONE_ID else None),
        "actual": actual,
        "expected": expected,
    }


def filter_tracks(tracks: list[dict[str, Any]], *, by: str = "all", value: str = "") -> list[dict[str, Any]]:
    mode = (by or "all").strip().lower()
    wanted = (value or "").strip()
    if mode in {"", "all", "full", "portfolio", "full_portfolio"}:
        return list(tracks)
    if mode == "sport":
        if not wanted:
            return []
        return [row for row in tracks if str((row.get("sport") or {}).get("value") or "") == wanted]
    if mode == "market":
        if not wanted:
            return []
        return [row for row in tracks if str((row.get("market") or {}).get("value") or "") == wanted]
    if mode in {"environment", "env"}:
        if not wanted:
            return []
        return [row for row in tracks if str(row.get("environment") or "") == wanted]
    if mode == "activity":
        if not wanted:
            return []
        return [row for row in tracks if str((row.get("activity") or {}).get("value") or "") == wanted]
    return list(tracks)
