use serde::{Deserialize, Serialize};

use crate::money::Money;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum FeeKind {
    Entry,
    Liquidation,
}

/// Fee in USD cents, tagged so entry and liquidation cannot be mixed.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Fee {
    amount: Money,
    kind: FeeKind,
}

impl Fee {
    pub const fn new(amount: Money, kind: FeeKind) -> Self {
        Self { amount, kind }
    }

    pub const fn zero(kind: FeeKind) -> Self {
        Self {
            amount: Money::ZERO,
            kind,
        }
    }

    pub const fn amount(self) -> Money {
        self.amount
    }

    pub const fn kind(self) -> FeeKind {
        self.kind
    }
}

/// Identifies which fee model produced an estimate. Not a venue payload.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct FeeModelId(String);

impl FeeModelId {
    pub fn new(id: impl Into<String>) -> Self {
        Self(id.into())
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }

    /// M1 constructor filler. Not a fee model.
    pub fn unspecified_legacy() -> Self {
        Self("unspecified-legacy-not-a-fee-model".into())
    }

    /// Temporary paper placeholder. **Not** confirmed Kalshi economics.
    pub fn zero_placeholder() -> Self {
        Self("zero-fee-placeholder-not-kalshi-economics".into())
    }
}
