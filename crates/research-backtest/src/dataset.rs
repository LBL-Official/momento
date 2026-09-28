//! Dataset manifest validation for requested date ranges.

use chrono::{Duration, NaiveDate};
use sha2::{Digest, Sha256};

use momento_research_data::{
    CompletenessStatus, DailyManifest, ReplayDataset, ResearchPaths, ResearchSport,
};
use momento_research_execution::DataQualityMetrics;

use crate::error::{BacktestError, BacktestErrorCode};

#[derive(Clone, Debug)]
pub struct DatasetPlan {
    pub sport: ResearchSport,
    pub dates: Vec<NaiveDate>,
    pub manifests: Vec<DailyManifest>,
    pub manifest_ids: Vec<String>,
    pub checksum_digest: String,
    pub coverage: String,
}

pub fn sports_from_series(series: &[String]) -> Result<Vec<ResearchSport>, BacktestError> {
    let mut out = Vec::new();
    for s in series {
        let sport = ResearchSport::from_series(s).ok_or_else(|| {
            BacktestError::coded(
                BacktestErrorCode::UnsupportedSeries,
                format!("unsupported series '{s}'"),
            )
        })?;
        if !out.contains(&sport) {
            out.push(sport);
        }
    }
    Ok(out)
}

pub fn dates_inclusive(start: NaiveDate, end: NaiveDate) -> Vec<NaiveDate> {
    let mut dates = Vec::new();
    let mut d = start;
    while d <= end {
        dates.push(d);
        d += Duration::days(1);
    }
    dates
}

/// Validate every requested sport/date is COMPLETE (unless allow_incomplete).
pub fn validate_dataset_coverage(
    paths: &ResearchPaths,
    sports: &[ResearchSport],
    start: NaiveDate,
    end: NaiveDate,
    allow_incomplete: bool,
) -> Result<Vec<DatasetPlan>, BacktestError> {
    let dates = dates_inclusive(start, end);
    let mut plans = Vec::new();
    for &sport in sports {
        let mut manifests = Vec::new();
        let mut manifest_ids = Vec::new();
        let mut hasher = Sha256::new();
        for date in &dates {
            let manifest = DailyManifest::read(paths, sport, *date).map_err(|e| {
                BacktestError::coded(
                    BacktestErrorCode::ReplayError,
                    format!("manifest read error {sport:?} {date}: {e}"),
                )
            })?;
            let Some(m) = manifest else {
                if allow_incomplete {
                    continue;
                }
                return Err(BacktestError::coded(
                    BacktestErrorCode::DatasetMissing,
                    format!(
                        "DATASET_MISSING: no manifest for {} {}",
                        sport.dir_name(),
                        date
                    ),
                ));
            };
            match m.completeness_status {
                CompletenessStatus::Complete => {}
                CompletenessStatus::Partial => {
                    if !allow_incomplete {
                        return Err(BacktestError::coded(
                            BacktestErrorCode::DatasetPartial,
                            format!("DATASET_PARTIAL: {} {}", sport.dir_name(), date),
                        ));
                    }
                }
                CompletenessStatus::Missing => {
                    if !allow_incomplete {
                        return Err(BacktestError::coded(
                            BacktestErrorCode::DatasetMissing,
                            format!("DATASET_MISSING: {} {}", sport.dir_name(), date),
                        ));
                    }
                }
                CompletenessStatus::Invalid => {
                    return Err(BacktestError::coded(
                        BacktestErrorCode::DatasetInvalid,
                        format!("DATASET_INVALID: {} {}", sport.dir_name(), date),
                    ));
                }
            }
            let id = format!("{}:{}", sport.dir_name(), date);
            hasher.update(id.as_bytes());
            for (k, v) in &m.checksums {
                hasher.update(k.as_bytes());
                hasher.update(v.as_bytes());
            }
            manifest_ids.push(id);
            manifests.push(m);
        }
        let digest = format!("{:x}", hasher.finalize());
        let coverage = if manifests.len() == dates.len() {
            format!("COMPLETE {} days", dates.len())
        } else {
            format!("PARTIAL {}/{} days", manifests.len(), dates.len())
        };
        plans.push(DatasetPlan {
            sport,
            dates: dates.clone(),
            manifests,
            manifest_ids,
            checksum_digest: digest,
            coverage,
        });
    }
    Ok(plans)
}

pub fn load_datasets(
    paths: &ResearchPaths,
    plan: &DatasetPlan,
) -> Result<Vec<ReplayDataset>, BacktestError> {
    let mut out = Vec::new();
    for date in &plan.dates {
        let ds = ReplayDataset::load(paths, plan.sport, *date).map_err(|e| {
            BacktestError::coded(
                BacktestErrorCode::ReplayError,
                format!("load {} {}: {e}", plan.sport.dir_name(), date),
            )
        })?;
        out.push(ds);
    }
    Ok(out)
}

pub fn data_quality_from_plans(plans: &[DatasetPlan]) -> DataQualityMetrics {
    let mut dates_requested = 0u32;
    let mut dates_used = 0u32;
    let mut complete_dates = 0u32;
    let mut partial_dates = 0u32;
    let mut invalid_dates = 0u32;
    let mut missing_dates = 0u32;
    for plan in plans {
        dates_requested += plan.dates.len() as u32;
        dates_used += plan.manifests.len() as u32;
        for m in &plan.manifests {
            match m.completeness_status {
                CompletenessStatus::Complete => complete_dates += 1,
                CompletenessStatus::Partial => partial_dates += 1,
                CompletenessStatus::Invalid => invalid_dates += 1,
                CompletenessStatus::Missing => missing_dates += 1,
            }
        }
        missing_dates += (plan.dates.len().saturating_sub(plan.manifests.len())) as u32;
    }
    DataQualityMetrics {
        dates_requested,
        dates_used,
        complete_dates,
        partial_dates,
        invalid_dates,
        missing_dates,
        ..DataQualityMetrics::default()
    }
}
