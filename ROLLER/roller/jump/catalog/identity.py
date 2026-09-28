"""Stable trade identity. Integer facts only. Never guess a bot."""

from __future__ import annotations

import hashlib
from typing import Any

from roller.jump.catalog.versions import UNATTRIBUTED


def jump_trade_id(
    environment: str,
    *,
    trade_id: str | None = None,
    fill_id: str | None = None,
    ledger_key: str | None = None,
) -> str:
    env = (environment or "").strip().upper()
    venue = str(trade_id or "").strip() or str(fill_id or "").strip()
    if venue:
        raw = f"{env}|kalshi|{venue}"
    else:
        raw = f"{env}|ledger|{ledger_key or ''}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return digest[:32]


def ledger_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("bot_id") or UNATTRIBUTED),
            str(row.get("exchange_ts") or ""),
            str(row.get("market") or row.get("ticker") or ""),
            str(row.get("qty") if row.get("qty") is not None else ""),
            str(row.get("price_cents") if row.get("price_cents") is not None else ""),
            str(row.get("premium_cents") if row.get("premium_cents") is not None else ""),
            str(row.get("fill_id") or ""),
            str(row.get("seq") if row.get("seq") is not None else ""),
        ]
    )
