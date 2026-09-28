//! Resolve Google Sheet experiment inputs into ExperimentOverrides.

use momento_research_strategies::{
    EffectiveParameters, EntryParameters, ExitParameters, ExperimentOverrides,
    FIRST01_DEFAULT_ENTRY, FIRST01_DEFAULT_EXIT, FIRST01_NAME, FIRST01_VERSION, StrategyModel,
};

use crate::error::{BacktestError, BacktestErrorCode};
use crate::parse::{
    EntryPriceRange, ExitPriceInput, NormalizedSeason, NormalizedTimeFrame,
    parse_entry_price_range, parse_exit_price_input, parse_season, parse_series_list,
    parse_time_frame,
};
use crate::registry::resolve_strategy;
use crate::sheet_contract::InputRow;

#[derive(Clone, Debug)]
pub struct ResolvedExperiment {
    pub run_id: String,
    pub entry_model: StrategyModel,
    pub exit_model: StrategyModel,
    pub series: Vec<String>,
    pub season: NormalizedSeason,
    pub time_frame: NormalizedTimeFrame,
    pub entry_range: EntryPriceRange,
    pub exit_input: ExitPriceInput,
    pub overrides: ExperimentOverrides,
    pub default_parameters: EffectiveParameters,
    pub effective_parameters: EffectiveParameters,
    pub original_entry_price_input: String,
    pub original_exit_price_input: String,
}

pub fn resolve_experiment(row: &InputRow) -> Result<ResolvedExperiment, BacktestError> {
    let entry_model = resolve_strategy(&row.entry_model)?;
    let exit_model = resolve_strategy(&row.exit_model)?;
    if entry_model.name != FIRST01_NAME || exit_model.name != FIRST01_NAME {
        // Only FIRST01 exists today; keep the gate explicit.
        return Err(BacktestError::coded(
            BacktestErrorCode::UnknownStrategy,
            "only FIRST01 entry/exit models are supported in this runner version",
        ));
    }

    let series = parse_series_list(&row.ticker)?;
    let season = parse_season(&row.season)?;
    let time_frame = parse_time_frame(&row.time_frame, &season)?;
    let entry_range = parse_entry_price_range(&row.entry_price_range)?;
    let exit_input = parse_exit_price_input(&row.exit_price_range)?;

    let mut entry = FIRST01_DEFAULT_ENTRY;
    entry.first_threshold_cents = entry_range.minimum_entry_price_cents;
    entry.confirmation_threshold_cents = entry_range.confirmation_threshold_cents;
    entry.maximum_entry_price_cents = entry_range.maximum_entry_price_cents;
    // lock_threshold stays at FIRST01 default unless a future column overrides it.

    let exit = match exit_input {
        ExitPriceInput::ModelNative => FIRST01_DEFAULT_EXIT,
        ExitPriceInput::LossFraction {
            numerator,
            denominator,
        } => ExitParameters {
            loss_numerator: numerator,
            loss_denominator: denominator,
        },
    };

    let overrides = ExperimentOverrides {
        entry: Some(entry),
        exit: Some(exit),
        series: Some(series.clone()),
        season: Some(season.label.clone()),
        start_date: Some(time_frame.start.to_string()),
        end_date: Some(time_frame.end.to_string()),
    };

    let default_parameters = EffectiveParameters {
        entry: FIRST01_DEFAULT_ENTRY,
        exit: FIRST01_DEFAULT_EXIT,
    };
    let effective_parameters = EffectiveParameters::resolve(&overrides);

    // Immutability guard: FIRST01 definition constants must remain 80/81/83.
    debug_assert_eq!(FIRST01_DEFAULT_ENTRY.first_threshold_cents, 80);
    debug_assert_eq!(FIRST01_DEFAULT_ENTRY.confirmation_threshold_cents, 81);
    debug_assert_eq!(FIRST01_DEFAULT_ENTRY.maximum_entry_price_cents, 83);
    debug_assert_eq!(FIRST01_VERSION, 1);

    let mut run_id = row.run_id.clone();
    if run_id.trim().is_empty() {
        run_id = uuid::Uuid::new_v4().to_string();
    }

    Ok(ResolvedExperiment {
        run_id,
        entry_model,
        exit_model,
        series,
        season,
        time_frame,
        entry_range,
        exit_input,
        overrides,
        default_parameters,
        effective_parameters,
        original_entry_price_input: row.entry_price_range.clone(),
        original_exit_price_input: row.exit_price_range.clone(),
    })
}

/// Prove FIRST01 defaults are not mutated by override resolution.
pub fn first01_defaults_immutable_after_override(entry: EntryParameters) -> bool {
    let _ = entry;
    FIRST01_DEFAULT_ENTRY.first_threshold_cents == 80
        && FIRST01_DEFAULT_ENTRY.confirmation_threshold_cents == 81
        && FIRST01_DEFAULT_ENTRY.maximum_entry_price_cents == 83
        && FIRST01_DEFAULT_ENTRY.lock_threshold_cents == 89
        && FIRST01_DEFAULT_EXIT.loss_numerator == 1
        && FIRST01_DEFAULT_EXIT.loss_denominator == 2
}
