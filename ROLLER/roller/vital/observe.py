"""Compose desired / observed / confirmed. Missing is not zero."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.vital.aws import inspect_mlb_001, instance_id
from roller.vital.bots import get_bot
from roller.vital.honesty import confirmed, observation_unavailable, unavailable
from roller.vital.models import utc_now
from roller.vital.store import (
    append_event,
    list_events,
    read_json,
    runtime_path,
    write_json,
)
from roller.vital.versions import BOT_ID, SERVICE_NAME

OBSERVED_STALE_S = 300.0
ENGINE_HEARTBEAT_SECS = 5
VENUE_AUTH_NEEDLES = (
    "auth=failed",
    "auth_error",
    "unauthorized",
    "invalid_signature",
    "401 ",
    "403 ",
    "venue_error",
    "venueerror",
    "production_auth=false",
)

try:
    from roller.jump.catalog.connection import connection_metrics
except Exception:  # pragma: no cover - Jump catalog optional at import
    connection_metrics = None  # type: ignore[assignment]


def _metric(value: Any, *, missing: str = "OBSERVATION_UNAVAILABLE") -> dict[str, Any]:
    if value is None:
        return {"value": None, "status": missing}
    if isinstance(value, dict) and "status" in value and "value" in value:
        return value
    return confirmed(value)


def _active(inspect: dict[str, Any]) -> bool | None:
    service = inspect.get("service")
    if isinstance(service, dict) and isinstance(service.get("value"), dict):
        raw = service["value"].get("active")
        if raw in {"active", "ACTIVE", True}:
            return True
        if raw in {"inactive", "failed", "dead", False}:
            return False
    return None


OCCUPANCY_CAP = 5


def _metric_raw(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def _journal_text(inspect: dict[str, Any]) -> str:
    logs = inspect.get("logs")
    if isinstance(logs, list):
        return "\n".join(str(line) for line in logs)
    if isinstance(logs, str):
        return logs
    return ""


def trading_health(
    *,
    fields: dict[str, Any] | None = None,
    inspect: dict[str, Any] | None = None,
    observed_at: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Observe-only trading gate. Process up is not authorization to trade.

    Flags; does not flatten, kill, or force Healthy.
    """
    payload = inspect if isinstance(inspect, dict) else {}
    if not payload.get("ok"):
        return observation_unavailable("host unread")
    beat = fields if isinstance(fields, dict) else {}
    recon = _metric_raw(beat.get("reconciliation"))
    submit = _metric_raw(beat.get("order_submission"))
    unknowns = _metric_raw(beat.get("unknown_orders"))
    recon_text = str(recon or "").strip()
    submit_text = str(submit or "").strip()
    flags: list[dict[str, Any]] = []
    clock = now or datetime.now(timezone.utc)
    stamp = _parse_observed_at(observed_at)
    age = (clock - stamp).total_seconds() if stamp is not None else None
    if age is None or age < 0 or age > OBSERVED_STALE_S:
        flags.append(
            {
                "id": "heartbeat_stale",
                "level": "alert",
                "age_secs": age,
                "stale_after_secs": int(OBSERVED_STALE_S),
            }
        )
    if recon_text.lower() == "ambiguous":
        flags.append(
            {
                "id": "recon_ambiguous",
                "level": "alert",
                "unknowns": unknowns,
            }
        )
    if submit_text.lower() == "blocked":
        flags.append({"id": "order_submission_blocked", "level": "alert"})
    journal = _journal_text(payload)
    journal_l = journal.lower()
    if "recon_cleared" in journal_l and submit_text.lower() == "blocked":
        flags.append({"id": "sticky_blocked_after_recon_cleared", "level": "alert"})
    auth_hits = [needle for needle in VENUE_AUTH_NEEDLES if needle in journal_l]
    if auth_hits:
        flags.append({"id": "venue_auth_error", "level": "alert", "needles": auth_hits})
    authorized = recon_text.lower() == "healthy" and submit_text.lower() == "enabled"
    return confirmed(
        {
            "status": "FLAGGED" if flags else "CLEAR",
            "authorized_to_submit": authorized,
            "process_up_is_not_authorization": True,
            "auto_flatten": False,
            "flags": flags,
            "heartbeat_age_secs": age,
            "stale_after_secs": int(OBSERVED_STALE_S),
            "engine_heartbeat_secs": ENGINE_HEARTBEAT_SECS,
            "reconciliation": recon_text or None,
            "order_submission": submit_text or None,
            "unknowns": unknowns,
            "needles": (
                "recon_cleared",
                "order_submission=blocked",
                "reconciliation=ambiguous",
            ),
        }
    )


