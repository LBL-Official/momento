"""Statically loaded My Bots profiles and posts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.jump.bots.pipeline import list_control_plane
from roller.jump.catalog.analysis import analyze, metric_bundle
from roller.jump.catalog.connection import connection_metrics
from roller.jump.catalog.charts import chart_for_trade
from roller.jump.catalog.refresh import ensure_catalog
from roller.jump.catalog.store import load_analysis, load_origin, load_trades
from roller.jump.catalog.versions import CATALOG_VERSION, CAVEATS, HONESTY, UNATTRIBUTED
from roller.jump.dashboard.ledger import pacific_week_start, parse_utc


def _clock(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _money(raw: Any) -> Any:
    if raw is None or raw == "UNAVAILABLE":
        return "UNAVAILABLE"
    try:
        return int(raw)
    except (TypeError, ValueError):
        return "UNAVAILABLE"


def _trade_post(row: dict[str, Any], *, root=None) -> dict[str, Any]:
    return {
        "kind": "trade",
        "jump_trade_id": row.get("jump_trade_id"),
        "bot_id": row.get("bot_id"),
        "environment": row.get("environment"),
        "exchange_ts": row.get("exchange_ts"),
        "ticker": row.get("ticker"),
        "qty": row.get("qty"),
        "yes_price_cents": row.get("yes_price_cents"),
        "result": _money(row.get("result")),
        "source": row.get("source"),
        "chart": chart_for_trade(row, fetch=False),
        "caption": "Candle path ≠ fill.",
    }


def _weekly_posts(bot_id: str, trades: list[dict[str, Any]], markers: dict[str, list[str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_week: dict[str, list[dict[str, Any]]] = {}
    for row in trades:
        ts = parse_utc(row.get("exchange_ts"))
        if ts is None:
            continue
        week = pacific_week_start(ts).isoformat()
        by_week.setdefault(week, []).append(row)
    for week, rows in sorted(by_week.items()):
        out.append(
            {
                "kind": "weekly",
                "bot_id": bot_id,
                "week_start": week,
                "exchange_ts": rows[-1].get("exchange_ts"),
                "trade_n": len(rows),
                "result": "UNAVAILABLE",
                "jump_trade_ids": markers.get(week) or [row.get("jump_trade_id") for row in rows],
            }
        )
    return out


def _every_ten_posts(bot_id: str, markers: list[dict[str, Any]], trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(row.get("jump_trade_id")): row for row in trades}
    out: list[dict[str, Any]] = []
    ordered = sorted(trades, key=lambda r: str(r.get("exchange_ts") or ""))
    for mark in markers:
        n = int(mark.get("n") or 0)
        subset = ordered[:n]
        out.append(
            {
                "kind": "every_10",
                "bot_id": bot_id,
                "n": n,
                "exchange_ts": mark.get("exchange_ts") or (by_id.get(str(mark.get("jump_trade_id"))) or {}).get("exchange_ts"),
                "trade_n": n,
                "result": "UNAVAILABLE",
                "jump_trade_id": mark.get("jump_trade_id"),
            }
        )
    return out


def build_posts(bot_id: str, trades: list[dict[str, Any]], analysis: dict[str, Any], *, root=None) -> list[dict[str, Any]]:
    posts = [_trade_post(row, root=root) for row in trades]
    markers = ((analysis.get("weekly_markers") or {}).get(bot_id)) or {}
    posts.extend(_weekly_posts(bot_id, trades, markers))
    posts.extend(_every_ten_posts(bot_id, ((analysis.get("every_ten") or {}).get(bot_id)) or [], trades))
    posts.sort(key=lambda row: str(row.get("exchange_ts") or ""), reverse=True)
    return posts


def handle_mybots(*, root=None, cfg=None, now: datetime | None = None) -> dict[str, Any]:
    clock = _clock(now)
    ensured = ensure_catalog(root=root, now=clock)
    plane = list_control_plane(root=root, cfg=cfg, observe=False)
    trades = load_trades()
    analysis = (ensured.get("analysis") if isinstance(ensured, dict) else None) or load_analysis() or analyze(trades, now=clock)
    origin = (ensured.get("origin") if isinstance(ensured, dict) else None) or load_origin()
    profiles = []
    for bot in plane.get("bots") or []:
        bot_id = str(bot.get("bot_id") or "")
        mine = [row for row in trades if str(row.get("bot_id") or "") == bot_id]
        bucket = (analysis.get("by_bot") or {}).get(bot_id)
        env = str(bot.get("environment") or "").upper() or "PRODUCTION"
        missing = "OBSERVATION_UNAVAILABLE" if env == "PRODUCTION" else "UNAVAILABLE"
        packed = []
        for row in mine:
            item = dict(row)
            item["chart"] = chart_for_trade(row, fetch=False)
            packed.append(item)
        env_metrics = connection_metrics(environment=env, now=clock, missing=missing)
        stats = metric_bundle(
            bucket,
            missing=missing,
            origin_pnl=env_metrics["origin_pnl"],
            bankroll=env_metrics["bankroll"],
        )
        stats["day_pnl"] = env_metrics["day_pnl"]
        stats["week_pnl"] = env_metrics["week_pnl"]
        stats["open_positions"] = env_metrics["positions"]
        profiles.append(
            {
                "bot": bot,
                "bot_id": bot_id,
                "stats": stats,
                "posts": build_posts(bot_id, mine, analysis),
                "trades": {
                    "ok": True,
                    "status": "CONFIRMED" if mine or origin else "OBSERVATION_UNAVAILABLE",
                    "bot_id": bot_id,
                    "trades": packed,
                    "source": "catalog",
                    "honesty": dict(HONESTY),
                },
            }
        )
    return {
        "ok": True,
        "status": "CONFIRMED",
        "catalog_version": CATALOG_VERSION,
        "origin": origin,
        "profiles": profiles,
        "unattributed_n": len([row for row in trades if str(row.get("bot_id") or "") == UNATTRIBUTED]),
        "honesty": dict(HONESTY),
        "caveats": list(CAVEATS),
    }
