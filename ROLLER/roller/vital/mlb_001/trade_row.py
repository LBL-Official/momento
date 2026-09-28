"""MLB 001 one-row-per-market trade contract.

Host Position wins. Confirmed-ticker Kalshi fills may seed OPEN rows when
the host is unread. JUMP_CATALOG rows without a ticker are not grouped.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.jump.dashboard.ledger import (
    I64_MAX,
    _checked_sub,
    in_trading_week,
    money_cents,
    parse_utc,
)
from roller.vital.execution import TRADE_CLOSED, fact, fact_value, unwrap_id
from roller.vital.honesty import unavailable
from roller.vital.mlb_001.market import game_label

STANDARD_ROW_KEYS = (
    "market",
    "game",
    "entry_price_cents",
    "exit_price_cents",
    "amount_traded_cents",
    "amount_exited_cents",
    "bankroll_at_entry_cents",
    "pct_bankroll_allocated_bp",
    "pct_bankroll_returned_bp",
    "pct_allocated_pnl_bp",
)


def basis_points(numer: int | None, denom: int | None) -> int | None:
    """Integer bp. Toward zero. No float money."""
    if numer is None or denom is None or denom <= 0:
        return None
    limit = I64_MAX // 10000
    if numer > limit or numer < -limit:
        return None
    scaled = numer * 10000
    if scaled >= 0:
        return scaled // denom
    return -((-scaled) // denom)


def identity_maps(runtime: dict[str, Any] | None) -> dict[str, Any]:
    by_market: dict[str, str] = {}
    by_game: dict[str, list[str]] = {}
    if not isinstance(runtime, dict):
        return {"by_market": by_market, "by_game": by_game}
    rows = runtime.get("identity")
    if not isinstance(rows, list):
        return {"by_market": by_market, "by_game": by_game}
    for row in rows:
        ticker = mid = gid = None
        if isinstance(row, (list, tuple)) and len(row) >= 3:
            ticker, mid, gid = str(row[0] or "").strip(), unwrap_id(row[1]), unwrap_id(row[2])
        elif isinstance(row, dict):
            ticker = str(row.get("ticker") or "").strip() or None
            mid = unwrap_id(row.get("market_id"))
            gid = unwrap_id(row.get("game_id"))
        if ticker and mid:
            by_market[mid] = ticker
        if ticker and gid:
            bucket = by_game.setdefault(gid, [])
            if ticker not in bucket:
                bucket.append(ticker)
    return {"by_market": by_market, "by_game": by_game}


def resolve_identity_ticker(position: dict[str, Any], identity: dict[str, Any] | None) -> str | None:
    maps = identity if isinstance(identity, dict) else {}
    by_market = maps.get("by_market") if isinstance(maps.get("by_market"), dict) else {}
    by_game = maps.get("by_game") if isinstance(maps.get("by_game"), dict) else {}
    mid = unwrap_id(position.get("market_id"))
    if mid and mid in by_market:
        return str(by_market[mid])
    gid = unwrap_id(position.get("game_id"))
    tickers = by_game.get(gid) if gid else None
    if isinstance(tickers, list) and len(tickers) == 1:
        return str(tickers[0])
    return None


def bankroll_at_entry_cents(
    entry_ts: datetime | None,
    *,
    snapshot: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> int | None:
    """Weekly snapshot only if entry is in that week. Else last history ≤ entry.

    Factory bankroll is not used. A later observation is future information.
    """
    if entry_ts is None:
        return None
    if isinstance(snapshot, dict):
        bankroll = money_cents(snapshot.get("bankroll"))
        week_start = parse_utc(snapshot.get("week_start_utc"))
        if bankroll is not None and bankroll > 0 and week_start is not None and in_trading_week(entry_ts, week_start):
            return bankroll
    best: int | None = None
    best_ts: datetime | None = None
    for row in history or []:
        if not isinstance(row, dict):
            continue
        env = str(row.get("environment") or "").strip().upper()
        if env and env != "PRODUCTION":
            continue
        ts = parse_utc(row.get("observed_at"))
        raw = row.get("current_cents")
        try:
            cents = int(raw) if raw is not None and not isinstance(raw, bool) else None
        except (TypeError, ValueError):
            cents = None
        if ts is None or cents is None or cents <= 0:
            continue
        if ts <= entry_ts and (best_ts is None or ts > best_ts):
            best, best_ts = cents, ts
    return best


def apply_standard_row(
    trade: dict[str, Any],
    *,
    snapshot: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    closed = trade.get("status") == TRADE_CLOSED
    ticker = fact_value(trade.get("market"))
    traded = fact_value(trade.get("entry_amount"))
    if closed:
        exited = fact_value(trade.get("exit_amount"))
        exit_price = trade.get("exit_price")
        exit_amount = trade.get("exit_amount")
    else:
        exited = None
        exit_price = unavailable("UNAVAILABLE")
        exit_amount = unavailable("UNAVAILABLE")
    entry_ts = parse_utc(fact_value(trade.get("entry_date")))
    bankroll = bankroll_at_entry_cents(entry_ts, snapshot=snapshot, history=history)
    allocated = basis_points(traded if isinstance(traded, int) else None, bankroll)
    returned = basis_points(exited if isinstance(exited, int) else None, bankroll) if closed else None
    pnl_bp = None
    if closed and isinstance(traded, int) and isinstance(exited, int):
        delta = _checked_sub(exited, traded)
        pnl_bp = basis_points(delta, traded)
    trade["game"] = fact(game_label(str(ticker) if ticker else None))
    trade["entry_price_cents"] = trade.get("entry_price")
    trade["exit_price_cents"] = exit_price
    trade["amount_traded_cents"] = trade.get("entry_amount")
    trade["amount_risked_cents"] = trade.get("entry_amount")
    trade["amount_exited_cents"] = exit_amount
    trade["bankroll_at_entry_cents"] = fact(bankroll)
    trade["pct_bankroll_allocated_bp"] = fact(allocated, missing="UNAVAILABLE")
    trade["pct_bankroll_returned_bp"] = fact(returned, missing="UNAVAILABLE")
    trade["pct_allocated_pnl_bp"] = fact(pnl_bp, missing="UNAVAILABLE")
    trade["standard_row"] = {key: trade.get(key) for key in STANDARD_ROW_KEYS}
    return trade
