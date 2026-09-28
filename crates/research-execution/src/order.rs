//! Simulated order lifecycle for research execution.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use momento_core::Side;

use crate::params::ExecutionParameters;
use crate::quality::ExecutionDataQuality;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum OrderPurpose {
    Entry,
    Liquidation,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum OrderSide {
    Bid,
    Ask,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum OrderStatus {
    Created,
    Working,
    PartiallyFilled,
    Filled,
    Cancelled,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum FillEvidence {
    FullL2DisplayedLiquidity,
    TopOfBookDisplayedLiquidity,
    InsufficientData,
    SequenceGap,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SimulatedOrder {
    pub order_id: u64,
    pub run_id: String,
    pub position_id: u128,
    pub game_id: u128,
    pub market_id: u128,
    pub ticker: String,
    pub outcome_side: Side,
    pub order_side: OrderSide,
    pub purpose: OrderPurpose,
    pub limit_price_cents: u16,
    pub quantity: u32,
    pub remaining_quantity: u32,
    pub filled_quantity: u32,
    pub post_only: bool,
    pub submitted_at_ms: i64,
    pub submitted_at: DateTime<Utc>,
    pub status: OrderStatus,
    pub execution_model_name: String,
    pub execution_model_version: u32,
    pub queue_ahead_contracts: u32,
    pub queue_assumption: String,
    pub data_quality_at_submit: ExecutionDataQuality,
    pub signal_exchange_ms: Option<i64>,
    pub signal_price_cents: Option<u16>,
    pub stop_threshold_hundredths: Option<u32>,
    pub trigger_bid_cents: Option<u16>,
}

impl SimulatedOrder {
    #[allow(clippy::too_many_arguments)]
    pub fn new_entry(
        order_id: u64,
        run_id: &str,
        position_id: u128,
        signal: &momento_research_strategies::EntrySignal,
        quantity: u32,
        params: &ExecutionParameters,
        quality: ExecutionDataQuality,
        queue_ahead: u32,
    ) -> Self {
        Self {
            order_id,
            run_id: run_id.to_string(),
            position_id,
            game_id: signal.game_id,
            market_id: signal.market_id,
            ticker: signal.ticker.clone(),
            outcome_side: signal.side,
            order_side: OrderSide::Bid,
            purpose: OrderPurpose::Entry,
            limit_price_cents: signal.signal_price_cents,
            quantity,
            remaining_quantity: quantity,
            filled_quantity: 0,
            post_only: true,
            submitted_at_ms: signal.exchange_timestamp_ms,
            submitted_at: signal.received_timestamp,
            status: OrderStatus::Working,
            execution_model_name: params.execution_model_name.clone(),
            execution_model_version: params.execution_model_version,
            queue_ahead_contracts: queue_ahead,
            queue_assumption: "CONSERVATIVE: displayed quantity at limit price ahead of order"
                .into(),
            data_quality_at_submit: quality,
            signal_exchange_ms: Some(signal.exchange_timestamp_ms),
            signal_price_cents: Some(signal.signal_price_cents),
            stop_threshold_hundredths: None,
            trigger_bid_cents: None,
        }
    }

    pub fn new_liquidation(
        order_id: u64,
        run_id: &str,
        _position_id: u128,
        signal: &momento_research_strategies::ExitSignal,
        params: &ExecutionParameters,
        quality: ExecutionDataQuality,
    ) -> Self {
        Self {
            order_id,
            run_id: run_id.to_string(),
            position_id: signal.scope.position_id,
            game_id: signal.scope.game_id,
            market_id: signal.scope.market_id,
            ticker: signal.ticker.clone(),
            outcome_side: signal.scope.side,
            order_side: OrderSide::Ask,
            purpose: OrderPurpose::Liquidation,
            limit_price_cents: signal.trigger_bid_cents,
            quantity: signal.quantity_contracts,
            remaining_quantity: signal.quantity_contracts,
            filled_quantity: 0,
            post_only: false,
            submitted_at_ms: signal.exchange_timestamp_ms,
            submitted_at: signal.received_timestamp,
            status: OrderStatus::Working,
            execution_model_name: params.execution_model_name.clone(),
            execution_model_version: params.execution_model_version,
            queue_ahead_contracts: 0,
            queue_assumption: "IOC liquidation: no queue priority".into(),
            data_quality_at_submit: quality,
            signal_exchange_ms: Some(signal.exchange_timestamp_ms),
            signal_price_cents: None,
            stop_threshold_hundredths: Some(signal.stop_threshold_hundredths_of_cent),
            trigger_bid_cents: Some(signal.trigger_bid_cents),
        }
    }

    pub fn apply_fill(&mut self, qty: u32) {
        if qty == 0 {
            return;
        }
        self.filled_quantity += qty;
        self.remaining_quantity = self.remaining_quantity.saturating_sub(qty);
        self.status = if self.remaining_quantity == 0 {
            OrderStatus::Filled
        } else {
            OrderStatus::PartiallyFilled
        };
    }

    pub fn cancel(&mut self) {
        if matches!(
            self.status,
            OrderStatus::Created | OrderStatus::Working | OrderStatus::PartiallyFilled
        ) {
            self.status = OrderStatus::Cancelled;
        }
    }
}
