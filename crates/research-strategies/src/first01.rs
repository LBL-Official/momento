//! FIRST01 — canonical research model for the current live desk strategy.

use serde::{Deserialize, Serialize};

use crate::model::StrategyModel;
use crate::params::{EntryParameters, ExitParameters};

pub const FIRST01_NAME: &str = "FIRST01";
pub const FIRST01_VERSION: u32 = 1;

pub const SERIES_MLB: &str = "KXMLBGAME";
pub const SERIES_WNBA: &str = "KXWNBAGAME";

pub const FIRST01_MARKET_UNIVERSE: [&str; 2] = [SERIES_MLB, SERIES_WNBA];

pub const FIRST01_DEFAULT_ENTRY: EntryParameters = EntryParameters {
    first_threshold_cents: 80,
    confirmation_threshold_cents: 81,
    maximum_entry_price_cents: 83,
    lock_threshold_cents: 89,
    require_bid_below_ask: true,
    maker_only: true,
};

pub const FIRST01_DEFAULT_EXIT: ExitParameters = ExitParameters {
    loss_numerator: 1,
    loss_denominator: 2,
};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct First01Model {
    pub name: String,
    pub version: u32,
    pub default_entry: EntryParameters,
    pub default_exit: ExitParameters,
    pub supported_series: Vec<String>,
}

impl Default for First01Model {
    fn default() -> Self {
        Self::definition()
    }
}

impl First01Model {
    pub fn definition() -> Self {
        Self {
            name: FIRST01_NAME.to_string(),
            version: FIRST01_VERSION,
            default_entry: FIRST01_DEFAULT_ENTRY,
            default_exit: FIRST01_DEFAULT_EXIT,
            supported_series: FIRST01_MARKET_UNIVERSE
                .iter()
                .map(|s| (*s).to_string())
                .collect(),
        }
    }

    pub fn as_strategy_model(&self) -> StrategyModel {
        StrategyModel {
            name: self.name.clone(),
            version: self.version,
            supported_series: self.supported_series.clone(),
            default_entry: self.default_entry,
            default_exit: self.default_exit,
        }
    }
}
