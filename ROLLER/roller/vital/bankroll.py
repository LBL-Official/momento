"""Vital bankroll view and desired allocation / session limits.

GET is disk-only. Browser never submits orders. Desired stored is not live size.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.jump.catalog.analysis import analyze
from roller.jump.catalog.bankroll import (
    MLB_EXCHANGE_INDEX,
    account_origin_pnl,
    book_for,
    breakdown_line_cents,
    current_cents,
    day_week_from_history,
    dollars_to_truncated_cents,
    origin_cents,
)
from roller.jump.catalog.kalshi import demo_unread_reason
from roller.jump.catalog.store import load_analysis, load_bankroll, load_bankroll_history, load_trades
from roller.jump.bots.store import DEMO_FALLBACK_BANKROLL_CENTS, DEMO_UNIT_CENTS
from roller.vital.bots import get_bot, list_bots
from roller.vital.control import confirmation_ok, control_enabled
from roller.vital.errors import VitalError
from roller.vital.honesty import confirmed, observation_unavailable
from roller.vital.models import factory_snapshot, resolve_bot_id, utc_now
from roller.vital.store import (
    allocation_history_path,
    allocation_path,
    append_event,
    append_jsonl,
    limits_history_path,
    limits_path,
    read_json,
    write_json,
)
from roller.vital.versions import BOT_ID, CONTROL_CONFIRMATION, FACTORY, LIVE_CONFIRMATION

MODES = ("FIXED_CENTS", "PCT_CURRENT", "PCT_WEEKLY")
LIMIT_KEYS = (
    "max_daily_entries",
    "max_daily_wins",
    "max_daily_losses",
    "max_daily_win_cents",
    "max_daily_loss_cents",
)


def _int(raw: Any) -> int | None:
    if raw is None or raw == "" or isinstance(raw, bool):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _positive_int(raw: Any, name: str) -> int:
    value = _int(raw)
    if value is None:
        raise VitalError("REJECTED", f"{name} must be an integer")
    if value <= 0:
        raise VitalError("REJECTED", f"{name} must be > 0")
    return value


def unit_cents(*, mode: str, amount_cents: int | None, allocation_bps: int | None, bankroll_cents: int | None) -> int | None:
    if mode == "FIXED_CENTS":
        return amount_cents if amount_cents is not None and amount_cents > 0 else None
    if mode in {"PCT_CURRENT", "PCT_WEEKLY"}:
        if bankroll_cents is None or allocation_bps is None:
            return None
        if allocation_bps < 1 or allocation_bps > 10_000:
            return None
        return (int(bankroll_cents) * int(allocation_bps)) // 10_000
    return None


def unit_bp(*, unit: int | None, bankroll_cents: int | None) -> int | None:
    if unit is None or bankroll_cents is None or bankroll_cents <= 0:
        return None
    return (int(unit) * 10_000) // int(bankroll_cents)


def factory_allocation() -> dict[str, Any]:
    return {
        "mode": "PCT_WEEKLY",
        "amount_cents": None,
        "allocation_bps": int(FACTORY["allocation_bps"]),
        "bankroll_cents": int(FACTORY["bankroll_cents"]),
        "unit_cents": int(FACTORY["per_game_cents"]),
        "source": "mlb_factory_v1",
    }


def factory_limits() -> dict[str, Any]:
    return {key: None for key in LIMIT_KEYS}


def parse_allocation_body(body: dict[str, Any] | None) -> dict[str, Any]:
    body = body or {}
    mode = str(body.get("mode") or "").strip().upper()
    if mode not in MODES:
        raise VitalError("REJECTED", f"mode must be one of {', '.join(MODES)}")
    amount = None
    bps = None
    if mode == "FIXED_CENTS":
        amount = _positive_int(body.get("amount_cents"), "amount_cents")
    else:
        bps = _positive_int(body.get("allocation_bps"), "allocation_bps")
        if bps > 10_000:
            raise VitalError("REJECTED", "allocation_bps must be 1..=10000")
    return {"mode": mode, "amount_cents": amount, "allocation_bps": bps}


def parse_limits_body(body: dict[str, Any] | None) -> dict[str, Any]:
    body = body or {}
    out: dict[str, Any] = {}
    for key in LIMIT_KEYS:
        if key not in body or body.get(key) is None or body.get(key) == "":
            out[key] = None
            continue
        out[key] = _positive_int(body.get(key), key)
    return out


def load_desired_allocation(bot_id: str, *, root: Path | None = None) -> dict[str, Any] | None:
    return read_json(allocation_path(bot_id, root=root))


def load_desired_limits(bot_id: str, *, root: Path | None = None) -> dict[str, Any] | None:
    return read_json(limits_path(bot_id, root=root))


def persist_desired_allocation(bot_id: str, policy: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    row = {**policy, "bot_id": bot_id, "recorded_at": utc_now(), "kind": "allocation_desired"}
    write_json(allocation_path(bot_id, root=root), row)
    append_jsonl(allocation_history_path(bot_id, root=root), row)
    append_event(bot_id, row, root=root)
    return row


def persist_desired_limits(bot_id: str, policy: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    row = {**policy, "bot_id": bot_id, "recorded_at": utc_now(), "kind": "limits_desired"}
    write_json(limits_path(bot_id, root=root), row)
    append_jsonl(limits_history_path(bot_id, root=root), row)
    append_event(bot_id, row, root=root)
    return row


def _reject_live_token(body: dict[str, Any] | None) -> None:
    token = str((body or {}).get("confirmation") or "").strip()
    if token == LIVE_CONFIRMATION:
        raise VitalError(
            "REJECTED",
            "ENABLE_LIVE_TRADING is the engine live gate, not a Vital control token",
        )


def apply_status_for(*, body: dict[str, Any] | None, environment: str) -> dict[str, Any]:
    _reject_live_token(body)
    if not confirmation_ok(body):
        return {
            "apply_status": "APPLY_REQUIRED",
            "detail": "desired stored; host apply needs confirmation=" + CONTROL_CONFIRMATION,
            "applied": False,
        }
    if environment == "PRODUCTION" and not control_enabled():
        return {
            "apply_status": "CONTROL_DISABLED",
            "detail": (
                "production writes require VITAL_AWS_CONTROL=1 and confirmation="
                f"{CONTROL_CONFIRMATION}; this session does not mutate the live host"
            ),
            "applied": False,
        }
    if environment == "PRODUCTION":
        return {
            "apply_status": "CONTROL_DISABLED",
            "detail": "live host TOML write is fail-closed in this session; desired is stored",
            "applied": False,
        }
    return {
        "apply_status": "APPLY_REQUIRED",
        "detail": "DEMO desired stored; demo.toml is rewritten from Jump settings on next deploy",
        "applied": False,
    }


CATCH_ALL_EXCHANGE_INDEX = 0
SPORTS_SHARD_LABEL = "sports shard 3 (baseball / basketball / tennis)"


def _breakdown_rows(book: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(book, dict):
        return []
    raw = book.get("balance_breakdown")
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def _shard_from_breakdown(rows: list[dict[str, Any]], index: int) -> int | None:
    for row in rows:
        try:
            if int(row.get("exchange_index")) != index:
                continue
        except (TypeError, ValueError):
            continue
        cents = breakdown_line_cents(row)
        if cents is None:
            cents = dollars_to_truncated_cents(row.get("balance") or row.get("balance_dollars"))
        return cents
    return None


def _account_view(*, now=None) -> dict[str, Any]:
    payload = load_bankroll()
    history = load_bankroll_history()
    book = book_for(payload, "PRODUCTION")
    top = None
    mlb = None
    source = None
    observed_at = None
    if isinstance(book, dict):
        top = _int(book.get("top_level_cents"))
        mlb = current_cents(book)
        source = book.get("source")
        observed_at = book.get("updated_at") or book.get("observed_at")
        if top is None and book.get("exchange_index") is None:
            top = mlb
    windows = day_week_from_history(
        history,
        environment="PRODUCTION",
        current=mlb if mlb is not None else top,
        now=now or datetime.now(timezone.utc),
        missing="OBSERVATION_UNAVAILABLE",
    )
    factory = factory_snapshot()
    rows = _breakdown_rows(book if isinstance(book, dict) else None)
    catch_all = _shard_from_breakdown(rows, CATCH_ALL_EXCHANGE_INDEX)
    return {
        "environment": "PRODUCTION",
        "demo_not_mixed": True,
        "top_level_cents": confirmed(top) if top is not None else observation_unavailable("Kalshi account unread"),
        "mlb_shard_cents": confirmed(mlb) if mlb is not None else observation_unavailable("MLB shard unread"),
        "catch_all_shard_cents": confirmed(catch_all) if catch_all is not None else observation_unavailable("catch-all shard unread"),
        "factory_bankroll_cents": confirmed(int(factory["bankroll_cents"])),
        "factory_unit_cents": confirmed(int(factory["per_game_cents"])),
        "factory_allocation_bps": confirmed(int(factory["allocation_bps"])),
        "day_delta_cents": windows["day_pnl"],
        "week_delta_cents": windows["week_pnl"],
        "exchange_index": confirmed(MLB_EXCHANGE_INDEX) if mlb is not None else observation_unavailable(),
        "balance_breakdown": rows,
        "shard_label": SPORTS_SHARD_LABEL,
        "source": confirmed(source) if source else observation_unavailable(),
        "observed_at": confirmed(observed_at) if observed_at else observation_unavailable(),
    }


def _metric_int(metric: dict[str, Any] | None) -> int | None:
    if not isinstance(metric, dict) or metric.get("status") != "CONFIRMED":
        return None
    try:
        value = metric.get("value")
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _selected_bankroll(
    *,
    mode: str,
    account: dict[str, Any],
    environment: str = "PRODUCTION",
    demo_account: dict[str, Any] | None = None,
) -> int | None:
    factory = int(FACTORY["bankroll_cents"])
    env = str(environment or "PRODUCTION").upper()
    if env == "DEMO":
        demo = demo_account or {}
        top_val = _metric_int(demo.get("top_level_cents") if isinstance(demo.get("top_level_cents"), dict) else None)
        if mode == "PCT_CURRENT":
            return top_val
        if mode == "PCT_WEEKLY":
            return top_val if top_val is not None else DEMO_FALLBACK_BANKROLL_CENTS
        return top_val if top_val is not None else DEMO_FALLBACK_BANKROLL_CENTS
    top = account.get("top_level_cents")
    top_val = _metric_int(top if isinstance(top, dict) else None)
    if mode == "PCT_CURRENT":
        return int(top_val) if top_val is not None else None
    if mode == "PCT_WEEKLY":
        return int(top_val) if top_val is not None else factory
    return factory


def _demo_account_view(*, now=None) -> dict[str, Any]:
    payload = load_bankroll()
    history = load_bankroll_history()
    book = book_for(payload, "DEMO")
    top = None
    source = None
    observed_at = None
    origin = None
    seeded = False
    if isinstance(book, dict):
        top = _int(book.get("top_level_cents"))
        if top is None:
            top = current_cents(book)
        source = book.get("source")
        observed_at = book.get("updated_at") or book.get("observed_at")
        origin = origin_cents(payload, book, environment="DEMO")
        seeded = book.get("seeded_from_mcp") is True
    mlb = _int(book.get("mlb_shard_cents")) if isinstance(book, dict) else None
    rows = _breakdown_rows(book if isinstance(book, dict) else None)
    if mlb is None:
        mlb = _shard_from_breakdown(rows, MLB_EXCHANGE_INDEX)
    catch_all = _shard_from_breakdown(rows, CATCH_ALL_EXCHANGE_INDEX)
    windows = day_week_from_history(
        history,
        environment="DEMO",
        current=top,
        now=now or datetime.now(timezone.utc),
        missing="OBSERVATION_UNAVAILABLE",
    )
    origin_pnl = account_origin_pnl(payload, environment="DEMO", missing="OBSERVATION_UNAVAILABLE")
    return {
        "environment": "DEMO",
        "production_not_mixed": True,
        "top_level_cents": confirmed(top) if top is not None else observation_unavailable("demo Kalshi account unread"),
        "mlb_shard_cents": confirmed(mlb) if mlb is not None else observation_unavailable("Demo sports shard unread"),
        "catch_all_shard_cents": confirmed(catch_all) if catch_all is not None else observation_unavailable("Demo catch-all shard unread"),
        "exchange_index": confirmed(MLB_EXCHANGE_INDEX) if mlb is not None else observation_unavailable("Demo sports shard unread"),
        "balance_breakdown": rows,
        "shard_label": SPORTS_SHARD_LABEL,
        "origin_cents": confirmed(origin) if origin is not None else observation_unavailable("demo origin unread"),
        "origin_pnl_cents": origin_pnl,
        "day_delta_cents": windows["day_pnl"],
        "week_delta_cents": windows["week_pnl"],
        "fallback_bankroll_cents": confirmed(DEMO_FALLBACK_BANKROLL_CENTS),
        "default_unit_cents": confirmed(DEMO_UNIT_CENTS),
        "source": confirmed(source) if source else observation_unavailable(demo_unread_reason()),
        "observed_at": confirmed(observed_at) if observed_at else observation_unavailable(),
        "seeded_from_mcp": bool(seeded),
    }


def _count_metric(raw: Any, *, unread: bool) -> dict[str, Any]:
    if unread:
        return observation_unavailable("demo fills unread")
    try:
        return confirmed(int(raw or 0))
    except (TypeError, ValueError):
        return observation_unavailable("demo fills unread")


def _demo_report(*, demo_account: dict[str, Any]) -> dict[str, Any]:
    analysis = load_analysis()
    trades = load_trades()
    demo_trades = [row for row in trades if str(row.get("environment") or "").upper() == "DEMO"]
    demo_book_present = _metric_int(demo_account.get("top_level_cents")) is not None
    unread = not demo_trades and not demo_book_present
    bucket = None
    if isinstance(analysis, dict):
        by_book = analysis.get("by_book")
        if isinstance(by_book, dict) and isinstance(by_book.get("DEMO"), dict):
            bucket = by_book["DEMO"]
    if bucket is None and demo_trades:
        bucket = analyze(trades, now=datetime.now(timezone.utc)).get("by_book", {}).get("DEMO")
    win_loss = (bucket or {}).get("win_loss") if bucket else None
    if unread:
        wins = observation_unavailable("demo fills unread")
        losses = observation_unavailable("demo fills unread")
        last_trade = observation_unavailable("demo fills unread")
        fill_sum = observation_unavailable("demo fills unread")
        day_fill = observation_unavailable("demo fills unread")
        week_fill = observation_unavailable("demo fills unread")
        trade_n = observation_unavailable("demo fills unread")
        settled_n = observation_unavailable("demo fills unread")
    else:
        if isinstance(win_loss, dict) and win_loss.get("status") == "CONFIRMED":
            wins = confirmed(int(win_loss.get("wins") or 0))
            losses = confirmed(int(win_loss.get("losses") or 0))
        else:
            wins = confirmed(int((bucket or {}).get("wins") or 0))
            losses = confirmed(int((bucket or {}).get("losses") or 0))
        last = (bucket or {}).get("last_trade")
        last_trade = confirmed(last) if last else observation_unavailable("no demo fill yet")
        fill_sum = _count_metric((bucket or {}).get("fill_result_sum_cents"), unread=False)
        day_fill = _count_metric((bucket or {}).get("day_fill_result_cents"), unread=False)
        week_fill = _count_metric((bucket or {}).get("week_fill_result_cents"), unread=False)
        trade_n = _count_metric((bucket or {}).get("trade_n"), unread=False)
        settled_n = _count_metric((bucket or {}).get("settled_n"), unread=False)
    return {
        "environment": "DEMO",
        "trade_n": trade_n,
        "settled_n": settled_n,
        "wins": wins,
        "losses": losses,
        "fill_result_sum_cents": fill_sum,
        "day_fill_result_cents": day_fill,
        "week_fill_result_cents": week_fill,
        "last_trade": last_trade,
        "origin_pnl_cents": demo_account.get("origin_pnl_cents"),
        "fill_result_is_not_account_pnl": True,
        "live_ev": "UNAVAILABLE",
        "sharpe": "UNAVAILABLE",
    }


def _allocation_row(
    bot: dict[str, Any],
    account: dict[str, Any],
    *,
    root: Path | None,
    demo_account: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bot_id = str(bot.get("bot_id") or BOT_ID)
    factory = factory_allocation()
    desired_raw = load_desired_allocation(bot_id, root=root)
    settings = bot.get("settings") if isinstance(bot.get("settings"), dict) else {}
    if desired_raw is None and str(bot.get("kind") or "") == "iti" and settings:
        desired_raw = {
            "mode": settings.get("sizing_mode") or "FIXED_CENTS",
            "amount_cents": settings.get("amount_cents"),
            "allocation_bps": settings.get("allocation_bps"),
        }
    mode = str((desired_raw or factory).get("mode") or factory["mode"])
    amount = _int((desired_raw or {}).get("amount_cents"))
    bps = _int((desired_raw or factory).get("allocation_bps"))
    bankroll = _selected_bankroll(
        mode=mode,
        account=account,
        environment=str(bot.get("environment") or "PRODUCTION"),
        demo_account=demo_account,
    )
    desired_unit = unit_cents(mode=mode, amount_cents=amount, allocation_bps=bps, bankroll_cents=bankroll)
    if desired_raw is None and str(bot.get("kind") or "") != "iti":
        desired_unit = int(FACTORY["per_game_cents"])
        mode = factory["mode"]
        bps = factory["allocation_bps"]
        bankroll = factory["bankroll_cents"]
    desired_metric = (
        confirmed(
            {
                "mode": mode,
                "amount_cents": amount,
                "allocation_bps": bps,
                "unit_cents": desired_unit,
                "unit_bp": unit_bp(unit=desired_unit, bankroll_cents=bankroll),
            }
        )
        if desired_unit is not None
        else observation_unavailable("desired unit unread")
    )
    if str(bot.get("kind") or "") == "iti":
        configured = (
            confirmed({"unit_cents": desired_unit, "mode": mode, "allocation_bps": bps, "amount_cents": amount})
            if desired_unit is not None
            else observation_unavailable("demo unit unset")
        )
        return {
            "desired": desired_metric,
            "observed": configured,
            "confirmed": configured,
            "unit_cents": confirmed(desired_unit) if desired_unit is not None else observation_unavailable(),
            "unit_bp": confirmed(unit_bp(unit=desired_unit, bankroll_cents=bankroll))
            if desired_unit is not None
            else observation_unavailable(),
            "apply_status": str(bot.get("activation") or "DEMO_ATTACH_UNAVAILABLE"),
        }
    observed_unit = int(FACTORY["per_game_cents"])
    confirmed_unit = observed_unit
    apply_status = "CONFIRMED" if desired_raw is None or desired_unit == observed_unit else "APPLY_REQUIRED"
    return {
        "desired": desired_metric,
        "observed": confirmed({"unit_cents": observed_unit, "mode": "PCT_WEEKLY", "allocation_bps": int(FACTORY["allocation_bps"])}),
        "confirmed": confirmed({"unit_cents": confirmed_unit, "mode": "PCT_WEEKLY", "allocation_bps": int(FACTORY["allocation_bps"])}),
        "unit_cents": confirmed(observed_unit),
        "unit_bp": confirmed(unit_bp(unit=observed_unit, bankroll_cents=int(FACTORY["bankroll_cents"]))),
        "apply_status": apply_status,
    }


def _limits_row(bot: dict[str, Any], *, root: Path | None) -> dict[str, Any]:
    bot_id = str(bot.get("bot_id") or BOT_ID)
    desired_raw = load_desired_limits(bot_id, root=root)
    desired = factory_limits()
    if desired_raw:
        for key in LIMIT_KEYS:
            desired[key] = _int(desired_raw.get(key))
    policy = desired if desired_raw else factory_limits()
    return {
        "desired": confirmed(desired) if desired_raw else confirmed(factory_limits()),
        "observed": confirmed(policy),
        "confirmed": confirmed(policy),
        "remaining": observation_unavailable("host session ledger unread"),
        "hit": observation_unavailable("host session ledger unread"),
        "one_bet_per_game": True,
        "block_new_entries_only": True,
        "day_clock": "America/Los_Angeles midnight",
    }


def _bot_row(
    bot: dict[str, Any],
    account: dict[str, Any],
    *,
    root: Path | None,
    demo_account: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "bot_id": bot.get("bot_id"),
        "name": bot.get("name"),
        "environment": bot.get("environment") or "PRODUCTION",
        "kind": bot.get("kind"),
        "allocation": _allocation_row(bot, account, root=root, demo_account=demo_account),
        "limits": _limits_row(bot, root=root),
    }


def _jump_demo_rows(
    account: dict[str, Any],
    seen: set[str],
    *,
    demo_account: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    try:
        from roller.jump.bots.store import list_bots as jump_list
        from roller.jump.bots.versions import BOT_ONE_ID
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    try:
        bots = jump_list()
    except Exception:
        return []
    for bot in bots:
        bot_id = str(bot.get("bot_id") or "")
        vital_id = str(bot.get("vital_bot_id") or "")
        if not bot_id or bot_id in seen or bot_id == BOT_ONE_ID or bot_id == BOT_ID:
            continue
        if vital_id and vital_id in seen:
            continue
        if str(bot.get("environment") or "").upper() == "PRODUCTION":
            continue
        settings = bot.get("settings") if isinstance(bot.get("settings"), dict) else {}
        mode = str(settings.get("sizing_mode") or "PCT_WEEKLY").upper()
        if mode not in MODES:
            mode = "PCT_WEEKLY"
        amount = _int(settings.get("amount_cents") or settings.get("max_position_budget_cents"))
        bps = _int(settings.get("allocation_bps")) or int(FACTORY["allocation_bps"])
        bankroll = _int(settings.get("bankroll_cents")) or DEMO_FALLBACK_BANKROLL_CENTS
        if mode == "PCT_CURRENT":
            demo_top = _metric_int((demo_account or {}).get("top_level_cents"))
            bankroll = demo_top if demo_top is not None else None
        elif mode == "PCT_WEEKLY":
            demo_top = _metric_int((demo_account or {}).get("top_level_cents"))
            if demo_top is not None:
                bankroll = demo_top
        unit = unit_cents(mode=mode, amount_cents=amount, allocation_bps=bps, bankroll_cents=bankroll)
        limits = {key: _int(settings.get(key)) for key in LIMIT_KEYS}
        rows.append(
            {
                "bot_id": bot_id,
                "name": bot.get("name"),
                "environment": "DEMO",
                "kind": bot.get("kind"),
                "allocation": {
                    "desired": confirmed(
                        {
                            "mode": mode,
                            "amount_cents": amount,
                            "allocation_bps": bps,
                            "unit_cents": unit,
                            "unit_bp": unit_bp(unit=unit, bankroll_cents=bankroll),
                        }
                    )
                    if unit is not None
                    else observation_unavailable(),
                    "observed": confirmed({"unit_cents": unit, "mode": mode, "allocation_bps": bps, "amount_cents": amount})
                    if unit is not None
                    else observation_unavailable("demo unit unset"),
                    "confirmed": confirmed({"unit_cents": unit, "mode": mode, "allocation_bps": bps, "amount_cents": amount})
                    if unit is not None
                    else observation_unavailable("demo unit unset"),
                    "unit_cents": confirmed(unit) if unit is not None else observation_unavailable(),
                    "unit_bp": confirmed(unit_bp(unit=unit, bankroll_cents=bankroll))
                    if unit is not None
                    else observation_unavailable(),
                    "apply_status": "APPLY_REQUIRED",
                },
                "limits": {
                    "desired": confirmed(limits),
                    "observed": confirmed(limits),
                    "confirmed": confirmed(limits),
                    "remaining": observation_unavailable("host session ledger unread"),
                    "hit": observation_unavailable("host session ledger unread"),
                    "one_bet_per_game": True,
                    "block_new_entries_only": True,
                    "day_clock": "America/Los_Angeles midnight",
                },
            }
        )
        seen.add(bot_id)
    return rows


def bankroll_view(*, root: Path | None = None, now=None) -> dict[str, Any]:
    from roller.vital.bots import ensure_mlb_001

    ensure_mlb_001(root=root)
    try:
        import os

        from roller.vital.register import backfill_jump_demo_bots

        if root is None or os.environ.get("JUMP_BOTS_ROOT"):
            backfill_jump_demo_bots(vital_root=root)
    except Exception:
        pass
    account = _account_view(now=now)
    demo_account = _demo_account_view(now=now)
    demo_report = _demo_report(demo_account=demo_account)
    bots = []
    seen: set[str] = set()
    for bot in list_bots(root=root):
        row = _bot_row(bot, account, root=root, demo_account=demo_account)
        bots.append(row)
        seen.add(str(row.get("bot_id") or ""))
    bots.extend(_jump_demo_rows(account, seen, demo_account=demo_account))
    seeded = bool(demo_account.get("seeded_from_mcp"))
    return {
        "account": account,
        "demo_account": demo_account,
        "demo_report": demo_report,
        "bots": bots,
        "n": len(bots),
        "honesty": {
            "desired_is_not_live_size": True,
            "demo_not_mixed_into_production_book": True,
            "remaining_not_invented_from_blotter": True,
            "one_bet_per_game_stays_in_risk": True,
            "fill_result_is_not_account_pnl": True,
            "live_ev": "UNAVAILABLE",
            "sharpe": "UNAVAILABLE",
        },
        "kalshi_mcp": False,
        "seeded_from_mcp": seeded,
        "observe": "POST /vital/bots/{id}/kalshi/observe",
    }


def _target_bot(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    resolved = resolve_bot_id(bot_id)
    try:
        return get_bot(resolved, root=root)
    except VitalError:
        if resolved == BOT_ID:
            raise
        try:
            from roller.jump.bots.store import load_bot as jump_load

            return jump_load(resolved)
        except Exception as exc:
            raise VitalError("BOT_NOT_FOUND", f"bot not found: {bot_id}") from exc


def _sync_jump_settings(bot_id: str, updates: dict[str, Any]) -> None:
    if resolve_bot_id(bot_id) == BOT_ID:
        return
    try:
        from roller.jump.bots.store import load_bot, save_bot
        from roller.jump.bots.versions import BOT_ONE_ID
    except Exception:
        return
    if bot_id == BOT_ONE_ID:
        return
    try:
        bot = load_bot(bot_id)
    except Exception:
        try:
            from roller.vital.bots import get_bot as vital_get

            vital = vital_get(bot_id)
            jump_id = str(vital.get("jump_bot_id") or "")
            if not jump_id:
                return
            bot = load_bot(jump_id)
            bot_id = jump_id
        except Exception:
            return
    if str(bot.get("environment") or "").upper() == "PRODUCTION" or bot.get("kind") == "grandfathered":
        return
    settings = dict(bot.get("settings") or {})
    settings.update(updates)
    bot["settings"] = settings
    save_bot(bot)


def handle_bankroll(*, root: Path | None = None) -> dict[str, Any]:
    return bankroll_view(root=root)


def handle_allocation(bot_id: str, body: dict[str, Any] | None = None, *, root: Path | None = None) -> dict[str, Any]:
    bot = _target_bot(bot_id, root=root)
    body = body or {}
    _reject_live_token(body)
    policy = parse_allocation_body(body)
    resolved = resolve_bot_id(bot_id)
    persist_id = resolved if resolved == BOT_ID else str(bot.get("bot_id") or resolved)
    jump_id = str(bot.get("jump_bot_id") or persist_id)
    if persist_id == BOT_ID:
        stored = persist_desired_allocation(BOT_ID, policy, root=root)
    else:
        if bot.get("kind") == "iti" or str(bot.get("bot_id") or "").startswith("mlb-"):
            stored = persist_desired_allocation(persist_id, policy, root=root)
        else:
            stored = {**policy, "bot_id": persist_id, "recorded_at": utc_now(), "kind": "allocation_desired"}
        _sync_jump_settings(
            jump_id,
            {
                "sizing_mode": policy["mode"],
                "amount_cents": policy.get("amount_cents"),
                "allocation_bps": policy.get("allocation_bps"),
                "max_position_budget_cents": policy.get("amount_cents") if policy["mode"] == "FIXED_CENTS" else None,
            },
        )
    apply = apply_status_for(body=body, environment=str(bot.get("environment") or "PRODUCTION"))
    account = _account_view()
    demo_account = _demo_account_view()
    bankroll = _selected_bankroll(
        mode=policy["mode"],
        account=account,
        environment=str(bot.get("environment") or "PRODUCTION"),
        demo_account=demo_account,
    )
    unit = unit_cents(
        mode=policy["mode"],
        amount_cents=policy.get("amount_cents"),
        allocation_bps=policy.get("allocation_bps"),
        bankroll_cents=bankroll,
    )
    return {
        "bot_id": persist_id,
        "desired": stored,
        "unit_cents": unit,
        "unit_bp": unit_bp(unit=unit, bankroll_cents=bankroll),
        "http_200_not_live_size": True,
        **apply,
    }


def handle_limits(bot_id: str, body: dict[str, Any] | None = None, *, root: Path | None = None) -> dict[str, Any]:
    bot = _target_bot(bot_id, root=root)
    body = body or {}
    _reject_live_token(body)
    policy = parse_limits_body(body)
    resolved = resolve_bot_id(bot_id)
    persist_id = resolved if resolved == BOT_ID else str(bot.get("bot_id") or resolved)
    if persist_id == BOT_ID:
        stored = persist_desired_limits(BOT_ID, policy, root=root)
    else:
        stored = {**policy, "bot_id": persist_id, "recorded_at": utc_now(), "kind": "limits_desired"}
        _sync_jump_settings(persist_id, policy)
    apply = apply_status_for(body=body, environment=str(bot.get("environment") or "PRODUCTION"))
    return {
        "bot_id": persist_id,
        "desired": stored,
        "http_200_not_live_size": True,
        **apply,
    }
