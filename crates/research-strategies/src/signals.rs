//! Normalized research signals. No order submission.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use momento_core::Side;

use crate::first01::FIRST01_NAME;
use crate::identity::{EntryStateKey, PositionScope};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EntrySignal {
    pub strategy: String,
    pub strategy_version: u32,
    pub market_id: u128,
    pub ticker: String,
    pub game_id: u128,
    pub side: Side,
    pub exchange_timestamp_ms: i64,
    pub received_timestamp: DateTime<Utc>,
    pub signal_price_cents: u16,
    pub first_threshold_cents: u16,
    pub confirmation_threshold_cents: u16,
    pub maximum_entry_price_cents: u16,
    pub bid_cents: u16,
    pub ask_cents: u16,
    pub maker_eligible: bool,
}

impl EntrySignal {
    pub fn key(&self) -> EntryStateKey {
        EntryStateKey {
            game_id: self.game_id,
            market_id: self.market_id,
            side: self.side,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ExitReason {
    LossFraction,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum LiquidationState {
    Open,
    StopTriggered,
    LiquidationActive,
    Flat,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExitSignal {
    pub strategy: String,
    pub strategy_version: u32,
    pub scope: PositionScope,
    pub ticker: String,
    pub exchange_timestamp_ms: i64,
    pub received_timestamp: DateTime<Utc>,
    pub trigger_bid_cents: u16,
    pub stop_threshold_hundredths_of_cent: u32,
    pub entry_vwap_hundredths_of_cent: u32,
    pub quantity_contracts: u32,
    pub reason: ExitReason,
    pub liquidation_state: LiquidationState,
    pub is_continuation: bool,
}

impl ExitSignal {
    pub fn strategy_is_first01(&self) -> bool {
        self.strategy == FIRST01_NAME
    }
}
