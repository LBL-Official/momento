"""Jump catalog HTTP handlers. Read + refresh. No order submit."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.jump.bots.versions import BOT_ONE_ID
from roller.jump.catalog.analysis import analyze, metric_bundle
from roller.jump.catalog.bankroll import account_bankroll, account_origin_pnl
from roller.jump.catalog.charts import chart_for_trade
from roller.jump.catalog.refresh import ensure_catalog, refresh_catalog
from roller.jump.catalog.store import load_analysis, load_bankroll, load_origin, load_trades
from roller.jump.catalog.versions import CATALOG_VERSION, CAVEATS, HONESTY, UNATTRIBUTED
from roller.jump.dashboard.heartbeat import unavailable


def _clock(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def public_catalog(*, root=None, now: datetime | None = None, environment: str | None = None) -> dict[str, Any]:
    clock = _clock(now)
    trades = load_trades()
    origin = load_origin()
    wanted = (environment or "").strip().upper()
    if wanted in {"DEMO", "PRODUCTION"}:
        trades = [row for row in trades if str(row.get("environment") or "").upper() == wanted]
    analysis = load_analysis() or analyze(trades, now=clock)
    bankroll = load_bankroll()
    return {
        "ok": True,
        "status": "CONFIRMED" if trades or origin else "OBSERVATION_UNAVAILABLE",
        "catalog_version": CATALOG_VERSION,
        "origin": origin,
        "bankroll": bankroll,
        "trades": trades,
        "trade_n": len(trades),
        "analysis": analysis,
        "bot_one_id": BOT_ONE_ID,
        "unattributed": UNATTRIBUTED,
        "honesty": dict(HONESTY),
        "caveats": list(CAVEATS),
    }


def handle_catalog(*, root=None, environment: str | None = None) -> dict[str, Any]:
    ensure_catalog(root=root)
    return public_catalog(root=root, environment=environment)


def handle_refresh(body: dict[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    body = body or {}
    pull = body.get("pull_kalshi")
    charts = body.get("fetch_charts")
    return refresh_catalog(
        root=root,
        pull_kalshi=True if pull is None else bool(pull),
        fetch_charts=bool(charts),
    )


def catalog_trades_for_bot(bot_id: str, *, root=None, now: datetime | None = None, with_charts: bool = False) -> dict[str, Any]:
    ensure_catalog(root=root, now=now)
    clock = _clock(now)
    trades = [
        row
        for row in load_trades()
        if str(row.get("bot_id") or "") == str(bot_id)
    ]
    analysis = load_analysis() or analyze(load_trades(), now=clock)
    bucket = (analysis.get("by_bot") or {}).get(str(bot_id))
    bankroll = load_bankroll()
    env = "PRODUCTION" if str(bot_id) == BOT_ONE_ID else "DEMO"
    missing = "OBSERVATION_UNAVAILABLE" if env == "PRODUCTION" else "UNAVAILABLE"
    metrics = metric_bundle(
        bucket,
        missing=missing,
        origin_pnl=account_origin_pnl(bankroll, environment=env, missing=missing),
        bankroll=account_bankroll(bankroll, environment=env, missing=missing),
    )
    if with_charts:
        packed = []
        for row in trades:
            item = dict(row)
            item["chart"] = chart_for_trade(row, fetch=False)
            packed.append(item)
        trades = packed
    origin = load_origin()
    if not trades and not origin:
        return {
            "ok": False,
            "status": "OBSERVATION_UNAVAILABLE",
            "bot_id": bot_id,
            "trades": None,
            "trade_n": unavailable("OBSERVATION_UNAVAILABLE"),
            "weekly_trade_n": unavailable("OBSERVATION_UNAVAILABLE"),
            "day_pnl": unavailable("OBSERVATION_UNAVAILABLE"),
            "week_pnl": unavailable("OBSERVATION_UNAVAILABLE"),
            "origin_pnl": unavailable("OBSERVATION_UNAVAILABLE"),
            "last_trade": unavailable("UNAVAILABLE"),
            "detail": "catalog empty and host ledger unread",
            "honesty": dict(HONESTY),
        }
    return {
        "ok": True,
        "status": "CONFIRMED",
        "bot_id": bot_id,
        "trades": trades,
        "trade_n": metrics["trade_n"],
        "weekly_trade_n": metrics["weekly_n"],
        "day_pnl": metrics["day_pnl"],
        "week_pnl": metrics["week_pnl"],
        "origin_pnl": metrics["origin_pnl"],
        "last_trade": metrics["last_trade"],
        "win_loss": metrics.get("win_loss"),
        "open_positions": metrics.get("open_positions"),
        "source": "catalog",
        "honesty": dict(HONESTY),
    }
