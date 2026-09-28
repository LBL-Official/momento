//! First upward YES-bid cross of `entry`, then REACH of win or loss.

use std::collections::HashMap;

use momento_core::{
    AdditionalExposure, BuildPositionIntent, Contracts, EntryStyle, GameId, KillSwitch,
    LiquidationReason, MarketEvent, MarketId, Position, PositionId, Price, ReconciliationState,
    Side, StrategyId, TradeIntent,
};
use serde::{Deserialize, Serialize};

pub const RESEARCH_ITI_STRATEGY_ID: StrategyId = StrategyId::RESEARCH_ITI;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ItiPrices {
    pub entry: Price,
    pub win: Price,
    pub loss: Price,
}

impl ItiPrices {
    pub fn from_cents(
        entry: u16,
        win: u16,
        loss: u16,
    ) -> Result<Self, momento_core::error::PriceError> {
        Ok(Self {
            entry: Price::from_cents(entry)?,
            win: Price::from_cents(win)?,
            loss: Price::from_cents(loss)?,
        })
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ItiGamePhase {
    Watching,
    EntryProposed,
    PositionOpen,
    ReachWin,
    ReachLoss,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ItiGameSnapshot {
    pub game_id: GameId,
    pub phase: ItiGamePhase,
    pub last_yes_bid: Option<Price>,
    pub entry_limit: Option<Price>,
    pub assigned_position_id: Option<PositionId>,
    pub reach_emitted: bool,
}

impl ItiGameSnapshot {
    pub fn new(game_id: GameId) -> Self {
        Self {
            game_id,
            phase: ItiGamePhase::Watching,
            last_yes_bid: None,
            entry_limit: None,
            assigned_position_id: None,
            reach_emitted: false,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ItiStrategySnapshot {
    pub prices: ItiPriceRecord,
    pub games: Vec<ItiGameSnapshot>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ItiPriceRecord {
    pub entry_cents: u16,
    pub win_cents: u16,
    pub loss_cents: u16,
}

pub struct ItiContext<'a> {
    pub event: &'a MarketEvent,
    pub position: Option<&'a Position>,
    pub assigned_position_id: Option<PositionId>,
    pub recon: ReconciliationState,
    pub kill_switch: KillSwitch,
    pub has_working_entry: bool,
    pub unknown_entry_order: bool,
    pub has_working_liquidation: bool,
    pub unknown_liquidation_order: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ItiDirective {
    Build(TradeIntent),
    ExecuteReach(ReachExecution),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ReachExecution {
    pub game_id: GameId,
    pub position_id: PositionId,
    pub market_id: MarketId,
    pub side: Side,
    pub quantity: Contracts,
    pub suggested_limit: Price,
    pub reason: LiquidationReason,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ItiIssue {
    MissingYesBid,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ItiTurn {
    pub directives: Vec<ItiDirective>,
    pub issue: Option<ItiIssue>,
}

#[derive(Clone, Debug)]
pub struct ItiStrategy {
    strategy_id: StrategyId,
    prices: ItiPrices,
    games: HashMap<u128, ItiGameSnapshot>,
}

impl ItiStrategy {
    pub fn new(prices: ItiPrices) -> Self {
        Self {
            strategy_id: RESEARCH_ITI_STRATEGY_ID,
            prices,
            games: HashMap::new(),
        }
    }

    pub fn strategy_id(&self) -> StrategyId {
        self.strategy_id
    }

    pub fn prices(&self) -> ItiPrices {
        self.prices
    }

    pub fn snapshot(&self) -> ItiStrategySnapshot {
        let mut games: Vec<_> = self.games.values().cloned().collect();
        games.sort_by_key(|g| g.game_id.raw());
        ItiStrategySnapshot {
            prices: ItiPriceRecord {
                entry_cents: self.prices.entry.cents(),
                win_cents: self.prices.win.cents(),
                loss_cents: self.prices.loss.cents(),
            },
            games,
        }
    }

    pub fn restore(snapshot: ItiStrategySnapshot) -> Result<Self, momento_core::error::PriceError> {
        let prices = ItiPrices::from_cents(
            snapshot.prices.entry_cents,
            snapshot.prices.win_cents,
            snapshot.prices.loss_cents,
        )?;
        let mut games = HashMap::new();
        for game in snapshot.games {
            games.insert(game.game_id.raw(), game);
        }
        Ok(Self {
            strategy_id: RESEARCH_ITI_STRATEGY_ID,
            prices,
            games,
        })
    }

    pub fn phase(&self, game: GameId) -> ItiGamePhase {
        self.games
            .get(&game.raw())
            .map(|g| g.phase)
            .unwrap_or(ItiGamePhase::Watching)
    }

    pub fn observe(&mut self, ctx: &ItiContext<'_>) -> ItiTurn {
        let mut turn = ItiTurn::default();
        let Some(bid) = ctx.event.bid else {
            turn.issue = Some(ItiIssue::MissingYesBid);
            return turn;
        };
        if ctx.event.side != Some(Side::Yes) && ctx.event.side.is_some() {
            return turn;
        }
        let state = self
            .games
            .entry(ctx.event.game_id.raw())
            .or_insert_with(|| ItiGameSnapshot::new(ctx.event.game_id));
        if let Some(position_id) = ctx.assigned_position_id {
            state.assigned_position_id = Some(position_id);
        }

        let prior = state.last_yes_bid;
        let crossed = prior.is_some_and(|p| p.cents() < self.prices.entry.cents())
            && bid.cents() >= self.prices.entry.cents();
        let filled = ctx.position.map(|p| p.filled_quantity().get()).unwrap_or(0);
        if filled > 0
            && !matches!(
                state.phase,
                ItiGamePhase::ReachWin | ItiGamePhase::ReachLoss
            )
        {
            state.phase = ItiGamePhase::PositionOpen;
        }

        if matches!(state.phase, ItiGamePhase::Watching) && crossed {
            if ctx.recon.blocks_new_exposure()
                || ctx.kill_switch.is_tripped()
                || ctx.has_working_entry
                || ctx.unknown_entry_order
            {
                state.last_yes_bid = Some(bid);
                return turn;
            }
            let Some(position_id) = ctx.assigned_position_id else {
                state.last_yes_bid = Some(bid);
                return turn;
            };
            let intent = TradeIntent::build(BuildPositionIntent {
                strategy_id: self.strategy_id,
                game_id: ctx.event.game_id,
                market_id: ctx.event.market_id,
                side: Side::Yes,
                position_id,
                limit_price: bid,
                style: EntryStyle::MakerOnly,
                additional: AdditionalExposure::RemainderOfApprovedBudget,
            });
            state.entry_limit = Some(bid);
            state.phase = ItiGamePhase::EntryProposed;
            turn.directives.push(ItiDirective::Build(intent));
        }

        if matches!(
            state.phase,
            ItiGamePhase::PositionOpen | ItiGamePhase::EntryProposed
        ) && filled > 0
            && !state.reach_emitted
            && !ctx.has_working_liquidation
            && !ctx.unknown_liquidation_order
        {
            let reason = if bid.cents() >= self.prices.win.cents() {
                Some(LiquidationReason::ReachWin)
            } else if bid.cents() <= self.prices.loss.cents() {
                Some(LiquidationReason::ReachLoss)
            } else {
                None
            };
            if let (Some(reason), Some(position)) = (reason, ctx.position) {
                if let (Some(market_id), Some(side)) = (position.market_id(), position.side()) {
                    state.reach_emitted = true;
                    state.phase = match reason {
                        LiquidationReason::ReachWin => ItiGamePhase::ReachWin,
                        LiquidationReason::ReachLoss => ItiGamePhase::ReachLoss,
                        LiquidationReason::StopLoss => ItiGamePhase::PositionOpen,
                    };
                    turn.directives
                        .push(ItiDirective::ExecuteReach(ReachExecution {
                            game_id: ctx.event.game_id,
                            position_id: position.id(),
                            market_id,
                            side,
                            quantity: position.filled_quantity(),
                            suggested_limit: bid,
                            reason,
                        }));
                }
            }
        }

        state.last_yes_bid = Some(bid);
        turn
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use momento_core::{ExchangeTimestamp, Money, ReceivedAt, SnapshotId, utc_now};

    fn prices() -> ItiPrices {
        ItiPrices::from_cents(20, 60, 10).unwrap()
    }

    fn event(bid: u16, game: u128) -> MarketEvent {
        let t = utc_now();
        MarketEvent {
            game_id: GameId::from_raw(game),
            market_id: MarketId::from_raw(2),
            side: Some(Side::Yes),
            exchange_ts: ExchangeTimestamp::from_utc(t),
            received_at: ReceivedAt::from_utc(t),
            last: None,
            bid: Some(Price::from_cents(bid).unwrap()),
            ask: Some(Price::from_cents(bid.saturating_add(1).min(99)).unwrap()),
            mid: None,
            bid_depth: Some(4),
            ask_depth: Some(4),
            game_state: None,
        }
    }

    fn ctx<'a>(event: &'a MarketEvent, position: Option<&'a Position>) -> ItiContext<'a> {
        ItiContext {
            event,
            position,
            assigned_position_id: Some(PositionId::from_raw(1)),
            recon: ReconciliationState::Healthy,
            kill_switch: KillSwitch::Armed,
            has_working_entry: false,
            unknown_entry_order: false,
            has_working_liquidation: false,
            unknown_liquidation_order: false,
        }
    }

    fn empty_position() -> Position {
        Position::new_for_game(
            PositionId::from_raw(1),
            GameId::from_raw(10),
            RESEARCH_ITI_STRATEGY_ID,
            SnapshotId::from_raw(1),
            Money::from_cents(625),
            Some(MarketId::from_raw(2)),
            Some(Side::Yes),
        )
    }

    fn observe_bid(strategy: &mut ItiStrategy, bid: u16) -> ItiTurn {
        let ev = event(bid, 10);
        let pos = empty_position();
        strategy.observe(&ctx(&ev, Some(&pos)))
    }

    #[test]
    fn no_cross_does_not_enter() {
        let mut s = ItiStrategy::new(prices());
        assert!(observe_bid(&mut s, 15).directives.is_empty());
        assert!(observe_bid(&mut s, 18).directives.is_empty());
        assert_eq!(s.phase(GameId::from_raw(10)), ItiGamePhase::Watching);
    }

    #[test]
    fn exact_20_after_below_enters_at_20() {
        let mut s = ItiStrategy::new(prices());
        assert!(observe_bid(&mut s, 19).directives.is_empty());
        let turn = observe_bid(&mut s, 20);
        match &turn.directives[..] {
            [ItiDirective::Build(intent)] => assert_eq!(intent.build.limit_price.cents(), 20),
            other => panic!("expected build, got {other:?}"),
        }
    }

    #[test]
    fn gap_through_40_enters_at_observed_bid() {
        let mut s = ItiStrategy::new(prices());
        assert!(observe_bid(&mut s, 19).directives.is_empty());
        let turn = observe_bid(&mut s, 40);
        match &turn.directives[..] {
            [ItiDirective::Build(intent)] => assert_eq!(intent.build.limit_price.cents(), 40),
            other => panic!("expected build at 40, got {other:?}"),
        }
    }

    #[test]
    fn already_above_at_start_does_not_enter() {
        let mut s = ItiStrategy::new(prices());
        assert!(observe_bid(&mut s, 25).directives.is_empty());
        assert!(observe_bid(&mut s, 40).directives.is_empty());
        assert_eq!(s.phase(GameId::from_raw(10)), ItiGamePhase::Watching);
    }

    #[test]
    fn win_60_emits_reach_win() {
        let mut s = ItiStrategy::new(prices());
        let ev_below = event(19, 10);
        let ev_cross = event(20, 10);
        let ev_win = event(60, 10);
        let empty = empty_position();
        let _ = s.observe(&ctx(&ev_below, Some(&empty)));
        let _ = s.observe(&ctx(&ev_cross, Some(&empty)));
        let filled = filled_position();
        let turn = s.observe(&ctx(&ev_win, Some(&filled)));
        match &turn.directives[..] {
            [ItiDirective::ExecuteReach(exec)] => {
                assert_eq!(exec.reason, LiquidationReason::ReachWin);
                assert_eq!(exec.suggested_limit.cents(), 60);
            }
            other => panic!("expected reach win, got {other:?}"),
        }
    }

    #[test]
    fn loss_10_emits_reach_loss() {
        let mut s = ItiStrategy::new(prices());
        let ev_below = event(19, 10);
        let ev_cross = event(20, 10);
        let ev_loss = event(10, 10);
        let empty = empty_position();
        let _ = s.observe(&ctx(&ev_below, Some(&empty)));
        let _ = s.observe(&ctx(&ev_cross, Some(&empty)));
        let filled = filled_position();
        let turn = s.observe(&ctx(&ev_loss, Some(&filled)));
        match &turn.directives[..] {
            [ItiDirective::ExecuteReach(exec)] => {
                assert_eq!(exec.reason, LiquidationReason::ReachLoss);
                assert_eq!(exec.suggested_limit.cents(), 10);
            }
            other => panic!("expected reach loss, got {other:?}"),
        }
    }

    fn filled_position() -> Position {
        use momento_core::{ClientOrderId, Contracts, Fee, FeeKind, Fill, FillId};
        let mut pos = empty_position();
        let t = utc_now();
        pos.apply_entry_fill(Fill::new(
            FillId::generate(),
            pos.id(),
            ClientOrderId::from_raw(9),
            None,
            Contracts::from_u32(1),
            Price::from_cents(20).unwrap(),
            Money::from_cents(20),
            Fee::zero(FeeKind::Entry),
            ExchangeTimestamp::from_utc(t),
            ReceivedAt::from_utc(t),
        ))
        .unwrap();
        pos
    }
}
