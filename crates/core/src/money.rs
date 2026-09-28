//! Exact financial types.
//!
//! Representations (do not mix these types):
//! - [`Money`]: USD integer cents. `$1.00 = 100`. `$6.25 = 625`.
//! - [`Price`]: contract price in integer cents. `80` = 80¢ per contract.
//! - [`Contracts`]: integer contract count.
//! - [`Bps`]: basis points. `12.5% = 1250`.
//! - [`EconomicExposure`]: USD cents of fill premium (not fees).
//!
//! No `f64` is used. Arithmetic is checked.

use crate::error::{ArithmeticError, MoneyError, PriceError};
use serde::{Deserialize, Serialize};

/// USD amount as integer cents. `$50.00 = 5000`.
#[derive(
    Clone, Copy, Debug, Default, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize,
)]
pub struct Money {
    cents: i64,
}

impl Money {
    pub const ZERO: Self = Self { cents: 0 };

    pub const fn from_cents(cents: i64) -> Self {
        Self { cents }
    }

    /// `$dollars.cents` with `cents` in `0..100`.
    pub const fn from_usd(dollars: i64, cents: u8) -> Result<Self, MoneyError> {
        if cents >= 100 {
            return Err(MoneyError::InvalidCents);
        }
        let dollar_cents = match dollars.checked_mul(100) {
            Some(v) => v,
            None => return Err(MoneyError::Overflow),
        };
        match dollar_cents.checked_add(cents as i64) {
            Some(total) => Ok(Self { cents: total }),
            None => Err(MoneyError::Overflow),
        }
    }

    pub const fn cents(self) -> i64 {
        self.cents
    }

    pub fn checked_add(self, other: Self) -> Result<Self, ArithmeticError> {
        self.cents
            .checked_add(other.cents)
            .map(Self::from_cents)
            .ok_or(ArithmeticError::Overflow)
    }

    pub fn checked_sub(self, other: Self) -> Result<Self, ArithmeticError> {
        self.cents
            .checked_sub(other.cents)
            .map(Self::from_cents)
            .ok_or(ArithmeticError::Overflow)
    }

    /// `self * bps / 10_000`. Example: `$50 * 1250 bps = $6.25`.
    pub fn checked_mul_bps(self, bps: Bps) -> Result<Self, ArithmeticError> {
        let product = (self.cents as i128)
            .checked_mul(i128::from(bps.get()))
            .ok_or(ArithmeticError::Overflow)?;
        let q = product / 10_000;
        let cents = i64::try_from(q).map_err(|_| ArithmeticError::Overflow)?;
        Ok(Self { cents })
    }

    pub fn saturating_sub(self, other: Self) -> Self {
        Self {
            cents: self.cents.saturating_sub(other.cents),
        }
    }
}

impl std::fmt::Display for Money {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let sign = if self.cents < 0 { "-" } else { "" };
        let abs = self.cents.unsigned_abs();
        write!(f, "{sign}${}.{:02}", abs / 100, abs % 100)
    }
}

/// Contract price in integer cents. `80` = 80¢. Valid range `0..=100`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct Price {
    cents: u16,
}

impl Price {
    pub const fn from_cents(cents: u16) -> Result<Self, PriceError> {
        if cents > 100 {
            Err(PriceError::OutOfRange { cents })
        } else {
            Ok(Self { cents })
        }
    }

    pub const fn cents(self) -> u16 {
        self.cents
    }
}

impl std::fmt::Display for Price {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}¢", self.cents)
    }
}

/// Integer contract quantity.
#[derive(
    Clone, Copy, Debug, Default, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize,
)]
pub struct Contracts {
    qty: u32,
}

impl Contracts {
    pub const ZERO: Self = Self { qty: 0 };

    pub const fn from_u32(qty: u32) -> Self {
        Self { qty }
    }

    pub const fn get(self) -> u32 {
        self.qty
    }

    pub fn checked_add(self, other: Self) -> Result<Self, ArithmeticError> {
        self.qty
            .checked_add(other.qty)
            .map(Self::from_u32)
            .ok_or(ArithmeticError::Overflow)
    }

    pub fn checked_sub(self, other: Self) -> Result<Self, ArithmeticError> {
        self.qty
            .checked_sub(other.qty)
            .map(Self::from_u32)
            .ok_or(ArithmeticError::Overflow)
    }
}

/// Basis points. `12.5% = 1250`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct Bps {
    bps: u32,
}

impl Bps {
    pub const ZERO: Self = Self { bps: 0 };
    /// 12.5% allocation (MLB per-game). `$50 × 1250 bps = $6.25`.
    pub const PCT_12_5: Self = Self { bps: 1250 };
    /// 8.33% allocation (WNBA per-game) as integer basis points.
    ///
    /// 8.33% cannot be represented as a terminating cent on a $50 snapshot:
    /// `$50.00 × 833 / 10_000 = 4_165_000 / 10_000 = 416` cents via truncating
    /// integer division (`$4.16`). Exact 8.33% of $50 is $4.165. This constant
    /// never rounds up.
    pub const PCT_8_33: Self = Self { bps: 833 };

    pub const fn from_bps(bps: u32) -> Self {
        Self { bps }
    }

    pub const fn get(self) -> u32 {
        self.bps
    }
}

/// USD cents of contract premium from fills. Fees are tracked separately.
#[derive(
    Clone, Copy, Debug, Default, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize,
)]
pub struct EconomicExposure {
    premium: Money,
}

impl EconomicExposure {
    pub const ZERO: Self = Self {
        premium: Money::ZERO,
    };

    pub const fn from_money(premium: Money) -> Self {
        Self { premium }
    }

    pub const fn as_money(self) -> Money {
        self.premium
    }

    pub fn checked_add(self, other: Self) -> Result<Self, ArithmeticError> {
        Ok(Self {
            premium: self.premium.checked_add(other.premium)?,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fifty_times_12_5_percent_is_six_25() {
        let bankroll = Money::from_usd(50, 0).expect("bankroll");
        let budget = bankroll.checked_mul_bps(Bps::PCT_12_5).expect("mul");
        assert_eq!(budget, Money::from_usd(6, 25).expect("6.25"));
    }

    #[test]
    fn fifty_times_8_33_percent_truncates_to_four_16() {
        let bankroll = Money::from_usd(50, 0).expect("bankroll");
        let budget = bankroll.checked_mul_bps(Bps::PCT_8_33).expect("mul");
        assert_eq!(budget.cents(), 416);
        assert_eq!(budget, Money::from_usd(4, 16).expect("4.16"));
        assert!(budget.cents() < 417);
    }

    #[test]
    fn money_rejects_invalid_cents() {
        assert!(Money::from_usd(1, 100).is_err());
    }

    #[test]
    fn price_rejects_above_100() {
        assert!(Price::from_cents(101).is_err());
        assert!(Price::from_cents(100).is_ok());
    }
}
