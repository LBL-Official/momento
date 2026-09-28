"""Ticker-grouped trades from Kalshi fills that already have a market.

JUMP_CATALOG rows without a ticker are not grouped. Host Position still wins.
Does not invent CLOSED from unknown fee_kind.
"""

from __future__ import annotations

from typing import Any

from roller.vital.execution import (
    SOURCE_HOST,
    SOURCE_KALSHI,
    TRADE_CLOSED,
    TRADE_OPEN,
    TRADE_PARTIAL,
    fact,
    fact_value,
    is_confirmed,
    trade_identity,
    vwap_cents,
)
from roller.vital.honesty import unavailable
from roller.vital.mlb_001.trade_row import apply_standard_row


def _int(raw: Any) -> int | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _fill_key(fill: dict[str, Any]) -> str | None:
    venue = str(fill.get("venue_fill_id") or "").strip()
    if venue:
        return f"venue|{venue}"
    fid = str(fill.get("fill_id") or "").strip()
    return f"id|{fid}" if fid else None


def apply_settlement(trade: dict[str, Any], settlement: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(settlement, dict) or settlement.get("status") != "CONFIRMED":
        return trade
    result = settlement.get("result")
    if result not in {"yes", "no"}:
        return trade
    qty = _int(fact_value(trade.get("entry_contracts")))
    value = _int(settlement.get("settlement_value_cents"))
    if value is None:
        value = 100 if result == "yes" else 0
    if qty is None:
        return trade
    paid = qty * value
    traded = _int(fact_value(trade.get("entry_amount")))
    trade["status"] = TRADE_CLOSED
    trade["exit_price"] = fact(value)
    trade["exit_amount"] = fact(paid)
    trade["exit_contracts"] = fact(qty)
    trade["exit_date"] = fact(settlement.get("settlement_ts"), missing="UNAVAILABLE")
    trade["settlement_result"] = fact(result)
    if traded is not None:
        trade["gross_realized_cents"] = fact(paid - traded)
    return trade


def reconstruct_ticker_trades(
    bot_id: str,
    fills: list[dict[str, Any]],
    *,
    snapshot: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
    settlements: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, dict[str, Any]]] = {}
    for fill in fills:
        if not isinstance(fill, dict):
            continue
        if fill.get("source") == SOURCE_HOST:
            continue
        if not is_confirmed(fill.get("market")):
            continue
        ticker = str(fact_value(fill.get("market")) or "").strip()
        if not ticker.startswith("KXMLBGAME"):
            continue
        key = _fill_key(fill)
        if key is None:
            continue
        groups.setdefault(ticker, {})[key] = fill

    out: list[dict[str, Any]] = []
    books = settlements if isinstance(settlements, dict) else {}
    for ticker, unique in groups.items():
        rows = sorted(unique.values(), key=lambda row: str(fact_value(row.get("timestamp")) or ""))
        entries: list[dict[str, Any]] = []
        exits: list[dict[str, Any]] = []
        unknown: list[dict[str, Any]] = []
        for row in rows:
            qty = _int(fact_value(row.get("contracts")))
            price = _int(fact_value(row.get("price_cents")))
            premium = _int(fact_value(row.get("amount_cents")))
            if premium is None and qty is not None and price is not None:
                premium = qty * price
            item = {
                "premium": premium,
                "qty": qty,
                "price": price,
                "ts": fact_value(row.get("timestamp")),
            }
            kind = fact_value(row.get("fee_kind"))
            if kind == "Liquidation":
                exits.append(item)
            elif kind == "Entry":
                entries.append(item)
            else:
                unknown.append(item)
        if not entries and unknown:
            entries = unknown
        elif unknown:
            # Mixed known fee_kind plus unknown: keep unknown as entries, do not guess exits.
            entries.extend(unknown)

        def _sum(key: str, items: list[dict[str, Any]]) -> int | None:
            values = [item[key] for item in items]
            if not items or any(item is None for item in values):
                return None
            return int(sum(int(item) for item in values))

        entry_amount = _sum("premium", entries) if entries else None
        entry_qty = _sum("qty", entries) if entries else None
        if not entries or (entry_amount is None and entry_qty is None):
            continue
        exit_amount = _sum("premium", exits) if exits else None
        exit_qty = _sum("qty", exits) if exits else None
        status = TRADE_PARTIAL if exits else TRADE_OPEN
        entry_date = entries[0]["ts"] if entries else None
        trade = {
            "trade_id": trade_identity(bot_id, f"ticker|{ticker}"),
            "bot_id": bot_id,
            "position_id": f"ticker|{ticker}",
            "event_ticker": fact(ticker),
            "market": fact(ticker),
            "status": status,
            "entry_date": fact(entry_date),
            "entry_amount": fact(entry_amount),
            "entry_price": fact(vwap_cents(entry_amount, entry_qty)),
            "entry_contracts": fact(entry_qty),
            "exit_date": fact(exits[-1]["ts"] if exits else None, missing="UNAVAILABLE"),
            "exit_amount": fact(exit_amount, missing="UNAVAILABLE") if exits else unavailable("UNAVAILABLE"),
            "exit_price": fact(vwap_cents(exit_amount, exit_qty), missing="UNAVAILABLE") if exits else unavailable("UNAVAILABLE"),
            "exit_contracts": fact(exit_qty, missing="UNAVAILABLE") if exits else unavailable("UNAVAILABLE"),
            "gross_realized_cents": unavailable("UNAVAILABLE"),
            "fee_cents": unavailable("UNAVAILABLE"),
            "net_realized_cents": unavailable("UNAVAILABLE"),
            "source": SOURCE_KALSHI,
            "observation_status": "CONFIRMED",
            "lifecycle": None,
            "grouping": "kalshi_ticker",
            "rev": 0,
        }
        trade = apply_settlement(trade, books.get(ticker))
        out.append(apply_standard_row(trade, snapshot=snapshot, history=history))
    return out