def occupancy_trap(
    *,
    open_slots: Any = None,
    open_mlb_positions: Any = None,
    max_open_slots: Any = OCCUPANCY_CAP,
) -> dict[str, Any]:
    """Ghost cap: Risk slots full while tracker fills are zero. Unread is not False."""
    if open_slots is None or open_mlb_positions is None:
        return observation_unavailable("occupancy unread")
    try:
        slots = int(open_slots)
        fills = int(open_mlb_positions)
        cap = int(max_open_slots) if max_open_slots is not None else OCCUPANCY_CAP
    except (TypeError, ValueError):
        return observation_unavailable("occupancy unreadable")
    trapped = slots >= cap > 0 and fills == 0
    return confirmed(
        {
            "trapped": trapped,
            "open_slots": slots,
            "open_mlb_positions": fills,
            "max_open_slots": cap,
            "detail": "ghost cap: open_slots at max with no tracker fills" if trapped else None,
        }
    )


def _heartbeat_fields(inspect: dict[str, Any]) -> dict[str, Any]:
    beat = inspect.get("heartbeat")
    if isinstance(beat, dict) and isinstance(beat.get("value"), dict):
        return dict(beat["value"])
    ledger = inspect.get("ledger")
    if isinstance(ledger, dict) and isinstance(ledger.get("fields"), dict):
        return dict(ledger["fields"])
    return {}


