"""Match Kalshi fills to host ledger fills. Never guess a bot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.jump.bots.versions import BOT_ONE_ID
from roller.jump.catalog.identity import jump_trade_id, ledger_key
from roller.jump.catalog.versions import MATCH_TS_TOLERANCE_SECONDS, UNATTRIBUTED
from roller.jump.dashboard.ledger import parse_utc


def _looks_like_ticker(raw: str | None) -> bool:
    text = str(raw or "").strip()
    if len(text) < 4:
        return False
    return any(ch.isalpha() for ch in text)


def _ts(row: dict[str, Any]) -> datetime | None:
    return parse_utc(row.get("exchange_ts"))


def _same_market(kalshi: dict[str, Any], ledger: dict[str, Any]) -> bool:
    kt = str(kalshi.get("ticker") or "").strip()
    lm = str(ledger.get("market") or ledger.get("ticker") or "").strip()
    if _looks_like_ticker(kt) and _looks_like_ticker(lm):
        return kt.casefold() == lm.casefold()
    return True


def _same_qty(kalshi: dict[str, Any], ledger: dict[str, Any]) -> bool:
    kq = kalshi.get("qty")
    lq = ledger.get("qty")
    if kq is None or lq is None:
        return True
    try:
        return int(kq) == int(lq)
    except (TypeError, ValueError):
        return False


def _same_price(kalshi: dict[str, Any], ledger: dict[str, Any]) -> bool:
    kp = kalshi.get("yes_price_cents")
    lp = ledger.get("price_cents")
    if kp is None or lp is None:
        return True
    try:
        return int(kp) == int(lp)
    except (TypeError, ValueError):
        return False


def _within_tolerance(kalshi: dict[str, Any], ledger: dict[str, Any]) -> bool:
    left = _ts(kalshi)
    right = _ts(ledger)
    if left is None or right is None:
        return False
    return abs((left - right).total_seconds()) <= MATCH_TS_TOLERANCE_SECONDS


def _matches(kalshi: dict[str, Any], ledger: dict[str, Any]) -> bool:
    return _within_tolerance(kalshi, ledger) and _same_market(kalshi, ledger) and _same_qty(kalshi, ledger) and _same_price(kalshi, ledger)


def _result(ledger: dict[str, Any] | None) -> Any:
    if not ledger:
        return "UNAVAILABLE"
    raw = ledger.get("realized_cents")
    if raw is None:
        return "UNAVAILABLE"
    try:
        return int(raw)
    except (TypeError, ValueError):
        return "UNAVAILABLE"


def _fmt(ts: datetime | None, fallback: str | None = None) -> str | None:
    if ts is None:
        return fallback
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ledger_record(row: dict[str, Any], *, environment: str, bot_id: str) -> dict[str, Any]:
    packed = dict(row)
    packed["bot_id"] = bot_id
    tid = jump_trade_id(
        environment,
        trade_id=None,
        fill_id=row.get("fill_id"),
        ledger_key=ledger_key(packed),
    )
    return {
        "jump_trade_id": tid,
        "bot_id": bot_id,
        "environment": environment,
        "kalshi_trade_id": None,
        "kalshi_fill_id": row.get("fill_id"),
        "order_id": None,
        "ticker": row.get("market") or row.get("ticker"),
        "yes_price_cents": row.get("price_cents"),
        "qty": row.get("qty"),
        "premium_cents": row.get("premium_cents"),
        "exchange_ts": row.get("exchange_ts"),
        "result": _result(row),
        "fee_kind": row.get("fee_kind"),
        "side": row.get("side"),
        "source": "ledger",
    }


def kalshi_record(
    fill: dict[str, Any],
    *,
    environment: str,
    ledger: dict[str, Any] | None,
    bot_id: str,
    source: str,
) -> dict[str, Any]:
    tid = jump_trade_id(
        environment,
        trade_id=fill.get("trade_id"),
        fill_id=fill.get("fill_id"),
        ledger_key=None,
    )
    return {
        "jump_trade_id": tid,
        "bot_id": bot_id,
        "environment": environment,
        "kalshi_trade_id": fill.get("trade_id"),
        "kalshi_fill_id": fill.get("fill_id"),
        "order_id": fill.get("order_id"),
        "ticker": fill.get("ticker") or (ledger or {}).get("market"),
        "yes_price_cents": fill.get("yes_price_cents") if fill.get("yes_price_cents") is not None else (ledger or {}).get("price_cents"),
        "qty": fill.get("qty") if fill.get("qty") is not None else (ledger or {}).get("qty"),
        "premium_cents": (ledger or {}).get("premium_cents"),
        "exchange_ts": fill.get("exchange_ts") or (ledger or {}).get("exchange_ts"),
        "result": _result(ledger),
        "fee_kind": (ledger or {}).get("fee_kind"),
        "side": fill.get("side") or (ledger or {}).get("side"),
        "source": source,
    }


def reconcile_book(
    fills: list[dict[str, Any]],
    ledgers: list[dict[str, Any]],
    *,
    environment: str,
    default_bot_id: str | None,
) -> list[dict[str, Any]]:
    """One Kalshi fill → at most one ledger fill. Ambiguous → UNATTRIBUTED."""
    unused = list(ledgers)
    out: list[dict[str, Any]] = []
    for fill in fills:
        hits = [row for row in unused if _matches(fill, row)]
        if len(hits) != 1:
            out.append(
                kalshi_record(
                    fill,
                    environment=environment,
                    ledger=None,
                    bot_id=UNATTRIBUTED,
                    source="kalshi",
                )
            )
            continue
        hit = hits[0]
        unused.remove(hit)
        bot_id = str(hit.get("bot_id") or default_bot_id or UNATTRIBUTED)
        if environment == "PRODUCTION":
            bot_id = BOT_ONE_ID
        out.append(
            kalshi_record(
                fill,
                environment=environment,
                ledger=hit,
                bot_id=bot_id,
                source="reconciled",
            )
        )
    for row in unused:
        bot_id = str(row.get("bot_id") or default_bot_id or UNATTRIBUTED)
        if environment == "PRODUCTION":
            bot_id = BOT_ONE_ID
        out.append(ledger_record(row, environment=environment, bot_id=bot_id))
    return out
