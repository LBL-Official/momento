"""Bot One MLB realized P&L from live-runtime.json.

Mirrors crates/pnl PnlBreakdown::from_position. Integer cents only.
Does not invent unrealized P&L, Kalshi marks, or expected value.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

MLB_STRATEGY_ID = 1
I64_MIN = -(2**63)
I64_MAX = (2**63) - 1
PACIFIC = ZoneInfo("America/Los_Angeles")
WEEK_START_HOUR = 4
FLAT = "Flat"
SETTLED = "Settled"
ENTRY = "Entry"
LIQUIDATION = "Liquidation"


def _checked_add(left: int, right: int) -> int | None:
    total = left + right
    if total < I64_MIN or total > I64_MAX:
        return None
    return total


def _checked_sub(left: int, right: int) -> int | None:
    total = left - right
    if total < I64_MIN or total > I64_MAX:
        return None
    return total


def money_cents(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, dict) and "cents" in raw:
        try:
            return int(raw["cents"])
        except (TypeError, ValueError):
            return None
    return None


def _qty(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, dict) and "qty" in raw:
        try:
            return int(raw["qty"])
        except (TypeError, ValueError):
            return None
    return None


def _strategy_id(raw: Any) -> int | None:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, dict) and "0" in raw:
        try:
            return int(raw["0"])
        except (TypeError, ValueError):
            return None
    return None


def parse_utc(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def pacific_week_start(at: datetime) -> datetime:
    """Monday 04:00 America/Los_Angeles of the trading week containing `at`."""
    local = at.astimezone(PACIFIC)
    monday = local.date() - timedelta(days=local.weekday())
    this_monday = datetime(monday.year, monday.month, monday.day, WEEK_START_HOUR, tzinfo=PACIFIC)
    if local < this_monday:
        monday = monday - timedelta(days=7)
        this_monday = datetime(monday.year, monday.month, monday.day, WEEK_START_HOUR, tzinfo=PACIFIC)
    return this_monday


def week_start_from_snapshot(snapshot: dict[str, Any] | None, now: datetime) -> datetime:
    if isinstance(snapshot, dict):
        parsed = parse_utc(snapshot.get("week_start_utc"))
        if parsed is not None:
            return parsed.astimezone(PACIFIC)
    return pacific_week_start(now)


def in_pacific_day(ts: datetime, now: datetime) -> bool:
    return ts.astimezone(PACIFIC).date() == now.astimezone(PACIFIC).date()


def in_trading_week(ts: datetime, week_start: datetime) -> bool:
    start = week_start.astimezone(timezone.utc)
    end = start + timedelta(days=7)
    at = ts.astimezone(timezone.utc)
    return start <= at < end


def realized_from_position(position: dict[str, Any]) -> int | None:
    """Same rule as PnlBreakdown::from_position. None = not realized."""
    entry_cost = 0
    entry_fees = 0
    liquidation_proceeds = 0
    liquidation_fees = 0
    for fill in position.get("fill_history") or []:
        if not isinstance(fill, dict):
            return None
        fee = fill.get("fee") if isinstance(fill.get("fee"), dict) else {}
        kind = str(fee.get("kind") or "")
        premium = money_cents(fill.get("premium"))
        fee_amt = money_cents(fee.get("amount"))
        if premium is None or fee_amt is None:
            return None
        if kind == ENTRY:
            nxt = _checked_add(entry_cost, premium)
            fees = _checked_add(entry_fees, fee_amt)
            if nxt is None or fees is None:
                return None
            entry_cost, entry_fees = nxt, fees
        elif kind == LIQUIDATION:
            nxt = _checked_add(liquidation_proceeds, premium)
            fees = _checked_add(liquidation_fees, fee_amt)
            if nxt is None or fees is None:
                return None
            liquidation_proceeds, liquidation_fees = nxt, fees
        else:
            return None
    total_fees = _checked_add(entry_fees, liquidation_fees)
    if total_fees is None:
        return None
    settlement = money_cents(position.get("settlement_proceeds"))
    lifecycle = str(position.get("lifecycle") or "")
    filled = _qty(position.get("filled_quantity"))
    if settlement is not None:
        credits = _checked_add(liquidation_proceeds, settlement)
        costs = _checked_add(entry_cost, total_fees)
        if credits is None or costs is None:
            return None
        return _checked_sub(credits, costs)
    if lifecycle == FLAT and filled == 0:
        credits = _checked_add(liquidation_proceeds, 0)
        costs = _checked_add(entry_cost, total_fees)
        if credits is None or costs is None:
            return None
        return _checked_sub(credits, costs)
    return None


def last_fill_utc(position: dict[str, Any]) -> datetime | None:
    latest: datetime | None = None
    for fill in position.get("fill_history") or []:
        if not isinstance(fill, dict):
            return None
        ts = parse_utc(fill.get("exchange_ts"))
        if ts is None:
            return None
        if latest is None or ts > latest:
            latest = ts
    return latest


def position_is_open(position: dict[str, Any]) -> bool:
    filled = _qty(position.get("filled_quantity")) or 0
    lifecycle = str(position.get("lifecycle") or "")
    return filled > 0 and lifecycle not in {SETTLED, FLAT}


def _positions(runtime: dict[str, Any]) -> list[dict[str, Any]] | None:
    tracker = runtime.get("tracker")
    if not isinstance(tracker, dict):
        return None
    rows = tracker.get("positions")
    if rows is None:
        return []
    if not isinstance(rows, list):
        return None
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            return None
        out.append(row)
    return out


def summarize_mlb_ledger(
    runtime: dict[str, Any],
    snapshot: dict[str, Any] | None,
    now: datetime,
) -> dict[str, Any]:
    """Day = America/Los_Angeles calendar day. Week = Monday 04:00 PT.

    A realized MLB position is attributed by its last fill exchange_ts.
    Position has no settlement clock; settlement P&L inherits that fill time.
    """
    positions = _positions(runtime)
    if positions is None:
        return {"ok": False, "reason": "live-runtime tracker.positions unreadable"}
    week_start = week_start_from_snapshot(snapshot, now)
    day_pnl = 0
    week_pnl = 0
    open_mlb = 0
    last_trade: datetime | None = None
    for position in positions:
        sid = _strategy_id(position.get("strategy_id"))
        if sid is None:
            return {"ok": False, "reason": "position missing strategy_id"}
        if sid != MLB_STRATEGY_ID:
            continue
        if position_is_open(position):
            open_mlb += 1
        ts = last_fill_utc(position)
        if ts is not None and (last_trade is None or ts > last_trade):
            last_trade = ts
        realized = realized_from_position(position)
        if realized is None:
            continue
        if ts is None:
            return {"ok": False, "reason": "realized MLB position missing fill exchange_ts"}
        if in_pacific_day(ts, now):
            nxt = _checked_add(day_pnl, realized)
            if nxt is None:
                return {"ok": False, "reason": "day PNL overflow"}
            day_pnl = nxt
        if in_trading_week(ts, week_start):
            nxt = _checked_add(week_pnl, realized)
            if nxt is None:
                return {"ok": False, "reason": "week PNL overflow"}
            week_pnl = nxt
    trades = list_mlb_fills(runtime, snapshot, now)
    fields: dict[str, Any] = {
        "day_pnl_cents": day_pnl,
        "week_pnl_cents": week_pnl,
        "open_mlb_positions": open_mlb,
        "trade_n": int((trades.get("fields") or {}).get("trade_n") or 0) if trades.get("ok") else None,
        "weekly_trade_n": int((trades.get("fields") or {}).get("weekly_trade_n") or 0) if trades.get("ok") else None,
    }
    if fields["trade_n"] is None:
        fields.pop("trade_n")
    if fields["weekly_trade_n"] is None:
        fields.pop("weekly_trade_n")
    bankroll = money_cents((snapshot or {}).get("bankroll")) if isinstance(snapshot, dict) else None
    if bankroll is not None:
        fields["bankroll_cents"] = bankroll
    if last_trade is not None:
        fields["last_trade"] = last_trade.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "ok": True,
        "fields": fields,
        "trades": (trades.get("trades") or []) if trades.get("ok") else [],
        "week_start": week_start.isoformat(),
        "timezone": "America/Los_Angeles",
        "sport": "MLB",
        "formula": "crates/pnl PnlBreakdown::from_position",
    }


def _fill_side(fill: dict[str, Any]) -> str | None:
    raw = fill.get("side") or fill.get("order_side")
    if raw is None or raw == "":
        return None
    return str(raw)


def _fill_market(position: dict[str, Any], fill: dict[str, Any]) -> str | None:
    for source in (fill, position):
        for key in ("ticker", "market"):
            raw = source.get(key)
            if raw and _compact_ticker(raw):
                return str(raw).strip()
    for source in (fill, position):
        raw = source.get("market_id")
        if raw and _compact_ticker(raw):
            return str(raw).strip()
    return None


def list_mlb_fills(
    runtime: dict[str, Any],
    snapshot: dict[str, Any] | None,
    now: datetime,
) -> dict[str, Any]:
    """Confirmed MLB fills from live-runtime. Unreadable → not an empty book."""
    positions = _positions(runtime)
    if positions is None:
        return {"ok": False, "reason": "live-runtime tracker.positions unreadable"}
    week_start = week_start_from_snapshot(snapshot, now)
    trades: list[dict[str, Any]] = []
    last_trade: datetime | None = None
    weekly = 0
    for position in positions:
        sid = _strategy_id(position.get("strategy_id"))
        if sid is None:
            return {"ok": False, "reason": "position missing strategy_id"}
        if sid != MLB_STRATEGY_ID:
            continue
        realized = realized_from_position(position)
        fills = position.get("fill_history") or []
        if not isinstance(fills, list):
            return {"ok": False, "reason": "fill_history unreadable"}
        for index, fill in enumerate(fills):
            if not isinstance(fill, dict):
                return {"ok": False, "reason": "fill unreadable"}
            ts = parse_utc(fill.get("exchange_ts"))
            if ts is None:
                return {"ok": False, "reason": "fill missing exchange_ts"}
            premium = money_cents(fill.get("premium"))
            fee = fill.get("fee") if isinstance(fill.get("fee"), dict) else {}
            fee_amt = money_cents(fee.get("amount"))
            if premium is None or fee_amt is None:
                return {"ok": False, "reason": "fill missing premium or fee"}
            if last_trade is None or ts > last_trade:
                last_trade = ts
            if in_trading_week(ts, week_start):
                weekly += 1
            last_on_position = index == len(fills) - 1
            qty = _qty(fill.get("quantity")) if fill.get("quantity") is not None else _qty(fill.get("qty"))
            price = money_cents(fill.get("price"))
            if price is None and qty and qty > 0 and premium % qty == 0:
                price = premium // qty
            fill_key = fill.get("fill_id")
            if fill_key is None:
                fill_key = fill.get("venue_fill_id")
            trades.append(
                {
                    "exchange_ts": ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "premium_cents": premium,
                    "fee_cents": fee_amt,
                    "fee_kind": str(fee.get("kind") or "") or None,
                    "side": _fill_side(fill),
                    "market": _fill_market(position, fill),
                    "qty": qty,
                    "price_cents": price,
                    "fill_id": str(fill_key) if fill_key is not None and str(fill_key) != "" else None,
                    "realized_cents": realized if last_on_position else None,
                }
            )
    fields: dict[str, Any] = {
        "trade_n": len(trades),
        "weekly_trade_n": weekly,
    }
    if last_trade is not None:
        fields["last_trade"] = last_trade.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "ok": True,
        "trades": trades,
        "fields": fields,
        "week_start": week_start.isoformat(),
        "timezone": "America/Los_Angeles",
        "sport": "MLB",
        "formula": "crates/pnl PnlBreakdown::from_position",
    }


def _compact_ticker(raw: Any) -> str | None:
    text = str(raw or "").strip()
    if len(text) < 4 or len(text) > 80 or text.isdigit():
        return None
    if any(ch.isalpha() for ch in text):
        return text
    return None


def _compact_fill_id(raw: Any) -> str | None:
    text = str(raw).strip() if raw is not None else ""
    if not text:
        return None
    if len(text) <= 24:
        return text
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _compact_side(raw: Any) -> str | None:
    text = str(raw or "").strip()
    if not text or len(text) > 16:
        return None
    return text


def compact_ssm_trades(trades: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    """Keep ticker + short fill identity. Drop bulky u128 market/fill ids for SSM 24KB."""
    compact: list[dict[str, Any]] = []
    earliest: str | None = None
    for index, row in enumerate(trades):
        if not isinstance(row, dict):
            continue
        ts = row.get("exchange_ts")
        if isinstance(ts, str) and (earliest is None or ts < earliest):
            earliest = ts
        item: dict[str, Any] = {
            "exchange_ts": ts,
            "premium_cents": row.get("premium_cents"),
            "fee_cents": row.get("fee_cents"),
            "fee_kind": row.get("fee_kind"),
            "qty": row.get("qty"),
            "price_cents": row.get("price_cents"),
            "realized_cents": row.get("realized_cents"),
            "seq": index,
        }
        ticker = _compact_ticker(row.get("ticker") or row.get("market"))
        if ticker:
            item["ticker"] = ticker
        fill_id = _compact_fill_id(row.get("fill_id"))
        if fill_id:
            item["fill_id"] = fill_id
        side = _compact_side(row.get("side"))
        if side:
            item["side"] = side
        compact.append(item)
    return compact, earliest


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    runtime_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("live-runtime.json")
    snapshot_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    snapshot = None
    if snapshot_path is not None and snapshot_path.is_file():
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    body = summarize_mlb_ledger(runtime, snapshot, datetime.now(timezone.utc))
    if body.get("ok"):
        compact, earliest = compact_ssm_trades(body.get("trades") or [])
        body["trades"] = compact
        fields = body.get("fields")
        if isinstance(fields, dict) and earliest:
            fields["earliest_fill_ts"] = earliest
    print(json.dumps(body, separators=(",", ":")))
