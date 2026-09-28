"""Kalshi result only. Missing stays missing. Never box-score fill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

SETTLEMENT_NAME = "settlement.parquet"


def write_settlement(path: Path, markets_by_ticker: dict[str, dict[str, Any]]) -> int:
    rows: list[dict[str, Any]] = []
    for ticker, rec in markets_by_ticker.items():
        result = rec.get("result") or rec.get("kalshi_result")
        if result in (None, ""):
            continue
        rows.append({"ticker": ticker, "result": str(result).lower()})
    pd.DataFrame(rows).to_parquet(path, index=False)
    return len(rows)


def read_settlement(path: Path) -> dict[str, dict[str, Any]]:
    df = pd.read_parquet(path)
    out: dict[str, dict[str, Any]] = {}
    if df.empty:
        return out
    for rec in df.to_dict("records"):
        ticker = str(rec.get("ticker") or "")
        if not ticker:
            continue
        out[ticker] = {"result": rec.get("result")}
    return out
