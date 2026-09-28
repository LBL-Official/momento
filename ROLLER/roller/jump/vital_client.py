"""Jump reads Vital. In-process. Not a second registry."""

from __future__ import annotations

from typing import Any

from roller.jump.bots.versions import BOT_ONE_ID
from roller.vital.versions import BOT_ID


def vital_id_for_jump_bot(bot: dict[str, Any] | str | None) -> str:
    if isinstance(bot, str):
        if bot in {BOT_ONE_ID, BOT_ID, "mlb-001"}:
            return BOT_ID
        return bot
    if not isinstance(bot, dict):
        return BOT_ID
    if str(bot.get("bot_id") or "") == BOT_ONE_ID or bot.get("kind") == "grandfathered":
        return BOT_ID
    return str(bot.get("vital_bot_id") or bot.get("bot_id") or BOT_ID)


def vital_bots(*, root=None) -> dict[str, Any]:
    from roller.vital.api import handle_bots_list

    return handle_bots_list(root=root)


def vital_bankroll(*, root=None, now=None) -> dict[str, Any]:
    from roller.vital.bankroll import bankroll_view

    return bankroll_view(root=root, now=now)


def vital_observe(bot_id: str, *, root=None, now=None) -> dict[str, Any]:
    from roller.vital.observe import observe_bot

    return observe_bot(vital_id_for_jump_bot(bot_id), persist=False, root=root, now=now)


def vital_kalshi_health(bot_id: str, *, root=None) -> dict[str, Any]:
    from roller.vital.api import handle_kalshi_health

    return handle_kalshi_health(vital_id_for_jump_bot(bot_id), root=root)


def vital_execution(bot_id: str, *, root=None) -> dict[str, Any]:
    from roller.vital.api import handle_execution

    return handle_execution(vital_id_for_jump_bot(bot_id), root=root)


def vital_bot_status(bot_id: str = BOT_ID, *, root=None) -> dict[str, Any]:
    view = vital_observe(bot_id, root=root)
    runtime = view.get("runtime") if isinstance(view.get("runtime"), dict) else {}
    bot = view.get("bot") if isinstance(view.get("bot"), dict) else {}
    return {
        "bot_id": bot.get("bot_id") or vital_id_for_jump_bot(bot_id),
        "name": bot.get("name"),
        "environment": bot.get("environment") or runtime.get("environment"),
        "lifecycle": runtime.get("lifecycle") or "OBSERVATION_UNAVAILABLE",
        "health": runtime.get("health"),
        "desired": runtime.get("desired"),
        "observed": runtime.get("observed"),
        "confirmed": runtime.get("confirmed"),
        "http_200_not_running": True,
    }


def vital_bot_health(bot_id: str = BOT_ID, *, root=None) -> dict[str, Any]:
    from roller.vital.api import handle_bot_health

    return handle_bot_health(vital_id_for_jump_bot(bot_id), root=root)


def vital_runtime(bot_id: str = BOT_ID, *, root=None, now=None) -> dict[str, Any]:
    return vital_observe(bot_id, root=root, now=now).get("runtime") or {}


def _unit_name(runtime: dict[str, Any], *, bot_id: str) -> str | None:
    del bot_id
    service = runtime.get("service")
    if isinstance(service, dict):
        value = service.get("value") if isinstance(service.get("value"), dict) else {}
        name = value.get("name") or service.get("name")
        active = value.get("active")
        if name and str(service.get("status") or "") == "CONFIRMED" and active in {"active", "ACTIVE", True}:
            return str(name)
    observed = runtime.get("observed") if isinstance(runtime.get("observed"), dict) else {}
    if observed.get("unit") and observed.get("unit_started"):
        return str(observed["unit"])
    return None


