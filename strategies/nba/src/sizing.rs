//! `C = floor(floor(E × 600 / 10_000) / p)`. Fees are extra. Never shrinks.

use momento_core::{Bps, Contracts, Money, Price};

pub fn contracts_for_reference(
    reference_equity: Money,
    allocation: Bps,
    price: Price,
) -> Option<Contracts> {
    if reference_equity.cents() < 0 || price.cents() == 0 || price.cents() >= 100 {
        return None;
    }
    let target = reference_equity.checked_mul_bps(allocation).ok()?;
    let qty = target.cents() / i64::from(price.cents());
    u32::try_from(qty).ok().map(Contracts::from_u32)
}
