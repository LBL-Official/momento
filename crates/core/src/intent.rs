//! Strategy expresses desired exposure. It never submits venue orders.

use serde::{Deserialize, Serialize};

use crate::ids::{ClientOrderId, GameId, MarketId, PositionId, StrategyId};
use crate::market::Side;
use crate::money::{Money, Price};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum EntryStyle {
    MakerOnly,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum LiquidationStyle {
    /// Official Kalshi Create V2: `side=ask`, `reduce_only=true`,
    /// `post_only=false`, `time_in_force=immediate_or_cancel`, limit at the
    /// current best YES bid (hit standing bids). Not a market-order endpoint.
    AggressiveReduce,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum LiquidationReason {
    StopLoss,
    ReachWin,
    ReachLoss,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum AdditionalExposure {
    RemainderOfApprovedBudget,
    NotMoreThan(Money),
}

/// "Build this position toward the approved target." Not a Kalshi order.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct BuildPositionIntent {
    pub strategy_id: StrategyId,
    pub game_id: GameId,
    pub market_id: MarketId,
    pub side: Side,
    pub position_id: PositionId,
    pub limit_price: Price,
    pub style: EntryStyle,
    pub additional: AdditionalExposure,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct TradeIntent {
    pub build: BuildPositionIntent,
}

impl TradeIntent {
    pub fn build(build: BuildPositionIntent) -> Self {
        Self { build }
    }
}

/// Stop/liquidation is not a strategy discretionary exit.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct LiquidationIntent {
    pub position_id: PositionId,
    pub game_id: GameId,
    pub market_id: MarketId,
    pub side: Side,
    pub client_order_id: ClientOrderId,
    pub reason: LiquidationReason,
    pub style: LiquidationStyle,
}
