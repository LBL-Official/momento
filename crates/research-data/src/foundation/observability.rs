//! Canonical observability vocabulary (W1-A7).
//!
//! Categories are never silently upgraded. A DERIVED value must name its
//! transform version. A MODELED value is not historical fact.

use serde::{Deserialize, Serialize};

/// Honesty class for a field or dataset.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ObservabilityKind {
    /// Present in an immutable raw record at time t.
    Observed,
    /// Deterministic function of observed data with timestamps ≤ t (no lookahead).
    Derived,
    /// Join/sync that can be wrong; must carry confidence. Not used as OBSERVED.
    Inferred,
    /// Simulation (fills, fees, queue, theta). Never stored as lake truth.
    Modeled,
    /// Not in source. Null + reason. Never fabricated.
    Unavailable,
    /// Historical L2 does not exist for this artifact. Stronger than a generic UNAVAILABLE.
    L2HistoricalUnavailable,
    /// Eventual winner / settlement used only as a label, never as replay input at t.
    OutcomeLabel,
}

impl ObservabilityKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Observed => "OBSERVED",
            Self::Derived => "DERIVED",
            Self::Inferred => "INFERRED",
            Self::Modeled => "MODELED",
            Self::Unavailable => "UNAVAILABLE",
            Self::L2HistoricalUnavailable => "L2_HISTORICAL_UNAVAILABLE",
            Self::OutcomeLabel => "OUTCOME_LABEL",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct FieldObservabilityContract {
    pub field: &'static str,
    pub kind: ObservabilityKind,
    pub notes: &'static str,
}

/// Canonical field contract for W1. Later waterfalls add rows; they must not
/// reclassify existing rows without a new contract version.
pub const OBSERVABILITY_CONTRACT: &[FieldObservabilityContract] = &[
    FieldObservabilityContract {
        field: "yes_bid",
        kind: ObservabilityKind::Observed,
        notes: "Kalshi YES bid when present on a quote/candle close/trade is OBSERVED. Candle close is still a candle, not an L2 bid.",
    },
    FieldObservabilityContract {
        field: "yes_ask",
        kind: ObservabilityKind::Observed,
        notes: "Same as yes_bid.",
    },
    FieldObservabilityContract {
        field: "public_trade",
        kind: ObservabilityKind::Observed,
        notes: "Kalshi public trade payload (price, qty, created_time).",
    },
    FieldObservabilityContract {
        field: "spread",
        kind: ObservabilityKind::Derived,
        notes: "ask − bid when both OBSERVED and ask ≥ bid. Not a venue field.",
    },
    FieldObservabilityContract {
        field: "price_velocity",
        kind: ObservabilityKind::Derived,
        notes: "Not computed in W1. Future DERIVED from OBSERVED path. Forbidden as OBSERVED.",
    },
    FieldObservabilityContract {
        field: "mid",
        kind: ObservabilityKind::Unavailable,
        notes: "Kalshi does not publish an official mid. Never invent (bid+ask)/2 as OBSERVED.",
    },
    FieldObservabilityContract {
        field: "l2_orderbook",
        kind: ObservabilityKind::L2HistoricalUnavailable,
        notes: "L2_HISTORICAL_UNAVAILABLE. REST backfill has no L2. Candles are not L2. PIT ingest snapshots are not game-time books.",
    },
    FieldObservabilityContract {
        field: "true_queue_position",
        kind: ObservabilityKind::Unavailable,
        notes: "Not in public historical data. MODELED later if an execution plugin exists.",
    },
    FieldObservabilityContract {
        field: "rest_snapshot_at_ingest",
        kind: ObservabilityKind::Observed,
        notes: "OBSERVED as of collector ingest time only. UNAVAILABLE as game-time L2.",
    },
    FieldObservabilityContract {
        field: "candlestick_1m_close",
        kind: ObservabilityKind::Observed,
        notes: "1-minute YES bid/ask OHLC close. Observability remains CANDLESTICK, never tick/L2.",
    },
    FieldObservabilityContract {
        field: "received_at",
        kind: ObservabilityKind::Observed,
        notes: "Collector ingestion clock. NOT exchange time unless proven identical.",
    },
    FieldObservabilityContract {
        field: "exchange_timestamp",
        kind: ObservabilityKind::Observed,
        notes: "Trade created_time or candle end_period_ts when present in payload.",
    },
    FieldObservabilityContract {
        field: "starting_price",
        kind: ObservabilityKind::Unavailable,
        notes: "STARTING_PRICE_UNVERIFIED for v1 close-day partitions. MARKET_OPEN_PRICE is not the first candle in the file. Metadata open_time may be OBSERVED independently.",
    },
    FieldObservabilityContract {
        field: "pbp",
        kind: ObservabilityKind::Unavailable,
        notes: "No MLB PBP in the lake. Do not invent.",
    },
    FieldObservabilityContract {
        field: "event_state",
        kind: ObservabilityKind::Unavailable,
        notes: "W2+. Not reconstructed in W1.",
    },
    FieldObservabilityContract {
        field: "synchronized_state",
        kind: ObservabilityKind::Unavailable,
        notes: "W3+. Not reconstructed in W1.",
    },
    FieldObservabilityContract {
        field: "future_winner",
        kind: ObservabilityKind::OutcomeLabel,
        notes: "Kalshi result/settlement is a LABEL. Forbidden as a feature at t < settlement.",
    },
    FieldObservabilityContract {
        field: "expected_fill_probability",
        kind: ObservabilityKind::Modeled,
        notes: "Execution plugin only. Not lake truth.",
    },
    FieldObservabilityContract {
        field: "event_theta",
        kind: ObservabilityKind::Modeled,
        notes: "Later waterfall. No formula in W1.",
    },
    FieldObservabilityContract {
        field: "market_theta",
        kind: ObservabilityKind::Modeled,
        notes: "Later waterfall. No formula in W1.",
    },
    FieldObservabilityContract {
        field: "kalshi_trade",
        kind: ObservabilityKind::Observed,
        notes: "Public trade print. Not a quote tick.",
    },
    FieldObservabilityContract {
        field: "kalshi_bid",
        kind: ObservabilityKind::Observed,
        notes: "YES bid when present. Candle close bid remains CANDLESTICK semantics.",
    },
    FieldObservabilityContract {
        field: "kalshi_ask",
        kind: ObservabilityKind::Observed,
        notes: "YES ask when present. Same candle caveat.",
    },
    FieldObservabilityContract {
        field: "kalshi_size",
        kind: ObservabilityKind::Unavailable,
        notes: "Bid/ask size not on historical candles. UNAVAILABLE unless a true book snapshot at t exists.",
    },
    FieldObservabilityContract {
        field: "kalshi_candle",
        kind: ObservabilityKind::Observed,
        notes: "1-minute OHLC of YES bid/ask. Not ticks, not L2.",
    },
    FieldObservabilityContract {
        field: "kalshi_orderbook",
        kind: ObservabilityKind::L2HistoricalUnavailable,
        notes: "Do not read v1 orderbook.parquet as historical L2.",
    },
    FieldObservabilityContract {
        field: "kalshi_timestamp_ingestion",
        kind: ObservabilityKind::Observed,
        notes: "received_at = collector clock.",
    },
    FieldObservabilityContract {
        field: "kalshi_timestamp_exchange",
        kind: ObservabilityKind::Observed,
        notes: "Trade created_time / candle end_period_ts only when in payload.",
    },
];

pub fn contract_kind(field: &str) -> Option<ObservabilityKind> {
    OBSERVABILITY_CONTRACT
        .iter()
        .find(|r| r.field == field)
        .map(|r| r.kind)
}
