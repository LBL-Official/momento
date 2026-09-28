"""Vital view of a research ITI engine. Not mlb_factory_v1. Does not submit."""

from __future__ import annotations

from typing import Any

from roller.vital.honesty import observation_unavailable, unavailable


def _engine(bot: dict[str, Any]) -> dict[str, Any]:
    return bot.get("engine") if isinstance(bot.get("engine"), dict) else {}


def _impl(engine: dict[str, Any]) -> dict[str, Any]:
    return engine.get("implementation") if isinstance(engine.get("implementation"), dict) else {}


def _prices(engine: dict[str, Any]) -> dict[str, Any]:
    return engine.get("prices") if isinstance(engine.get("prices"), dict) else {}


def _iti(bot: dict[str, Any], engine: dict[str, Any]) -> dict[str, Any]:
    packed = engine.get("iti") if isinstance(engine.get("iti"), dict) else {}
    if packed:
        return packed
    return bot.get("iti") if isinstance(bot.get("iti"), dict) else {}


def _iti_price_mismatch(prices: dict[str, Any], iti: dict[str, Any], question: dict[str, Any] | None) -> bool:
    try:
        entry = int(prices.get("entry_cents") if prices.get("entry_cents") is not None else iti.get("entry_cents"))
        win = int(prices.get("win_cents") if prices.get("win_cents") is not None else iti.get("win_cents"))
        loss = int(prices.get("loss_cents") if prices.get("loss_cents") is not None else iti.get("loss_cents"))
    except (TypeError, ValueError):
        return True
    for key, expected in (("entry_cents", entry), ("win_cents", win), ("loss_cents", loss)):
        raw = iti.get(key)
        if raw is None or raw == "":
            continue
        try:
            if int(raw) != expected:
                return True
        except (TypeError, ValueError):
            return True
    if not isinstance(question, dict):
        return False
    entry_e4 = prices.get("entry_e4")
    q_entry = None
    conditions = question.get("entry_conditions") if isinstance(question.get("entry_conditions"), list) else []
    for row in conditions:
        if not isinstance(row, dict):
            continue
        if row.get("price_e4") is not None:
            q_entry = row.get("price_e4")
            break
    if q_entry is not None and entry_e4 is not None:
        try:
            if int(q_entry) != int(entry_e4):
                return True
        except (TypeError, ValueError):
            return True
    return False


def strategy_view(bot: dict[str, Any]) -> dict[str, Any]:
    engine = _engine(bot)
    prices = _prices(engine)
    iti = _iti(bot, engine)
    impl = _impl(engine)
    question = engine.get("question") if isinstance(engine.get("question"), dict) else None
    committed = dict(bot.get("iti") or {}) if isinstance(bot.get("iti"), dict) else {}
    committed.update({key: iti[key] for key in iti if iti.get(key) not in {None, ""}})
    mismatch = _iti_price_mismatch(prices, committed, question)
    return {
        "bot_id": bot.get("bot_id"),
        "layer": "strategy",
        "kind": engine.get("kind") or "research_iti",
        "pointer": engine.get("strategy_pointer") or bot.get("strategy_pointer"),
        "engine_pointer": engine.get("engine_pointer") or bot.get("engine_pointer") or "research_iti",
        "sport": engine.get("sport") or bot.get("sport"),
        "source": engine.get("source") or "ROLLER → SuperASI A → SuperASI B → ITI",
        "signal": impl.get("signal") or "research_iti_candle_path",
        "proposes": True,
        "submits": False,
        "locked": False,
        "does_not_retune": True,
        "not_mlb_factory": True,
        "not_80_81": True,
        "question": question,
        "prices": prices,
        "looking_for": (
            f"First Touch YES bid of {prices.get('entry_cents')}¢ "
            f"(prior < entry, current >= entry); limit = observed bid"
        ),
        "entry_rules": {
            "observation": "YES_BID",
            "kind": "FIRST_TOUCH",
            "entry_cents": prices.get("entry_cents"),
            "limit": "observed YES bid (gap-through allowed)",
            "order_type": "maker_only_post_only",
        },
        "exit_rules": {
            "kind": "REACH",
            "win_cents": prices.get("win_cents"),
            "loss_cents": prices.get("loss_cents"),
            "order_type": "reduce_only",
            "not_89_lock": True,
            "not_vwap_stop": True,
        },
        "order_rules": {
            "entry": "post-only maker at observed YES bid",
            "exit": "reduce-only REACH of win or loss",
            "risk": "Risk Decision Engine on the isolated unit",
            "submitter": "momento-trading-engine",
            "browser_submits": False,
        },
        "spec_status": "SPEC_MISMATCH" if mismatch else "CONFIRMED",
        "candle_path_not_fill": True,
        "iti": {
            "folder": iti.get("folder"),
            "slot_id": iti.get("slot_id") or bot.get("slot_id"),
            "run_id": iti.get("run_id"),
            "BASE_GRADE": iti.get("BASE_GRADE"),
            "DEBASE_GRADE": iti.get("DEBASE_GRADE"),
            "population": iti.get("population"),
        },
        "implementation": {
            "spec": impl.get("spec") or "IMPLEMENTED",
            "worker": impl.get("worker") or "OPERATION_REQUIRED",
            "submit": False,
        },
        "state": observation_unavailable("research ITI host strategy dump unread"),
        "note": (
            "This bot's engine is the committed ROLLER → SuperASI → ITI slot. "
            "It is not strategies/mlb 80/81. Candle path ≠ fill. Browser does not submit."
        ),
    }


