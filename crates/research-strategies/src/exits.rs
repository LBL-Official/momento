//! FIRST01 exit model — 50% loss trigger, position-scoped, liquidation continuation.

use momento_core::{GameId, MarketId, PositionId, Side};

use crate::first01::{FIRST01_NAME, FIRST01_VERSION};
use crate::identity::PositionScope;
use crate::params::ExitParameters;
use crate::quote::{QuoteReject, StrategyQuote, ValidQuote, validate_quote_for_exit};
use crate::signals::{ExitReason, ExitSignal, LiquidationState};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ResearchPositionFill {
    pub quantity_contracts: u32,
    pub price_cents: u16,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ResearchPosition {
    pub scope: PositionScope,
    pub ticker: String,
    pub entry_fills: Vec<ResearchPositionFill>,
    pub lifecycle: LiquidationState,
    pub filled_quantity: u32,
    pub remaining_quantity: u32,
}

impl ResearchPosition {
    pub fn new(
        position_id: PositionId,
        game_id: GameId,
        market_id: MarketId,
        side: Side,
        ticker: impl Into<String>,
        fills: Vec<ResearchPositionFill>,
    ) -> Self {
        let filled_quantity = fills.iter().map(|f| f.quantity_contracts).sum();
        Self {
            scope: PositionScope::new(position_id, game_id, market_id, side),
            ticker: ticker.into(),
            entry_fills: fills,
            lifecycle: LiquidationState::Open,
            filled_quantity,
            remaining_quantity: filled_quantity,
        }
    }

    pub fn entry_vwap_hundredths(&self) -> Option<u32> {
        if self.entry_fills.is_empty() {
            return None;
        }
        let mut qty: u64 = 0;
        let mut premium_cents: u128 = 0;
        for fill in &self.entry_fills {
            qty = qty.checked_add(u64::from(fill.quantity_contracts))?;
            premium_cents = premium_cents
                .checked_add(u128::from(fill.quantity_contracts) * u128::from(fill.price_cents))?;
        }
        if qty == 0 {
            return None;
        }
        let hundredths = premium_cents.checked_mul(100)? / u128::from(qty);
        u32::try_from(hundredths).ok()
    }

    pub fn stop_threshold_hundredths(&self, params: &ExitParameters) -> Option<u32> {
        let vwap = self.entry_vwap_hundredths()?;
        Some(vwap * params.loss_numerator / params.loss_denominator.max(1))
    }
}

fn quote_matches_position(
    position: &ResearchPosition,
    quote: &StrategyQuote,
    valid: ValidQuote,
) -> bool {
    position.scope.market_id == quote.market_id.raw()
        && position.scope.side == valid.side
        && position.scope.side == quote.side
}

fn bid_triggers_stop(bid_cents: u16, threshold_hundredths: u32) -> bool {
    u32::from(bid_cents).saturating_mul(100) <= threshold_hundredths
}

fn liquidation_active(lifecycle: LiquidationState) -> bool {
    matches!(
        lifecycle,
        LiquidationState::StopTriggered | LiquidationState::LiquidationActive
    )
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ExitTurn {
    pub signals: Vec<ExitSignal>,
    pub reject: Option<QuoteReject>,
}

pub struct ExitEngine {
    params: ExitParameters,
}

impl ExitEngine {
    pub fn new(params: ExitParameters) -> Self {
        Self { params }
    }

    pub fn observe(&self, quote: &StrategyQuote, position: &mut ResearchPosition) -> ExitTurn {
        let mut turn = ExitTurn::default();
        let valid = match validate_quote_for_exit(quote) {
            Ok(v) => v,
            Err(reject) => {
                turn.reject = Some(reject);
                return turn;
            }
        };

        if position.remaining_quantity == 0 {
            position.lifecycle = LiquidationState::Flat;
            return turn;
        }

        if !quote_matches_position(position, quote, valid) {
            return turn;
        }

        let Some(threshold) = position.stop_threshold_hundredths(&self.params) else {
            return turn;
        };
        let vwap = position.entry_vwap_hundredths().unwrap_or(0);
        let reducing = liquidation_active(position.lifecycle);
        let triggered = bid_triggers_stop(valid.bid.cents(), threshold);

        if !reducing && !triggered {
            return turn;
        }

        if !reducing {
            position.lifecycle = LiquidationState::StopTriggered;
        }
        position.lifecycle = LiquidationState::LiquidationActive;

        turn.signals.push(ExitSignal {
            strategy: FIRST01_NAME.to_string(),
            strategy_version: FIRST01_VERSION,
            scope: position.scope,
            ticker: position.ticker.clone(),
            exchange_timestamp_ms: quote.exchange_timestamp_ms,
            received_timestamp: quote.received_timestamp,
            trigger_bid_cents: valid.bid.cents(),
            stop_threshold_hundredths_of_cent: threshold,
            entry_vwap_hundredths_of_cent: vwap,
            quantity_contracts: position.remaining_quantity,
            reason: ExitReason::LossFraction,
            liquidation_state: position.lifecycle,
            is_continuation: reducing,
        });
        turn
    }

    /// Apply a simulated fill from a future execution layer. FIRST01 does not
    /// invent fills — the host/backtest runner supplies them.
    pub fn apply_liquidation_fill(position: &mut ResearchPosition, filled: u32) {
        if filled == 0 {
            return;
        }
        if filled >= position.remaining_quantity {
            position.remaining_quantity = 0;
            position.lifecycle = LiquidationState::Flat;
        } else {
            position.remaining_quantity -= filled;
            position.lifecycle = LiquidationState::LiquidationActive;
        }
    }

    /// Recovery above stop does not cancel liquidation once triggered.
    pub fn lifecycle(&self, position: &ResearchPosition) -> LiquidationState {
        position.lifecycle
    }
}

/// Serializable exit observation for persistence tests.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ExitObservation {
    pub scope: PositionScope,
    pub lifecycle: LiquidationState,
    pub remaining_quantity: u32,
}

impl ExitEngine {
    pub fn snapshot_position(position: &ResearchPosition) -> ExitObservation {
        ExitObservation {
            scope: position.scope,
            lifecycle: position.lifecycle,
            remaining_quantity: position.remaining_quantity,
        }
    }

    pub fn restore_position(
        obs: ExitObservation,
        ticker: &str,
        fills: Vec<ResearchPositionFill>,
    ) -> ResearchPosition {
        let mut pos = ResearchPosition::new(
            PositionId::from_raw(obs.scope.position_id),
            GameId::from_raw(obs.scope.game_id),
            MarketId::from_raw(obs.scope.market_id),
            obs.scope.side,
            ticker,
            fills,
        );
        pos.lifecycle = obs.lifecycle;
        pos.remaining_quantity = obs.remaining_quantity;
        pos
    }
}
