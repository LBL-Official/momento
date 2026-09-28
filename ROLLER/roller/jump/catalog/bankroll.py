"""Account PNL is bankroll delta. Fill-result sums are not the $50 book."""

from __future__ import annotations

from typing import Any

from datetime import datetime

from roller.jump.bots.factory import FACTORY
from roller.jump.dashboard.heartbeat import confirmed, unavailable
from roller.jump.dashboard.ledger import (
    I64_MAX,
    I64_MIN,
    PACIFIC,
    parse_utc,
    pacific_week_start,
)

# KXMLBGAME / Bot One live book. Observed on GET /portfolio/balance
# balance_breakdown (docs/incidents/kalshi-user-not-found.md).
MLB_EXCHANGE_INDEX = 3


def origin_bankroll_cents() -> int:
    return int(FACTORY["bankroll_cents"])


def dollars_to_truncated_cents(raw: Any) -> int | None:
    """Whole USD cents. Extra decimals are dropped, not rounded."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    sign = 1
    if text.startswith("-"):
        sign = -1
        text = text[1:]
    if "." in text:
        whole, frac = text.split(".", 1)
    else:
        whole, frac = text, ""
    if not whole.isdigit() or (frac and not frac.isdigit()):
        return None
    try:
        whole_n = int(whole)
    except ValueError:
        return None
    frac_cents = 0
    if len(frac) >= 1:
        frac_cents += int(frac[0]) * 10
    if len(frac) >= 2:
        frac_cents += int(frac[1])
    total = whole_n * 100 + frac_cents
    if total < 0:
        return None
    return sign * total


def breakdown_line_cents(line: dict[str, Any] | None) -> int | None:
    if not isinstance(line, dict):
        return None
    for key in ("balance", "balance_dollars"):
        raw = line.get(key)
        if isinstance(raw, int) and not isinstance(raw, bool):
            return raw
        cents = dollars_to_truncated_cents(raw)
        if cents is not None:
            return cents
    return None


def select_production_cents(body: dict[str, Any] | None) -> dict[str, Any]:
    """Bot One uses the MLB shard when Kalshi returns a breakdown. No demo mix-in."""
    if not isinstance(body, dict):
        return {"ok": False, "detail": "balance payload missing"}
    top = body.get("current_cents")
    if top is None:
        top = body.get("balance_cents")
    try:
        top_cents = int(top) if top is not None else None
    except (TypeError, ValueError):
        top_cents = None
    rows = body.get("balance_breakdown")
    if not isinstance(rows, list) or not rows:
        if top_cents is None:
            return {"ok": False, "detail": "balance_cents missing"}
        return {
            "ok": True,
            "current_cents": top_cents,
            "selected": "kalshi_get_balance",
            "exchange_index": None,
            "top_level_cents": top_cents,
        }
    chosen = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            index = int(row.get("exchange_index"))
        except (TypeError, ValueError):
            continue
        if index == MLB_EXCHANGE_INDEX:
            chosen = row
            break
    if chosen is None:
        return {"ok": False, "detail": "MLB exchange_index 3 unread", "top_level_cents": top_cents}
    cents = breakdown_line_cents(chosen)
    if cents is None:
        return {"ok": False, "detail": "MLB shard balance unreadable", "top_level_cents": top_cents}
    return {
        "ok": True,
        "current_cents": cents,
        "selected": "kalshi_balance_breakdown",
        "exchange_index": MLB_EXCHANGE_INDEX,
        "top_level_cents": top_cents,
        "raw_balance": chosen.get("balance") or chosen.get("balance_dollars"),
    }


def _int(raw: Any) -> int | None:
    if raw is None or raw == "" or isinstance(raw, bool):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def book_for(payload: dict[str, Any] | None, environment: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    books = payload.get("books")
    if not isinstance(books, dict):
        return None
    book = books.get(str(environment).upper())
    return book if isinstance(book, dict) else None


def current_cents(book: dict[str, Any] | None) -> int | None:
    if not book:
        return None
    return _int(book.get("current_cents"))


def origin_cents(
    payload: dict[str, Any] | None,
    book: dict[str, Any] | None = None,
    *,
    environment: str | None = None,
) -> int | None:
    env = str(environment or (book or {}).get("environment") or "").upper()
    if book:
        raw = _int(book.get("origin_cents"))
        if raw is not None:
            return raw
    if env == "DEMO":
        return None
    if isinstance(payload, dict):
        raw = _int(payload.get("origin_bankroll_cents"))
        if raw is not None:
            return raw
    return origin_bankroll_cents()


def account_origin_pnl(
    payload: dict[str, Any] | None,
    *,
    environment: str,
    missing: str = "UNAVAILABLE",
) -> dict[str, Any]:
    book = book_for(payload, environment)
    current = current_cents(book)
    origin = origin_cents(payload, book)
    if current is None or origin is None:
        return unavailable(missing)
    delta = current - origin
    if delta < I64_MIN or delta > I64_MAX:
        return unavailable(missing)
    return confirmed(delta)


def pack_book(
    body: dict[str, Any],
    *,
    existing_book: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    env = str(body.get("environment") or "").upper()
    if env == "PRODUCTION":
        selected = select_production_cents(body)
        if not selected.get("ok"):
            return None
        current = selected.get("current_cents")
        source = selected.get("selected") or body.get("source") or "kalshi_get_balance"
        extra = {
            "exchange_index": selected.get("exchange_index"),
            "top_level_cents": selected.get("top_level_cents"),
            "raw_balance": selected.get("raw_balance"),
        }
        origin = origin_bankroll_cents()
    else:
        current = body.get("current_cents") if body.get("current_cents") is not None else body.get("balance_cents")
        try:
            current = int(current) if current is not None else None
        except (TypeError, ValueError):
            current = None
        source = body.get("source") or "kalshi_get_balance"
        extra = {"top_level_cents": current}
        selected = select_production_cents(body)
        if selected.get("ok") and selected.get("exchange_index") == MLB_EXCHANGE_INDEX:
            extra["exchange_index"] = MLB_EXCHANGE_INDEX
            extra["mlb_shard_cents"] = selected.get("current_cents")
            extra["raw_balance"] = selected.get("raw_balance")
        prior = origin_cents(None, existing_book, environment="DEMO")
        origin = prior if prior is not None else current
    if current is None:
        return None
    packed = {
        "current_cents": current,
        "origin_cents": origin,
        "source": source,
        "balance_dollars": body.get("balance_dollars"),
        "portfolio_value_cents": body.get("portfolio_value_cents"),
        "balance_breakdown": body.get("balance_breakdown"),
        "environment": env or body.get("environment"),
        "status": body.get("status") or "CONFIRMED",
    }
    if env == "DEMO" and body.get("seeded_from_mcp") is True:
        packed["seeded_from_mcp"] = True
    packed.update({key: value for key, value in extra.items() if value is not None})
    return packed


def account_bankroll(
    payload: dict[str, Any] | None,
    *,
    environment: str,
    missing: str = "UNAVAILABLE",
) -> dict[str, Any]:
    current = current_cents(book_for(payload, environment))
    if current is None:
        return unavailable(missing)
    return confirmed(current)


def _pacific_day_start(now: datetime) -> datetime:
    local = now.astimezone(PACIFIC)
    return datetime(local.year, local.month, local.day, tzinfo=PACIFIC)


def prior_cents_before(history: list[dict[str, Any]], *, environment: str, start: datetime) -> int | None:
    latest_ts = None
    latest_cents = None
    wanted = str(environment).upper()
    for row in history:
        if str(row.get("environment") or "").upper() != wanted:
            continue
        ts = parse_utc(row.get("observed_at"))
        cents = _int(row.get("current_cents"))
        if ts is None or cents is None or ts >= start:
            continue
        if latest_ts is None or ts > latest_ts:
            latest_ts = ts
            latest_cents = cents
    return latest_cents


def window_pnl(
    history: list[dict[str, Any]],
    *,
    environment: str,
    current: int | None,
    start: datetime,
    missing: str = "UNAVAILABLE",
) -> dict[str, Any]:
    if current is None:
        return unavailable(missing)
    prior = prior_cents_before(history, environment=environment, start=start)
    if prior is None:
        return unavailable(missing)
    delta = current - prior
    if delta < I64_MIN or delta > I64_MAX:
        return unavailable(missing)
    return confirmed(delta)


def day_week_from_history(
    history: list[dict[str, Any]],
    *,
    environment: str,
    current: int | None,
    now: datetime,
    missing: str = "UNAVAILABLE",
) -> dict[str, Any]:
    return {
        "day_pnl": window_pnl(
            history,
            environment=environment,
            current=current,
            start=_pacific_day_start(now),
            missing=missing,
        ),
        "week_pnl": window_pnl(
            history,
            environment=environment,
            current=current,
            start=pacific_week_start(now),
            missing=missing,
        ),
    }


def open_mlb_positions(positions: list[dict[str, Any]] | None) -> int | None:
    if positions is None:
        return None
    n = 0
    for row in positions:
        if not isinstance(row, dict):
            return None
        ticker = str(row.get("ticker") or "")
        try:
            index = int(row["exchange_index"]) if row.get("exchange_index") is not None else None
        except (TypeError, ValueError):
            index = None
        mlb = ticker.startswith("KXMLBGAME") or index == MLB_EXCHANGE_INDEX
        if not mlb:
            continue
        if row.get("open") is True:
            n += 1
            continue
        hundredths = _int(row.get("position_hundredths"))
        if hundredths is not None and hundredths != 0:
            n += 1
    return n
