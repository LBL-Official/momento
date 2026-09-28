//! Opaque identifiers. These are not venue payloads.

use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

static NEXT: AtomicU64 = AtomicU64::new(1);

fn next() -> u128 {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(1);
    let seq = u128::from(NEXT.fetch_add(1, Ordering::Relaxed));
    nanos.saturating_add(seq)
}

macro_rules! id_type {
    ($name:ident) => {
        #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
        pub struct $name(u128);

        impl $name {
            pub fn generate() -> Self {
                Self(next())
            }

            pub const fn from_raw(raw: u128) -> Self {
                Self(raw)
            }

            pub const fn raw(self) -> u128 {
                self.0
            }
        }
    };
}

id_type!(PositionId);
id_type!(GameId);
id_type!(MarketId);
id_type!(ClientOrderId);
id_type!(VenueOrderId);
id_type!(FillId);
id_type!(EventId);
id_type!(StrategyId);
id_type!(SnapshotId);
id_type!(RiskDecisionId);

impl StrategyId {
    pub const MLB: Self = Self::from_raw(1);
    pub const WNBA: Self = Self::from_raw(2);
    pub const RESEARCH_ITI: Self = Self::from_raw(3);
}

impl Default for StrategyId {
    fn default() -> Self {
        Self::MLB
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ids_are_distinct_types() {
        let p = PositionId::from_raw(1);
        let g = GameId::from_raw(1);
        assert_eq!(p.raw(), g.raw());
        // Distinct types: PositionId is not GameId (compile-time).
    }
}
