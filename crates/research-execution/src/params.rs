//! Explicit execution-model configuration.

use serde::{Deserialize, Serialize};

pub const EXECUTION_MODEL_NAME: &str = "CONSERVATIVE_MAKER";
pub const EXECUTION_MODEL_VERSION: u32 = 1;

/// How queue priority ahead of our resting order is modeled.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum QueueModel {
    /// Existing displayed quantity at our limit price is assumed ahead of us.
    Conservative,
}

/// How maker entry fills are inferred from historical evidence.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MakerFillModel {
    /// Use displayed opposite-side liquidity; consume queue ahead first.
    DisplayedLiquidityWithQueue,
}

/// How liquidation (exit) fills are inferred.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum LiquidationFillModel {
    /// Sell into displayed YES bid depth at the executable best bid.
    BestBidDepth,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum FeesModel {
    NotModeled,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MarkModel {
    /// Mark open positions at last valid executable YES bid for the exact market.
    LastExecutableYesBid,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutionParameters {
    pub execution_model_name: String,
    pub execution_model_version: u32,
    pub queue_model: QueueModel,
    pub allow_partial_fills: bool,
    pub maker_fill_model: MakerFillModel,
    pub liquidation_fill_model: LiquidationFillModel,
    pub fees_model: FeesModel,
    pub mark_model: MarkModel,
    /// Research bankroll snapshot in USD cents ($50 = 5000).
    pub bankroll_snapshot_cents: i64,
    /// Position allocation numerator (12.5% = 125/1000).
    pub allocation_numerator: u32,
    pub allocation_denominator: u32,
}

impl Default for ExecutionParameters {
    fn default() -> Self {
        Self {
            execution_model_name: EXECUTION_MODEL_NAME.to_string(),
            execution_model_version: EXECUTION_MODEL_VERSION,
            queue_model: QueueModel::Conservative,
            allow_partial_fills: true,
            maker_fill_model: MakerFillModel::DisplayedLiquidityWithQueue,
            liquidation_fill_model: LiquidationFillModel::BestBidDepth,
            fees_model: FeesModel::NotModeled,
            mark_model: MarkModel::LastExecutableYesBid,
            bankroll_snapshot_cents: 5_000,
            allocation_numerator: 125,
            allocation_denominator: 1_000,
        }
    }
}

impl ExecutionParameters {
    /// Fee-inclusive economic budget for one position (integer USD cents).
    pub fn position_budget_cents(&self) -> i64 {
        self.bankroll_snapshot_cents
            .saturating_mul(i64::from(self.allocation_numerator))
            / i64::from(self.allocation_denominator.max(1))
    }

    /// Maximum whole contracts affordable at `limit_price_cents`.
    pub fn requested_quantity(&self, limit_price_cents: u16) -> u32 {
        if limit_price_cents == 0 {
            return 0;
        }
        let budget = self.position_budget_cents();
        u32::try_from(budget / i64::from(limit_price_cents)).unwrap_or(0)
    }
}
