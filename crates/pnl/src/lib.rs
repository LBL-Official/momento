//! P&L foundation. Realized P&L is derived from fills, fees, and settlement
//! events only. This crate does not implement Kalshi fee or settlement formulas.

#![forbid(unsafe_code)]

use momento_core::{FeeKind, Money, Position, PositionLifecycle, Price};

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct RealizedPnl(Money);

impl RealizedPnl {
    pub const fn from_money(money: Money) -> Self {
        Self(money)
    }

    pub const fn as_money(self) -> Money {
        self.0
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct UnrealizedPnl(Money);

impl UnrealizedPnl {
    pub const fn from_money(money: Money) -> Self {
        Self(money)
    }

    pub const fn as_money(self) -> Money {
        self.0
    }
}

/// Entry and liquidation fees must be recorded separately before combining into P&L.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct FeeTotals {
    pub entry: Money,
    pub liquidation: Money,
}

impl FeeTotals {
    pub fn total(self) -> Result<Money, momento_core::error::ArithmeticError> {
        self.entry.checked_add(self.liquidation)
    }
}

/// Ledger of P&L components. None of these fields is inferred from submission.
///
/// `realized_pnl` is `None` until an authoritative settlement event exists or
/// actual liquidation fills have flattened the position. Unrealized P&L is
/// never invented from an assumed mark.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct PnlBreakdown {
    pub entry_cost: Money,
    pub entry_fees: Money,
    pub liquidation_proceeds: Money,
    pub liquidation_fees: Money,
    pub settlement_proceeds: Option<Money>,
    pub realized_pnl: Option<RealizedPnl>,
    pub unrealized_pnl: Option<UnrealizedPnl>,
    pub total_fees: Money,
}

impl PnlBreakdown {
    pub fn from_position(position: &Position) -> Self {
        let mut entry_cost = Money::ZERO;
        let mut entry_fees = Money::ZERO;
        let mut liquidation_proceeds = Money::ZERO;
        let mut liquidation_fees = Money::ZERO;

        for fill in position.fill_history() {
            match fill.fee().kind() {
                FeeKind::Entry => {
                    entry_cost = entry_cost.checked_add(fill.premium()).unwrap_or(entry_cost);
                    entry_fees = entry_fees
                        .checked_add(fill.fee().amount())
                        .unwrap_or(entry_fees);
                }
                FeeKind::Liquidation => {
                    liquidation_proceeds = liquidation_proceeds
                        .checked_add(fill.premium())
                        .unwrap_or(liquidation_proceeds);
                    liquidation_fees = liquidation_fees
                        .checked_add(fill.fee().amount())
                        .unwrap_or(liquidation_fees);
                }
            }
        }

        let total_fees = entry_fees
            .checked_add(liquidation_fees)
            .unwrap_or(entry_fees);
        let settlement_proceeds = position.settlement_proceeds();

        let realized_pnl = if let Some(settlement) = settlement_proceeds {
            realized_from_components(entry_cost, liquidation_proceeds, settlement, total_fees)
        } else if position.lifecycle() == PositionLifecycle::Flat
            && position.filled_quantity() == momento_core::Contracts::ZERO
        {
            realized_from_components(entry_cost, liquidation_proceeds, Money::ZERO, total_fees)
        } else {
            None
        };

        Self {
            entry_cost,
            entry_fees,
            liquidation_proceeds,
            liquidation_fees,
            settlement_proceeds,
            realized_pnl,
            unrealized_pnl: None,
            total_fees,
        }
    }

    /// Mark-to-market is UNRESOLVED. Do not invent a Kalshi mid or last as P&L.
    pub fn unrealized_with_unverified_mark(&self, _mark: Price) -> Option<UnrealizedPnl> {
        None
    }
}

fn realized_from_components(
    entry_cost: Money,
    liquidation_proceeds: Money,
    settlement_proceeds: Money,
    total_fees: Money,
) -> Option<RealizedPnl> {
    let credits = liquidation_proceeds.checked_add(settlement_proceeds).ok()?;
    let costs = entry_cost.checked_add(total_fees).ok()?;
    credits.checked_sub(costs).ok().map(RealizedPnl::from_money)
}
