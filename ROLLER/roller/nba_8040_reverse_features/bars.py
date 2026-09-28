"""Read-only pre/post 1m TRADABLE_YES_BID bars. Not a Confirm & Run source."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from roller.config import RollerConfig
from roller.nba_8040_reverse_features.errors import ReverseFeaturesError
from roller.warehouse.layout import observations_dir
from roller.warehouse.partitioning import list_month_parquets

OBS_COLS = ("ticker", "available_at", "yes_bid_close", "yes_bid_high", "yes_bid_low")


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _e4_cents(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(str(value).strip()) / 100.0
    except (TypeError, ValueError):
        return None


def load_ticker_bars(
    tickers: set[str],
    *,
    sport: str = "NBA",
    season: str = "2025-2026",
) -> dict[str, list[tuple[datetime, float, float, float]]]:
    if not tickers:
        raise ReverseFeaturesError("DATA_REQUIRED", "no tickers for warehouse bar load")
    cfg = RollerConfig()
    directory = observations_dir(cfg, sport=sport, season=season)
    files = list_month_parquets(directory)
    if not files:
        raise ReverseFeaturesError("DATA_REQUIRED", f"no observation parquet under {directory}")
    wanted = set(tickers)
    grouped: dict[str, list[tuple[datetime, float, float, float]]] = defaultdict(list)
    for path in files:
        frame = pd.read_parquet(path, columns=list(OBS_COLS))
        frame = frame[frame["ticker"].isin(wanted)]
        for rec in frame.itertuples(index=False):
            stamp = _parse_utc(rec.available_at)
            close = _e4_cents(rec.yes_bid_close)
            if stamp is None or close is None:
                continue
            high = _e4_cents(rec.yes_bid_high)
            low = _e4_cents(rec.yes_bid_low)
            grouped[str(rec.ticker)].append((stamp, close, high if high is not None else close, low if low is not None else close))
    for ticker, rows in grouped.items():
        rows.sort(key=lambda item: item[0])
        grouped[ticker] = rows
    return grouped


def split_pre_post(
    series: list[tuple[datetime, float, float, float]],
    entry: datetime,
) -> tuple[list[tuple[datetime, float]], list[tuple[datetime, float]]]:
    pre: list[tuple[datetime, float]] = []
    post: list[tuple[datetime, float]] = []
    for stamp, close, _high, _low in series:
        if stamp < entry:
            pre.append((stamp, close))
        elif stamp > entry:
            post.append((stamp, close))
    return pre, post
