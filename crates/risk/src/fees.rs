//! Injectable venue fee estimation.
//!
//! **Zero fees are a temporary paper placeholder.**
//! They MUST NOT be interpreted as confirmed Kalshi economics.
//!
//! Replace [`ZeroFeeModel`] with a documented `KalshiFeeModel` later without
//! rewriting the risk engine.

use momento_core::{Contracts, FeeModelId, Money, Price};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FeeEstimateError {
    Overflow,
}

/// Estimates fees for risk reservation. Not an order router.
pub trait FeeModel: Send + Sync + Clone {
    fn model_id(&self) -> FeeModelId;

    fn estimate_entry_fee(
        &self,
        quantity: Contracts,
        price: Price,
    ) -> Result<Money, FeeEstimateError>;

    fn estimate_liquidation_fee(
        &self,
        quantity: Contracts,
        price: Price,
    ) -> Result<Money, FeeEstimateError>;
}

/// Temporary paper/infrastructure placeholder.
///
/// This is **not** the Kalshi fee schedule. A later `KalshiFeeModel` must
/// replace this implementation after official venue documentation is inspected.
#[derive(Clone, Copy, Debug, Default)]
pub struct ZeroFeeModel;

impl FeeModel for ZeroFeeModel {
    fn model_id(&self) -> FeeModelId {
        FeeModelId::zero_placeholder()
    }

    fn estimate_entry_fee(
        &self,
        _quantity: Contracts,
        _price: Price,
    ) -> Result<Money, FeeEstimateError> {
        Ok(Money::ZERO)
    }

    fn estimate_liquidation_fee(
        &self,
        _quantity: Contracts,
        _price: Price,
    ) -> Result<Money, FeeEstimateError> {
        Ok(Money::ZERO)
    }
}

/// Size a maker entry given remaining economic capacity and a fee model.
///
/// Re-estimates fees after choosing quantity so a non-zero model can shrink qty.
pub fn size_entry<F: FeeModel>(
    remaining: Money,
    price: Price,
    fees: &F,
) -> Result<(Contracts, Money, Money), FeeEstimateError> {
    use momento_core::arithmetic::{contract_premium, max_contracts_for_budget};

    let mut qty = max_contracts_for_budget(remaining, price, Money::ZERO)
        .map_err(|_| FeeEstimateError::Overflow)?;
    if qty.get() == 0 {
        return Ok((qty, Money::ZERO, Money::ZERO));
    }
    let mut fee = fees.estimate_entry_fee(qty, price)?;
    qty =
        max_contracts_for_budget(remaining, price, fee).map_err(|_| FeeEstimateError::Overflow)?;
    fee = fees.estimate_entry_fee(qty, price)?;
    if qty.get() == 0 {
        return Ok((qty, Money::ZERO, fee));
    }
    let premium = contract_premium(qty, price).map_err(|_| FeeEstimateError::Overflow)?;
    Ok((qty, premium, fee))
}
