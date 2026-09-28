"""Per-bot and per-book catalog analysis. Integer cents. Demo not added to live."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.jump.catalog.versions import UNATTRIBUTED
from roller.jump.dashboard.heartbeat import confirmed, unavailable
from roller.jump.dashboard.ledger import (
    I64_MAX,
    I64_MIN,
    in_pacific_day,
    in_trading_week,
    pacific_week_start,
    parse_utc,
    week_start_from_snapshot,
)


def _add(left: int, right: int) -> int | None:
    total = left + right
    if total < I64_MIN or total > I64_MAX:
        return None
    return total


def _realized(row: dict[str, Any]) -> int | None:
    raw = row.get("result")
    if raw is None or raw == "UNAVAILABLE":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _empty_bucket() -> dict[str, Any]:
    return {
        "trade_n": 0,
        "weekly_n": 0,
        "settled_n": 0,
        "fill_result_sum_cents": 0,
        "day_fill_result_cents": 0,
        "week_fill_result_cents": 0,
        "wins": 0,
        "losses": 0,
        "open_positions": None,
        "last_trade": None,
        "win_loss": "UNAVAILABLE",
    }


def _apply(bucket: dict[str, Any], row: dict[str, Any], *, now: datetime, week_start: datetime) -> None:
    ts = parse_utc(row.get("exchange_ts"))
    bucket["trade_n"] += 1
    if ts is not None and in_trading_week(ts, week_start):
        bucket["weekly_n"] += 1
    last_ts = parse_utc(bucket.get("last_trade"))
    if ts is not None and (last_ts is None or ts > last_ts):
        bucket["last_trade"] = ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    realized = _realized(row)
    if realized is None or ts is None:
        return
    bucket["settled_n"] = int(bucket.get("settled_n") or 0) + 1
    if realized > 0:
        bucket["wins"] += 1
    elif realized < 0:
        bucket["losses"] += 1
    total = _add(int(bucket.get("fill_result_sum_cents") or 0), realized)
    if total is not None:
        bucket["fill_result_sum_cents"] = total
    if in_pacific_day(ts, now):
        nxt = _add(int(bucket.get("day_fill_result_cents") or 0), realized)
        if nxt is not None:
            bucket["day_fill_result_cents"] = nxt
    if in_trading_week(ts, week_start):
        nxt = _add(int(bucket.get("week_fill_result_cents") or 0), realized)
        if nxt is not None:
            bucket["week_fill_result_cents"] = nxt


def _finalize(bucket: dict[str, Any]) -> dict[str, Any]:
    wins = int(bucket["wins"])
    losses = int(bucket["losses"])
    if wins + losses == 0:
        bucket["win_loss"] = "UNAVAILABLE"
    else:
        bucket["win_loss"] = {"wins": wins, "losses": losses, "status": "CONFIRMED"}
    return bucket


def analyze(
    trades: list[dict[str, Any]],
    *,
    now: datetime,
    snapshot: dict[str, Any] | None = None,
    open_positions: dict[str, int] | None = None,
) -> dict[str, Any]:
    week_start = week_start_from_snapshot(snapshot, now)
    by_bot: dict[str, dict[str, Any]] = {}
    by_book = {"DEMO": _empty_bucket(), "PRODUCTION": _empty_bucket()}
    weekly_markers: dict[str, dict[str, list[str]]] = {}
    every_ten: dict[str, list[dict[str, Any]]] = {}
    ordered = sorted(
        [row for row in trades if row.get("bot_id") and row.get("bot_id") != UNATTRIBUTED],
        key=lambda r: str(r.get("exchange_ts") or ""),
    )
    counts: dict[str, int] = {}
    for row in trades:
        env = str(row.get("environment") or "").upper()
        if env in by_book:
            _apply(by_book[env], row, now=now, week_start=week_start)
        bot_id = str(row.get("bot_id") or UNATTRIBUTED)
        if bot_id == UNATTRIBUTED:
            continue
        by_bot.setdefault(bot_id, _empty_bucket())
        _apply(by_bot[bot_id], row, now=now, week_start=week_start)
        ts = parse_utc(row.get("exchange_ts"))
        if ts is not None:
            week = pacific_week_start(ts).isoformat()
            weekly_markers.setdefault(bot_id, {}).setdefault(week, []).append(str(row.get("jump_trade_id")))
    for row in ordered:
        bot_id = str(row["bot_id"])
        counts[bot_id] = counts.get(bot_id, 0) + 1
        n = counts[bot_id]
        if n >= 10 and n % 10 == 0:
            every_ten.setdefault(bot_id, []).append(
                {
                    "n": n,
                    "jump_trade_id": row.get("jump_trade_id"),
                    "exchange_ts": row.get("exchange_ts"),
                    "environment": row.get("environment"),
                }
            )
    for key, bucket in by_bot.items():
        _finalize(bucket)
        if open_positions and key in open_positions:
            bucket["open_positions"] = open_positions[key]
    for bucket in by_book.values():
        _finalize(bucket)
    return {
        "by_bot": by_bot,
        "by_book": by_book,
        "weekly_markers": weekly_markers,
        "every_ten": every_ten,
        "week_start": week_start.isoformat(),
        "timezone": "America/Los_Angeles",
        "honesty": {
            "demo_not_added_to_live": True,
            "win_loss_only_when_realized": True,
            "fill_result_sum_is_not_account_pnl": True,
            "live_ev": "UNAVAILABLE",
        },
    }


def metric_bundle(
    bucket: dict[str, Any] | None,
    *,
    missing: str = "UNAVAILABLE",
    origin_pnl: dict[str, Any] | None = None,
    bankroll: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not bucket:
        return {
            "trade_n": unavailable(missing),
            "weekly_n": unavailable(missing),
            "day_pnl": unavailable(missing),
            "week_pnl": unavailable(missing),
            "origin_pnl": origin_pnl or unavailable(missing),
            "bankroll": bankroll or unavailable(missing),
            "open_positions": unavailable(missing),
            "last_trade": unavailable("UNAVAILABLE"),
            "win_loss": unavailable(missing),
            "realized_win_rate": unavailable(missing),
        }
    wins = int(bucket.get("wins") or 0)
    losses = int(bucket.get("losses") or 0)
    settled = int(bucket.get("settled_n") or 0)
    win_loss = bucket.get("win_loss")
    if isinstance(win_loss, dict) and win_loss.get("status") == "CONFIRMED":
        packed_wl = confirmed({"wins": int(win_loss.get("wins") or 0), "losses": int(win_loss.get("losses") or 0)})
    else:
        packed_wl = unavailable(missing)
    return {
        "trade_n": confirmed(bucket.get("trade_n")),
        "weekly_n": confirmed(bucket.get("weekly_n")),
        "day_pnl": unavailable(missing),
        "week_pnl": unavailable(missing),
        "origin_pnl": origin_pnl or unavailable(missing),
        "bankroll": bankroll or unavailable(missing),
        "open_positions": (
            confirmed(bucket["open_positions"])
            if bucket.get("open_positions") is not None
            else unavailable(missing)
        ),
        "last_trade": (
            confirmed(bucket["last_trade"]) if bucket.get("last_trade") else unavailable("UNAVAILABLE")
        ),
        "win_loss": packed_wl,
        "realized_win_rate": (
            confirmed({"wins": wins, "losses": losses, "settled_n": settled})
            if settled > 0
            else unavailable(missing)
        ),
    }
