//! Strategy registry — FIRST01 now; future models plug in here.

use momento_research_strategies::{FIRST01_NAME, First01Model, StrategyModel};

use crate::error::{BacktestError, BacktestErrorCode};

#[derive(Clone, Debug, Default)]
pub struct StrategyRegistry;

impl StrategyRegistry {
    pub fn resolve(&self, name: &str) -> Result<StrategyModel, BacktestError> {
        resolve_strategy(name)
    }

    pub fn known(&self) -> Vec<&'static str> {
        vec![FIRST01_NAME]
    }
}

pub fn resolve_strategy(name: &str) -> Result<StrategyModel, BacktestError> {
    let trimmed = name.trim();
    if trimmed.eq_ignore_ascii_case(FIRST01_NAME) {
        return Ok(First01Model::definition().as_strategy_model());
    }
    Err(BacktestError::coded(
        BacktestErrorCode::UnknownStrategy,
        format!("unknown strategy model '{trimmed}'"),
    ))
}
