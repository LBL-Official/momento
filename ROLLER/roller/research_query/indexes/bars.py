"""Compact tradable-bar series. Path / extrema / later-bar lookup."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from roller.research_query.entry_engine import TradableBar
from roller.research_query.facts import TradableIndex
from roller.research_query.models import BASIS_TRADABLE
from roller.timeutil import parse_utc

BARS_NAME = "bars.parquet"


def _optional_int(value: Any) -> int | None:
    """Missing parquet volume/ask is None, not 0. NaN is missing."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def rows_from_index(index: TradableIndex) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticker, bars in index.bars.items():
        skipped = int(index.skipped.get(ticker, 0))
        for i, bar in enumerate(bars):
            rows.append(
                {
                    "ticker": ticker,
                    "game_id": bar.game_id,
                    "seq": i,
                    "ts": bar.ts.isoformat().replace("+00:00", "Z"),
                    "bid_e4": int(bar.bid),
                    "ask_e4": int(bar.ask) if bar.ask is not None else None,
                    "volume": bar.volume,
                    "skipped_untradable": skipped,
                    "basis": index.basis,
                    "team_side": (bar.raw or {}).get("team_side"),
                }
            )
    return rows


def write_bars(path: Path, index: TradableIndex) -> int:
    rows = rows_from_index(index)
    pd.DataFrame(rows).to_parquet(path, index=False)
    return len(rows)


def read_bars(path: Path) -> TradableIndex:
    df = pd.read_parquet(path)
    bars: dict[str, list[TradableBar]] = {}
    skipped: dict[str, int] = {}
    if df.empty:
        return TradableIndex()
    df = df.sort_values(["ticker", "seq"])
    basis = BASIS_TRADABLE
    if "basis" in df.columns and len(df):
        basis = str(df.iloc[0]["basis"] or BASIS_TRADABLE)
    for rec in df.to_dict("records"):
        ticker = str(rec["ticker"])
        ts = parse_utc(str(rec["ts"]))
        if ts is None:
            ts = datetime.fromisoformat(str(rec["ts"]).replace("Z", "+00:00"))
        ask_raw = rec.get("ask_e4")
        team_side = rec.get("team_side")
        if team_side is not None and str(team_side) == "":
            team_side = None
        raw = {"ticker": ticker, "internal_game_id": str(rec.get("game_id") or "")}
        if team_side is not None:
            raw["team_side"] = team_side
        bars.setdefault(ticker, []).append(
            TradableBar(
                ts=ts,
                bid=int(rec["bid_e4"]),
                ask=_optional_int(ask_raw) if ask_raw != "" else None,
                volume=_optional_int(rec.get("volume")),
                ticker=ticker,
                game_id=str(rec.get("game_id") or ""),
                raw=raw,
                basis=basis,
            )
        )
        skipped[ticker] = int(rec.get("skipped_untradable") or 0)
    return TradableIndex(bars=bars, skipped=skipped, basis=basis)