def compose_runtime(
    bot: dict[str, Any],
    inspect: dict[str, Any],
    *,
    root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    fields = _heartbeat_fields(inspect)
    observed_ok = bool(inspect.get("ok"))
    active = _active(inspect)
    kill = fields.get("kill_switch")
    if kill is None and isinstance(inspect.get("paths"), dict):
        kill = inspect["paths"].get("kill_exists")
    desired = {
        "lifecycle": "OBSERVATION_UNAVAILABLE",
        "detail": "Vital does not claim RUNNING until observe confirms the host",
        "aws_runtime_id": SERVICE_NAME,
    }
    last_desired = read_json(runtime_path(str(bot["bot_id"]), "desired", root=root))
    if isinstance(last_desired, dict) and last_desired.get("lifecycle"):
        desired = dict(last_desired)

    if now is not None:
        clock = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        observed_at = clock.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        observed_at = utc_now()
    service_name = None
    service = inspect.get("service")
    if isinstance(service, dict) and isinstance(service.get("value"), dict):
        service_name = service["value"].get("name")
    if not observed_ok:
        lifecycle = "OBSERVATION_UNAVAILABLE"
        health = "UNKNOWN"
        confirmed_lifecycle = observation_unavailable(str(inspect.get("reason") or "host unread"))
    elif kill is True:
        lifecycle = "KILLED" if active is False else "RUNNING"
        health = "UNHEALTHY" if active is False else "DEGRADED"
        confirmed_lifecycle = confirmed(lifecycle)
    elif active is True:
        lifecycle = "RUNNING"
        health = "HEALTHY"
        confirmed_lifecycle = confirmed("RUNNING")
    elif active is False:
        lifecycle = "STOPPED"
        health = "UNKNOWN"
        confirmed_lifecycle = confirmed("STOPPED")
    elif fields:
        lifecycle = "OBSERVATION_UNAVAILABLE"
        health = "UNKNOWN"
        confirmed_lifecycle = observation_unavailable("service active not confirmed")
    else:
        lifecycle = "OBSERVATION_UNAVAILABLE"
        health = "UNKNOWN"
        confirmed_lifecycle = observation_unavailable(str(inspect.get("reason") or "host unread"))

    return {
        "bot_id": bot.get("bot_id"),
        "environment": bot.get("environment") or "PRODUCTION",
        "desired": desired,
        "observed": {
            "ok": observed_ok,
            "source": inspect.get("source"),
            "status": inspect.get("status") or ("OBSERVED" if observed_ok else "OBSERVATION_UNAVAILABLE"),
            "reason": inspect.get("reason"),
            "lifecycle_guess": lifecycle if observed_ok else "OBSERVATION_UNAVAILABLE",
            "observed_at": observed_at,
            "instance_id": inspect.get("instance_id") or instance_id(),
            "service": service_name or SERVICE_NAME,
        },
        "confirmed": {
            "lifecycle": confirmed_lifecycle,
            "health": confirmed(health) if observed_ok and health != "UNKNOWN" else observation_unavailable("health unconfirmed"),
        },
        "lifecycle": lifecycle,
        "health": health,
        "host": inspect.get("host") or observation_unavailable(),
        "service": inspect.get("service") or observation_unavailable(),
        "process": inspect.get("process") or observation_unavailable(),
        "version": inspect.get("version") or observation_unavailable(),
        "environment_fact": inspect.get("environment") or observation_unavailable(),
        "heartbeat": inspect.get("heartbeat") if isinstance(inspect.get("heartbeat"), dict) else observation_unavailable(),
        "kill_switch": _metric(kill, missing="OBSERVATION_UNAVAILABLE"),
        "live_armed": _metric(
            fields["live_armed_confirmed"] if "live_armed_confirmed" in fields else fields.get("live_armed"),
            missing="OBSERVATION_UNAVAILABLE",
        ),
        "open_mlb_positions": _metric(fields.get("open_mlb_positions"), missing="OBSERVATION_UNAVAILABLE"),
        "reconciliation": _metric(fields.get("reconciliation"), missing="OBSERVATION_UNAVAILABLE"),
        "reservations_n": _metric(fields.get("reservations_n"), missing="OBSERVATION_UNAVAILABLE"),
        "unknown_orders": _metric(fields.get("unknown_orders"), missing="OBSERVATION_UNAVAILABLE"),
        "open_slots": _metric(fields.get("open_slots"), missing="OBSERVATION_UNAVAILABLE"),
        "order_submission": _metric(fields.get("order_submission"), missing="OBSERVATION_UNAVAILABLE"),
        "trading_health": trading_health(
            fields=fields,
            inspect=inspect,
            observed_at=observed_at,
            now=now,
        ),
        "occupancy_trap": occupancy_trap(
            open_slots=fields.get("open_slots"),
            open_mlb_positions=fields.get("open_mlb_positions"),
            max_open_slots=fields.get("max_open_slots"),
        ),
        "mlb_yes_bid_n": _metric(fields.get("mlb_yes_bid_n"), missing="OBSERVATION_UNAVAILABLE"),
        "first80_n": _metric(fields.get("first80_n"), missing="OBSERVATION_UNAVAILABLE"),
        "first81_n": _metric(fields.get("first81_n"), missing="OBSERVATION_UNAVAILABLE"),
        "submit_to_ack_n": _metric(fields.get("submit_to_ack_n"), missing="OBSERVATION_UNAVAILABLE"),
        "submit_refused_n": _metric(fields.get("submit_refused_n"), missing="OBSERVATION_UNAVAILABLE"),
        "last_mlb_ticker": _metric(fields.get("last_mlb_ticker"), missing="OBSERVATION_UNAVAILABLE"),
        "last_mlb_bid_cents": _metric(fields.get("last_mlb_bid_cents"), missing="OBSERVATION_UNAVAILABLE"),
        "last_mlb_ask_cents": _metric(fields.get("last_mlb_ask_cents"), missing="OBSERVATION_UNAVAILABLE"),
        "heartbeat_markets": _metric(fields.get("heartbeat_markets"), missing="OBSERVATION_UNAVAILABLE"),
        "strategy_games": _metric(fields.get("strategy_games"), missing="OBSERVATION_UNAVAILABLE"),
        "wnba_games": _metric(fields.get("wnba_games"), missing="OBSERVATION_UNAVAILABLE"),
        "max_open_slots": _metric(fields.get("max_open_slots"), missing="OBSERVATION_UNAVAILABLE"),
        "journal_since": _metric(fields.get("journal_since"), missing="OBSERVATION_UNAVAILABLE"),
        "bankroll_cents": _metric(fields.get("bankroll_cents"), missing="OBSERVATION_UNAVAILABLE"),
        "day_pnl": _metric(fields.get("day_pnl_cents"), missing="OBSERVATION_UNAVAILABLE"),
        "week_pnl": _metric(fields.get("week_pnl_cents"), missing="OBSERVATION_UNAVAILABLE"),
        "live_ev": unavailable("UNAVAILABLE"),
        "sharpe": unavailable("UNAVAILABLE"),
        "instance_id": inspect.get("instance_id"),
        "instance_verified": bool(inspect.get("instance_verified")),
        "http_200_not_running": True,
    }


def _overlay_runtime_book(runtime: dict[str, Any], book: dict[str, Any]) -> None:
    current = runtime.get("open_mlb_positions")
    if isinstance(current, dict) and current.get("status") == "CONFIRMED":
        return
    pos = book.get("positions") if isinstance(book, dict) else None
    if not isinstance(pos, dict) or pos.get("status") != "CONFIRMED" or pos.get("value") is None:
        return
    runtime["open_mlb_positions"] = confirmed(pos.get("value"))
    runtime["open_mlb_positions_basis"] = "kalshi_book"


def _parse_observed_at(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def observation_is_fresh(observed: dict[str, Any] | None, *, now: datetime | None = None) -> bool:
    if not isinstance(observed, dict):
        return False
    stamp = _parse_observed_at(observed.get("observed_at"))
    if stamp is None:
        return False
    clock = now or datetime.now(timezone.utc)
    age = (clock - stamp).total_seconds()
    return 0 <= age <= OBSERVED_STALE_S


def overlay_confirmed_lifecycle(bot: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    rec = dict(bot)
    bot_id = str(bot.get("bot_id") or "")
    observed = read_json(runtime_path(bot_id, "observed", root=root))
    if not observation_is_fresh(observed if isinstance(observed, dict) else None):
        rec["status"] = "OBSERVATION_UNAVAILABLE"
        rec["activation"] = "OBSERVATION_UNAVAILABLE"
        rec["observation_freshness"] = "STALE" if isinstance(observed, dict) else "UNREAD"
        return rec
    payload = read_json(runtime_path(bot_id, "confirmed", root=root))
    if not isinstance(payload, dict):
        return rec
    life = payload.get("lifecycle")
    if isinstance(life, dict) and life.get("status") == "CONFIRMED" and life.get("value"):
        rec["status"] = life["value"]
        rec["activation"] = life["value"]
        rec["observation_freshness"] = "FRESH"
    health = payload.get("health")
    if isinstance(health, dict) and health.get("status") == "CONFIRMED" and health.get("value"):
        rec["health"] = health["value"]
    return rec


def _persist_observed_bot(bot: dict[str, Any], runtime: dict[str, Any], *, root: Path | None) -> None:
    lifecycle = str(runtime.get("lifecycle") or "")
    if lifecycle not in {"RUNNING", "STOPPED", "KILLED", "RUNNING_DEMO"}:
        return
    from roller.vital.store import save_bot

    rec = dict(bot)
    rec["status"] = lifecycle
    rec["activation"] = lifecycle
    rec["health"] = runtime.get("health") or rec.get("health")
    armed = runtime.get("live_armed")
    if isinstance(armed, dict) and armed.get("status") == "CONFIRMED":
        rec["live_armed_confirmed"] = bool(armed.get("value"))
    service = runtime.get("service")
    service_value = service.get("value") if isinstance(service, dict) and isinstance(service.get("value"), dict) else {}
    if service_value.get("name"):
        rec["aws_runtime_id"] = service_value["name"]
    save_bot(rec, root=root)


def kalshi_overlay() -> dict[str, Any]:
    if connection_metrics is None:
        return {
            "orders": observation_unavailable("kalshi book unread"),
            "positions": observation_unavailable("kalshi book unread"),
            "bankroll": observation_unavailable("kalshi book unread"),
            "day_pnl": observation_unavailable("kalshi book unread"),
            "week_pnl": observation_unavailable("kalshi book unread"),
            "live_ev": unavailable("UNAVAILABLE"),
            "sharpe": unavailable("UNAVAILABLE"),
        }
    metrics = connection_metrics(environment="PRODUCTION", now=datetime.now(timezone.utc), missing="OBSERVATION_UNAVAILABLE")
    return {
        "orders": observation_unavailable("orders are Kalshi fills; catalog is observation not ownership")
        if metrics.get("observed_at", {}).get("status") != "CONFIRMED"
        else confirmed({"source": "jump_kalshi_book", "note": "observation only"}),
        "positions": metrics.get("positions") or observation_unavailable(),
        "bankroll": metrics.get("bankroll") or observation_unavailable(),
        "day_pnl": metrics.get("day_pnl") or observation_unavailable(),
        "week_pnl": metrics.get("week_pnl") or observation_unavailable(),
        "origin_pnl": metrics.get("origin_pnl") or observation_unavailable(),
        "observed_at": metrics.get("observed_at") or unavailable("UNAVAILABLE"),
        "live_ev": unavailable("UNAVAILABLE"),
        "sharpe": unavailable("UNAVAILABLE"),
        "source": "jump_kalshi_book",
        "note": "Existing Jump Kalshi book is telemetry. Vital does not own a second book.",
    }


def observe_bot(
    bot_id: str = BOT_ID,
    *,
    root: Path | None = None,
    persist: bool = True,
    now: datetime | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    if refresh:
        from roller.vital.aws import clear_ssm_cache

        clear_ssm_cache()
    bot = get_bot(bot_id, root=root)
    if str(bot.get("bot_id") or "") != BOT_ID and bot.get("kind") != "grandfathered":
        from roller.vital.unit_observe import inspect_isolated_unit, kalshi_health_view

        attach = bot.get("attach") if isinstance(bot.get("attach"), dict) else {}
        kalshi = attach.get("kalshi_demo") if isinstance(attach.get("kalshi_demo"), dict) else {}
        aws = attach.get("aws") if isinstance(attach.get("aws"), dict) else {}
        inspected = inspect_isolated_unit(str(bot.get("bot_id") or bot_id), root=root)
        running = bool(inspected.get("ok") and inspected.get("active") and inspected.get("heartbeat"))
        unread = not inspected.get("ok")
        unit_state = "RUNNING_DEMO" if running else ("OBSERVATION_UNAVAILABLE" if unread else "DEPLOY_REQUIRED")
        runtime = {
            "bot_id": bot.get("bot_id"),
            "environment": bot.get("environment") or "DEMO",
            "desired": {"activation": bot.get("activation") or "DEPLOY_REQUIRED"},
            "observed": {
                "status": unit_state,
                "reason": None if running else (inspected.get("detail") or inspected.get("reason") or "isolated demo unit unread"),
                "kalshi_demo": kalshi.get("status") or "OBSERVATION_UNAVAILABLE",
                "aws": aws.get("status") or "OBSERVATION_UNAVAILABLE",
                "unit_started": running,
                "unit_state": unit_state,
                "active": inspected.get("active"),
                "heartbeat": inspected.get("heartbeat"),
                "unit": inspected.get("unit"),
            },
            "confirmed": {
                "lifecycle": {"status": "CONFIRMED", "value": "RUNNING_DEMO"} if running else observation_unavailable("isolated demo unit unread"),
                "health": {"status": "CONFIRMED", "value": "RUNNING_DEMO"} if running else observation_unavailable("isolated demo unit unread"),
            },
            "lifecycle": "RUNNING_DEMO" if running else ("OBSERVATION_UNAVAILABLE" if unread else str(bot.get("status") or "CREATED")),
            "health": "RUNNING_DEMO" if running else "UNKNOWN",
            "service": {
                "value": {"name": inspected.get("unit"), "active": "active" if inspected.get("active") else inspected.get("detail")},
                "status": "CONFIRMED" if inspected.get("ok") else "OBSERVATION_UNAVAILABLE",
            },
            "heartbeat": {
                "value": {"present": bool(inspected.get("heartbeat")), "runtime": inspected.get("runtime")},
                "status": "CONFIRMED" if inspected.get("heartbeat") else "OBSERVATION_UNAVAILABLE",
            },
            "kill_switch": observation_unavailable("ITI unit kill unread"),
            "live_armed": confirmed(False),
            "open_mlb_positions": observation_unavailable("ITI host positions unread"),
            "http_200_not_running": True,
            "live_ev": unavailable("UNAVAILABLE"),
            "sharpe": unavailable("UNAVAILABLE"),
        }
        view = {
            "bot": {
                "bot_id": bot.get("bot_id"),
                "name": bot.get("name"),
                "kind": bot.get("kind"),
                "environment": bot.get("environment"),
                "engine_pointer": bot.get("engine_pointer"),
                "strategy_pointer": bot.get("strategy_pointer"),
                "activation": "RUNNING_DEMO" if running else bot.get("activation"),
            },
            "runtime": runtime,
            "kalshi": kalshi,
            "kalshi_health": kalshi_health_view(str(bot.get("bot_id") or bot_id), root=root),
            "inspect": {
                "ok": bool(inspected.get("ok")),
                "reason": None if running else (inspected.get("detail") or "ITI bot does not use momento-live.service"),
                "aws": aws,
                "unit_started": running,
                "unit_state": unit_state,
                "unit": inspected.get("unit"),
                "factory_toml_refused": True,
            },
            "attach": attach or None,
        }
        if persist:
            write_json(runtime_path(str(bot["bot_id"]), "observed", root=root), runtime["observed"])
            write_json(runtime_path(str(bot["bot_id"]), "confirmed", root=root), runtime["confirmed"])
            _persist_observed_bot(bot, runtime, root=root)
            from roller.vital.integration_proof import record_observe_sample

            record_observe_sample(str(bot["bot_id"]), inspected, root=root)
        return view
    from roller.vital.unit_observe import kalshi_health_view

    inspect = inspect_mlb_001(now=now, refresh=refresh)
    runtime = compose_runtime(bot, inspect, root=root, now=now)
    book = kalshi_overlay()
    _overlay_runtime_book(runtime, book)
    view = {
        "bot": {
            "bot_id": bot.get("bot_id"),
            "name": bot.get("name"),
            "kind": bot.get("kind"),
            "environment": bot.get("environment"),
            "aliases": bot.get("aliases"),
            "engine_pointer": bot.get("engine_pointer"),
            "strategy_pointer": bot.get("strategy_pointer"),
            "factory": bot.get("factory") or bot.get("factory_id"),
        },
        "runtime": runtime,
        "kalshi": book,
        "inspect": {
            "ok": inspect.get("ok"),
            "source": inspect.get("source"),
            "reason": inspect.get("reason"),
        },
        "kalshi_health": kalshi_health_view(BOT_ID, root=root),
    }
    if persist:
        write_json(runtime_path(str(bot["bot_id"]), "observed", root=root), runtime["observed"])
        write_json(runtime_path(str(bot["bot_id"]), "confirmed", root=root), runtime["confirmed"])
        _persist_observed_bot(bot, runtime, root=root)
        from roller.vital.integration_proof import record_observe_sample

        record_observe_sample(str(bot["bot_id"]), inspect, root=root)
        append_event(
            str(bot["bot_id"]),
            {
                "kind": "observed",
                "ok": bool(inspect.get("ok")),
                "lifecycle": runtime.get("lifecycle"),
                "health": runtime.get("health"),
                "source": inspect.get("source"),
            },
            root=root,
        )
    return view


def status_view(bot_id: str = BOT_ID, *, root: Path | None = None) -> dict[str, Any]:
    view = observe_bot(bot_id, root=root)
    runtime = view["runtime"]
    return {
        "bot_id": view["bot"]["bot_id"],
        "name": view["bot"]["name"],
        "environment": view["bot"]["environment"],
        "lifecycle": runtime["lifecycle"],
        "health": runtime["health"],
        "desired": runtime["desired"],
        "observed": runtime["observed"],
        "confirmed": runtime["confirmed"],
        "http_200_not_running": True,
    }


def health_view(bot_id: str = BOT_ID, *, root: Path | None = None) -> dict[str, Any]:
    from roller.vital.unit_observe import kalshi_health_view

    view = observe_bot(bot_id, root=root)
    runtime = view["runtime"]
    return {
        "bot_id": view["bot"]["bot_id"],
        "health": runtime["health"],
        "lifecycle": runtime["lifecycle"],
        "kill_switch": runtime["kill_switch"],
        "confirmed": runtime["confirmed"],
        "trading_health": runtime.get("trading_health") or observation_unavailable("host unread"),
        "kalshi_health": view.get("kalshi_health") or kalshi_health_view(str(view["bot"]["bot_id"]), root=root),
        "live_ev": unavailable("UNAVAILABLE"),
        "sharpe": unavailable("UNAVAILABLE"),
        "http_200_not_running": True,
    }


def runtime_view(bot_id: str = BOT_ID, *, root: Path | None = None) -> dict[str, Any]:
    return observe_bot(bot_id, root=root)["runtime"]


def logs_view(bot_id: str = BOT_ID, *, root: Path | None = None) -> dict[str, Any]:
    from roller.vital.unit_observe import inspect_isolated_unit, kalshi_health_view, redact_logs

    bot = get_bot(bot_id, root=root)
    inspected = inspect_isolated_unit(str(bot.get("bot_id") or bot_id), root=root)
    logs = redact_logs(inspected.get("logs"))
    unit = str(inspected.get("unit") or "")
    if str(bot.get("bot_id") or "") != BOT_ID and bot.get("kind") != "grandfathered" and SERVICE_NAME in unit:
        return {
            "bot_id": bot.get("bot_id"),
            "unit": f"momento-demo@{bot.get('bot_id')}.service",
            "status": "OBSERVATION_UNAVAILABLE",
            "logs": [],
            "detail": "ITI logs refused Bot One journal",
        }
    if not inspected.get("ok"):
        return {
            "bot_id": bot.get("bot_id"),
            "unit": inspected.get("unit"),
            "status": "OBSERVATION_UNAVAILABLE",
            "logs": [],
            "detail": inspected.get("detail") or "host unread",
            "kalshi_health": kalshi_health_view(str(bot.get("bot_id") or bot_id), root=root),
        }
    return {
        "bot_id": bot.get("bot_id"),
        "unit": inspected.get("unit"),
        "status": "OBSERVED",
        "logs": logs,
        "source": inspected.get("source"),
        "kalshi_health": kalshi_health_view(str(bot.get("bot_id") or bot_id), root=root),
    }


def events_view(bot_id: str = BOT_ID, *, root: Path | None = None) -> dict[str, Any]:
    from roller.vital.models import resolve_bot_id

    resolved = resolve_bot_id(bot_id)
    return {"bot_id": resolved, "events": list_events(resolved, root=root)}


def orders_view(bot_id: str = BOT_ID, *, root: Path | None = None) -> dict[str, Any]:
    book = kalshi_overlay()
    return {
        "bot_id": bot_id,
        "layer": "orders",
        "orders": book.get("orders"),
        "live_ev": unavailable("UNAVAILABLE"),
        "note": book.get("note"),
        "distinction": "ORDERS are observed order objects. They are not fills or trades.",
    }


def positions_view(bot_id: str = BOT_ID, *, root: Path | None = None) -> dict[str, Any]:
    book = kalshi_overlay()
    runtime = observe_bot(bot_id, root=root, persist=False)["runtime"]
    host_positions = runtime.get("open_mlb_positions")
    kalshi_positions = book.get("positions")
    if (
        isinstance(host_positions, dict)
        and host_positions.get("status") == "CONFIRMED"
    ):
        chosen = host_positions
        source = "host_ledger"
    elif isinstance(kalshi_positions, dict) and kalshi_positions.get("status") == "CONFIRMED":
        chosen = kalshi_positions
        source = "jump_kalshi_book"
    else:
        chosen = observation_unavailable("positions unread")
        source = None
    return {
        "bot_id": bot_id,
        "layer": "positions",
        "positions": chosen,
        "source": source,
        "live_ev": unavailable("UNAVAILABLE"),
        "sharpe": unavailable("UNAVAILABLE"),
        "distinction": "POSITIONS are current inventory. They are not the execution ledger.",
    }
