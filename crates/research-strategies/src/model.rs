//! Strategy metadata for reproducible backtests.

use serde::{Deserialize, Serialize};

use crate::params::{EffectiveParameters, EntryParameters, ExitParameters, ExperimentOverrides};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct StrategyModel {
    pub name: String,
    pub version: u32,
    pub supported_series: Vec<String>,
    pub default_entry: EntryParameters,
    pub default_exit: ExitParameters,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct StrategyRunMetadata {
    pub strategy_name: String,
    pub strategy_version: u32,
    pub parameter_set: EffectiveParameters,
    pub series: Vec<String>,
    pub season: Option<String>,
    pub start_date: Option<String>,
    pub end_date: Option<String>,
    pub dataset_schema_version: Option<String>,
    pub dataset_manifest_checksum: Option<String>,
}

impl StrategyRunMetadata {
    pub fn for_first01(overrides: &ExperimentOverrides) -> Self {
        let model = crate::first01::First01Model::definition();
        Self {
            strategy_name: model.name,
            strategy_version: model.version,
            parameter_set: EffectiveParameters::resolve(overrides),
            series: overrides.series.clone().unwrap_or(model.supported_series),
            season: overrides.season.clone(),
            start_date: overrides.start_date.clone(),
            end_date: overrides.end_date.clone(),
            dataset_schema_version: None,
            dataset_manifest_checksum: None,
        }
    }
}
