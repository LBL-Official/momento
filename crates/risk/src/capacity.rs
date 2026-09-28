//! Available economic capacity. Live venue balance is not implemented.

use momento_core::Money;

/// Paper/live available funds for risk gating.
///
/// **M2:** implementations may use the weekly snapshot / configured paper
/// bankroll. **Later:** a venue/account adapter will supply live available
/// balance. Risk must not depend on Kalshi.
pub trait AvailableCapacity: Send + Sync {
    fn available(&self) -> Money;
}

/// Uses the weekly snapshot bankroll as paper available capacity.
#[derive(Clone, Copy, Debug)]
pub struct SnapshotPaperBalance {
    bankroll: Money,
}

impl SnapshotPaperBalance {
    pub const fn from_bankroll(bankroll: Money) -> Self {
        Self { bankroll }
    }
}

impl AvailableCapacity for SnapshotPaperBalance {
    fn available(&self) -> Money {
        self.bankroll
    }
}
