//! Separate immutable FIRST01 defaults from per-experiment overrides.

use serde::{Deserialize, Serialize};

use crate::first01::{FIRST01_DEFAULT_ENTRY, FIRST01_DEFAULT_EXIT};

/// Entry thresholds for a single backtest run. Overrides FIRST01 defaults only
/// when supplied through [`ExperimentOverrides`].
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EntryParameters {
    pub first_threshold_cents: u16,
    pub confirmation_threshold_cents: u16,
    pub maximum_entry_price_cents: u16,
    pub lock_threshold_cents: u16,
    pub require_bid_below_ask: bool,
    pub maker_only: bool,
}

impl Default for EntryParameters {
    fn default() -> Self {
        FIRST01_DEFAULT_ENTRY
    }
}

/// Exit thresholds for a single backtest run.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExitParameters {
    /// Loss trigger as a rational fraction of actual entry VWAP basis.
    /// Default `1/2` = 50%.
    pub loss_numerator: u32,
    pub loss_denominator: u32,
}

impl Default for ExitParameters {
    fn default() -> Self {
        FIRST01_DEFAULT_EXIT
    }
}

impl ExitParameters {
    pub fn half_loss() -> Self {
        Self {
            loss_numerator: 1,
            loss_denominator: 2,
        }
    }

    pub fn fraction_bps(&self) -> u32 {
        (self.loss_numerator.saturating_mul(10_000)) / self.loss_denominator.max(1)
    }
}

/// Per-experiment overrides. The FIRST01 model definition stays immutable.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExperimentOverrides {
    pub entry: Option<EntryParameters>,
    pub exit: Option<ExitParameters>,
    pub series: Option<Vec<String>>,
    pub season: Option<String>,
    pub start_date: Option<String>,
    pub end_date: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EffectiveParameters {
    pub entry: EntryParameters,
    pub exit: ExitParameters,
}

impl EffectiveParameters {
    pub fn resolve(overrides: &ExperimentOverrides) -> Self {
        Self {
            entry: overrides.entry.unwrap_or_default(),
            exit: overrides.exit.unwrap_or_default(),
        }
    }
}
