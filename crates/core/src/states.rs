//! Process-level flags that are not order or position lifecycle.

use serde::{Deserialize, Serialize};

/// Kill switch is independent of strategy. Tripped => no new entry exposure.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub enum KillSwitch {
    #[default]
    Armed,
    Tripped,
}

impl KillSwitch {
    pub const fn is_tripped(self) -> bool {
        matches!(self, Self::Tripped)
    }
}
