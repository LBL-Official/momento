"""WNBA fill reconciliation. Conflicts are not resolved by dropping a row."""

from __future__ import annotations

import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any


def _status_value(field: object) -> tuple[str, Any]:
    if isinstance(field, dict) and "status" in field:
        return str(field.get("status") or ""), field.get("value")
    if field is None:
        return "UNAVAILABLE", None
    return "CONFIRMED", field


def reconcile_fill_id(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = (
        "contracts",
        "price_cents",
        "amount_cents",
        "market",
        "timestamp",
        "order_id",
        "fee_cents",
        "fee_kind",
        "side",
    )
    out: dict[str, Any] = {"duplicate_rows": len(rows), "conflict": False}
    for name in fields:
        confirmed: list[Any] = []
        for row in rows:
            status, value = _status_value(row.get(name))
            if status == "CONFIRMED" and value is not None:
                confirmed.append(value)
        distinct = {json.dumps(value, sort_keys=True, default=str) for value in confirmed}
        if len(distinct) > 1:
            out["conflict"] = True
            out[name] = {"status": "RECONCILIATION_CONFLICT", "values": sorted(distinct)}
        elif len(distinct) == 1:
            out[name] = {"status": "CONFIRMED", "value": confirmed[0]}
        else:
            out[name] = {"status": "UNAVAILABLE", "value": None}
    return out


def _confirmed(rec: dict[str, Any], name: str) -> Any:
    field = rec.get(name) or {}
    if field.get("status") == "CONFIRMED":
        return field.get("value")
    return None


def aggregate_positions(fills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One position per order. Conflicting fills stay unresolved."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fill in fills:
        if fill.get("conflict"):
            key = f"CONFLICT:{fill.get('fill_id')}"
        else:
            order = _confirmed(fill, "order_id")
            market = _confirmed(fill, "market")
            key = f"ORDER:{order}" if order else f"MARKET:{market or fill.get('fill_id')}"
        groups[key].append(fill)

    positions: list[dict[str, Any]] = []
    for key, members in groups.items():
        if any(member.get("conflict") for member in members):
            positions.append(
                {
                    "position_key": key,
                    "status": "RECONCILIATION_CONFLICT",
                    "realized_pnl": "NOT_SUPPORTED",
                    "fee_cents": "UNAVAILABLE",
                    "fills": len(members),
                }
            )
            continue
        qtys = []
        costs = []
        prices = []
        markets = []
        timestamps = []
        qty_ok = True
        cost_ok = True
        for member in members:
            qty = _confirmed(member, "contracts")
            amount = _confirmed(member, "amount_cents")
            price = _confirmed(member, "price_cents")
            market = _confirmed(member, "market")
            ts = _confirmed(member, "timestamp")
            if market:
                markets.append(str(market))
            if ts:
                timestamps.append(str(ts))
            if qty is None:
                qty_ok = False
            else:
                qtys.append(int(qty))
            if amount is not None:
                costs.append(int(amount))
            elif qty is not None and price is not None:
                costs.append(int(qty) * int(price))
            else:
                cost_ok = False
            if price is not None:
                prices.append(int(price))
        market_set = sorted(set(markets))
        price_set = sorted(set(prices))
        positions.append(
            {
                "position_key": key,
                "status": "CONFIRMED_ACQUISITION" if qty_ok and cost_ok else "INCOMPLETE_QUANTITY",
                "market": market_set[0] if len(market_set) == 1 else market_set,
                "contracts": sum(qtys) if qty_ok else "UNAVAILABLE",
                "acquisition_cost_cents": sum(costs) if cost_ok else "UNAVAILABLE",
                "price_cents": price_set[0] if len(price_set) == 1 else price_set,
                "price_band": _price_band(price_set),
                "fill_timestamps": timestamps,
                "fills": len(members),
                "fee_cents": "UNAVAILABLE",
                "realized_pnl": "NOT_SUPPORTED",
                "valuation": "HYPOTHETICAL_UNLESS_EXIT_AND_SETTLEMENT",
                "exit_linkage": "UNAVAILABLE",
                "note": "gross acquisition only; ledger fees unavailable",
            }
        )
    return positions


def _price_band(prices: list[int]) -> str:
    if not prices:
        return "UNAVAILABLE"
    if prices == [80]:
        return "EXACT_80"
    if all(price == 81 for price in prices):
        return "EXACT_81"
    if all(78 <= price <= 82 for price in prices):
        return "AROUND_80_78_82"
    return "OUTSIDE_LABELED_BANDS"


def load_wnba_fills(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            market_status, market = _status_value(row.get("market"))
            event_status, event = _status_value(row.get("event_ticker"))
            text = ""
            if market_status == "CONFIRMED" and market:
                text = str(market)
            elif event_status == "CONFIRMED" and event:
                text = str(event)
            if "KXWNBAGAME" not in text:
                continue
            fill_status, fill_id = _status_value(row.get("fill_id"))
            key = str(fill_id) if fill_status == "CONFIRMED" and fill_id else f"ROW:{len(grouped)}"
            grouped[key].append(row)
    fills = []
    for fill_id, rows in grouped.items():
        rec = reconcile_fill_id(rows)
        rec["fill_id"] = fill_id
        fills.append(rec)
    return fills


def hypothetical_mark_value(contracts: int, price_e4: int) -> Fraction:
    return Fraction(int(contracts) * int(price_e4), 10000)