def configuration_view(bot: dict[str, Any]) -> dict[str, Any]:
    engine = _engine(bot)
    return {
        "bot_id": bot.get("bot_id"),
        "layer": "configuration",
        "editable": False,
        "secrets": False,
        "factory": None,
        "engine": engine,
        "settings": bot.get("settings") or {},
        "live_arm_is_not_vital_start": True,
        "note": "Research ITI engine is the configuration. Not mlb_factory_v1.",
    }


def plane_view(bot: dict[str, Any]) -> dict[str, Any]:
    engine = _engine(bot)
    impl = _impl(engine)
    return {
        "bot_id": bot.get("bot_id"),
        "phase": "research_iti",
        "layer": "control_plane",
        "sport": engine.get("sport") or bot.get("sport"),
        "engine_pointer": engine.get("engine_pointer") or bot.get("engine_pointer") or "research_iti",
        "surfaces": (
            "status",
            "configuration",
            "strategy",
            "risk",
            "heartbeat",
            "worker",
            "pipeline",
            "controls",
            "boundary",
        ),
        "frontend_owns_trading_logic": False,
        "live_execution": False,
        "http_200_not_running": True,
        "start_is_not_live_arm": True,
        "factory": None,
        "implementation": {
            "spec": impl.get("spec") or "IMPLEMENTED",
            "worker": impl.get("worker") or "OPERATION_REQUIRED",
            "submit": False,
        },
        "honesty": {
            "browser_is_not_engine": True,
            "http_200_not_running": True,
            "not_mlb_factory": True,
            "not_80_81": True,
        },
    }


def risk_view(bot: dict[str, Any]) -> dict[str, Any]:
    settings = bot.get("settings") if isinstance(bot.get("settings"), dict) else {}
    return {
        "bot_id": bot.get("bot_id"),
        "layer": "risk",
        "pointer": None,
        "engine": None,
        "factory": None,
        "second_engine": False,
        "submits": False,
        "limits": {
            "bankroll_cents": settings.get("bankroll_cents"),
            "allocation_bps": settings.get("allocation_bps"),
            "amount_cents": settings.get("amount_cents"),
            "max_daily_entries": settings.get("max_daily_entries"),
            "max_daily_wins": settings.get("max_daily_wins"),
            "max_daily_losses": settings.get("max_daily_losses"),
            "max_daily_win_cents": settings.get("max_daily_win_cents"),
            "max_daily_loss_cents": settings.get("max_daily_loss_cents"),
        },
        "occupancy": observation_unavailable("research ITI unit positions unread"),
        "kill_switch": unavailable("UNAVAILABLE"),
        "live_armed": {"value": False, "status": "CONFIRMED"},
        "state": observation_unavailable("research ITI Risk dump unread"),
        "note": (
            "Desired session limits only. This is not the MLB 001 Risk dump. "
            "Browser does not submit. Risk lives on the isolated demo unit."
        ),
    }


def heartbeat_view(bot: dict[str, Any]) -> dict[str, Any]:
    attach = bot.get("attach") if isinstance(bot.get("attach"), dict) else {}
    unit = attach.get("unit") if isinstance(attach.get("unit"), dict) else {}
    running = bot.get("activation") == "RUNNING_DEMO" or bot.get("status") == "RUNNING_DEMO"
    return {
        "bot_id": bot.get("bot_id"),
        "layer": "heartbeat",
        "source_pointer": unit.get("unit") or bot.get("aws_runtime_id"),
        "heartbeat": (
            {"status": "CONFIRMED", "value": "RUNNING_DEMO"}
            if running
            else observation_unavailable("research ITI unit heartbeat unread")
        ),
        "lifecycle": bot.get("activation") or bot.get("status") or "CREATED",
        "health": "RUNNING_DEMO" if running else "UNKNOWN",
        "kill_switch": unavailable("UNAVAILABLE"),
        "live_armed": {"value": False, "status": "CONFIRMED"},
        "http_200_not_running": True,
        "unit_state": "RUNNING_DEMO" if running else (bot.get("deploy") or {}).get("status") or "DEPLOY_REQUIRED",
        "kalshi_demo": (attach.get("kalshi_demo") or {}).get("status") or "OBSERVATION_UNAVAILABLE",
        "live_ev": unavailable("UNAVAILABLE"),
        "sharpe": unavailable("UNAVAILABLE"),
    }


