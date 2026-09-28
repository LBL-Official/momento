use serde::{Deserialize, Serialize};

use momento_core::{ExchangeTimestamp, GameId, MarketId, PositionId, Price, ReceivedAt, Side};

use crate::quote::ValidQuote;

/// Canonical MLB entry-flow phase. There is no take-profit phase.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum MlbGamePhase {
    NotEligible,
    Watching,
    First80Triggered,
    WaitingFor81Confirmation,
    EntryEligible,
    PositionBuilding,
    PositionOpen,
    GameLocked,
}

impl MlbGamePhase {
    pub const fn blocks_entry(self) -> bool {
        matches!(self, Self::GameLocked | Self::NotEligible | Self::Watching)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct FirstTrigger {
    pub game_id: GameId,
    pub market_id: MarketId,
    pub side: Side,
    pub exchange_ts: ExchangeTimestamp,
    pub received_at: ReceivedAt,
    pub bid: Price,
    pub ask: Price,
    /// Recorded qualifying observation (YES bid). Not a venue mid.
    /// Kept as `mid` in JSON for snapshot compatibility.
    pub mid: Price,
    pub bid_depth: Option<u32>,
    pub ask_depth: Option<u32>,
    pub game_state: Option<String>,
}

impl FirstTrigger {
    pub fn capture(event: &momento_core::MarketEvent, quote: ValidQuote) -> Self {
        Self {
            game_id: event.game_id,
            market_id: event.market_id,
            side: quote.side,
            exchange_ts: event.exchange_ts,
            received_at: event.received_at,
            bid: quote.bid,
            ask: quote.ask,
            mid: quote.bid,
            bid_depth: event.bid_depth,
            ask_depth: event.ask_depth,
            game_state: event.game_state.clone(),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct QuoteFingerprint {
    pub exchange_ts: ExchangeTimestamp,
    pub side: Side,
    pub bid: u16,
    pub ask: u16,
    /// Qualifying YES bid cents. Legacy JSON key; not a venue mid.
    pub mid: u16,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MlbGameSnapshot {
    pub game_id: GameId,
    pub phase: MlbGamePhase,
    pub first_80: Option<FirstTrigger>,
    pub confirmed_81: bool,
    pub first_89: Option<FirstTrigger>,
    pub paused_above_max: bool,
    pub assigned_position_id: Option<PositionId>,
    pub last_fingerprint: Option<QuoteFingerprint>,
    pub last_exchange_ts: Option<ExchangeTimestamp>,
    pub stop_watch_emitted: bool,
    pub ordering_ambiguous: bool,
}

impl MlbGameSnapshot {
    pub fn new(game_id: GameId) -> Self {
        Self {
            game_id,
            phase: MlbGamePhase::Watching,
            first_80: None,
            confirmed_81: false,
            first_89: None,
            paused_above_max: false,
            assigned_position_id: None,
            last_fingerprint: None,
            last_exchange_ts: None,
            stop_watch_emitted: false,
            ordering_ambiguous: false,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MlbStrategySnapshot {
    pub games: Vec<MlbGameSnapshot>,
}
