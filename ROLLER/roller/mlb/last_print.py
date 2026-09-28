"""Last-print one-minute bars.

A minute with prints → last chronological print as last_close_e4.
A minute with no print → row absent.
Never forward-fill. Never write yes_bid from a print.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from roller.timeutil import parse_utc

LAST_TRADE_COLUMNS = [
    "internal_game_id",
    "ticker",
    "team_side",
    "candle_timestamp",
    "event_timestamp",
    "available_at",
    "ingested_at",
    "last_open_e4",
    "last_high_e4",
    "last_low_e4",
    "last_close_e4",
    "volume",
    "print_count",
    "is_valid",
    "spread_e4",
    "uncrossed",
    "spread_ok",
    "volume_positive",
    "tradable_cross",
    "market_data_type",
    "source_dataset",
    "source_file_hash",
    "pipeline_version",
    "derived_at",
]

CANDLE_COLUMNS = [
    "internal_game_id",
    "ticker",
    "team_side",
    "candle_timestamp",
    "event_timestamp",
    "available_at",
    "ingested_at",
    "yes_bid_open",
    "yes_bid_high",
    "yes_bid_low",
    "yes_bid_close",
    "yes_ask_open",
    "yes_ask_high",
    "yes_ask_low",
    "yes_ask_close",
    "volume",
    "market_data_type",
    "source_dataset",
    "source_file_hash",
    "pipeline_version",
    "derived_at",
]


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def cents_to_e4(cents: Any) -> int | None:
    n = _int(cents)
    if n is None:
        return None
    return n * 100


def dollars_to_cents(raw: Any) -> int | None:
    """Exact integer cents only. Digits past two decimals are not rounded."""
    if raw in (None, ""):
        return None
    text = str(raw).strip()
    if not text or text[0] in "+-":
        return None
    if "." in text:
        whole_s, frac_s = text.split(".", 1)
    else:
        whole_s, frac_s = text, ""
    if not whole_s.isdigit() or (frac_s and not frac_s.isdigit()):
        return None
    if len(frac_s) > 2 and any(ch != "0" for ch in frac_s[2:]):
        return None
    frac_s = (frac_s + "00")[:2]
    return int(whole_s) * 100 + int(frac_s or "0")


def dollars_to_e4(raw: Any) -> int | None:
    cents = dollars_to_cents(raw)
    if cents is None:
        return None
    return cents * 100


def trade_yes_cents(rec: dict[str, Any]) -> int | None:
    if rec.get("yes_price_cents") not in (None, ""):
        return _int(rec.get("yes_price_cents"))
    if rec.get("yes_price") not in (None, ""):
        return _int(rec.get("yes_price"))
    return dollars_to_cents(rec.get("yes_price_dollars"))


def floor_minute(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


def iso_z(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def aggregate_last_prints(
    trades: list[dict[str, Any]],
    *,
    ingested_at: str,
    pipeline_version: str,
    source_dataset: str = "kalshi_public_trades",
    ticker_meta: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Group prints by ticker + UTC minute. Last chronological print wins.

    Minutes without a print are omitted. yes_bid is never written.
    """
    buckets: dict[tuple[str, datetime], list[tuple[datetime, dict[str, Any]]]] = defaultdict(list)
    for rec in trades:
        ts = parse_utc(rec.get("exchange_timestamp") or rec.get("created_time") or rec.get("timestamp"))
        if ts is None:
            continue
        ticker = str(rec.get("ticker") or "")
        if not ticker:
            continue
        cents = trade_yes_cents(rec)
        px = cents_to_e4(cents)
        if px is None:
            continue
        rec = {**rec, "_px_e4": px}
        buckets[(ticker, floor_minute(ts))].append((ts, rec))

    rows: list[dict[str, str]] = []
    meta = ticker_meta or {}
    for (ticker, minute), items in sorted(buckets.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        items.sort(key=lambda item: item[0])
        first_px = int(items[0][1]["_px_e4"])
        last_px = int(items[-1][1]["_px_e4"])
        highs = [int(x[1]["_px_e4"]) for x in items]
        info = meta.get(ticker) or {}
        ts_iso = iso_z(minute)
        rows.append(
            {
                "internal_game_id": str(info.get("internal_game_id") or items[-1][1].get("internal_game_id") or ""),
                "ticker": ticker,
                "team_side": str(info.get("team_side") or items[-1][1].get("team_side") or ""),
                "candle_timestamp": ts_iso,
                "event_timestamp": ts_iso,
                "available_at": ts_iso,
                "ingested_at": ingested_at,
                "last_open_e4": str(first_px),
                "last_high_e4": str(max(highs)),
                "last_low_e4": str(min(highs)),
                "last_close_e4": str(last_px),
                "volume": str(sum(_int(x[1].get("quantity_hundredths")) or 0 for x in items)),
                "print_count": str(len(items)),
                "is_valid": "1",
                "spread_e4": "",
                "uncrossed": "0",
                "spread_ok": "0",
                "volume_positive": "1" if any(_int(x[1].get("quantity_hundredths")) for x in items) else "0",
                "tradable_cross": "0",
                "market_data_type": "LAST_TRADE_PRINT",
                "source_dataset": source_dataset,
                "source_file_hash": "",
                "pipeline_version": pipeline_version,
                "derived_at": ingested_at,
            }
        )
    return rows


def last_print_has_yes_bid(row: dict[str, Any]) -> bool:
    return row.get("yes_bid_close") not in (None, "") or row.get("yes_bid") not in (None, "")


def aggregate_last_prints_frame(
    frame: Any,
    *,
    ingested_at: str,
    pipeline_version: str,
    source_dataset: str = "kalshi_public_trades",
    ticker_meta: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Same contract as aggregate_last_prints, vectorized for warehouse ingest."""
    import pandas as pd

    if frame is None or getattr(frame, "empty", True):
        return []
    ts_col = None
    for name in ("exchange_timestamp", "created_time", "timestamp"):
        if name in frame.columns:
            ts_col = name
            break
    if ts_col is None or "ticker" not in frame.columns:
        return []
    px_col = "yes_price_cents" if "yes_price_cents" in frame.columns else "yes_price"
    if px_col not in frame.columns:
        return []
    work = frame[["ticker", ts_col, px_col]].copy()
    if "quantity_hundredths" in frame.columns:
        work["quantity_hundredths"] = frame["quantity_hundredths"]
    else:
        work["quantity_hundredths"] = 0
    work["_ts"] = pd.to_datetime(work[ts_col], utc=True, errors="coerce")
    work["_px"] = pd.to_numeric(work[px_col], errors="coerce") * 100
    work = work.dropna(subset=["_ts", "ticker", "_px"])
    if work.empty:
        return []
    work["_minute"] = work["_ts"].dt.floor("min")
    work = work.sort_values(["ticker", "_ts"])
    grouped = work.groupby(["ticker", "_minute"], sort=True)
    first = grouped["_px"].first()
    last = grouped["_px"].last()
    high = grouped["_px"].max()
    low = grouped["_px"].min()
    count = grouped["_px"].size()
    qty = grouped["quantity_hundredths"].sum()
    meta = ticker_meta or {}
    rows: list[dict[str, str]] = []
    for (ticker, minute), close_px in last.items():
        info = meta.get(str(ticker)) or {}
        ts_iso = iso_z(minute.to_pydatetime() if hasattr(minute, "to_pydatetime") else minute)
        q = qty.loc[(ticker, minute)]
        n = int(count.loc[(ticker, minute)])
        rows.append(
            {
                "internal_game_id": str(info.get("internal_game_id") or ""),
                "ticker": str(ticker),
                "team_side": str(info.get("team_side") or ""),
                "candle_timestamp": ts_iso,
                "event_timestamp": ts_iso,
                "available_at": ts_iso,
                "ingested_at": ingested_at,
                "last_open_e4": str(int(first.loc[(ticker, minute)])),
                "last_high_e4": str(int(high.loc[(ticker, minute)])),
                "last_low_e4": str(int(low.loc[(ticker, minute)])),
                "last_close_e4": str(int(close_px)),
                "volume": str(int(q) if pd.notna(q) else 0),
                "print_count": str(n),
                "is_valid": "1",
                "spread_e4": "",
                "uncrossed": "0",
                "spread_ok": "0",
                "volume_positive": "1" if pd.notna(q) and int(q) > 0 else "0",
                "tradable_cross": "0",
                "market_data_type": "LAST_TRADE_PRINT",
                "source_dataset": source_dataset,
                "source_file_hash": "",
                "pipeline_version": pipeline_version,
                "derived_at": ingested_at,
            }
        )
    return rows
