"""Versioned dataset contracts. Observation bases stay distinct.

Do not rename last_close_e4 to yes_bid_close.
Do not fabricate fields the source does not provide.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from roller.research_query.models import BASIS_LAST_TRADE, BASIS_TRADABLE

SCHEMA_VERSION = "1.0.0"

# Observational clocks. Do not collapse into one timestamp.
CLOCK_OBSERVED = "observed_timestamp"
CLOCK_SOURCE = "source_timestamp"
CLOCK_AVAILABLE = "available_at"
CLOCK_INGESTED = "ingestion_timestamp"

BASIS_TRADABLE_YES_BID = BASIS_TRADABLE
BASIS_LAST_TRADE_PRINT = BASIS_LAST_TRADE

IDENTITY_FIELDS = (
    "dataset_name",
    "dataset_version",
    "schema_version",
    "source",
    "sport",
    "league",
    "season",
    "game_date",
    "internal_game_id",
    "ticker",
    "available_at",
    "source_timestamp",
    "ingestion_timestamp",
    "source_revision",
)

# Present on current canonical CSVs. Identity metadata may live on the
# partition manifest rather than every row.
ROW_CLOCKS = ("available_at", "event_timestamp", "ingested_at")


@dataclass(frozen=True)
class DatasetContract:
    dataset_name: str
    observation_basis: str | None
    required_columns: tuple[str, ...]
    price_columns: tuple[str, ...] = ()
    notes: str = ""
    optional_identity: tuple[str, ...] = field(default=IDENTITY_FIELDS)


CONTRACTS: dict[str, DatasetContract] = {
    "kalshi_candles": DatasetContract(
        dataset_name="kalshi_candles",
        observation_basis=BASIS_TRADABLE_YES_BID,
        required_columns=(
            "internal_game_id",
            "ticker",
            "available_at",
            "yes_bid_close",
            "yes_ask_close",
            "volume",
        ),
        price_columns=("yes_bid_close", "yes_ask_close"),
        notes="TRADABLE_YES_BID. Absent minutes stay absent. Untradable bars stay in CSV.",
    ),
    "kalshi_last_trade": DatasetContract(
        dataset_name="kalshi_last_trade",
        observation_basis=BASIS_LAST_TRADE_PRINT,
        required_columns=(
            "internal_game_id",
            "ticker",
            "available_at",
            "last_close_e4",
        ),
        price_columns=("last_close_e4",),
        notes="LAST_TRADE_PRINT. last_close_e4 is not yes_bid. Minutes without a print are absent.",
    ),
    "polymarket_candles": DatasetContract(
        dataset_name="polymarket_candles",
        observation_basis=BASIS_LAST_TRADE_PRINT,
        required_columns=("internal_game_id", "ticker", "available_at"),
        notes="Polymarket last-trade-like candles. Not Kalshi yes_bid. Not Kalshi settlement.",
    ),
    "pbp": DatasetContract(
        dataset_name="pbp",
        observation_basis=None,
        required_columns=("internal_game_id", "event_timestamp"),
        notes="Events. Missing PBP is UNALIGNED, not a false event.",
    ),
    "games": DatasetContract(
        dataset_name="games",
        observation_basis=None,
        required_columns=("internal_game_id", "sport", "season"),
        notes="Game metadata. Box score is not Kalshi settlement.",
    ),
    "kalshi_markets": DatasetContract(
        dataset_name="kalshi_markets",
        observation_basis=None,
        required_columns=("ticker",),
        notes="Kalshi result only. Missing ≠ NO. Do not fill from PBP.",
    ),
    "kalshi_orderbook_snapshots": DatasetContract(
        dataset_name="kalshi_orderbook_snapshots",
        observation_basis=None,
        required_columns=("ticker", "available_at"),
        notes="Live snapshots as stored. Not synthesized L2. Top-of-book stays top-of-book.",
    ),
    "polymarket_markets": DatasetContract(
        dataset_name="polymarket_markets",
        observation_basis=None,
        required_columns=("ticker",),
        notes="Polymarket market metadata. Not a Kalshi settlement substitute.",
    ),
}


def contract_for(dataset_name: str) -> DatasetContract | None:
    return CONTRACTS.get(dataset_name)


def e4_domain_ok(value: object) -> bool:
    """Kalshi E4 prices are integer cents×100 in [0, 10000] when present."""
    if value in (None, ""):
        return True
    try:
        n = int(value)
    except (TypeError, ValueError):
        return False
    return 0 <= n <= 10000
