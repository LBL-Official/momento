//! Simulated fill records.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use momento_core::Side;

use crate::order::{FillEvidence, OrderPurpose};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SimulatedFill {
    pub fill_id: u64,
    pub order_id: u64,
    pub position_id: u128,
    pub market_id: u128,
    pub ticker: String,
    pub side: Side,
    pub purpose: OrderPurpose,
    pub price_cents: u16,
    pub quantity_contracts: u32,
    pub exchange_timestamp_ms: i64,
    pub received_timestamp: DateTime<Utc>,
    pub fill_evidence: FillEvidence,
    pub queue_ahead_at_fill: u32,
    pub is_partial: bool,
}
