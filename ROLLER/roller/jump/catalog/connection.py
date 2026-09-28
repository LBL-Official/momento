"""Read-only Kalshi book for Jump. Never POSTs. Dashboard GET stays disk-only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.jump.bots.versions import BOT_ONE_ID
from roller.jump.catalog.analysis import analyze
from roller.jump.catalog.bankroll import (
    MLB_EXCHANGE_INDEX,
    account_bankroll,
    account_origin_pnl,
    book_for,
    current_cents,
    day_week_from_history,
    open_mlb_positions,
    origin_bankroll_cents,
    pack_book,
)
from roller.jump.catalog.kalshi import fetch_connection
from roller.jump.catalog.reconcile import _matches, kalshi_record
from roller.jump.catalog.store import (
    append_bankroll_history,
    append_trades,
    load_bankroll,
    load_bankroll_history,
    load_kalshi_book,
    load_origin,
    load_trades,
    persist_bankroll,
    persist_kalshi_book,
    write_analysis,
)
from roller.jump.catalog.versions import CAVEATS, HONESTY, UNATTRIBUTED
from roller.jump.dashboard.heartbeat import confirmed, unavailable
from roller.jump.dashboard.ledger import parse_utc


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clock(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _after_origin(row: dict[str, Any], origin_ts: str | None) -> bool:
    if not origin_ts:
        return True
    ts = parse_utc(row.get("exchange_ts"))
    origin = parse_utc(origin_ts)
    if ts is None or origin is None:
        return True
    return ts >= origin


def _already_cataloged(fill: dict[str, Any], existing: list[dict[str, Any]]) -> bool:
    trade_id = str(fill.get("trade_id") or "")
    fill_id = str(fill.get("fill_id") or "")
    for row in existing:
        if trade_id and str(row.get("kalshi_trade_id") or "") == trade_id:
            return True
        if fill_id and str(row.get("kalshi_fill_id") or "") == fill_id:
            return True
        if _matches(fill, row):
            return True
    return False


def _mlb_fill(fill: dict[str, Any]) -> bool:
    ticker = str(fill.get("ticker") or "")
    try:
        index = int(fill["exchange_index"]) if fill.get("exchange_index") is not None else None
    except (TypeError, ValueError):
        index = None
    if ticker.startswith("KXMLBGAME"):
        return True
    if index == MLB_EXCHANGE_INDEX:
        return True
    if not ticker and index is None:
        return False
    return False


def _ingest_fills(fills: list[dict[str, Any]], *, environment: str, origin_ts: str | None) -> int:
    existing = load_trades()
    incoming: list[dict[str, Any]] = []
    for fill in fills:
        if not isinstance(fill, dict):
            continue
        if environment == "PRODUCTION":
            if not _mlb_fill(fill):
                continue
            if not _after_origin(fill, origin_ts):
                continue
        if _already_cataloged(fill, existing + incoming):
            continue
        bot_id = BOT_ONE_ID if environment == "PRODUCTION" else UNATTRIBUTED
        incoming.append(
            kalshi_record(
                fill,
                environment=environment,
                ledger=None,
                bot_id=bot_id,
                source="kalshi",
            )
        )
    return append_trades(incoming)


def connection_metrics(
    *,
    environment: str = "PRODUCTION",
    now: datetime | None = None,
    missing: str = "UNAVAILABLE",
) -> dict[str, Any]:
    clock = _clock(now)
    bankroll = load_bankroll()
    history = load_bankroll_history()
    book = load_kalshi_book()
    env_book = ((book or {}).get("books") or {}).get(environment) if isinstance(book, dict) else None
    current = current_cents(((bankroll or {}).get("books") or {}).get(environment) if bankroll else None)
    windows = day_week_from_history(
        history,
        environment=environment,
        current=current,
        now=clock,
        missing=missing,
    )
    positions = (env_book or {}).get("positions") if isinstance(env_book, dict) else None
    open_n = open_mlb_positions(positions if isinstance(positions, list) else None)
    observed = (env_book or {}).get("observed_at") if isinstance(env_book, dict) else None
    return {
        "bankroll": account_bankroll(bankroll, environment=environment, missing=missing),
        "origin_pnl": account_origin_pnl(bankroll, environment=environment, missing=missing),
        "day_pnl": windows["day_pnl"],
        "week_pnl": windows["week_pnl"],
        "positions": confirmed(open_n) if open_n is not None else unavailable(missing),
        "observed_at": confirmed(observed) if observed else unavailable("UNAVAILABLE"),
        "source": confirmed((env_book or {}).get("source")) if isinstance(env_book, dict) and env_book.get("source") else unavailable("UNAVAILABLE"),
        "sharpe": unavailable(),
        "live_ev": unavailable(),
    }


def handle_status(*, now: datetime | None = None) -> dict[str, Any]:
    book = load_kalshi_book()
    bankroll = load_bankroll()
    metrics = connection_metrics(now=now, missing="OBSERVATION_UNAVAILABLE")
    observed = False
    if isinstance(book, dict) and (book.get("books") or {}).get("PRODUCTION"):
        observed = True
    return {
        "ok": observed,
        "status": "CONFIRMED" if observed else "OBSERVATION_UNAVAILABLE",
        "product": "Jump Kalshi",
        "read_only": True,
        "mutating_sent": False,
        "bankroll": bankroll,
        "book": book,
        "metrics": metrics,
        "honesty": {
            **dict(HONESTY),
            "fill_result_sum_is_not_account_pnl": True,
            "sharpe": "UNAVAILABLE",
            "live_ev": "UNAVAILABLE",
            "headline_pnl": "KALSHI_MLB_CASH_MINUS_FACTORY_ORIGIN",
        },
        "caveats": list(CAVEATS),
    }


def sync_kalshi(
    *,
    now: datetime | None = None,
    environments: tuple[str, ...] = ("PRODUCTION",),
) -> dict[str, Any]:
    clock = _clock(now)
    origin = load_origin()
    origin_ts = (origin or {}).get("bot_one_first_fill_ts") if origin else None
    books: dict[str, Any] = {}
    incoming_bankroll: dict[str, Any] = {}
    added = 0
    details: dict[str, Any] = {}
    for env in environments:
        body = fetch_connection(env)
        details[env] = {
            "ok": bool(body.get("ok")),
            "status": body.get("status") or "OBSERVATION_UNAVAILABLE",
            "detail": body.get("detail"),
            "fill_n": len(body.get("fills") or []) if isinstance(body.get("fills"), list) else 0,
            "position_n": len(body.get("positions") or []) if isinstance(body.get("positions"), list) else 0,
        }
        if not body.get("ok"):
            continue
        packed_balance = {
            "ok": True,
            "environment": env,
            "current_cents": body.get("current_cents"),
            "balance_cents": body.get("current_cents"),
            "balance_dollars": body.get("balance_dollars"),
            "portfolio_value_cents": body.get("portfolio_value_cents"),
            "balance_breakdown": body.get("balance_breakdown"),
            "source": "kalshi_get_balance",
        }
        existing_payload = load_bankroll()
        book_row = pack_book(packed_balance, existing_book=book_for(existing_payload, env))
        if book_row and book_row.get("current_cents") is not None:
            incoming_bankroll[env] = book_row
            append_bankroll_history(
                {
                    "observed_at": _utc_now(),
                    "environment": env,
                    "current_cents": book_row["current_cents"],
                    "exchange_index": book_row.get("exchange_index"),
                    "source": book_row.get("source"),
                }
            )
        raw_positions = body.get("positions") or []
        mlb_positions = [
            row
            for row in raw_positions
            if isinstance(row, dict)
            and (
                str(row.get("ticker") or "").startswith("KXMLBGAME")
                or row.get("exchange_index") == MLB_EXCHANGE_INDEX
            )
        ]
        books[env] = {
            "ok": True,
            "status": "CONFIRMED",
            "observed_at": _utc_now(),
            "source": "kalshi_book",
            "fill_n": len(body.get("fills") or []) if isinstance(body.get("fills"), list) else 0,
            "position_n": len(mlb_positions),
            "positions": mlb_positions,
            "current_cents": (book_row or {}).get("current_cents"),
            "exchange_index": (book_row or {}).get("exchange_index"),
            "top_level_cents": (book_row or {}).get("top_level_cents"),
            "mlb_shard_cents": (book_row or {}).get("mlb_shard_cents"),
            "balance_breakdown": body.get("balance_breakdown") or (book_row or {}).get("balance_breakdown"),
            "balance_dollars": body.get("balance_dollars"),
        }
        added += _ingest_fills(body.get("fills") or [], environment=env, origin_ts=origin_ts)

    if incoming_bankroll:
        persist_bankroll(
            {
                "origin_bankroll_cents": origin_bankroll_cents(),
                "origin_source": "mlb_factory_v1",
                "books": incoming_bankroll,
            }
        )
    if books:
        persist_kalshi_book({"books": books, "read_only": True, "mutating_sent": False})
        trades = load_trades()
        write_analysis(analyze(trades, now=clock))

    observed = any(row.get("ok") for row in books.values())
    return {
        "ok": observed,
        "status": "CONFIRMED" if observed else "OBSERVATION_UNAVAILABLE",
        "added": added,
        "books": details,
        "metrics": connection_metrics(now=clock, missing="OBSERVATION_UNAVAILABLE"),
        "honesty": {
            **dict(HONESTY),
            "browser_is_not_engine": True,
            "read_only": True,
            "sharpe": "UNAVAILABLE",
            "live_ev": "UNAVAILABLE",
        },
        "caveats": list(CAVEATS),
    }


def handle_sync(*, now: datetime | None = None) -> dict[str, Any]:
    return sync_kalshi(now=now)
