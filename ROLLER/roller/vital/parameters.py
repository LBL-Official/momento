"""Per-bot parameter sheet. Factory rows stay locked. Demo ITI can patch prices."""

from __future__ import annotations

import os
from typing import Any

from roller.jump.bots.factory import FACTORY
from roller.vital.bots import get_bot
from roller.vital.errors import VitalError
from roller.vital.models import utc_now
from roller.vital.store import save_bot
from roller.vital.versions import BOT_ID, LIVE_CONFIRMATION


def _int(raw: Any) -> int | None:
    if raw is None or raw == "" or isinstance(raw, bool):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _factory_bot(bot: dict[str, Any]) -> bool:
    return str(bot.get("bot_id") or "") == BOT_ID or bot.get("kind") == "grandfathered"


def _row(
    key: str,
    value: Any,
    *,
    unit: str,
    source: str,
    editable: bool,
    locked_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "value": value,
        "unit": unit,
        "source": source,
        "editable": bool(editable) and locked_reason is None,
        "locked_reason": locked_reason,
    }


def _iti_prices(bot: dict[str, Any]) -> dict[str, int | None]:
    engine = bot.get("engine") if isinstance(bot.get("engine"), dict) else {}
    prices = engine.get("prices") if isinstance(engine.get("prices"), dict) else {}
    iti = bot.get("iti") if isinstance(bot.get("iti"), dict) else {}
    return {
        "entry": _int(prices.get("entry_cents") if prices.get("entry_cents") is not None else iti.get("entry_cents")),
        "win": _int(prices.get("win_cents") if prices.get("win_cents") is not None else iti.get("win_cents")),
        "loss": _int(prices.get("loss_cents") if prices.get("loss_cents") is not None else iti.get("loss_cents")),
    }


def validate_iti_prices(entry: int, win: int, loss: int) -> None:
    if not (1 <= loss < entry < win <= 99):
        raise VitalError("REJECTED", "ITI prices must satisfy 1 <= loss < entry < win <= 99")
    if entry == 80 and win == 81:
        raise VitalError("REJECTED", "ITI parameters refuse the factory 80/81/83/89 band")


