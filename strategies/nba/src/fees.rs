//! Kalshi trading fees in integer centicents ($0.0001).
//!
//! Sources (read 2026-09-27): Kalshi fee schedule (7.7.26 update) and
//! docs.kalshi.com/getting_started/fee_rounding.
//!
//! - taker fee = ceil(0.07 × M × C × P × (1 − P))
//! - maker fee = ceil(0.0175 × M × C × P × (1 − P)), only when the series
//!   `fee_type` is `quadratic_with_maker_fees`; `quadratic` charges makers 0
//! - the trade fee is rounded up to $0.000001, then a per-order rounding fee
//!   aligns the balance to $0.0001 (direct member) or $0.01 (non-direct); the
//!   accumulator runs across every fill of one order, so the order total never
//!   exceeds the single-fill ceiling below
//!
//! Anything else (`flat`, combo maker fees, unread type) is `Unsupported`.
//! A bound is not a confirmed fee.

use momento_core::{Contracts, Money, Price};
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct FeeSchedule {
    /// Coefficient as a rational, e.g. 0.07 = 7/100.
    pub coef_num: i64,
    pub coef_den: i64,
    /// Series `fee_multiplier` in thousandths (1 → 1000, 0.5 → 500).
    pub multiplier_milli: i64,
    /// True only after the fee facts are verified (FEES.md).
    pub verified: bool,
}

impl FeeSchedule {
    /// 0.07 taker coefficient; series multiplier as observed.
    pub fn taker_bound(multiplier_milli: i64) -> Self {
        Self {
            coef_num: 7,
            coef_den: 100,
            multiplier_milli,
            verified: false,
        }
    }
}

/// Parses a Kalshi `fee_multiplier` (JSON number or string) into thousandths.
pub fn multiplier_milli(raw: &serde_json::Value) -> Option<i64> {
    let text = match raw {
        serde_json::Value::Number(n) => n.to_string(),
        serde_json::Value::String(s) => s.trim().to_string(),
        _ => return None,
    };
    let (whole, frac) = text.split_once('.').unwrap_or((text.as_str(), ""));
    if frac.len() > 3 || whole.is_empty() {
        return None;
    }
    let whole: i64 = whole.parse().ok()?;
    let mut frac_digits = frac.to_string();
    while frac_digits.len() < 3 {
        frac_digits.push('0');
    }
    let frac: i64 = frac_digits.parse().ok()?;
    if whole < 0 {
        return None;
    }
    whole.checked_mul(1000)?.checked_add(frac)
}

pub fn fee_bound_cents(qty: Contracts, price: Price, schedule: &FeeSchedule) -> Option<Money> {
    let p = i128::from(price.cents());
    if p <= 0 || p >= 100 || schedule.coef_den <= 0 || schedule.multiplier_milli < 0 {
        return None;
    }
    // cents = coef × mult × C × P × (100 − P) / 100, with mult in thousandths.
    let numerator = i128::from(schedule.coef_num)
        .checked_mul(i128::from(schedule.multiplier_milli))?
        .checked_mul(i128::from(qty.get()))?
        .checked_mul(p)?
        .checked_mul(100 - p)?;
    let denominator = i128::from(schedule.coef_den).checked_mul(100 * 1000)?;
    let cents = (numerator + denominator - 1) / denominator;
    i64::try_from(cents).ok().map(Money::from_cents)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Liquidity {
    Maker,
    Taker,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FeeType {
    Quadratic,
    QuadraticWithMakerFees,
    QuadraticWithComboMakerFees,
    Flat,
}

impl FeeType {
    pub fn parse(raw: &str) -> Option<Self> {
        match raw.trim() {
            "quadratic" => Some(Self::Quadratic),
            "quadratic_with_maker_fees" => Some(Self::QuadraticWithMakerFees),
            "quadratic_with_combo_maker_fees" => Some(Self::QuadraticWithComboMakerFees),
            "flat" => Some(Self::Flat),
            _ => None,
        }
    }
}

/// Balance precision of the account. Direct members settle to $0.0001.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum BalancePrecision {
    Centicent,
    Cent,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum FeeError {
    /// Fee type not modelled; do not guess.
    Unsupported,
    InvalidPrice,
    Overflow,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct FeeModel {
    pub fee_type: FeeType,
    pub multiplier_milli: i64,
    pub precision: BalancePrecision,
}

impl FeeModel {
    pub fn new(fee_type: FeeType, multiplier_milli: i64, precision: BalancePrecision) -> Self {
        Self {
            fee_type,
            multiplier_milli,
            precision,
        }
    }

    /// Coefficient as (num, den): 0.07 = 7/100, 0.0175 = 7/400, 0 = 0/1.
    fn coefficient(&self, liq: Liquidity) -> Result<(i128, i128), FeeError> {
        match (self.fee_type, liq) {
            (FeeType::Quadratic | FeeType::QuadraticWithMakerFees, Liquidity::Taker) => {
                Ok((7, 100))
            }
            (FeeType::QuadraticWithMakerFees, Liquidity::Maker) => Ok((7, 400)),
            (FeeType::Quadratic, Liquidity::Maker) => Ok((0, 1)),
            _ => Err(FeeError::Unsupported),
        }
    }

    /// Worst-case fee in centicents for one order of `qty` filled at `price`.
    pub fn order_fee_centicents(
        &self,
        liq: Liquidity,
        qty: u32,
        price_cents: u16,
    ) -> Result<i64, FeeError> {
        let p = i128::from(price_cents);
        if !(1..=99).contains(&p) || self.multiplier_milli < 0 {
            return Err(FeeError::InvalidPrice);
        }
        let (num, den) = self.coefficient(liq)?;
        // centicents = coef × M × C × p × (100 − p), with M in thousandths.
        let numerator = num
            .checked_mul(i128::from(self.multiplier_milli))
            .and_then(|v| v.checked_mul(i128::from(qty)))
            .and_then(|v| v.checked_mul(p))
            .and_then(|v| v.checked_mul(100 - p))
            .ok_or(FeeError::Overflow)?;
        let denominator = den.checked_mul(1000).ok_or(FeeError::Overflow)?;
        let mut cc = (numerator + denominator - 1) / denominator;
        if self.precision == BalancePrecision::Cent {
            cc = (cc + 99) / 100 * 100;
        }
        i64::try_from(cc).map_err(|_| FeeError::Overflow)
    }

    /// Worst-case fee when fills may land anywhere in `[lo, hi]` cents
    /// (a marketable order sweeping levels). P(1−P) peaks at 50.
    pub fn order_fee_bound_over(
        &self,
        liq: Liquidity,
        qty: u32,
        lo: u16,
        hi: u16,
    ) -> Result<i64, FeeError> {
        if lo == 0 || hi > 99 || lo > hi {
            return Err(FeeError::InvalidPrice);
        }
        let worst = 50u16.clamp(lo, hi);
        self.order_fee_centicents(liq, qty, worst)
    }
}

/// Centicents rounded up to whole cents (reservations never round down).
pub fn centicents_to_cents_ceil(cc: i64) -> i64 {
    if cc >= 0 { (cc + 99) / 100 } else { cc / 100 }
}
