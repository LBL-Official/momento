"""Vital HTTP handlers. Mounted on the ROLLER terminal API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.vital.activate import handle_activate as activate_bot
from roller.vital.bankroll import handle_allocation, handle_bankroll, handle_limits
from roller.vital.bots import ensure_mlb_001, get_bot, list_bots, public_bot
from roller.vital.control import submit_command
from roller.vital.fingerprints import (
    load_fingerprints,
    record_ownership,
)
from roller.vital.mlb_001.kalshi_observe import kalshi_demo_status, kalshi_status, observe_kalshi
from roller.vital.mlb_001.pipeline import pipeline_view
from roller.vital.mlb_001.plane import (
    boundary_view,
    configuration_view,
    controls_view,
    heartbeat_view,
    plane_catalog,
    risk_view,
    strategy_view,
)
from roller.vital.mlb_001.worker import worker_view
from roller.vital.naming import BOT_STANDARD_PHASE
from roller.vital.observe import (
    events_view,
    health_view,
    logs_view,
    observe_bot,
    orders_view,
    positions_view,
    runtime_view,
    status_view,
)
from roller.vital.parameters import parameters_view, patch_parameters
from roller.vital.unit_observe import kalshi_health_view
from roller.vital.reconcile import (
    execution_view,
    fills_view,
    trade_detail_view,
    trades_view,
)
from roller.vital.store import (
    config_identity_path,
    default_vital_root,
    deployment_identity_path,
    read_json,
)
from roller.vital.versions import (
    BOT_ID,
    CAVEATS,
    CODE_VERSION,
    HONESTY,
    INTEGRATION_PROOF,
    INTEGRATION_PROOF_STATUS,
    LIVE_EXECUTION,
    PHASE_STATUS,
    SCHEMA_VERSION,
)


def _root(root: Path | None) -> Path | None:
    return root


def handle_desk(bot_id: str | None = None, surface: str = "list", *, root: Path | None = None) -> dict[str, Any]:
    from roller.vital.desk import build_desk

    return build_desk(bot_id, surface, root=root)


def handle_health(*, root: Path | None = None) -> dict[str, Any]:
    ensure_mlb_001(root=root)
    try:
        record_ownership(root=root)
    except OSError:
        pass
    return {
        "status": "ok",
        "product": "Vital",
        "code_version": CODE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "phases": dict(PHASE_STATUS),
        "bot_standard_phases": dict(BOT_STANDARD_PHASE),
        "library_path": str(root or default_vital_root()),
        "bot_id": BOT_ID,
        "live_execution": LIVE_EXECUTION,
        "canonical_owner": True,
        "http_200_not_running": True,
        "honesty": dict(HONESTY),
        "caveats": list(CAVEATS),
        "integration_proof": {
            "id": INTEGRATION_PROOF,
            "status": INTEGRATION_PROOF_STATUS,
            "accepted_only_if_suites_confirmed": True,
        },
    }


def handle_bots_list(*, root: Path | None = None) -> dict[str, Any]:
    ensure_mlb_001(root=root)
    try:
        import os

        from roller.vital.register import backfill_jump_demo_bots

        if root is None or os.environ.get("JUMP_BOTS_ROOT"):
            backfill_jump_demo_bots(vital_root=root)
    except Exception:
        pass
    from roller.vital.observe import overlay_confirmed_lifecycle

    bots = [public_bot(overlay_confirmed_lifecycle(row, root=root)) for row in list_bots(root=root)]
    return {"bots": bots, "n": len(bots), "canonical_owner": True}


def handle_bots_get(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    from roller.vital.observe import overlay_confirmed_lifecycle

    bot = overlay_confirmed_lifecycle(get_bot(bot_id, root=root), root=root)
    if str(bot.get("bot_id") or "") == BOT_ID or bot.get("kind") == "grandfathered":
        extra = {
            "fingerprints": load_fingerprints(root=root),
            "config_identity": read_json(config_identity_path(BOT_ID, root=root)),
            "deployment_identity": read_json(deployment_identity_path(BOT_ID, root=root)),
        }
        return public_bot(bot, extra=extra)
    return public_bot(bot)


def handle_status(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    return status_view(bot_id, root=root)


def handle_bot_health(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    return health_view(bot_id, root=root)


def handle_runtime(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    return runtime_view(bot_id, root=root)


def handle_deployment(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    return {
        "bot_id": BOT_ID,
        "identity": read_json(deployment_identity_path(BOT_ID, root=root)),
        "fingerprints": load_fingerprints(root=root),
    }


def handle_logs(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    return logs_view(bot_id, root=root)


def handle_parameters(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    return parameters_view(bot_id, root=root)


def handle_parameters_patch(bot_id: str, body: dict[str, Any] | None = None, *, root: Path | None = None) -> dict[str, Any]:
    return patch_parameters(bot_id, body or {}, root=root)


def handle_kalshi_health(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    return kalshi_health_view(bot_id, root=root)


def handle_orders(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    return orders_view(bot_id, root=root)


def handle_positions(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    return positions_view(bot_id, root=root)


def handle_execution(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    return execution_view(bot_id, root=root)


def handle_execution_trades(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    return trades_view(bot_id, root=root)


def handle_execution_fills(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    return fills_view(bot_id, root=root)


def handle_execution_trade(bot_id: str, trade_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    return trade_detail_view(bot_id, trade_id, root=root)


def handle_events(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    return events_view(bot_id, root=root)


def handle_observe(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    return observe_bot(bot_id, root=root)


def handle_integration(bot_id: str, *, root: Path | None = None, refresh: bool = False) -> dict[str, Any]:
    from roller.vital.integration_proof import evaluate_proof

    view = observe_bot(bot_id, root=root, persist=False, refresh=refresh)
    bot = view.get("bot") if isinstance(view.get("bot"), dict) else get_bot(bot_id, root=root)
    inspect = view.get("inspect") if isinstance(view.get("inspect"), dict) else None
    runtime = view.get("runtime") if isinstance(view.get("runtime"), dict) else {}
    if isinstance(inspect, dict) and runtime:
        inspect = dict(inspect)
        inspect.setdefault("ok", runtime.get("lifecycle") in {"RUNNING", "RUNNING_DEMO", "STOPPED", "KILLED"})
        inspect.setdefault("heartbeat", runtime.get("heartbeat"))
        inspect.setdefault("service", runtime.get("service"))
        inspect.setdefault("process", runtime.get("process"))
        inspect.setdefault("version", runtime.get("version"))
        inspect.setdefault("environment", runtime.get("environment_fact") or runtime.get("environment"))
        inspect.setdefault("logs", (view.get("kalshi_health") or {}).get("logs"))
    return evaluate_proof(str(bot.get("bot_id") or bot_id), bot=bot, inspect=inspect, view=view, root=root)


def handle_demo_lifecycle(bot_id: str, body: dict[str, Any] | None = None, *, root: Path | None = None) -> dict[str, Any]:
    from roller.vital.demo_control import run_demo_lifecycle

    bot = get_bot(bot_id, root=root)
    if _mlb_factory_bot(bot):
        from roller.vital.errors import VitalError

        raise VitalError("REJECTED", "mlb-001 factory unit is not a demo lifecycle target")
    return run_demo_lifecycle(bot, body or {}, root=root)


def handle_integration_handshake(bot_id: str, body: dict[str, Any] | None = None, *, root: Path | None = None) -> dict[str, Any]:
    from roller.vital.integration_proof import (
        build_production_handshake,
        persist_demo_strategy_proof,
    )
    from roller.vital.versions import LIVE_CONFIRMATION

    body = body or {}
    if str(body.get("confirmation") or "").strip() == LIVE_CONFIRMATION:
        from roller.vital.errors import VitalError

        raise VitalError("REJECTED", "ENABLE_LIVE_TRADING is not an integration handshake token")
    bot = get_bot(bot_id, root=root)
    if _mlb_factory_bot(bot):
        view = observe_bot(BOT_ID, root=root, persist=True, refresh=bool(body.get("refresh")))
        inspect = view.get("inspect") if isinstance(view.get("inspect"), dict) else {}
        runtime = view.get("runtime") if isinstance(view.get("runtime"), dict) else {}
        packed = dict(inspect)
        packed.setdefault("ok", runtime.get("lifecycle") == "RUNNING")
        packed.setdefault("heartbeat", runtime.get("heartbeat"))
        packed.setdefault("service", runtime.get("service"))
        packed.setdefault("process", runtime.get("process"))
        packed.setdefault("version", runtime.get("version"))
        handshake = build_production_handshake(packed, root=root)
        return {
            **handshake,
            "http_200_not_running": True,
            "wrote_live_toml": False,
            "submits": False,
        }
    from roller.vital.unit_observe import inspect_isolated_unit

    inspected = inspect_isolated_unit(str(bot.get("bot_id") or bot_id), root=root)
    engine = bot.get("engine") if isinstance(bot.get("engine"), dict) else {}
    prices = engine.get("prices") if isinstance(engine.get("prices"), dict) else {}
    iti = bot.get("iti") if isinstance(bot.get("iti"), dict) else {}
    desired = {
        "strategy_id": str(body.get("strategy_id") or bot.get("bot_id")),
        "profile": "research_iti",
        "entry_cents": prices.get("entry_cents") if prices.get("entry_cents") is not None else iti.get("entry_cents"),
        "win_cents": prices.get("win_cents") if prices.get("win_cents") is not None else iti.get("win_cents"),
        "loss_cents": prices.get("loss_cents") if prices.get("loss_cents") is not None else iti.get("loss_cents"),
    }
    config = inspected.get("config") if isinstance(inspected.get("config"), dict) else {}
    proof = {
        "ok": bool(inspected.get("ok")),
        "bot_id": bot.get("bot_id"),
        "bot": bot,
        "inspect": inspected,
        "desired": desired,
        "written": {"strategy_profile": config.get("strategy_profile") or desired["profile"]},
        "observed": config,
        "loaded": {"ok": bool(inspected.get("ok") and inspected.get("heartbeat") and config.get("strategy_profile") == "research_iti")},
        "vital_test_id": body.get("vital_test_id"),
        "strategy_id": desired["strategy_id"],
        "signal_id": body.get("signal_id"),
        "intent_id": body.get("intent_id"),
        "order_id": body.get("order_id"),
        "fill_id": body.get("fill_id"),
        "risk_decision": body.get("risk_decision"),
        "demo_order_attempt": body.get("demo_order_attempt"),
        "demo_exchange_response": body.get("demo_exchange_response"),
        "correlation": {
            "vital_test_id": body.get("vital_test_id"),
            "strategy_id": desired["strategy_id"],
            "signal_id": body.get("signal_id"),
            "intent_id": body.get("intent_id"),
            "order_id": body.get("order_id"),
        },
        "never_momento_live": True,
        "http_200_not_running": True,
        "submits": False,
    }
    persist_demo_strategy_proof(proof, root=root)
    return proof


def handle_host_observe(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    view = observe_bot(bot_id, root=root, persist=True, refresh=True)
    runtime = view.get("runtime") if isinstance(view.get("runtime"), dict) else {}
    inspect = view.get("inspect") if isinstance(view.get("inspect"), dict) else {}
    return {
        "bot_id": (view.get("bot") or {}).get("bot_id") or bot_id,
        "refreshed": True,
        "read_only": True,
        "submits": False,
        "http_200_not_running": True,
        "runtime": runtime,
        "inspect": inspect,
        "lifecycle": runtime.get("lifecycle") or "OBSERVATION_UNAVAILABLE",
        "health": runtime.get("health") or "UNKNOWN",
    }


def handle_command(bot_id: str, body: dict[str, Any] | None = None, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    return submit_command(bot_id, body or {}, root=root)


def _mlb_factory_bot(bot: dict[str, Any]) -> bool:
    return str(bot.get("bot_id") or "") == BOT_ID or bot.get("kind") == "grandfathered"


def handle_plane(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if _mlb_factory_bot(bot):
        return plane_catalog(bot_id, root=root)
    from roller.vital.research_engine import plane_view

    return plane_view(bot)


def handle_configuration(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if _mlb_factory_bot(bot):
        return configuration_view(bot_id, root=root)
    from roller.vital.research_engine import configuration_view as research_configuration_view

    return research_configuration_view(bot)


def handle_strategy(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if _mlb_factory_bot(bot):
        return strategy_view(bot_id, root=root)
    from roller.vital.research_engine import strategy_view as research_strategy_view

    return research_strategy_view(bot)


def handle_risk(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if _mlb_factory_bot(bot):
        return risk_view(bot_id, root=root)
    from roller.vital.research_engine import risk_view as research_risk_view

    return research_risk_view(bot)


def handle_heartbeat(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if _mlb_factory_bot(bot):
        return heartbeat_view(bot_id, root=root)
    from roller.vital.research_engine import heartbeat_view as research_heartbeat_view

    return research_heartbeat_view(bot)


def handle_controls(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if _mlb_factory_bot(bot):
        return controls_view(bot_id, root=root)
    from roller.vital.research_engine import controls_view as research_controls_view

    return research_controls_view(bot)


def handle_boundary(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if _mlb_factory_bot(bot):
        return boundary_view(bot_id, root=root)
    from roller.vital.research_engine import boundary_view as research_boundary_view

    return research_boundary_view(bot)


def handle_worker(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if _mlb_factory_bot(bot):
        return worker_view(bot_id, root=root)
    from roller.vital.research_engine import worker_view as research_worker_view

    return research_worker_view(bot)


def handle_pipeline(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if _mlb_factory_bot(bot):
        return pipeline_view(bot_id, root=root)
    from roller.vital.research_engine import pipeline_view as research_pipeline_view

    return research_pipeline_view(bot)


def handle_bankroll_get(*, root: Path | None = None) -> dict[str, Any]:
    return handle_bankroll(root=root)


def handle_allocation_post(bot_id: str, body: dict[str, Any] | None = None, *, root: Path | None = None) -> dict[str, Any]:
    return handle_allocation(bot_id, body, root=root)


def handle_limits_post(bot_id: str, body: dict[str, Any] | None = None, *, root: Path | None = None) -> dict[str, Any]:
    return handle_limits(bot_id, body, root=root)


def handle_activate_post(bot_id: str, body: dict[str, Any] | None = None, *, root: Path | None = None) -> dict[str, Any]:
    return activate_bot(bot_id, body, root=root)


def handle_promote_post(bot_id: str, body: dict[str, Any] | None = None, *, root: Path | None = None) -> dict[str, Any]:
    from roller.jump.bots.pipeline import promote_bot
    from roller.jump.bots.store import list_bots as jump_list
    from roller.jump.bots.store import load_bot as jump_load
    from roller.vital.errors import VitalError

    if _mlb_factory_bot({"bot_id": bot_id}) or bot_id in {BOT_ID, "mlb-bot-one"}:
        raise VitalError("REJECTED", "mlb-001 is observed, not promoted")
    jump_id = None
    try:
        bot = get_bot(bot_id, root=root)
        jump_id = bot.get("jump_bot_id")
    except Exception:
        bot = None
    if not jump_id:
        for row in jump_list():
            if str(row.get("vital_bot_id") or "") == bot_id or str(row.get("bot_id") or "") == bot_id:
                jump_id = row.get("bot_id")
                break
    if not jump_id:
        raise VitalError("BOT_NOT_FOUND", "Jump bot id unread for promote")
    promoted = promote_bot(str(jump_id), body)
    vital = get_bot(bot_id, root=root) if bot else promoted
    return {
        **(vital if isinstance(vital, dict) else {}),
        "promote": promoted,
        "http_200_not_running": True,
        "submits": False,
    }


def handle_diagnose(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if _mlb_factory_bot(bot):
        from roller.vital.mlb_001.diagnose import diagnose_mlb_001

        return diagnose_mlb_001(root=root)
    from roller.vital.errors import VitalError

    raise VitalError("REJECTED", "diagnose is implemented for mlb-001 only")


def handle_start_if_armed(bot_id: str, body: dict[str, Any] | None = None, *, root: Path | None = None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if not _mlb_factory_bot(bot):
        from roller.vital.errors import VitalError

        raise VitalError("REJECTED", "armed start is implemented for mlb-001 only")
    from roller.vital.mlb_001.diagnose import start_mlb_001_if_armed

    return start_mlb_001_if_armed(body, root=root)


def handle_kalshi(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    if _mlb_factory_bot(bot):
        return kalshi_status()
    attach = bot.get("attach") if isinstance(bot.get("attach"), dict) else {}
    if str(bot.get("environment") or "").upper() == "PRODUCTION":
        live = kalshi_status()
        return {
            **live,
            "bot_id": str(bot.get("bot_id") or bot_id),
            "environment": "PRODUCTION",
            "read_only": True,
            "submits": False,
            "fill_n": None,
            "mlb_001_fills_not_copied": True,
            "http_200_not_running": True,
        }
    stored = attach.get("kalshi_demo") if isinstance(attach.get("kalshi_demo"), dict) else {}
    live = kalshi_demo_status()
    chosen = live if live.get("status") == "CONFIRMED" else (stored or live)
    return {
        **chosen,
        "bot_id": str(bot.get("bot_id") or bot_id),
        "environment": "DEMO",
        "read_only": True,
        "submits": False,
        "attach": stored or None,
        "http_200_not_running": True,
    }


def handle_kalshi_observe(
    bot_id: str,
    body: dict[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    from roller.vital.bankroll import _target_bot
    from roller.vital.versions import LIVE_CONFIRMATION

    body = body or {}
    if str(body.get("confirmation") or "").strip() == LIVE_CONFIRMATION:
        from roller.vital.errors import VitalError

        raise VitalError(
            "REJECTED",
            "ENABLE_LIVE_TRADING is the engine live gate, not a Vital observe token",
        )
    env = str(body.get("environment") or "").strip().upper()
    bot = None
    try:
        bot = _target_bot(bot_id, root=root)
    except Exception:
        bot = None
    if env not in {"DEMO", "PRODUCTION"}:
        env = "DEMO" if bot and str(bot.get("environment") or "").upper() == "DEMO" else "PRODUCTION"
    if bot and not _mlb_factory_bot(bot) and env == "PRODUCTION":
        if str(bot.get("environment") or "").upper() != "PRODUCTION":
            from roller.vital.errors import VitalError

            raise VitalError(
                "OPERATION_REQUIRED",
                "research ITI production observe requires a promoted isolated live unit",
            )
    observed = observe_kalshi(environment=env)
    if env != "PRODUCTION":
        if bot and not _mlb_factory_bot(bot):
            from roller.vital.demo_attach import update_kalshi_attach

            update_kalshi_attach(bot, observed, vital_root=root)
        return {
            **observed,
            "bot_id": str((bot or {}).get("bot_id") or bot_id),
            "environment": env,
            "http_200_not_running": True,
        }
    if bot and not _mlb_factory_bot(bot):
        from roller.vital.demo_attach import update_kalshi_attach

        update_kalshi_attach(bot, observed, vital_root=root)
        return {
            **observed,
            "bot_id": str(bot.get("bot_id") or bot_id),
            "environment": env,
            "http_200_not_running": True,
            "mlb_001_fills_not_copied": True,
        }
    get_bot(bot_id, root=root)
    from roller.vital.mlb_001.settlement import observe_settlements
    from roller.vital.store import load_execution_fills
    from roller.vital.execution import fact_value, is_confirmed

    resolved = BOT_ID
    tickers = [
        str(fact_value(row.get("market")) or "")
        for row in load_execution_fills(resolved, root=root)
        if is_confirmed(row.get("market"))
    ]
    observe_settlements(resolved, tickers, root=root, fetch=True, max_fetch=None)
    execution = execution_view(bot_id, root=root)
    return {
        **observed,
        "bot_id": BOT_ID,
        "environment": env,
        "execution": {
            "status": execution.get("status"),
            "trades_status": execution.get("trades_status"),
            "fills_status": execution.get("fills_status"),
            "grouping": execution.get("grouping"),
        },
    }
