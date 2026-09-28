//! FIRST01 entry state machine — mirrors live `MlbStrategy` sequencing and
//! game-scoped trade concurrency (one canonical FIRST01 opportunity per `GameId`).

use std::collections::HashMap;

use chrono::{DateTime, Utc};

use momento_core::{GameId, MarketId};

use crate::first01::{FIRST01_NAME, FIRST01_VERSION};
use crate::identity::EntryStateKey;
use crate::params::EntryParameters;
use crate::quote::{QuoteReject, StrategyQuote};
use crate::quote::{
    above_max_entry, maker_limit, qualifying_price, reaches_confirmation, reaches_first_threshold,
    reaches_lock, validate_quote,
};
use crate::signals::EntrySignal;
use crate::trade::{
    ActiveOpportunityState, ENTRY_REASON_FIRST01, EntryContext, EntryIntent, EntryOpportunity,
    GameTradePhase, LifecycleAction, OpportunityId, OpportunityLifecycle, QuoteObservation,
    TradeId,
};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub enum EntryPhase {
    #[default]
    Watching,
    FirstTriggered,
    WaitingForConfirmation,
    EntryEligible,
    GameLocked,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FirstObservation {
    pub key: EntryStateKey,
    pub exchange_timestamp_ms: i64,
    pub received_timestamp: DateTime<Utc>,
    pub bid_cents: u16,
    pub ask_cents: u16,
}

#[derive(Clone, Debug, Default)]
struct GameEntryState {
    phase: EntryPhase,
    first_observation: Option<FirstObservation>,
    confirmed: bool,
    confirmation_81_timestamp_ms: Option<i64>,
    confirmation_81_price_cents: Option<u16>,
    paused_above_max: bool,
    last_exchange_ms: Option<i64>,
    last_bid: Option<u16>,
    last_ask: Option<u16>,
    /// Sticky: once a canonical opportunity exists for this game, never create another.
    /// Matches live: `first_80` never clears; Flat/OpenComplete block re-entry forever.
    canonical_lifecycle_consumed: bool,
    active_opportunity: Option<ActiveOpportunityState>,
    game_trade_phase: GameTradePhase,
    suppressed_qualifying_quotes: u64,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct EntryTurn {
    pub quote_observation: Option<QuoteObservation>,
    pub new_opportunity: Option<EntryOpportunity>,
    pub intents: Vec<EntryIntent>,
    /// Legacy alias — populated only from [`EntryIntent`] (never quote-level duplicates).
    pub signals: Vec<EntrySignal>,
    pub phase: Option<EntryPhase>,
    pub game_trade_phase: Option<GameTradePhase>,
    pub reject: Option<QuoteReject>,
}

pub struct EntryEngine {
    params: EntryParameters,
    games: HashMap<u128, GameEntryState>,
    next_trade_number: u64,
}

impl EntryEngine {
    pub fn new(params: EntryParameters) -> Self {
        Self {
            params,
            games: HashMap::new(),
            next_trade_number: 1,
        }
    }

    pub fn params(&self) -> &EntryParameters {
        &self.params
    }

    pub fn phase(&self, game: GameId) -> EntryPhase {
        self.games
            .get(&game.raw())
            .map(|g| g.phase)
            .unwrap_or(EntryPhase::Watching)
    }

    pub fn game_trade_phase(&self, game: GameId) -> GameTradePhase {
        self.games
            .get(&game.raw())
            .map(|g| g.game_trade_phase)
            .unwrap_or(GameTradePhase::NoTrade)
    }

    pub fn first_observation(&self, game: GameId) -> Option<&FirstObservation> {
        self.games
            .get(&game.raw())
            .and_then(|g| g.first_observation.as_ref())
    }

    pub fn active_opportunity(&self, game: GameId) -> Option<&EntryOpportunity> {
        self.games
            .get(&game.raw())
            .and_then(|g| g.active_opportunity.as_ref())
            .map(|a| &a.opportunity)
    }

    pub fn canonical_lifecycle_consumed(&self, game: GameId) -> bool {
        self.games
            .get(&game.raw())
            .map(|g| g.canonical_lifecycle_consumed)
            .unwrap_or(false)
    }

    pub fn suppressed_qualifying_quotes(&self, game: GameId) -> u64 {
        self.games
            .get(&game.raw())
            .map(|g| g.suppressed_qualifying_quotes)
            .unwrap_or(0)
    }

    pub fn observe(&mut self, quote: &StrategyQuote) -> EntryTurn {
        self.observe_with_context(quote, &EntryContext::default())
    }

    pub fn observe_with_context(&mut self, quote: &StrategyQuote, ctx: &EntryContext) -> EntryTurn {
        let mut turn = EntryTurn::default();
        let valid = match validate_quote(quote, &self.params) {
            Ok(v) => v,
            Err(reject) => {
                turn.reject = Some(reject);
                return turn;
            }
        };

        let state = self.games.entry(quote.game_id.raw()).or_default();
        Self::sync_trade_lifecycle(state, ctx);

        let qualifying = qualifying_price(valid);
        let in_band = (self.params.first_threshold_cents..=self.params.maximum_entry_price_cents)
            .contains(&qualifying.cents());
        let maker_ok = maker_limit(valid, &self.params).is_some();
        let qualifies = in_band && maker_ok;

        if state.phase == EntryPhase::GameLocked {
            turn.quote_observation = Some(Self::obs(
                quote,
                valid.side,
                qualifying.cents(),
                state.game_trade_phase,
                qualifies,
                LifecycleAction::SuppressedByGameLock,
            ));
            if qualifies {
                state.suppressed_qualifying_quotes =
                    state.suppressed_qualifying_quotes.saturating_add(1);
            }
            turn.game_trade_phase = Some(GameTradePhase::GameLocked);
            turn.phase = Some(EntryPhase::GameLocked);
            return turn;
        }

        if state.last_exchange_ms == Some(quote.exchange_timestamp_ms)
            && state.last_bid == Some(valid.bid.cents())
            && state.last_ask == Some(valid.ask.cents())
        {
            turn.phase = Some(state.phase);
            turn.game_trade_phase = Some(state.game_trade_phase);
            return turn;
        }
        state.last_exchange_ms = Some(quote.exchange_timestamp_ms);
        state.last_bid = Some(valid.bid.cents());
        state.last_ask = Some(valid.ask.cents());

        let mut action = LifecycleAction::Observed;

        if reaches_lock(qualifying, &self.params) {
            let relevant = match &state.first_observation {
                None => true,
                Some(first) => {
                    first.key.market_id == quote.market_id.raw() && first.key.side == valid.side
                }
            };
            if relevant {
                state.phase = EntryPhase::GameLocked;
                state.game_trade_phase = GameTradePhase::GameLocked;
                state.paused_above_max = false;
                if let Some(active) = state.active_opportunity.as_mut() {
                    active.opportunity.lifecycle = OpportunityLifecycle::GameLocked;
                    active.opportunity.game_trade_phase = GameTradePhase::GameLocked;
                }
                turn.quote_observation = Some(Self::obs(
                    quote,
                    valid.side,
                    qualifying.cents(),
                    GameTradePhase::GameLocked,
                    qualifies,
                    LifecycleAction::GameLocked,
                ));
                turn.phase = Some(EntryPhase::GameLocked);
                turn.game_trade_phase = Some(GameTradePhase::GameLocked);
                return turn;
            }
        }

        if state.first_observation.is_none() {
            if reaches_first_threshold(qualifying, &self.params) {
                let key = EntryStateKey::new(quote.game_id, quote.market_id, valid.side);
                state.first_observation = Some(FirstObservation {
                    key,
                    exchange_timestamp_ms: quote.exchange_timestamp_ms,
                    received_timestamp: quote.received_timestamp,
                    bid_cents: valid.bid.cents(),
                    ask_cents: valid.ask.cents(),
                });
                state.phase = EntryPhase::FirstTriggered;
                action = LifecycleAction::FirstThresholdRecorded;
            } else {
                state.phase = EntryPhase::Watching;
            }
            turn.quote_observation = Some(Self::obs(
                quote,
                valid.side,
                qualifying.cents(),
                state.game_trade_phase,
                false,
                action,
            ));
            turn.phase = Some(state.phase);
            turn.game_trade_phase = Some(state.game_trade_phase);
            return turn;
        }

        let Some(first) = state.first_observation.clone() else {
            turn.phase = Some(state.phase);
            turn.game_trade_phase = Some(state.game_trade_phase);
            return turn;
        };

        if quote.market_id.raw() != first.key.market_id || valid.side != first.key.side {
            if qualifies {
                state.suppressed_qualifying_quotes =
                    state.suppressed_qualifying_quotes.saturating_add(1);
                action = LifecycleAction::SuppressedByOpponentMarket;
            }
            turn.quote_observation = Some(Self::obs(
                quote,
                valid.side,
                qualifying.cents(),
                state.game_trade_phase,
                qualifies,
                action,
            ));
            turn.phase = Some(state.phase);
            turn.game_trade_phase = Some(state.game_trade_phase);
            return turn;
        }

        if !state.confirmed {
            state.phase = EntryPhase::WaitingForConfirmation;
            if reaches_confirmation(qualifying, &self.params) {
                state.confirmed = true;
                state.confirmation_81_timestamp_ms = Some(quote.exchange_timestamp_ms);
                state.confirmation_81_price_cents = Some(qualifying.cents());
                state.phase = EntryPhase::EntryEligible;
            } else {
                turn.quote_observation = Some(Self::obs(
                    quote,
                    valid.side,
                    qualifying.cents(),
                    state.game_trade_phase,
                    false,
                    LifecycleAction::ConfirmationPending,
                ));
                turn.phase = Some(state.phase);
                turn.game_trade_phase = Some(state.game_trade_phase);
                return turn;
            }
        }

        if above_max_entry(qualifying, &self.params) {
            state.paused_above_max = true;
            state.phase = EntryPhase::EntryEligible;
            if qualifies || in_band {
                state.suppressed_qualifying_quotes =
                    state.suppressed_qualifying_quotes.saturating_add(1);
            }
            turn.quote_observation = Some(Self::obs(
                quote,
                valid.side,
                qualifying.cents(),
                state.game_trade_phase,
                false,
                LifecycleAction::SuppressedAboveMax,
            ));
            turn.phase = Some(state.phase);
            turn.game_trade_phase = Some(state.game_trade_phase);
            return turn;
        }
        state.paused_above_max = false;
        state.phase = EntryPhase::EntryEligible;

        if !maker_ok {
            turn.quote_observation = Some(Self::obs(
                quote,
                valid.side,
                qualifying.cents(),
                state.game_trade_phase,
                false,
                LifecycleAction::SuppressedMakerIneligible,
            ));
            turn.phase = Some(state.phase);
            turn.game_trade_phase = Some(state.game_trade_phase);
            return turn;
        }

        // Maker-eligible on bound market — decide create / intent / suppress.
        if state.canonical_lifecycle_consumed && state.active_opportunity.is_none() {
            state.suppressed_qualifying_quotes =
                state.suppressed_qualifying_quotes.saturating_add(1);
            turn.quote_observation = Some(Self::obs(
                quote,
                valid.side,
                qualifying.cents(),
                state.game_trade_phase,
                true,
                LifecycleAction::SuppressedByLifecycleConsumed,
            ));
            turn.phase = Some(state.phase);
            turn.game_trade_phase = Some(state.game_trade_phase);
            return turn;
        }

        if ctx.blocks_entry_intent() && state.active_opportunity.is_some() {
            let suppress = if ctx.has_working_entry {
                LifecycleAction::SuppressedByWorkingEntry
            } else if ctx.liquidation_active {
                LifecycleAction::SuppressedByLiquidation
            } else {
                LifecycleAction::SuppressedByPosition
            };
            state.suppressed_qualifying_quotes =
                state.suppressed_qualifying_quotes.saturating_add(1);
            turn.quote_observation = Some(Self::obs(
                quote,
                valid.side,
                qualifying.cents(),
                state.game_trade_phase,
                true,
                suppress,
            ));
            turn.phase = Some(state.phase);
            turn.game_trade_phase = Some(state.game_trade_phase);
            return turn;
        }

        if state.active_opportunity.is_none()
            && (state.canonical_lifecycle_consumed || ctx.blocks_new_opportunity())
        {
            state.suppressed_qualifying_quotes =
                state.suppressed_qualifying_quotes.saturating_add(1);
            let suppress = if state.canonical_lifecycle_consumed {
                LifecycleAction::SuppressedByLifecycleConsumed
            } else if ctx.has_working_entry {
                LifecycleAction::SuppressedByWorkingEntry
            } else {
                LifecycleAction::SuppressedByExistingGameTrade
            };
            turn.quote_observation = Some(Self::obs(
                quote,
                valid.side,
                qualifying.cents(),
                state.game_trade_phase,
                true,
                suppress,
            ));
            turn.phase = Some(state.phase);
            turn.game_trade_phase = Some(state.game_trade_phase);
            return turn;
        }

        let game_raw = quote.game_id.raw();
        let needs_create = self
            .games
            .get(&game_raw)
            .map(|g| g.active_opportunity.is_none() && !g.canonical_lifecycle_consumed)
            .unwrap_or(false)
            && !ctx.blocks_new_opportunity();

        if needs_create {
            let first = self
                .games
                .get(&game_raw)
                .and_then(|g| g.first_observation.clone())
                .expect("first_observation");
            let (confirm_81_ms, confirm_81_px) = {
                let g = self.games.get(&game_raw).expect("game");
                (
                    g.confirmation_81_timestamp_ms
                        .unwrap_or(quote.exchange_timestamp_ms),
                    g.confirmation_81_price_cents.unwrap_or(qualifying.cents()),
                )
            };
            let limit = maker_limit(valid, &self.params).expect("maker eligible");
            let trade_num = self.next_trade_number;
            self.next_trade_number = self.next_trade_number.saturating_add(1);
            let opportunity_id = OpportunityId::new(game_raw, quote.market_id.raw(), valid.side, 0);
            let trade_id = TradeId::numbered(trade_num);
            let opportunity = EntryOpportunity {
                opportunity_id: opportunity_id.clone(),
                trade_id: trade_id.clone(),
                game_id: game_raw,
                market_id: quote.market_id.raw(),
                ticker: quote.ticker.clone(),
                side: valid.side,
                sequence: 0,
                first_80_timestamp_ms: first.exchange_timestamp_ms,
                first_80_price_cents: first.bid_cents,
                confirmation_81_timestamp_ms: confirm_81_ms,
                confirmation_81_price_cents: confirm_81_px,
                qualifying_timestamp_ms: quote.exchange_timestamp_ms,
                qualifying_bid_cents: valid.bid.cents(),
                qualifying_ask_cents: valid.ask.cents(),
                maker_limit_cents: limit.cents(),
                entry_reason: ENTRY_REASON_FIRST01.to_string(),
                lifecycle: OpportunityLifecycle::Open,
                game_trade_phase: GameTradePhase::OpportunityOpen,
            };
            let state = self.games.get_mut(&game_raw).expect("game");
            state.active_opportunity = Some(ActiveOpportunityState {
                opportunity: opportunity.clone(),
                intent_emitted: false,
                intent_count: 0,
                had_position: false,
            });
            state.canonical_lifecycle_consumed = true;
            state.game_trade_phase = GameTradePhase::OpportunityOpen;
            turn.new_opportunity = Some(opportunity);
            action = LifecycleAction::OpportunityCreated;
        }

        let state = self.games.get_mut(&quote.game_id.raw()).expect("game");
        let Some(active) = state.active_opportunity.as_mut() else {
            turn.quote_observation = Some(Self::obs(
                quote,
                valid.side,
                qualifying.cents(),
                state.game_trade_phase,
                true,
                LifecycleAction::SuppressedByExistingGameTrade,
            ));
            turn.phase = Some(state.phase);
            turn.game_trade_phase = Some(state.game_trade_phase);
            return turn;
        };

        let is_remainder = active.intent_emitted && ctx.allows_remainder_intent();
        if active.intent_emitted && !is_remainder {
            state.suppressed_qualifying_quotes =
                state.suppressed_qualifying_quotes.saturating_add(1);
            let suppress = if ctx.has_working_entry {
                LifecycleAction::SuppressedByWorkingEntry
            } else if ctx.position_filled_qty > 0 {
                LifecycleAction::SuppressedByExistingGameTrade
            } else {
                // Unfilled working cleared — same opportunity; do not spawn a new trade.
                LifecycleAction::SuppressedByExistingGameTrade
            };
            turn.quote_observation = Some(Self::obs(
                quote,
                valid.side,
                qualifying.cents(),
                state.game_trade_phase,
                true,
                suppress,
            ));
            turn.phase = Some(state.phase);
            turn.game_trade_phase = Some(state.game_trade_phase);
            return turn;
        }

        if ctx.blocks_entry_intent() && !is_remainder {
            state.suppressed_qualifying_quotes =
                state.suppressed_qualifying_quotes.saturating_add(1);
            turn.quote_observation = Some(Self::obs(
                quote,
                valid.side,
                qualifying.cents(),
                state.game_trade_phase,
                true,
                LifecycleAction::SuppressedByWorkingEntry,
            ));
            turn.phase = Some(state.phase);
            turn.game_trade_phase = Some(state.game_trade_phase);
            return turn;
        }

        let limit = maker_limit(valid, &self.params).expect("maker eligible");
        // Freeze entry quote on first intent; remainder updates limit only.
        if !active.intent_emitted {
            active.opportunity.qualifying_timestamp_ms = quote.exchange_timestamp_ms;
            active.opportunity.qualifying_bid_cents = valid.bid.cents();
            active.opportunity.qualifying_ask_cents = valid.ask.cents();
            active.opportunity.maker_limit_cents = limit.cents();
        } else {
            active.opportunity.maker_limit_cents = limit.cents();
        }

        let intent_seq = active.intent_count;
        let intent = EntryIntent::new(
            &active.opportunity,
            quote.exchange_timestamp_ms,
            quote.received_timestamp,
            self.params.first_threshold_cents,
            self.params.confirmation_threshold_cents,
            self.params.maximum_entry_price_cents,
            is_remainder,
            intent_seq,
        );
        active.intent_emitted = true;
        active.intent_count = active.intent_count.saturating_add(1);
        active.opportunity.lifecycle = OpportunityLifecycle::IntentEmitted;
        active.opportunity.game_trade_phase = GameTradePhase::EntryWorking;
        state.game_trade_phase = GameTradePhase::EntryWorking;

        if action != LifecycleAction::OpportunityCreated {
            action = LifecycleAction::IntentEmitted;
        }

        turn.quote_observation = Some(Self::obs(
            quote,
            valid.side,
            qualifying.cents(),
            state.game_trade_phase,
            true,
            action,
        ));
        turn.intents.push(intent.clone());
        turn.signals.push(intent_to_signal(&intent));
        turn.phase = Some(state.phase);
        turn.game_trade_phase = Some(state.game_trade_phase);
        turn
    }

    fn obs(
        quote: &StrategyQuote,
        side: momento_core::Side,
        qualifying: u16,
        phase: GameTradePhase,
        qualifies: bool,
        action: LifecycleAction,
    ) -> QuoteObservation {
        QuoteObservation {
            strategy: FIRST01_NAME.to_string(),
            strategy_version: FIRST01_VERSION,
            game_id: quote.game_id.raw(),
            market_id: quote.market_id.raw(),
            ticker: quote.ticker.clone(),
            side,
            exchange_timestamp_ms: quote.exchange_timestamp_ms,
            received_timestamp: quote.received_timestamp,
            bid_cents: quote.yes_bid_cents,
            ask_cents: quote.yes_ask_cents,
            qualifying_bid_cents: qualifying,
            entry_phase: phase,
            qualifies_first01: qualifies,
            lifecycle_action: action,
        }
    }

    fn sync_trade_lifecycle(state: &mut GameEntryState, ctx: &EntryContext) {
        if let Some(active) = state.active_opportunity.as_mut() {
            if ctx.position_net_qty > 0 || ctx.position_filled_qty > 0 {
                active.had_position = true;
            }
            if ctx.liquidation_active {
                active.opportunity.lifecycle = OpportunityLifecycle::LiquidationActive;
                active.opportunity.game_trade_phase = GameTradePhase::LiquidationActive;
                state.game_trade_phase = GameTradePhase::LiquidationActive;
            } else if ctx.has_working_entry && ctx.position_filled_qty > 0 {
                active.opportunity.lifecycle = OpportunityLifecycle::PartiallyFilled;
                active.opportunity.game_trade_phase = GameTradePhase::PartiallyFilled;
                state.game_trade_phase = GameTradePhase::PartiallyFilled;
            } else if ctx.has_working_entry {
                active.opportunity.lifecycle = OpportunityLifecycle::EntryWorking;
                active.opportunity.game_trade_phase = GameTradePhase::EntryWorking;
                state.game_trade_phase = GameTradePhase::EntryWorking;
            } else if ctx.position_net_qty > 0 {
                active.opportunity.lifecycle = OpportunityLifecycle::PositionOpen;
                active.opportunity.game_trade_phase = GameTradePhase::PositionOpen;
                state.game_trade_phase = GameTradePhase::PositionOpen;
            } else if active.intent_emitted
                && active.had_position
                && (ctx.position_entry_closed || ctx.position_net_qty == 0)
            {
                // Live: Flat/OpenComplete permanently blocks re-entry; keep consumed sticky.
                active.opportunity.lifecycle = OpportunityLifecycle::TradeComplete;
                active.opportunity.game_trade_phase = GameTradePhase::TradeComplete;
                state.game_trade_phase = GameTradePhase::TradeComplete;
                state.canonical_lifecycle_consumed = true;
            } else if active.intent_emitted
                && !active.had_position
                && !ctx.has_working_entry
                && ctx.position_filled_qty == 0
            {
                // Unfilled order ended — same opportunity remains; no new trade.
                active.opportunity.lifecycle = OpportunityLifecycle::Unfilled;
                active.opportunity.game_trade_phase = GameTradePhase::Unfilled;
                state.game_trade_phase = GameTradePhase::Unfilled;
                state.canonical_lifecycle_consumed = true;
            }
        } else if state.phase != EntryPhase::GameLocked && !state.canonical_lifecycle_consumed {
            state.game_trade_phase = if ctx.game_trade_active() {
                GameTradePhase::EntryWorking
            } else {
                GameTradePhase::NoTrade
            };
        }
    }
}

fn intent_to_signal(intent: &EntryIntent) -> EntrySignal {
    EntrySignal {
        strategy: intent.strategy.clone(),
        strategy_version: intent.strategy_version,
        market_id: intent.market_id,
        ticker: intent.ticker.clone(),
        game_id: intent.game_id,
        side: intent.side,
        exchange_timestamp_ms: intent.exchange_timestamp_ms,
        received_timestamp: intent.received_timestamp,
        signal_price_cents: intent.maker_limit_cents,
        first_threshold_cents: intent.first_threshold_cents,
        confirmation_threshold_cents: intent.confirmation_threshold_cents,
        maximum_entry_price_cents: intent.maximum_entry_price_cents,
        bid_cents: intent.bid_cents,
        ask_cents: intent.ask_cents,
        maker_eligible: true,
    }
}

/// Serializable snapshot for persistence tests.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EntryObservation {
    pub game_id: GameId,
    pub market_id: MarketId,
    pub phase: EntryPhase,
    pub first: Option<FirstObservation>,
    pub confirmed: bool,
}

impl EntryEngine {
    pub fn snapshot_game(&self, game: GameId) -> EntryObservation {
        let g = self.games.get(&game.raw());
        EntryObservation {
            game_id: game,
            market_id: g
                .and_then(|s| {
                    s.first_observation
                        .as_ref()
                        .map(|f| MarketId::from_raw(f.key.market_id))
                })
                .unwrap_or(MarketId::from_raw(0)),
            phase: g.map(|s| s.phase).unwrap_or(EntryPhase::Watching),
            first: g.and_then(|s| s.first_observation.clone()),
            confirmed: g.map(|s| s.confirmed).unwrap_or(false),
        }
    }

    pub fn restore_game(&mut self, obs: EntryObservation) {
        self.games.insert(
            obs.game_id.raw(),
            GameEntryState {
                phase: obs.phase,
                first_observation: obs.first,
                confirmed: obs.confirmed,
                confirmation_81_timestamp_ms: None,
                confirmation_81_price_cents: None,
                paused_above_max: false,
                last_exchange_ms: None,
                last_bid: None,
                last_ask: None,
                canonical_lifecycle_consumed: false,
                active_opportunity: None,
                game_trade_phase: GameTradePhase::NoTrade,
                suppressed_qualifying_quotes: 0,
            },
        );
    }
}
