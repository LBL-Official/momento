//! MLB 80/81/89 strategy. Emits intents; does not submit orders or call Kalshi.

use std::collections::HashMap;

use momento_core::{
    AdditionalExposure, AuditEvent, AuditMeta, BasisPrice, BuildPositionIntent, Contracts,
    EntryBasisCalculator, EntryStyle, GameId, KillSwitch, MarketEvent, MarketId, Position,
    PositionExitCause, PositionId, PositionLifecycle, Price, ProposedVwapEntryBasis,
    ReconciliationState, Side, StrategyId, TradeIntent,
};

use crate::quote::{
    QuoteReject, ValidQuote, above_max_entry, maker_limit, qualifying_price, reaches_81,
    reaches_89, reaches_first_80, validate_quote,
};
use crate::state::{
    FirstTrigger, MlbGamePhase, MlbGameSnapshot, MlbStrategySnapshot, QuoteFingerprint,
};
use crate::stop::{
    loss_reduction_in_progress, quote_is_position_stop_eligible, stop_threshold,
    yes_bid_triggers_stop,
};

pub const MLB_STRATEGY_ID: StrategyId = StrategyId::MLB;

#[derive(Clone, Debug)]
pub struct MlbContext<'a> {
    pub event: &'a MarketEvent,
    pub position: Option<&'a Position>,
    pub assigned_position_id: Option<PositionId>,
    pub recon: ReconciliationState,
    pub kill_switch: KillSwitch,
    pub data_stale: bool,
    pub has_working_entry: bool,
    pub unknown_entry_order: bool,
    pub has_working_liquidation: bool,
    pub unknown_liquidation_order: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum MlbDirective {
    Build(TradeIntent),
    CancelRemainingEntries {
        game_id: GameId,
        position_id: Option<PositionId>,
    },
    PauseEntry {
        game_id: GameId,
    },
    StopWatch(StopWatchSignal),
    ExecuteStop(StopExecution),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StopWatchSignal {
    pub game_id: GameId,
    pub position_id: PositionId,
    /// VWAP of actual entry fills.
    pub proposed_basis: Option<momento_core::BasisPrice>,
    pub rounding: StopRounding,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StopRounding {
    /// 50% of VWAP hundredths-of-cent, integer division.
    HalfOfVwapHundredths,
}

/// Strategy proposes reduce-only liquidation. Host/Risk/Execution submit it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StopExecution {
    pub game_id: GameId,
    pub position_id: PositionId,
    pub market_id: MarketId,
    pub side: Side,
    pub quantity: Contracts,
    pub suggested_limit: Price,
    pub basis: BasisPrice,
    pub threshold: BasisPrice,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MlbIssue {
    InsufficientQuote(QuoteReject),
    ContradictoryEventOrdering,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct MlbTurn {
    pub directives: Vec<MlbDirective>,
    pub audit: Vec<AuditEvent>,
    pub issue: Option<MlbIssue>,
}

#[derive(Clone, Debug)]
pub struct MlbStrategy {
    strategy_id: StrategyId,
    games: HashMap<u128, MlbGameSnapshot>,
}

impl Default for MlbStrategy {
    fn default() -> Self {
        Self::new()
    }
}

impl MlbStrategy {
    pub fn new() -> Self {
        Self::for_strategy(MLB_STRATEGY_ID)
    }

    /// Same 80/81/89 machine with a caller-supplied strategy identity.
    /// Production MLB continues to use [`Self::new`].
    pub fn for_strategy(strategy_id: StrategyId) -> Self {
        Self {
            strategy_id,
            games: HashMap::new(),
        }
    }

    pub fn strategy_id(&self) -> StrategyId {
        self.strategy_id
    }

    pub fn snapshot(&self) -> MlbStrategySnapshot {
        let mut games: Vec<_> = self.games.values().cloned().collect();
        games.sort_by_key(|g| g.game_id.raw());
        MlbStrategySnapshot { games }
    }

    pub fn restore(snapshot: MlbStrategySnapshot) -> Self {
        Self::restore_for(MLB_STRATEGY_ID, snapshot)
    }

    pub fn restore_for(strategy_id: StrategyId, snapshot: MlbStrategySnapshot) -> Self {
        let mut games = HashMap::new();
        for g in snapshot.games {
            games.insert(g.game_id.raw(), g);
        }
        Self { strategy_id, games }
    }

    pub fn phase(&self, game: GameId) -> MlbGamePhase {
        self.games
            .get(&game.raw())
            .map(|g| g.phase)
            .unwrap_or(MlbGamePhase::Watching)
    }

    pub fn first_80(&self, game: GameId) -> Option<&FirstTrigger> {
        self.games
            .get(&game.raw())
            .and_then(|g| g.first_80.as_ref())
    }

    pub fn first_89(&self, game: GameId) -> Option<&FirstTrigger> {
        self.games
            .get(&game.raw())
            .and_then(|g| g.first_89.as_ref())
    }

    pub fn paused_above_max(&self, game: GameId) -> bool {
        self.games
            .get(&game.raw())
            .map(|g| g.paused_above_max)
            .unwrap_or(false)
    }

    pub fn ordering_ambiguous(&self, game: GameId) -> bool {
        self.games
            .get(&game.raw())
            .map(|g| g.ordering_ambiguous)
            .unwrap_or(false)
    }

    pub fn observe(&mut self, ctx: &MlbContext<'_>) -> MlbTurn {
        let game_id = ctx.event.game_id;
        let mut turn = MlbTurn::default();
        let state = self
            .games
            .entry(game_id.raw())
            .or_insert_with(|| MlbGameSnapshot::new(game_id));

        if let Some(pid) = ctx
            .assigned_position_id
            .or_else(|| ctx.position.map(|p| p.id()))
        {
            if let Some(existing) = state.assigned_position_id {
                if existing != pid {
                    state.phase = MlbGamePhase::NotEligible;
                    return turn;
                }
            } else if state.phase != MlbGamePhase::GameLocked {
                state.assigned_position_id = Some(pid);
            }
        }

        if ctx
            .position
            .map(|p| p.game_lock().is_locked())
            .unwrap_or(false)
        {
            state.phase = MlbGamePhase::GameLocked;
        }

        if state.phase == MlbGamePhase::GameLocked {
            return Self::locked_turn(state, ctx);
        }

        let quote = match validate_quote(ctx.event, ctx.data_stale) {
            Ok(q) => q,
            Err(reject) => {
                if matches!(
                    state.phase,
                    MlbGamePhase::Watching | MlbGamePhase::NotEligible
                ) {
                    state.phase = MlbGamePhase::Watching;
                }
                turn.issue = Some(MlbIssue::InsufficientQuote(reject));
                return turn;
            }
        };

        // Stop protection is independent of 80/81/89 entry sequencing.
        Self::maybe_execute_stop(ctx, quote, &mut turn);

        let qualifying = qualifying_price(quote);
        let fingerprint = QuoteFingerprint {
            exchange_ts: ctx.event.exchange_ts,
            side: quote.side,
            bid: quote.bid.cents(),
            ask: quote.ask.cents(),
            mid: qualifying.cents(),
        };
        if state.last_fingerprint == Some(fingerprint) {
            Self::maybe_execute_stop(ctx, quote, &mut turn);
            return turn;
        }
        state.last_fingerprint = Some(fingerprint);

        if let Some(prev) = state.last_exchange_ts {
            if ctx.event.exchange_ts < prev && reaches_89(qualifying) {
                state.ordering_ambiguous = true;
                turn.issue = Some(MlbIssue::ContradictoryEventOrdering);
            }
        }
        state.last_exchange_ts = Some(ctx.event.exchange_ts);

        if reaches_89(qualifying) {
            let relevant = match &state.first_80 {
                None => true,
                Some(first) => quote.side == first.side && ctx.event.market_id == first.market_id,
            };
            if relevant {
                Self::apply_first_89(state, ctx, quote, &mut turn);
                return turn;
            }
        }

        if state.first_80.is_none() {
            if reaches_first_80(qualifying) {
                Self::record_first_80(state, ctx, quote, &mut turn);
            } else {
                state.phase = MlbGamePhase::Watching;
                Self::maybe_execute_stop(ctx, quote, &mut turn);
                return turn;
            }
        } else if let Some(first) = &state.first_80 {
            if quote.side != first.side || ctx.event.market_id != first.market_id {
                Self::refresh_phase(state, ctx);
                Self::maybe_execute_stop(ctx, quote, &mut turn);
                return turn;
            }
        }

        if !state.confirmed_81 {
            state.phase = MlbGamePhase::WaitingFor81Confirmation;
            if let Some(first) = &state.first_80 {
                if quote.side == first.side
                    && ctx.event.market_id == first.market_id
                    && reaches_81(qualifying)
                {
                    state.confirmed_81 = true;
                    turn.audit.push(AuditEvent::First81Confirmed {
                        meta: AuditMeta::now(),
                        game_id,
                        market_id: ctx.event.market_id,
                        exchange_ts: ctx.event.exchange_ts,
                        received_at: ctx.event.received_at,
                    });
                } else {
                    Self::maybe_execute_stop(ctx, quote, &mut turn);
                    return turn;
                }
            }
        }

        Self::maybe_pause_or_enter(self.strategy_id, state, ctx, quote, &mut turn);
        turn
    }

    fn record_first_80(
        state: &mut MlbGameSnapshot,
        ctx: &MlbContext<'_>,
        quote: ValidQuote,
        turn: &mut MlbTurn,
    ) {
        let trigger = FirstTrigger::capture(ctx.event, quote);
        turn.audit.push(AuditEvent::First80Observed {
            meta: AuditMeta::now(),
            game_id: trigger.game_id,
            market_id: trigger.market_id,
            exchange_ts: trigger.exchange_ts,
            received_at: trigger.received_at,
            mid: None,
            bid: Some(trigger.bid),
            ask: Some(trigger.ask),
        });
        state.first_80 = Some(trigger);
        state.phase = MlbGamePhase::First80Triggered;
    }

    fn apply_first_89(
        state: &mut MlbGameSnapshot,
        ctx: &MlbContext<'_>,
        quote: ValidQuote,
        turn: &mut MlbTurn,
    ) {
        if state.first_89.is_none() {
            let trigger = FirstTrigger::capture(ctx.event, quote);
            turn.audit.push(AuditEvent::First89Observed {
                meta: AuditMeta::now(),
                game_id: trigger.game_id,
                market_id: trigger.market_id,
                exchange_ts: trigger.exchange_ts,
                received_at: trigger.received_at,
            });
            state.first_89 = Some(trigger);
        }
        state.phase = MlbGamePhase::GameLocked;
        state.paused_above_max = false;
        let position_id = ctx.position.map(|p| p.id()).or(state.assigned_position_id);
        turn.audit.push(AuditEvent::GameLocked {
            meta: AuditMeta::now(),
            game_id: ctx.event.game_id,
            position_id: position_id.unwrap_or(PositionId::from_raw(0)),
            exchange_ts: ctx.event.exchange_ts,
            received_at: ctx.event.received_at,
        });
        if ctx.has_working_entry || ctx.unknown_entry_order {
            turn.directives.push(MlbDirective::CancelRemainingEntries {
                game_id: ctx.event.game_id,
                position_id,
            });
        }
        if state.ordering_ambiguous {
            turn.issue = Some(MlbIssue::ContradictoryEventOrdering);
        }
        Self::maybe_execute_stop(ctx, quote, turn);
    }

    fn locked_turn(state: &MlbGameSnapshot, ctx: &MlbContext<'_>) -> MlbTurn {
        let mut turn = MlbTurn::default();
        if ctx.has_working_entry {
            turn.directives.push(MlbDirective::CancelRemainingEntries {
                game_id: ctx.event.game_id,
                position_id: ctx.position.map(|p| p.id()).or(state.assigned_position_id),
            });
        }
        if let Ok(quote) = validate_quote(ctx.event, ctx.data_stale) {
            Self::maybe_execute_stop(ctx, quote, &mut turn);
        }
        turn
    }

    fn maybe_pause_or_enter(
        strategy_id: StrategyId,
        state: &mut MlbGameSnapshot,
        ctx: &MlbContext<'_>,
        quote: ValidQuote,
        turn: &mut MlbTurn,
    ) {
        Self::maybe_execute_stop(ctx, quote, turn);
        if turn
            .directives
            .iter()
            .any(|d| matches!(d, MlbDirective::ExecuteStop(_)))
        {
            Self::maybe_stop_watch(state, ctx, turn);
            return;
        }
        if above_max_entry(qualifying_price(quote)) {
            state.paused_above_max = true;
            Self::refresh_phase(state, ctx);
            turn.directives.push(MlbDirective::PauseEntry {
                game_id: ctx.event.game_id,
            });
            Self::maybe_stop_watch(state, ctx, turn);
            return;
        }
        state.paused_above_max = false;
        Self::refresh_phase(state, ctx);

        if ctx.kill_switch.is_tripped()
            || ctx.recon.blocks_new_exposure()
            || ctx.unknown_entry_order
        {
            Self::maybe_stop_watch(state, ctx, turn);
            return;
        }
        if ctx.has_working_entry {
            Self::maybe_stop_watch(state, ctx, turn);
            return;
        }
        if matches!(
            ctx.position.map(|p| p.lifecycle()),
            Some(
                PositionLifecycle::Settled
                    | PositionLifecycle::StopTriggered
                    | PositionLifecycle::LiquidationActive
                    | PositionLifecycle::SettlementPending
            )
        ) {
            Self::maybe_stop_watch(state, ctx, turn);
            return;
        }

        let Some(limit) = maker_limit(quote) else {
            Self::maybe_stop_watch(state, ctx, turn);
            return;
        };
        if state.phase == MlbGamePhase::PositionOpen {
            Self::maybe_stop_watch(state, ctx, turn);
            return;
        }
        if !matches!(
            state.phase,
            MlbGamePhase::EntryEligible | MlbGamePhase::PositionBuilding
        ) {
            return;
        }

        let Some(position_id) = ctx
            .assigned_position_id
            .or_else(|| ctx.position.map(|p| p.id()))
            .or(state.assigned_position_id)
        else {
            return;
        };
        let side = state
            .first_80
            .as_ref()
            .map(|t| t.side)
            .unwrap_or(quote.side);
        let market_id = state
            .first_80
            .as_ref()
            .map(|t| t.market_id)
            .unwrap_or(ctx.event.market_id);

        let intent = TradeIntent::build(BuildPositionIntent {
            strategy_id,
            game_id: ctx.event.game_id,
            market_id,
            side,
            position_id,
            limit_price: limit,
            style: EntryStyle::MakerOnly,
            additional: AdditionalExposure::RemainderOfApprovedBudget,
        });
        turn.directives.push(MlbDirective::Build(intent));
        Self::maybe_stop_watch(state, ctx, turn);
    }

    fn refresh_phase(state: &mut MlbGameSnapshot, ctx: &MlbContext<'_>) {
        if state.phase == MlbGamePhase::GameLocked {
            return;
        }
        if state.first_80.is_none() {
            state.phase = MlbGamePhase::Watching;
            return;
        }
        if !state.confirmed_81 {
            state.phase = MlbGamePhase::WaitingFor81Confirmation;
            return;
        }
        let filled = ctx.position.map(|p| p.filled_quantity().get()).unwrap_or(0);
        let remaining = ctx
            .position
            .and_then(|p| p.actionable_remaining_entry().ok())
            .map(|m| m.cents())
            .unwrap_or(1);
        if filled > 0 && remaining <= 0 {
            state.phase = MlbGamePhase::PositionOpen;
        } else if filled > 0 || ctx.has_working_entry {
            state.phase = MlbGamePhase::PositionBuilding;
        } else {
            state.phase = MlbGamePhase::EntryEligible;
        }
    }

    fn maybe_stop_watch(state: &mut MlbGameSnapshot, ctx: &MlbContext<'_>, turn: &mut MlbTurn) {
        let Some(pos) = ctx.position else {
            return;
        };
        if pos.filled_quantity().get() == 0 || state.stop_watch_emitted {
            return;
        }
        let Ok(quote) = validate_quote(ctx.event, ctx.data_stale) else {
            return;
        };
        if !quote_is_position_stop_eligible(pos, ctx.event, quote) {
            return;
        }
        let entry_fills: Vec<_> = pos
            .fill_history()
            .iter()
            .filter(|f| f.is_entry_fee())
            .cloned()
            .collect();
        let proposed_basis = ProposedVwapEntryBasis.basis(&entry_fills);
        state.stop_watch_emitted = true;
        turn.directives
            .push(MlbDirective::StopWatch(StopWatchSignal {
                game_id: ctx.event.game_id,
                position_id: pos.id(),
                proposed_basis,
                rounding: StopRounding::HalfOfVwapHundredths,
            }));
        let _ = PositionExitCause::StopLoss;
    }

    fn maybe_execute_stop(ctx: &MlbContext<'_>, quote: ValidQuote, turn: &mut MlbTurn) {
        if turn
            .directives
            .iter()
            .any(|d| matches!(d, MlbDirective::ExecuteStop(_)))
        {
            return;
        }
        let Some(pos) = ctx.position else {
            return;
        };
        if matches!(
            pos.lifecycle(),
            PositionLifecycle::Settled | PositionLifecycle::Flat
        ) {
            return;
        }
        if pos.filled_quantity().get() == 0 {
            return;
        }
        if ctx.has_working_liquidation || ctx.unknown_liquidation_order {
            return;
        }
        if !quote_is_position_stop_eligible(pos, ctx.event, quote) {
            return;
        }
        let Some(market_id) = pos.market_id() else {
            return;
        };
        let Some(side) = pos.side() else {
            return;
        };
        let entry_fills: Vec<_> = pos
            .fill_history()
            .iter()
            .filter(|f| f.is_entry_fee())
            .cloned()
            .collect();
        let reducing = loss_reduction_in_progress(pos);
        if !reducing && !yes_bid_triggers_stop(quote.bid, &entry_fills) {
            return;
        }
        let Some(threshold) = stop_threshold(&entry_fills) else {
            return;
        };
        let Some(basis) = ProposedVwapEntryBasis.basis(&entry_fills) else {
            return;
        };
        let position_id = pos.id();
        if !reducing {
            turn.audit.push(AuditEvent::StopTriggered {
                meta: AuditMeta::now(),
                position_id,
                game_id: ctx.event.game_id,
            });
        }
        turn.directives
            .push(MlbDirective::ExecuteStop(StopExecution {
                game_id: ctx.event.game_id,
                position_id,
                market_id,
                side,
                quantity: pos.filled_quantity(),
                suggested_limit: quote.bid,
                basis,
                threshold,
            }));
    }
}
