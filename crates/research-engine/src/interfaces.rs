//! Research-plane contracts. These do not submit venue orders.
//!
//! B1 v1 is a snapshot HOLD_TO_SETTLEMENT wrap. A tick-level replay clock
//! is not invented here; W8 observational replay remains the event source.

/// Strategy identity. Parameters live on the experiment, not in this type.
pub trait ResearchStrategy: Send + Sync {
    fn id(&self) -> &'static str;
    fn version(&self) -> &'static str;
    fn family(&self) -> &'static str;
    fn production_status(&self) -> &'static str;
}

/// First research family. Not a production trading strategy.
pub struct B1HoldToSettlement;

impl ResearchStrategy for B1HoldToSettlement {
    fn id(&self) -> &'static str {
        "B1"
    }
    fn version(&self) -> &'static str {
        "B1.ENGINE.1.1.0"
    }
    fn family(&self) -> &'static str {
        "first-exact-83 HOLD_TO_SETTLEMENT"
    }
    fn production_status(&self) -> &'static str {
        "NONE"
    }
}

/// How a research fill is modeled. Do not invent L2 or live POST from these.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ExecutionModel {
    /// Observed TRADE print used as modeled entry. Not a confirmed fill.
    TradePrintModeled,
}

impl ExecutionModel {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::TradePrintModeled => "TRADE_PRINT_MODELED",
        }
    }
}

/// Integer-cent research portfolio snapshot. Same conceptual fields as live
/// accounting; values come from modeled B1 P&L, not venue positions.
#[derive(Clone, Debug, Default)]
pub struct ResearchPortfolioSnapshot {
    pub cash_cents: i64,
    pub realized_pnl_cents: i64,
    pub unrealized_pnl_cents: i64,
    pub fees_cents: i64,
    pub slippage_cents: i64,
    pub exposure_cents: i64,
    pub drawdown_cents: i64,
    pub open_contracts: i64,
}

/// Live execution is a typed hole. Research jobs must not construct this.
pub struct LiveExecutionGate;

impl LiveExecutionGate {
    pub fn may_submit() -> bool {
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn b1_is_not_production() {
        assert_eq!(B1HoldToSettlement.production_status(), "NONE");
        assert!(!LiveExecutionGate::may_submit());
        assert_eq!(
            ExecutionModel::TradePrintModeled.as_str(),
            "TRADE_PRINT_MODELED"
        );
    }
}
