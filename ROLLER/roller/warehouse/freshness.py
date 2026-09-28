"""Source-aware freshness. Historical-only is not automatically STALE."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FreshnessClass = Literal[
    "LIVE_EXPECTED",
    "DAILY_EXPECTED",
    "HISTORICAL_ONLY",
    "SOURCE_UNAVAILABLE",
]

FreshnessStatus = Literal[
    "CURRENT",
    "STALE",
    "HISTORICAL_ONLY",
    "SOURCE_UNAVAILABLE",
    "NOT_APPLICABLE",
]


@dataclass(frozen=True)
class Freshness:
    classification: FreshnessClass
    status: FreshnessStatus
    source_latest_timestamp: str | None
    warehouse_latest_timestamp: str | None
    last_successful_ingest: str | None
    expected_next_update: str | None
    ingestion_lag: str | None
    note: str = ""


def classify_dataset(dataset: str, *, sport: str) -> FreshnessClass:
    if sport.upper() == "NHL":
        return "SOURCE_UNAVAILABLE"
    if dataset == "kalshi_orderbook_snapshots":
        return "LIVE_EXPECTED"
    if dataset in {"kalshi_candles", "kalshi_last_trade", "pbp", "games", "kalshi_markets"}:
        return "DAILY_EXPECTED"
    return "HISTORICAL_ONLY"


def evaluate(
    *,
    classification: FreshnessClass,
    warehouse_latest: str | None,
    source_latest: str | None = None,
    last_ingest: str | None = None,
) -> Freshness:
    if classification == "SOURCE_UNAVAILABLE":
        return Freshness(
            classification,
            "SOURCE_UNAVAILABLE",
            source_latest,
            warehouse_latest,
            last_ingest,
            None,
            None,
            "No warehouse tree. Do not call this missing.",
        )
    if classification == "HISTORICAL_ONLY":
        return Freshness(
            classification,
            "HISTORICAL_ONLY",
            source_latest,
            warehouse_latest,
            last_ingest,
            None,
            None,
            "Does not update. Not stale merely because the clock advanced.",
        )
    if warehouse_latest is None:
        return Freshness(
            classification,
            "STALE" if classification == "DAILY_EXPECTED" else "NOT_APPLICABLE",
            source_latest,
            None,
            last_ingest,
            None,
            None,
            "No warehouse timestamp observed.",
        )
    return Freshness(
        classification,
        "CURRENT",
        source_latest,
        warehouse_latest,
        last_ingest,
        None,
        None,
    )