def jump_observation_from_vital(
    status: dict[str, Any] | None = None,
    *,
    bot_id: str = BOT_ID,
    root=None,
    now=None,
) -> dict[str, Any]:
    resolved = vital_id_for_jump_bot(bot_id)
    if isinstance(status, dict) and status.get("runtime"):
        view = status
    elif isinstance(status, dict) and ("lifecycle" in status or "confirmed" in status):
        view = {"runtime": status, "bot": {"bot_id": resolved, "environment": status.get("environment")}}
    else:
        try:
            view = vital_observe(resolved, root=root, now=now)
        except Exception:
            return {
                "status": "OBSERVATION_UNAVAILABLE",
                "environment": None,
                "live_armed_confirmed": False,
                "aws_runtime_id": None,
                "observed": False,
                "source": "vital",
                "detail": "Vital has not confirmed this bot; Jump does not invent RUNNING",
                "vital_bot_id": resolved,
            }
    runtime = view.get("runtime") if isinstance(view.get("runtime"), dict) else {}
    bot = view.get("bot") if isinstance(view.get("bot"), dict) else {}
    lifecycle = str(runtime.get("lifecycle") or "OBSERVATION_UNAVAILABLE")
    confirmed = runtime.get("confirmed") if isinstance(runtime.get("confirmed"), dict) else {}
    life = confirmed.get("lifecycle") if isinstance(confirmed.get("lifecycle"), dict) else {}
    observed = life.get("status") == "CONFIRMED"
    armed = runtime.get("live_armed") if isinstance(runtime.get("live_armed"), dict) else {}
    live = bool(armed.get("status") == "CONFIRMED" and armed.get("value") is True)
    environment = bot.get("environment") or runtime.get("environment")
    if observed and not environment:
        environment = "PRODUCTION" if resolved == BOT_ID else "DEMO"
    return {
        "status": lifecycle,
        "environment": environment if observed else None,
        "live_armed_confirmed": live,
        "aws_runtime_id": _unit_name(runtime, bot_id=resolved) if observed else None,
        "health": runtime.get("health"),
        "observed": observed,
        "source": "vital",
        "detail": (
            None
            if observed
            else (life.get("detail") or "Vital has not confirmed this bot; Jump does not invent RUNNING")
        ),
        "vital_bot_id": resolved,
    }


def jump_heartbeat_from_vital(
    runtime: dict[str, Any] | None = None,
    *,
    bot_id: str = BOT_ID,
    now=None,
    root=None,
) -> dict[str, Any]:
    if runtime is None:
        try:
            body = vital_runtime(bot_id, root=root, now=now)
        except Exception:
            body = {}
    else:
        body = runtime
    fields: dict[str, Any] = {}
    for key in (
        "bankroll_cents",
        "open_mlb_positions",
        "day_pnl",
        "week_pnl",
        "kill_switch",
        "reconciliation",
        "reservations_n",
        "unknown_orders",
        "open_slots",
        "order_submission",
        "mlb_yes_bid_n",
        "first80_n",
        "first81_n",
        "submit_to_ack_n",
        "submit_refused_n",
        "last_mlb_ticker",
        "last_mlb_bid_cents",
        "last_mlb_ask_cents",
        "occupancy_trap",
    ):
        metric = body.get(key)
        if not isinstance(metric, dict) or metric.get("status") != "CONFIRMED":
            continue
        dest = "day_pnl_cents" if key == "day_pnl" else "week_pnl_cents" if key == "week_pnl" else key
        fields[dest] = metric.get("value")
    unit = _unit_name(body if isinstance(body, dict) else {}, bot_id=vital_id_for_jump_bot(bot_id))
    if unit:
        fields["aws_runtime_id"] = unit
    observed = bool(fields) or (
        isinstance(body.get("confirmed"), dict)
        and isinstance(body["confirmed"].get("lifecycle"), dict)
        and body["confirmed"]["lifecycle"].get("status") == "CONFIRMED"
    )
    return {
        "observed": observed,
        "fields": fields,
        "status": "CONFIRMED" if observed else "OBSERVATION_UNAVAILABLE",
        "source": "vital",
        "ledger": False,
        "detail": None if observed else "Vital host unread; Jump does not invent Bot One metrics",
    }
