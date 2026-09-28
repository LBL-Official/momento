use crate::error::ArithmeticError;
use crate::money::{Contracts, Money, Price};

/// `contracts * price_cents` as USD cents of premium.
pub fn contract_premium(qty: Contracts, price: Price) -> Result<Money, ArithmeticError> {
    let cents = i128::from(qty.get())
        .checked_mul(i128::from(price.cents()))
        .ok_or(ArithmeticError::Overflow)?;
    let cents = i64::try_from(cents).map_err(|_| ArithmeticError::Overflow)?;
    Ok(Money::from_cents(cents))
}

/// Maximum whole contracts purchasable with `budget` at `price` after reserving `entry_fee`.
///
/// `entry_fee` MUST come from an injected `FeeModel` estimate, not a hardcoded
/// assumption that venue fees are zero.
pub fn max_contracts_for_budget(
    budget: Money,
    price: Price,
    estimated_entry_fee: Money,
) -> Result<Contracts, ArithmeticError> {
    let available = budget.checked_sub(estimated_entry_fee)?;
    if available.cents() <= 0 {
        return Ok(Contracts::ZERO);
    }
    let px = i64::from(price.cents());
    if px == 0 {
        return Err(ArithmeticError::DivisionByZero);
    }
    let n = available.cents() / px;
    if n <= 0 {
        return Ok(Contracts::ZERO);
    }
    let n = u32::try_from(n).map_err(|_| ArithmeticError::Overflow)?;
    Ok(Contracts::from_u32(n))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn three_contracts_at_80_is_240_cents() {
        let premium =
            contract_premium(Contracts::from_u32(3), Price::from_cents(80).unwrap()).unwrap();
        assert_eq!(premium, Money::from_usd(2, 40).unwrap());
    }
}
