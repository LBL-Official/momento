use serde::{Deserialize, Serialize};

use crate::error::ArithmeticError;
use crate::fill::Fill;
use crate::money::Price;

/// Price basis in hundredths of a cent.
///
/// `80.00¢ = 8000`. `40.50¢ = 4050`.
///
/// MLB 50% stop uses this scale so `81¢ → 40.5¢` does not require `f64`.
/// Trigger comparison: integer-cent YES bid converted to hundredths
/// (`bid.cents() * 100`) is `<=` half of VWAP hundredths (integer division).
/// Executable liquidation price is the venue's current best YES bid, which
/// already sits on Kalshi's tick grid.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct BasisPrice {
    hundredths_of_cent: u32,
}

impl BasisPrice {
    pub const fn from_hundredths_of_cent(v: u32) -> Self {
        Self {
            hundredths_of_cent: v,
        }
    }

    pub fn from_price(price: Price) -> Self {
        Self {
            hundredths_of_cent: u32::from(price.cents()) * 100,
        }
    }

    pub const fn hundredths_of_cent(self) -> u32 {
        self.hundredths_of_cent
    }
}

/// Computes the stop/entry basis from actual entry fills.
pub trait EntryBasisCalculator {
    fn basis(&self, entry_fills: &[Fill]) -> Option<BasisPrice>;
}

/// VWAP of actual entry fills. Submitted quantity and limit prices are ignored.
#[derive(Clone, Copy, Debug, Default)]
pub struct ProposedVwapEntryBasis;

impl EntryBasisCalculator for ProposedVwapEntryBasis {
    fn basis(&self, entry_fills: &[Fill]) -> Option<BasisPrice> {
        let mut qty: u64 = 0;
        let mut premium_cents: u128 = 0;
        for fill in entry_fills {
            qty = qty.checked_add(u64::from(fill.quantity().get()))?;
            let p = u128::try_from(fill.premium().cents()).ok()?;
            premium_cents = premium_cents.checked_add(p)?;
        }
        if qty == 0 {
            return None;
        }
        // VWAP in hundredths of a cent: (premium_cents * 100) / qty.
        let hundredths = premium_cents.checked_mul(100)? / u128::from(qty);
        let hundredths = u32::try_from(hundredths).ok()?;
        Some(BasisPrice::from_hundredths_of_cent(hundredths))
    }
}

pub trait StopThresholdPolicy {
    fn threshold(&self, basis: BasisPrice) -> Result<BasisPrice, ArithmeticError>;
}

/// 50% of VWAP basis. Integer division of hundredths-of-cent.
#[derive(Clone, Copy, Debug, Default)]
pub struct ProposedHalfEntryStop;

impl StopThresholdPolicy for ProposedHalfEntryStop {
    fn threshold(&self, basis: BasisPrice) -> Result<BasisPrice, ArithmeticError> {
        Ok(BasisPrice::from_hundredths_of_cent(
            basis.hundredths_of_cent() / 2,
        ))
    }
}

/// Authoritative MLB stop threshold from actual entry fills.
pub fn half_entry_stop_from_fills(entry_fills: &[Fill]) -> Option<BasisPrice> {
    let basis = ProposedVwapEntryBasis.basis(entry_fills)?;
    ProposedHalfEntryStop.threshold(basis).ok()
}

/// True when the integer-cent YES bid has reached or gone through the 50% stop.
pub fn yes_bid_reaches_stop(bid: Price, stop: BasisPrice) -> bool {
    u32::from(bid.cents()).saturating_mul(100) <= stop.hundredths_of_cent()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fee::{Fee, FeeKind};
    use crate::ids::{ClientOrderId, FillId, PositionId};
    use crate::money::{Contracts, Money};
    use crate::time::{ExchangeTimestamp, ReceivedAt};
    use chrono::{TimeZone, Utc};

    fn ts() -> (ExchangeTimestamp, ReceivedAt) {
        let t = Utc
            .with_ymd_and_hms(2026, 8, 24, 18, 0, 0)
            .single()
            .unwrap();
        (ExchangeTimestamp::from_utc(t), ReceivedAt::from_utc(t))
    }

    fn entry_fill(qty: u32, cents: u16, raw: u128) -> Fill {
        let (ex, recv) = ts();
        let price = Price::from_cents(cents).unwrap();
        let premium = Money::from_cents(i64::from(qty) * i64::from(cents));
        Fill::new(
            FillId::from_raw(raw),
            PositionId::from_raw(1),
            ClientOrderId::from_raw(raw),
            None,
            Contracts::from_u32(qty),
            price,
            premium,
            Fee::zero(FeeKind::Entry),
            ex,
            recv,
        )
    }

    #[test]
    fn seven_at_80_and_three_at_82_half_stop_is_40_30() {
        let fills = [entry_fill(7, 80, 1), entry_fill(3, 82, 2)];
        let stop = half_entry_stop_from_fills(&fills).unwrap();
        // VWAP = 80.60¢ → 50% = 40.30¢ = 4030 hundredths.
        assert_eq!(stop.hundredths_of_cent(), 4030);
        assert!(yes_bid_reaches_stop(Price::from_cents(40).unwrap(), stop));
        assert!(!yes_bid_reaches_stop(Price::from_cents(41).unwrap(), stop));
    }

    #[test]
    fn submitted_quantity_is_not_the_basis() {
        let fills = [entry_fill(3, 80, 1)];
        let stop = half_entry_stop_from_fills(&fills).unwrap();
        assert_eq!(stop.hundredths_of_cent(), 4000);
    }
}