def parameters_view(bot_id: str, *, root=None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if _factory_bot(bot):
        rows = [
            _row("min_entry_cents", FACTORY["min_entry_cents"], unit="cents", source="mlb_factory_v1", editable=False, locked_reason="live factory 80/81 is locked"),
            _row("preferred_entry_cents", FACTORY["preferred_entry_cents"], unit="cents", source="mlb_factory_v1", editable=False, locked_reason="live factory 80/81 is locked"),
            _row("confirm_cents", FACTORY["confirm_cents"], unit="cents", source="mlb_factory_v1", editable=False, locked_reason="live factory 80/81 is locked"),
            _row("max_entry_cents", FACTORY["max_entry_cents"], unit="cents", source="mlb_factory_v1", editable=False, locked_reason="live factory 80/81 is locked"),
            _row("lock_cents", FACTORY["lock_cents"], unit="cents", source="mlb_factory_v1", editable=False, locked_reason="live factory 80/81 is locked"),
            _row("order_type", FACTORY["order_type"], unit="enum", source="mlb_factory_v1", editable=False, locked_reason="live factory 80/81 is locked"),
            _row("signal", FACTORY["signal"], unit="enum", source="mlb_factory_v1", editable=False, locked_reason="live factory 80/81 is locked"),
            _row("bankroll_cents", FACTORY["bankroll_cents"], unit="cents", source="mlb_factory_v1", editable=False, locked_reason="live factory 80/81 is locked"),
            _row("allocation_bps", FACTORY["allocation_bps"], unit="bps", source="mlb_factory_v1", editable=False, locked_reason="live factory 80/81 is locked"),
            _row("max_open_mlb_positions", FACTORY["max_open_mlb_positions"], unit="count", source="mlb_factory_v1", editable=False, locked_reason="live factory 80/81 is locked"),
            _row("live.confirmation", LIVE_CONFIRMATION, unit="gate", source="config/live.toml", editable=False, locked_reason="triple live gate is not a Vital edit"),
        ]
        return {
            "bot_id": BOT_ID,
            "kind": "grandfathered",
            "environment": "PRODUCTION",
            "editable": False,
            "spec_status": "CONFIRMED",
            "parameters": rows,
            "submits": False,
            "note": "MLB 001 factory constants are observed, not edited.",
        }
    settings = bot.get("settings") if isinstance(bot.get("settings"), dict) else {}
    prices = _iti_prices(bot)
    demo = str(bot.get("environment") or "DEMO").upper() == "DEMO"
    lock = None if demo else "production ITI parameters are not patched from Vital"
    mismatch = False
    committed = bot.get("iti") if isinstance(bot.get("iti"), dict) else {}
    for key, current in (("entry_cents", prices["entry"]), ("win_cents", prices["win"]), ("loss_cents", prices["loss"])):
        raw = _int(committed.get(key))
        if raw is not None and current is not None and raw != current:
            mismatch = True
    rows = [
        _row("sport", bot.get("sport") or (bot.get("engine") or {}).get("sport"), unit="enum", source="committed_iti", editable=False, locked_reason="sport rewrite would invent a series"),
        _row("iti_entry_cents", prices["entry"], unit="cents", source="committed_iti", editable=demo, locked_reason=lock),
        _row("iti_win_cents", prices["win"], unit="cents", source="committed_iti", editable=demo, locked_reason=lock),
        _row("iti_loss_cents", prices["loss"], unit="cents", source="committed_iti", editable=demo, locked_reason=lock),
        _row("sizing_mode", settings.get("sizing_mode") or "FIXED_CENTS", unit="enum", source="bot.settings", editable=False, locked_reason="sizing_mode stays FIXED_CENTS on Demo ITI"),
        _row("max_position_budget_cents", settings.get("amount_cents") or settings.get("max_position_budget_cents"), unit="cents", source="bot.settings", editable=demo, locked_reason=lock),
        _row("allocation_bps", settings.get("allocation_bps"), unit="bps", source="bot.settings", editable=False, locked_reason="allocation_bps is display-only here"),
        _row("max_daily_entries", settings.get("max_daily_entries"), unit="count", source="bot.settings", editable=False, locked_reason="session limits stay on the existing allocation/limits APIs"),
        _row("strategy_profile", "research_iti", unit="enum", source="engine", editable=False, locked_reason="ITI must not become mlb_factory"),
        _row("live.enabled", False, unit="bool", source="demo.toml", editable=False, locked_reason="Demo cannot be live-armed"),
    ]
    return {
        "bot_id": bot.get("bot_id"),
        "kind": bot.get("kind") or "iti",
        "environment": bot.get("environment") or "DEMO",
        "editable": demo,
        "spec_status": "SPEC_MISMATCH" if mismatch else "CONFIRMED",
        "parameters": rows,
        "submits": False,
        "candle_path_not_fill": True,
        "not_80_81": True,
        "note": "Demo ITI entry/win/loss can be patched. Browser does not submit orders.",
    }


def patch_parameters(bot_id: str, body: dict[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if _factory_bot(bot):
        raise VitalError("REJECTED", "mlb-001 factory parameters are locked")
    if str(bot.get("environment") or "DEMO").upper() != "DEMO":
        raise VitalError("REJECTED", "production ITI parameters are not patched from Vital")
    if str(body.get("confirmation") if isinstance(body, dict) else "") == LIVE_CONFIRMATION:
        raise VitalError("REJECTED", "ENABLE_LIVE_TRADING is not a parameter edit token")
    payload = body if isinstance(body, dict) else {}
    if payload.get("sport"):
        raise VitalError("REJECTED", "sport rewrite would invent a series")
    prices = _iti_prices(bot)
    settings = dict(bot.get("settings") or {}) if isinstance(bot.get("settings"), dict) else {}
    entry = _int(payload.get("iti_entry_cents") if payload.get("iti_entry_cents") is not None else prices["entry"])
    win = _int(payload.get("iti_win_cents") if payload.get("iti_win_cents") is not None else prices["win"])
    loss = _int(payload.get("iti_loss_cents") if payload.get("iti_loss_cents") is not None else prices["loss"])
    if entry is None or win is None or loss is None:
        raise VitalError("REJECTED", "ITI entry/win/loss are required integers")
    validate_iti_prices(entry, win, loss)
    budget = _int(
        payload.get("max_position_budget_cents")
        if payload.get("max_position_budget_cents") is not None
        else settings.get("amount_cents") or settings.get("max_position_budget_cents")
    )
    settings["amount_cents"] = budget
    if budget is not None:
        settings["max_position_budget_cents"] = budget
    bot["settings"] = settings
    iti = dict(bot.get("iti") or {}) if isinstance(bot.get("iti"), dict) else {}
    iti.update({"entry_cents": entry, "win_cents": win, "loss_cents": loss})
    bot["iti"] = iti
    engine = dict(bot.get("engine") or {}) if isinstance(bot.get("engine"), dict) else {}
    engine_prices = dict(engine.get("prices") or {})
    engine_prices.update({"entry_cents": entry, "win_cents": win, "loss_cents": loss})
    engine["prices"] = engine_prices
    engine["sport"] = engine.get("sport") or bot.get("sport")
    bot["engine"] = engine
    bot["updated_at"] = utc_now()
    save_bot(bot, root=root)
    apply = {"attempted": False, "ok": False, "reason": "host apply skipped in test isolation"}
    skip_apply = os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("VITAL_SKIP_HOST_APPLY")
    if root is None and not skip_apply:
        from roller.jump.bots.demo_host import apply_iti_demo_toml

        apply = apply_iti_demo_toml(bot)
    return {
        **parameters_view(str(bot["bot_id"]), root=root),
        "patched": True,
        "apply": apply,
        "submits": False,
        "http_200_not_running": True,
    }
