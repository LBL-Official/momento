//! Admission reserve: principal + entry fee bound + the maximum approved exit
//! cost across the normal ladder and emergency execution + exit fee bound.
//! Exact in centicents; `total` rounds up to whole cents.

use momento_core::{Contracts, Money, Price};
use serde::{Deserialize, Serialize};

use crate::fees::{FeeModel, Liquidity, centicents_to_cents_ceil};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ExitBound {
    /// Owner-approved worst price for an emergency opponent-YES buy.
    Bounded { worst_price_cents: u16 },
    /// Owner-approved reduce-only IOC sale of the reconciled original
    /// residual, never below `floor_cents`. A sale needs no cash.
    SellOriginal { floor_cents: u16 },
    /// Emergency action or bound not approved.
    Unbounded,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EntryReserve {
    pub qty: Contracts,
    pub principal: Money,
    pub entry_liquidity: Liquidity,
    pub entry_fee_centicents: i64,
    pub entry_fee_bound: Money,
    pub exit_price_cents: u16,
    pub exit_cost: Money,
    pub exit_fee_centicents: i64,
    pub exit_fee_bound: Money,
    pub total_centicents: i64,
    pub total: Money,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ReserveError {
    ExitCapacityUnbounded,
    /// Sizing reference or series fee data not read.
    InputUnread,
    /// Series fee type is not one the model supports.
    FeeUnsupported,
    InvalidPrice,
    Overflow,
}

pub fn reserve_for_entry(
    qty: Contracts,
    entry_price: Price,
    entry_liquidity: Liquidity,
    ladder_cap: Price,
    emergency: ExitBound,
    fees: &FeeModel,
) -> Result<EntryReserve, ReserveError> {
    let exit_cents = match emergency {
        ExitBound::Unbounded => return Err(ReserveError::ExitCapacityUnbounded),
        ExitBound::Bounded { worst_price_cents } => worst_price_cents.max(ladder_cap.cents()),
        ExitBound::SellOriginal { .. } => ladder_cap.cents(),
    };
    let q = i64::from(qty.get());
    let principal_c = q
        .checked_mul(i64::from(entry_price.cents()))
        .ok_or(ReserveError::Overflow)?;
    let exit_c = q
        .checked_mul(i64::from(exit_cents))
        .ok_or(ReserveError::Overflow)?;
    let fee = |liq, price| {
        fees.order_fee_centicents(liq, qty.get(), price)
            .map_err(|e| match e {
                crate::fees::FeeError::Unsupported => ReserveError::FeeUnsupported,
                crate::fees::FeeError::InvalidPrice => ReserveError::InvalidPrice,
                crate::fees::FeeError::Overflow => ReserveError::Overflow,
            })
    };
    let entry_fee_cc = fee(entry_liquidity, entry_price.cents())?;
    // Hedge and emergency legs are marketable: taker, worst at the limit (< 50).
    let exit_fee_cc = fee(Liquidity::Taker, exit_cents)?;
    let total_cc = principal_c
        .checked_mul(100)
        .and_then(|v| v.checked_add(entry_fee_cc))
        .and_then(|v| v.checked_add(exit_c.checked_mul(100)?))
        .and_then(|v| v.checked_add(exit_fee_cc))
        .ok_or(ReserveError::Overflow)?;
    Ok(EntryReserve {
        qty,
        principal: Money::from_cents(principal_c),
        entry_liquidity,
        entry_fee_centicents: entry_fee_cc,
        entry_fee_bound: Money::from_cents(centicents_to_cents_ceil(entry_fee_cc)),
        exit_price_cents: exit_cents,
        exit_cost: Money::from_cents(exit_c),
        exit_fee_centicents: exit_fee_cc,
        exit_fee_bound: Money::from_cents(centicents_to_cents_ceil(exit_fee_cc)),
        total_centicents: total_cc,
        total: Money::from_cents(centicents_to_cents_ceil(total_cc)),
    })
}
