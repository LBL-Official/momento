//! Honest W4 coverage. Never claim FULL_L2.

use std::collections::BTreeMap;

use chrono::NaiveDate;
use momento_research_data::foundation::StartingPriceClass;
use momento_research_ingest::types::IdentityMapping;
use serde::{Deserialize, Serialize};

use crate::types::{LifetimeCoverage, MarketCompleteness, MarketPath, MissingSide};
use crate::versions::COVERAGE_VERSION;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct W4CoverageReport {
    pub coverage_version: String,
    pub window_start: String,
    pub window_end: String,
    pub reconstructed_tickers: usize,
    pub paths_by_completeness: BTreeMap<String, usize>,
    pub identity_mapped: usize,
    pub identity_unmatched: usize,
    pub identity_ambiguous: usize,
    pub coupled_episodes: usize,
    pub coupled_both_yes: usize,
    pub coupled_missing_side: usize,
    pub starting_price_unverified: usize,
    pub starting_price_verified: usize,
    pub lifetime_open_to_settlement: usize,
    pub lifetime_settlement_day_only: usize,
    pub lifetime_unknown: usize,
    pub blocked_on_ingest_observations: usize,
    pub ingest_only_pit_snapshots: usize,
    pub completeness_claimed: bool,
    pub notes: Vec<String>,
}

pub fn measure(
    date: NaiveDate,
    paths: &[MarketPath],
    coupled_both: usize,
    coupled_missing: usize,
    coupled_n: usize,
    completeness_claimed: bool,
    notes: Vec<String>,
) -> W4CoverageReport {
    let mut paths_by_completeness = BTreeMap::new();
    let mut identity_mapped = 0usize;
    let mut identity_unmatched = 0usize;
    let mut identity_ambiguous = 0usize;
    let mut starting_price_unverified = 0usize;
    let mut starting_price_verified = 0usize;
    let mut lifetime_open_to_settlement = 0usize;
    let mut lifetime_settlement_day_only = 0usize;
    let mut lifetime_unknown = 0usize;
    let mut blocked_on_ingest_observations = 0usize;
    let mut ingest_only_pit_snapshots = 0usize;

    for p in paths {
        *paths_by_completeness
            .entry(p.completeness.as_str().to_string())
            .or_insert(0) += 1;
        match p.identity {
            IdentityMapping::Mapped => identity_mapped += 1,
            IdentityMapping::Unmatched => identity_unmatched += 1,
            IdentityMapping::Ambiguous => identity_ambiguous += 1,
            IdentityMapping::Observed => {}
        }
        match p.starting_price_class {
            StartingPriceClass::StartingPriceUnverified => starting_price_unverified += 1,
            _ => starting_price_verified += 1,
        }
        match p.lifetime_coverage {
            LifetimeCoverage::OpenToSettlement => lifetime_open_to_settlement += 1,
            LifetimeCoverage::SettlementDayOnly => lifetime_settlement_day_only += 1,
            LifetimeCoverage::Unknown => lifetime_unknown += 1,
        }
        if p.blocked_on_ingest_observations {
            blocked_on_ingest_observations += 1;
        }
        ingest_only_pit_snapshots += p.ingest_only_pit_count;
    }

    W4CoverageReport {
        coverage_version: COVERAGE_VERSION.into(),
        window_start: date.to_string(),
        window_end: date.to_string(),
        reconstructed_tickers: paths.len(),
        paths_by_completeness,
        identity_mapped,
        identity_unmatched,
        identity_ambiguous,
        coupled_episodes: coupled_n,
        coupled_both_yes: coupled_both,
        coupled_missing_side: coupled_missing,
        starting_price_unverified,
        starting_price_verified,
        lifetime_open_to_settlement,
        lifetime_settlement_day_only,
        lifetime_unknown,
        blocked_on_ingest_observations,
        ingest_only_pit_snapshots,
        completeness_claimed,
        notes,
    }
}

pub fn coupled_counts(episodes: &[crate::types::CoupledMarketEpisode]) -> (usize, usize) {
    let both = episodes
        .iter()
        .filter(|e| e.missing_side == MissingSide::None)
        .count();
    let missing = episodes
        .iter()
        .filter(|e| e.missing_side == MissingSide::SecondYesContract)
        .count();
    (both, missing)
}

pub fn has_l2_complete_claim(paths: &[MarketPath]) -> bool {
    paths
        .iter()
        .any(|p| p.completeness == MarketCompleteness::L2Complete)
}