def controls_view(bot: dict[str, Any]) -> dict[str, Any]:
    return {
        "bot_id": bot.get("bot_id"),
        "layer": "controls",
        "actions": ("attach",),
        "post": f"/vital/bots/{bot.get('bot_id')}/activate",
        "enabled": True,
        "control_env": None,
        "host_unit": (bot.get("aws_runtime_id") if bot.get("activation") == "RUNNING_DEMO" else None),
        "confirmation_token_name": "VITAL_ENABLE_DEMO",
        "live_confirmation_is_not_control": "ENABLE_LIVE_TRADING",
        "start_is_not_live_arm": True,
        "kill_is_not_stop": True,
        "http_200_not_running": True,
        "fail_closed": True,
        "default_status": bot.get("activation") or "DEMO_ATTACH_UNAVAILABLE",
        "note": (
            "Create starts momento-demo@{bot} with the ITI toml after Kalshi/AWS observe. "
            "RUNNING_DEMO only after is-active. Browser does not submit."
        ),
    }


def boundary_view(bot: dict[str, Any]) -> dict[str, Any]:
    engine = _engine(bot)
    impl = _impl(engine)
    return {
        "bot_id": bot.get("bot_id"),
        "layer": "boundary",
        "engine_pointer": engine.get("engine_pointer") or bot.get("engine_pointer") or "research_iti",
        "strategy_pointer": engine.get("strategy_pointer") or bot.get("strategy_pointer"),
        "sport": engine.get("sport") or bot.get("sport"),
        "factory": None,
        "not_mlb_factory": True,
        "not_80_81": True,
        "submit": False,
        "implementation": {
            "spec": impl.get("spec") or "IMPLEMENTED",
            "worker": impl.get("worker") or "OPERATION_REQUIRED",
        },
    }


def worker_view(bot: dict[str, Any]) -> dict[str, Any]:
    engine = _engine(bot)
    impl = _impl(engine)
    attach = bot.get("attach") if isinstance(bot.get("attach"), dict) else {}
    unit = attach.get("unit") if isinstance(attach.get("unit"), dict) else {}
    running = bool(unit.get("active") or bot.get("activation") == "RUNNING_DEMO")
    unit_name = unit.get("unit") or bot.get("aws_runtime_id")
    return {
        "bot_id": bot.get("bot_id"),
        "phase": "research_iti",
        "layer": "worker",
        "kind": "research_iti",
        "independent_of_vital": False,
        "vital_submits": False,
        "second_worker": False,
        "moved": False,
        "unit": unit_name if running else None,
        "unit_state": "RUNNING_DEMO" if running else "DEPLOY_REQUIRED",
        "binary": "momento-trading-engine-demo" if running else None,
        "repo_pointer": engine.get("engine_pointer") or "research_iti",
        "submitter": None,
        "implementation": {
            "spec": impl.get("spec") or "IMPLEMENTED",
            "worker": impl.get("worker") or unit_name or "OPERATION_REQUIRED",
            "submit": False,
        },
        "observed": (
            {"status": "CONFIRMED", "value": unit_name}
            if running
            else observation_unavailable("research ITI unit unread")
        ),
        "note": (
            "Isolated momento-demo unit runs the ITI spec through existing Risk. "
            "Not momento-live. Not factory 80–83. Browser does not submit."
        ),
    }


def pipeline_view(bot: dict[str, Any]) -> dict[str, Any]:
    engine = _engine(bot)
    prices = _prices(engine)
    iti = _iti(bot, engine)
    return {
        "bot_id": bot.get("bot_id"),
        "layer": "pipeline",
        "path": "ROLLER → SuperASI A → SuperASI B → ITI → Jump → Vital",
        "factory": None,
        "engine": engine,
        "prices": prices,
        "iti": {
            "folder": iti.get("folder") or bot.get("strategy_pointer") or bot.get("iti_lineage"),
            "slot_id": iti.get("slot_id") or bot.get("slot_id"),
        },
        "stages": (
            {"id": "ROLLER", "owner": "research question", "submits": False},
            {"id": "SUPERASI_A", "owner": "A Base", "submits": False},
            {"id": "SUPERASI_B", "owner": "B Debase", "submits": False},
            {"id": "ITI", "owner": "price-variant slot", "submits": False},
            {"id": "JUMP", "owner": "bot identity", "submits": False},
            {"id": "VITAL", "owner": "engine spec + isolated demo unit", "submits": False},
            {"id": "WORKER", "owner": "momento-demo@ ITI", "submits": False},
        ),
        "note": "Candle path ≠ fill. This pipeline does not become 80/81.",
    }
