//! Research position tracking with execution fills.

use serde::{Deserialize, Serialize};

use momento_core::{GameId, MarketId, PositionId, Side};
use momento_research_strategies::{LiquidationState, ResearchPosition, ResearchPositionFill};

use crate::fill::SimulatedFill;
use crate::order::OrderPurpose;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PositionStatus {
    Open,
    LiquidationActive,
    Flat,
    OpenAtEnd,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutionPosition {
    pub position_id: u128,
    pub game_id: u128,
    pub market_id: u128,
    pub ticker: String,
    pub side: Side,
    pub requested_quantity: u32,
    pub filled_quantity: u32,
    pub remaining_entry_quantity: u32,
    pub entry_fills: Vec<SimulatedFill>,
    pub exit_fills: Vec<SimulatedFill>,
    pub opened_at_ms: Option<i64>,
    pub closed_at_ms: Option<i64>,
    pub status: PositionStatus,
    pub lifecycle: LiquidationState,
}

impl ExecutionPosition {
    pub fn new(
        position_id: u128,
        game_id: u128,
        market_id: u128,
        ticker: impl Into<String>,
        side: Side,
        requested_quantity: u32,
    ) -> Self {
        Self {
            position_id,
            game_id,
            market_id,
            ticker: ticker.into(),
            side,
            requested_quantity,
            filled_quantity: 0,
            remaining_entry_quantity: requested_quantity,
            entry_fills: Vec::new(),
            exit_fills: Vec::new(),
            opened_at_ms: None,
            closed_at_ms: None,
            status: PositionStatus::Open,
            lifecycle: LiquidationState::Open,
        }
    }

    pub fn to_research_position(&self) -> Option<ResearchPosition> {
        if self.entry_fills.is_empty() {
            return None;
        }
        let fills: Vec<ResearchPositionFill> = self
            .entry_fills
            .iter()
            .map(|f| ResearchPositionFill {
                quantity_contracts: f.quantity_contracts,
                price_cents: f.price_cents,
            })
            .collect();
        let filled: u32 = fills.iter().map(|f| f.quantity_contracts).sum();
        let remaining =
            filled.saturating_sub(self.exit_fills.iter().map(|f| f.quantity_contracts).sum());
        let mut pos = ResearchPosition::new(
            PositionId::from_raw(self.position_id),
            GameId::from_raw(self.game_id),
            MarketId::from_raw(self.market_id),
            self.side,
            &self.ticker,
            fills,
        );
        pos.lifecycle = self.lifecycle;
        pos.remaining_quantity = remaining;
        pos.filled_quantity = filled;
        Some(pos)
    }

    pub fn apply_entry_fill(&mut self, fill: &SimulatedFill) {
        if self.opened_at_ms.is_none() {
            self.opened_at_ms = Some(fill.exchange_timestamp_ms);
        }
        self.filled_quantity += fill.quantity_contracts;
        self.remaining_entry_quantity =
            self.requested_quantity.saturating_sub(self.filled_quantity);
        self.entry_fills.push(fill.clone());
        if self.remaining_entry_quantity == 0 && self.exit_fills.is_empty() {
            self.status = PositionStatus::Open;
        }
    }

    pub fn apply_exit_fill(&mut self, fill: &SimulatedFill, closed_ms: i64) {
        self.exit_fills.push(fill.clone());
        let remaining = self
            .filled_quantity
            .saturating_sub(self.exit_fills.iter().map(|f| f.quantity_contracts).sum());
        if remaining == 0 {
            self.status = PositionStatus::Flat;
            self.lifecycle = LiquidationState::Flat;
            self.closed_at_ms = Some(closed_ms);
        } else {
            self.status = PositionStatus::LiquidationActive;
            self.lifecycle = LiquidationState::LiquidationActive;
        }
    }

    pub fn mark_open_at_end(&mut self) {
        if !matches!(self.status, PositionStatus::Flat) && self.filled_quantity > 0 {
            self.status = PositionStatus::OpenAtEnd;
        }
    }

    pub fn entry_vwap_cents(&self) -> Option<u16> {
        if self.entry_fills.is_empty() {
            return None;
        }
        let mut qty: u64 = 0;
        let mut premium: u128 = 0;
        for f in &self.entry_fills {
            qty += u64::from(f.quantity_contracts);
            premium += u128::from(f.quantity_contracts) * u128::from(f.price_cents);
        }
        if qty == 0 {
            return None;
        }
        u16::try_from(premium / u128::from(qty)).ok()
    }

    pub fn net_contracts(&self) -> u32 {
        let exited: u32 = self.exit_fills.iter().map(|f| f.quantity_contracts).sum();
        self.filled_quantity.saturating_sub(exited)
    }
}

pub fn fill_purpose_is_entry(fill: &SimulatedFill) -> bool {
    fill.purpose == OrderPurpose::Entry
}
