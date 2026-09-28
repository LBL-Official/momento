"""Rebuild catalog from host ledgers + optional read-only Kalshi pull."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from roller.jump.bots.store import ensure_bot_one, list_bots, load_bot
from roller.jump.bots.versions import BOT_ONE_ID
from roller.jump.errors import JumpError
from roller.jump.catalog.analysis import analyze
from roller.jump.catalog.bankroll import book_for, origin_bankroll_cents, pack_book
from roller.jump.catalog.kalshi import SKIP_ENV, fetch_balance, fetch_book, fills_bin
from roller.jump.catalog.reconcile import ledger_record, reconcile_book
from roller.jump.catalog.store import (
    append_trades,
    load_analysis,
    load_bankroll,
    load_origin,
    load_trades,
    persist_bankroll,
    persist_origin,
    write_analysis,
)
from roller.jump.catalog.versions import CATALOG_VERSION, CAVEATS, HONESTY, UNATTRIBUTED
from roller.jump.dashboard.host_state import load_host_state
from roller.jump.dashboard.ledger import list_mlb_fills, parse_utc, summarize_mlb_ledger


def _clock(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _ledger_rows(runtime: dict[str, Any] | None, snapshot: dict[str, Any] | None, now: datetime, *, bot_id: str) -> list[dict[str, Any]]:
    if not runtime:
        return []
    packed = list_mlb_fills(runtime, snapshot, now)
    if not packed.get("ok"):
        return []
    rows = []
    for row in packed.get("trades") or []:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["bot_id"] = bot_id
        rows.append(item)
    return rows


def bot_one_origin_ts(*, now: datetime | None = None) -> str | None:
    host = load_host_state()
    if not host.get("ok"):
        return None
    clock = _clock(now)
    if host.get("runtime"):
        rows = _ledger_rows(host["runtime"], host.get("snapshot"), clock, bot_id=BOT_ONE_ID)
    else:
        rows = [row for row in (host.get("trades") or []) if isinstance(row, dict)]
        for row in rows:
            row.setdefault("bot_id", BOT_ONE_ID)
    earliest: datetime | None = None
    for row in rows:
        ts = parse_utc(row.get("exchange_ts"))
        if ts is None:
            continue
        if earliest is None or ts < earliest:
            earliest = ts
    if earliest is None:
        return None
    return earliest.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _after_origin(row: dict[str, Any], origin_ts: str | None) -> bool:
    if not origin_ts:
        return True
    ts = parse_utc(row.get("exchange_ts"))
    origin = parse_utc(origin_ts)
    if ts is None or origin is None:
        return True
    return ts >= origin


def collect_ledgers(*, root=None, now: datetime | None = None) -> dict[str, Any]:
    clock = _clock(now)
    ensure_bot_one(root=root)
    production: list[dict[str, Any]] = []
    demo: list[dict[str, Any]] = []
    open_positions: dict[str, int] = {}
    snapshot = None
    host = load_host_state()
    if host.get("ok"):
        snapshot = host.get("snapshot")
        if host.get("runtime"):
            production.extend(_ledger_rows(host["runtime"], snapshot, clock, bot_id=BOT_ONE_ID))
            summary = summarize_mlb_ledger(host["runtime"], snapshot, clock)
            if summary.get("ok"):
                open_positions[BOT_ONE_ID] = int((summary.get("fields") or {}).get("open_mlb_positions") or 0)
        else:
            for row in host.get("trades") or []:
                if isinstance(row, dict):
                    item = dict(row)
                    item["bot_id"] = BOT_ONE_ID
                    production.append(item)
    from roller.jump.bots.demo_host import load_demo_host_state

    for row in list_bots(root=root):
        bot_id = str(row.get("bot_id") or "")
        if not bot_id or bot_id == BOT_ONE_ID:
            continue
        try:
            bot = load_bot(bot_id, root=root)
        except JumpError:
            continue
        if str(bot.get("kind") or "") == "grandfathered":
            continue
        demo_host = load_demo_host_state(bot_id)
        if not demo_host.get("ok"):
            continue
        if demo_host.get("runtime"):
            demo.extend(_ledger_rows(demo_host["runtime"], demo_host.get("snapshot"), clock, bot_id=bot_id))
            summary = summarize_mlb_ledger(demo_host["runtime"], demo_host.get("snapshot"), clock)
            if summary.get("ok"):
                open_positions[bot_id] = int((summary.get("fields") or {}).get("open_mlb_positions") or 0)
        else:
            for fill in demo_host.get("trades") or []:
                if isinstance(fill, dict):
                    item = dict(fill)
                    item["bot_id"] = bot_id
                    demo.append(item)
    return {
        "production": production,
        "demo": demo,
        "open_positions": open_positions,
        "snapshot": snapshot,
        "host_ok": bool(host.get("ok")),
        "host_detail": None if host.get("ok") else (host.get("reason") or "Bot One ledger unread"),
    }


def refresh_catalog(
    *,
    root=None,
    now: datetime | None = None,
    pull_kalshi: bool = True,
    fetch_charts: bool = False,
    kalshi_books: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clock = _clock(now)
    ledgers = collect_ledgers(root=root, now=clock)
    origin_ts = bot_one_origin_ts(now=clock)
    origin = None
    if origin_ts:
        origin = persist_origin(
            {
                "bot_one_first_fill_ts": origin_ts,
                "source": "bot_one_host_ledger",
                "catalog_version": CATALOG_VERSION,
            }
        )
    else:
        origin = load_origin()
        origin_ts = (origin or {}).get("bot_one_first_fill_ts") if origin else None

    books = {
        "PRODUCTION": {"ok": False, "status": "OBSERVATION_UNAVAILABLE", "fills": []},
        "DEMO": {"ok": False, "status": "OBSERVATION_UNAVAILABLE", "fills": []},
    }
    if kalshi_books:
        for key, value in kalshi_books.items():
            books[str(key).upper()] = value
    elif pull_kalshi:
        books["PRODUCTION"] = fetch_book("PRODUCTION")
        books["DEMO"] = fetch_book("DEMO")
    bankroll = _refresh_bankroll(pull_kalshi=pull_kalshi)

    production_ledger = [row for row in ledgers["production"] if _after_origin(row, origin_ts)]
    demo_ledger = list(ledgers["demo"])

    incoming: list[dict[str, Any]] = []
    if books["PRODUCTION"].get("ok"):
        incoming.extend(
            reconcile_book(
                [row for row in books["PRODUCTION"].get("fills") or [] if _after_origin(row, origin_ts)],
                production_ledger,
                environment="PRODUCTION",
                default_bot_id=BOT_ONE_ID,
            )
        )
    else:
        incoming.extend(
            ledger_record(row, environment="PRODUCTION", bot_id=BOT_ONE_ID) for row in production_ledger
        )
    if books["DEMO"].get("ok"):
        incoming.extend(
            reconcile_book(
                books["DEMO"].get("fills") or [],
                demo_ledger,
                environment="DEMO",
                default_bot_id=None,
            )
        )
    else:
        for row in demo_ledger:
            incoming.append(ledger_record(row, environment="DEMO", bot_id=str(row.get("bot_id") or UNATTRIBUTED)))

    if origin_ts:
        incoming = [
            row
            for row in incoming
            if str(row.get("environment") or "") != "PRODUCTION" or _after_origin(row, origin_ts)
        ]

    added = append_trades(incoming)
    trades = load_trades()
    analysis = analyze(
        trades,
        now=clock,
        snapshot=ledgers.get("snapshot"),
        open_positions=ledgers.get("open_positions"),
    )
    write_analysis(analysis)
    if fetch_charts:
        from roller.jump.catalog.charts import chart_for_trade

        for row in trades:
            chart_for_trade(row, fetch=True)

    return {
        "ok": True,
        "status": "CONFIRMED" if trades or origin_ts else "OBSERVATION_UNAVAILABLE",
        "catalog_version": CATALOG_VERSION,
        "origin": origin,
        "added": added,
        "trade_n": len(trades),
        "books": {
            "PRODUCTION": {
                "status": books["PRODUCTION"].get("status") or "OBSERVATION_UNAVAILABLE",
                "ok": bool(books["PRODUCTION"].get("ok")),
                "detail": books["PRODUCTION"].get("detail"),
            },
            "DEMO": {
                "status": books["DEMO"].get("status") or "OBSERVATION_UNAVAILABLE",
                "ok": bool(books["DEMO"].get("ok")),
                "detail": books["DEMO"].get("detail"),
            },
        },
        "analysis": analysis,
        "bankroll": bankroll,
        "honesty": dict(HONESTY),
        "caveats": list(CAVEATS),
    }


def _refresh_bankroll(*, pull_kalshi: bool) -> dict[str, Any] | None:
    existing = load_bankroll()
    if not pull_kalshi:
        return existing
    incoming: dict[str, Any] = {}
    for env in ("PRODUCTION", "DEMO"):
        body = fetch_balance(env)
        if not body.get("ok"):
            continue
        packed = pack_book(body, existing_book=book_for(existing, env))
        if packed and packed.get("current_cents") is not None:
            incoming[env] = packed
    if not incoming:
        return existing
    return persist_bankroll(
        {
            "origin_bankroll_cents": origin_bankroll_cents(),
            "origin_source": "mlb_factory_v1",
            "books": incoming,
        }
    )


def _analysis_stale(analysis: dict[str, Any] | None) -> bool:
    if not analysis:
        return True
    honesty = analysis.get("honesty") if isinstance(analysis.get("honesty"), dict) else {}
    if honesty.get("fill_result_sum_is_not_account_pnl") is not True:
        return True
    buckets = list((analysis.get("by_bot") or {}).values()) + list((analysis.get("by_book") or {}).values())
    if not buckets:
        return True
    return any("fill_result_sum_cents" not in row for row in buckets if isinstance(row, dict))


def _latest_exchange_ts(rows: list[dict[str, Any]]) -> datetime | None:
    latest: datetime | None = None
    for row in rows:
        ts = parse_utc(row.get("exchange_ts"))
        if ts is not None and (latest is None or ts > latest):
            latest = ts
    return latest


def _catalog_last_trade(analysis: dict[str, Any] | None) -> datetime | None:
    latest: datetime | None = None
    by_bot = (analysis or {}).get("by_bot")
    buckets = by_bot.values() if isinstance(by_bot, dict) else []
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        ts = parse_utc(bucket.get("last_trade"))
        if ts is not None and (latest is None or ts > latest):
            latest = ts
    return latest


def _should_pull_kalshi() -> bool:
    if (os.environ.get(SKIP_ENV) or "").strip().lower() in {"1", "true", "yes"}:
        return False
    return fills_bin() is not None


def ensure_catalog(*, root=None, now: datetime | None = None, sync_host: bool = False) -> dict[str, Any]:
    clock = _clock(now)
    trades = load_trades()
    origin = load_origin()
    analysis = load_analysis()
    if not trades and not origin:
        return refresh_catalog(root=root, now=clock, pull_kalshi=False, fetch_charts=False)
    if _analysis_stale(analysis):
        analysis = analyze(trades, now=clock)
        write_analysis(analysis)
    if sync_host:
        ledgers = collect_ledgers(root=root, now=clock)
        host_last = _latest_exchange_ts(list(ledgers.get("production") or []) + list(ledgers.get("demo") or []))
        catalog_last = _catalog_last_trade(analysis)
        if host_last is not None and (catalog_last is None or host_last > catalog_last):
            return refresh_catalog(
                root=root,
                now=clock,
                pull_kalshi=_should_pull_kalshi(),
                fetch_charts=False,
            )
    return {
        "ok": True,
        "status": "CONFIRMED",
        "origin": origin,
        "trade_n": len(trades),
        "analysis": analysis,
        "bankroll": load_bankroll(),
    }
