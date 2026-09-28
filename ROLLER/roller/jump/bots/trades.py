"""Per-bot fill log. Host ledger only. Does not invent fills or live EV."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.jump.bots.store import ensure_bot_one, load_bot, public_bot
from roller.jump.bots.versions import BOT_ONE_ID
from roller.jump.dashboard.heartbeat import unavailable
from roller.jump.dashboard.host_state import load_host_state
from roller.jump.dashboard.ledger import list_mlb_fills, summarize_mlb_ledger

from roller.jump.bots.demo_host import load_demo_host_state
from roller.jump.catalog.api import catalog_trades_for_bot
from roller.jump.catalog.store import load_origin, load_trades


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "OBSERVATION_UNAVAILABLE",
        "trades": None,
        "trade_n": unavailable("OBSERVATION_UNAVAILABLE"),
        "weekly_trade_n": unavailable("OBSERVATION_UNAVAILABLE"),
        "day_pnl": unavailable("OBSERVATION_UNAVAILABLE"),
        "week_pnl": unavailable("OBSERVATION_UNAVAILABLE"),
        "last_trade": unavailable("UNAVAILABLE"),
        "detail": reason,
        "honesty": {
            "live_ev": "UNAVAILABLE",
            "candle_path_not_fill": True,
            "empty_unread_not_zero": True,
        },
    }


def _from_runtime(runtime: dict[str, Any], snapshot: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    fills = list_mlb_fills(runtime, snapshot, now)
    if not fills.get("ok"):
        return _unavailable(str(fills.get("reason") or "ledger unread"))
    pnl = summarize_mlb_ledger(runtime, snapshot, now)
    fields = dict(fills.get("fields") or {})
    if pnl.get("ok"):
        fields.update(pnl.get("fields") or {})
    def _cents(key: str) -> dict[str, Any]:
        if key not in fields:
            return unavailable("UNAVAILABLE")
        return {"value": fields[key], "status": "CONFIRMED"}

    return {
        "ok": True,
        "status": "CONFIRMED",
        "trades": fills.get("trades") or [],
        "trade_n": {"value": fields.get("trade_n"), "status": "CONFIRMED"},
        "weekly_trade_n": {"value": fields.get("weekly_trade_n"), "status": "CONFIRMED"},
        "day_pnl": _cents("day_pnl_cents"),
        "week_pnl": _cents("week_pnl_cents"),
        "last_trade": (
            {"value": fields.get("last_trade"), "status": "CONFIRMED"}
            if fields.get("last_trade")
            else unavailable("UNAVAILABLE")
        ),
        "week_start": fills.get("week_start"),
        "formula": fills.get("formula"),
        "honesty": {
            "live_ev": "UNAVAILABLE",
            "candle_path_not_fill": True,
            "research_ev_not_live": True,
        },
    }


def bot_trades(bot_id: str, *, root=None, now: datetime | None = None) -> dict[str, Any]:
    ensure_bot_one(root=root)
    bot = public_bot(load_bot(bot_id, root=root))
    clock = now or datetime.now(timezone.utc)
    catalog = catalog_trades_for_bot(bot_id, root=root, now=clock, with_charts=True)
    if catalog.get("ok") and (catalog.get("trades") or load_origin() or load_trades()):
        catalog["bot"] = {"bot_id": bot_id, "name": bot.get("name"), "kind": bot.get("kind")}
        return catalog
    if str(bot_id) == BOT_ONE_ID or bot.get("kind") == "grandfathered":
        host = load_host_state()
        if not host.get("ok"):
            out = _unavailable(str(host.get("reason") or "Bot One ledger unread"))
            out["bot_id"] = bot_id
            out["bot"] = {"bot_id": bot_id, "name": bot.get("name"), "kind": bot.get("kind")}
            return out
        if host.get("source") == "ssm" and not host.get("runtime"):
            fields = host.get("fields") or {}
            if "trade_n" not in fields and "weekly_trade_n" not in fields:
                out = _unavailable("Bot One SSM ledger has no fill list")
                out["bot_id"] = bot_id
                out["fields"] = fields
                return out
            return {
                "ok": True,
                "status": "CONFIRMED",
                "bot_id": bot_id,
                "trades": host.get("trades") or [],
                "trade_n": {"value": fields.get("trade_n"), "status": "CONFIRMED"}
                if "trade_n" in fields
                else unavailable("UNAVAILABLE"),
                "weekly_trade_n": {"value": fields.get("weekly_trade_n"), "status": "CONFIRMED"}
                if "weekly_trade_n" in fields
                else unavailable("UNAVAILABLE"),
                "day_pnl": {"value": fields.get("day_pnl_cents"), "status": "CONFIRMED"}
                if "day_pnl_cents" in fields
                else unavailable("UNAVAILABLE"),
                "week_pnl": {"value": fields.get("week_pnl_cents"), "status": "CONFIRMED"}
                if "week_pnl_cents" in fields
                else unavailable("UNAVAILABLE"),
                "last_trade": (
                    {"value": fields.get("last_trade"), "status": "CONFIRMED"}
                    if fields.get("last_trade")
                    else unavailable("UNAVAILABLE")
                ),
                "source": "ssm",
                "honesty": {"live_ev": "UNAVAILABLE", "candle_path_not_fill": True},
            }
        packed = _from_runtime(host["runtime"], host.get("snapshot"), clock)
        packed["bot_id"] = bot_id
        packed["source"] = host.get("source")
        return packed
    demo = load_demo_host_state(bot_id)
    if not demo.get("ok"):
        out = _unavailable(str(demo.get("reason") or "demo ledger unread"))
        out["bot_id"] = bot_id
        return out
    packed = _from_runtime(demo["runtime"], demo.get("snapshot"), clock)
    packed["bot_id"] = bot_id
    packed["source"] = demo.get("source")
    return packed
