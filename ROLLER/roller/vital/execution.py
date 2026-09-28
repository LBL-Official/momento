"""Vital execution facts. Order ≠ fill ≠ trade ≠ realized result."""

from __future__ import annotations

import hashlib
from typing import Any

from roller.vital.honesty import confirmed, observation_unavailable, unavailable
from roller.vital.versions import BOT_ID

SOURCE_HOST = "HOST_LEDGER"
SOURCE_CATALOG = "JUMP_CATALOG"
SOURCE_KALSHI = "KALSHI_ACCOUNT"

TRADE_OPEN = "OPEN"
TRADE_PARTIAL = "PARTIAL"
TRADE_CLOSED = "CLOSED"
TRADE_STATUSES = (TRADE_OPEN, TRADE_PARTIAL, TRADE_CLOSED)

FILL_FACT_KEYS = (
    "bot_id",
    "event_ticker",
    "market",
    "side",
    "timestamp",
    "price_cents",
    "contracts",
    "amount_cents",
    "fee_cents",
    "fee_kind",
    "position_id",
    "venue_fill_id",
    "order_id",
    "source",
    "sources",
    "observation_status",
)

TRADE_FACT_KEYS = (
    "bot_id",
    "position_id",
    "event_ticker",
    "market",
    "game",
    "status",
    "entry_date",
    "entry_amount",
    "entry_price",
    "entry_price_cents",
    "entry_contracts",
    "exit_date",
    "exit_amount",
    "exit_price",
    "exit_price_cents",
    "exit_contracts",
    "amount_traded_cents",
    "amount_exited_cents",
    "bankroll_at_entry_cents",
    "pct_bankroll_allocated_bp",
    "pct_bankroll_returned_bp",
    "pct_allocated_pnl_bp",
    "gross_realized_cents",
    "fee_cents",
    "net_realized_cents",
    "source",
    "observation_status",
    "lifecycle",
)


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fill_identity(
    *,
    venue_id: str | None = None,
    source: str,
    fallback: str | None = None,
) -> str:
    venue = str(venue_id or "").strip()
    if venue:
        return _digest(f"venue|{venue}")[:32]
    return _digest(f"{source}|{fallback or ''}")[:32]


def trade_identity(bot_id: str, position_id: str) -> str:
    digest = _digest(f"{bot_id}|position|{position_id}")[:12]
    return f"{bot_id}-{digest}"


def fact(value: Any, *, missing: str = "OBSERVATION_UNAVAILABLE") -> dict[str, Any]:
    if value is None or value == "":
        if missing == "UNAVAILABLE":
            return unavailable("UNAVAILABLE")
        return observation_unavailable(missing) if missing != "OBSERVATION_UNAVAILABLE" else observation_unavailable()
    return confirmed(value)


def is_confirmed(row: Any) -> bool:
    return isinstance(row, dict) and row.get("status") == "CONFIRMED" and row.get("value") is not None


def fact_value(row: Any) -> Any:
    if is_confirmed(row):
        return row.get("value")
    return None


def facts_equal(left: dict[str, Any], right: dict[str, Any], keys: tuple[str, ...]) -> bool:
    for key in keys:
        if left.get(key) != right.get(key):
            return False
    return True


def catalog_source(raw: Any) -> str:
    token = str(raw or "").strip().lower()
    if token == "kalshi":
        return SOURCE_KALSHI
    return SOURCE_CATALOG


def unwrap_id(raw: Any) -> str | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, dict):
        if "0" in raw:
            return str(raw["0"])
        if "id" in raw:
            return unwrap_id(raw.get("id"))
        return None
    text = str(raw).strip()
    return text or None


def vwap_cents(amount_cents: int | None, contracts: int | None) -> int | None:
    if amount_cents is None or contracts is None or contracts <= 0:
        return None
    if amount_cents % contracts != 0:
        return None
    return amount_cents // contracts


def default_bot_id() -> str:
    return BOT_ID
