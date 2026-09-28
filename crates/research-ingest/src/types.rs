//! Run identity, windows, and report types.

use std::path::PathBuf;

use chrono::{DateTime, NaiveDate, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

pub const PLANE: &str = "DATA-INGEST";
pub const ARTIFACT_VERSION: &str = "INGEST.2.1.3";
pub const SOURCE_STATSAPI: &str = "mlb_statsapi";
pub const SOURCE_KALSHI: &str = "kalshi_v1_lake";
pub const SOURCE_KALSHI_DISCOVERY: &str = "kalshi_discovery";
pub const SOURCE_KALSHI_MATCHED_TRADES: &str = "kalshi_historical_trades";
pub const SOURCE_KALSHI_HISTORICAL_CANDLES: &str = "kalshi_historical_candles";
pub const SOURCE_KALSHI_SETTLEMENT: &str = "kalshi_market_settlement";
pub const NETWORK_AUTHORIZATION_PHRASE: &str = "ENABLE_RESEARCH_INGEST_NETWORK";

pub const TARGET_MIN_PBP_GAMES: usize = 2000;
pub const TARGET_PREFERRED_PBP_GAMES: usize = 3000;
pub const TARGET_MIN_MAPPED_PAIRS: usize = 2000;
pub const TARGET_PREFERRED_MAPPED_PAIRS: usize = 3000;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum RunStatus {
    Complete,
    CompleteWithGaps,
    Failed,
    Blocked,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum WindowStatus {
    Complete,
    CompleteWithGaps,
    Failed,
    #[default]
    Unavailable,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PartitionStatus {
    Complete,
    Unavailable,
    Failed,
    AlreadyKnown,
    VersionConflict,
    NotAttempted,
    Skipped,
    Unmatched,
    Ambiguous,
    Discovered,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum CommitStatus {
    Pending,
    Committed,
    Rejected,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ExecutionMode {
    HistoricalBackfill,
    Weekly,
    Manual,
    Replay,
    Recovery,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum IdentityMapping {
    Unmatched,
    Ambiguous,
    Mapped,
    Observed,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MarketCompleteness {
    L2Complete,
    L2Partial,
    TradesOnly,
    CandlesOnly,
    MarketMetadataOnly,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct DateWindow {
    pub label: String,
    pub start: NaiveDate,
    pub end: NaiveDate,
}

impl DateWindow {
    pub fn contains(&self, date: NaiveDate) -> bool {
        date >= self.start && date <= self.end
    }

    pub fn mlb_calendar_2024() -> Self {
        Self {
            label: "mlb-2024".into(),
            start: NaiveDate::from_ymd_opt(2024, 1, 1).expect("date"),
            end: NaiveDate::from_ymd_opt(2024, 12, 31).expect("date"),
        }
    }

    pub fn mlb_calendar_2025() -> Self {
        Self {
            label: "mlb-2025".into(),
            start: NaiveDate::from_ymd_opt(2025, 1, 1).expect("date"),
            end: NaiveDate::from_ymd_opt(2025, 12, 31).expect("date"),
        }
    }

    pub fn mlb_calendar_2026_through(as_of: NaiveDate) -> Self {
        let start = NaiveDate::from_ymd_opt(2026, 1, 1).expect("date");
        Self {
            label: "mlb-2026".into(),
            start,
            end: as_of.max(start),
        }
    }

    /// Required DATA-INGEST MLB windows. Not a completeness claim.
    pub fn required_mlb_windows(as_of: NaiveDate) -> Vec<Self> {
        vec![
            Self::mlb_calendar_2024(),
            Self::mlb_calendar_2025(),
            Self::mlb_calendar_2026_through(as_of),
        ]
    }

    /// MLB 2024 regular + postseason ingest bound (not a completeness claim).
    pub fn mlb_2024_2025() -> Self {
        Self {
            label: "2024-2025".into(),
            start: NaiveDate::from_ymd_opt(2024, 3, 20).expect("date"),
            end: NaiveDate::from_ymd_opt(2024, 11, 2).expect("date"),
        }
    }

    /// MLB 2025–2026 ingest bound through `as_of` (not a completeness claim).
    pub fn mlb_2025_2026_through(as_of: NaiveDate) -> Self {
        let start = NaiveDate::from_ymd_opt(2025, 3, 18).expect("date");
        let cap = NaiveDate::from_ymd_opt(2026, 11, 2).expect("date");
        Self {
            label: "2025-2026".into(),
            start,
            end: as_of.min(cap),
        }
    }
}

#[derive(Clone, Debug)]
pub struct IngestPlan {
    pub lake_root: PathBuf,
    pub ingest_root: PathBuf,
    pub generated_at: DateTime<Utc>,
    pub pbp_windows: Vec<DateWindow>,
    pub include_weekly: bool,
    pub weekly_lookback_days: i64,
    pub overlap_days: i64,
    pub persist_watermarks: bool,
    pub fill_unlisted_dates: bool,
    pub invoke_w2: bool,
    pub execution_mode: ExecutionMode,
    pub kalshi_catalog: bool,
    pub kalshi_discover: bool,
    pub fetch_kalshi_artifacts: bool,
    pub network_enabled: bool,
    pub max_retries: u32,
    pub retry_sleep_ms: u64,
    pub rate_limit_ms: u64,
    pub max_days: Option<u32>,
    pub skip_existing: bool,
    pub forbidden_write_roots: Vec<PathBuf>,
}

impl IngestPlan {
    pub fn test_defaults(lake_root: PathBuf, ingest_root: PathBuf) -> Self {
        Self {
            lake_root,
            ingest_root,
            generated_at: Utc::now(),
            pbp_windows: Vec::new(),
            include_weekly: false,
            weekly_lookback_days: 7,
            overlap_days: 0,
            persist_watermarks: false,
            fill_unlisted_dates: true,
            invoke_w2: true,
            execution_mode: ExecutionMode::Manual,
            kalshi_catalog: true,
            kalshi_discover: false,
            fetch_kalshi_artifacts: false,
            network_enabled: false,
            max_retries: 0,
            retry_sleep_ms: 0,
            rate_limit_ms: 0,
            max_days: None,
            skip_existing: false,
            forbidden_write_roots: Vec::new(),
        }
    }

    pub fn as_of_date(&self) -> NaiveDate {
        self.generated_at.date_naive()
    }

    pub fn digest(&self) -> String {
        let mut h = Sha256::new();
        h.update(ARTIFACT_VERSION.as_bytes());
        for w in &self.pbp_windows {
            h.update(w.label.as_bytes());
            h.update(w.start.to_string().as_bytes());
            h.update(w.end.to_string().as_bytes());
        }
        h.update([
            u8::from(self.include_weekly),
            u8::from(self.kalshi_catalog),
            u8::from(self.kalshi_discover),
        ]);
        format!("{:x}", h.finalize())
    }

    pub fn run_id(&self) -> String {
        let d = self.digest();
        format!(
            "ingest-{}-{}",
            self.generated_at.format("%Y%m%dT%H%M%SZ"),
            &d[..12]
        )
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CoverageRow {
    pub date: String,
    pub source: String,
    pub partition_id: String,
    pub status: PartitionStatus,
    pub sha256: Option<String>,
    pub path: Option<String>,
    pub notes: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct WindowCoverage {
    pub label: String,
    pub start: String,
    pub end: String,
    pub source: String,
    pub scheduled: usize,
    pub discovered: usize,
    pub fetched: usize,
    pub committed: usize,
    pub reconstructed_ready: usize,
    pub failed: usize,
    pub unavailable: usize,
    pub skipped: usize,
    pub duplicates: usize,
    pub checksum_conflicts: usize,
    pub status: WindowStatus,
    pub completeness_claimed: bool,
    pub notes: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Watermark {
    pub source: String,
    pub last_committed_date: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct WatermarkState {
    pub mlb_schedule_discovery: Option<String>,
    pub mlb_pbp_acquisition: Option<String>,
    pub kalshi_market_discovery: Option<String>,
    pub kalshi_market_artifact: Option<String>,
    #[serde(default)]
    pub mlb_pbp_committed_dates: Vec<String>,
    #[serde(default)]
    pub kalshi_discovery_committed_dates: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CommittedArtifact {
    pub artifact_id: String,
    pub source: String,
    pub path: String,
    pub sha256: String,
    pub partition_id: String,
    pub date: String,
    pub commit_status: CommitStatus,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct W1CommitHandoff {
    pub run_id: String,
    pub plane: String,
    pub artifact_version: String,
    pub committed_at: DateTime<Utc>,
    pub artifacts: Vec<CommittedArtifact>,
}

impl W1CommitHandoff {
    pub fn all_committed_and_verified(&self) -> Result<(), String> {
        for a in &self.artifacts {
            if a.commit_status != CommitStatus::Committed {
                return Err(format!("{} is {:?}", a.artifact_id, a.commit_status));
            }
            if a.sha256.is_empty() {
                return Err(format!("{} missing checksum", a.artifact_id));
            }
        }
        Ok(())
    }

    pub fn statsapi_committed(&self) -> impl Iterator<Item = &CommittedArtifact> {
        self.artifacts
            .iter()
            .filter(|a| a.source == SOURCE_STATSAPI && a.commit_status == CommitStatus::Committed)
    }

    pub fn kalshi_committed(&self) -> impl Iterator<Item = &CommittedArtifact> {
        self.artifacts.iter().filter(|a| {
            (a.source == SOURCE_KALSHI || a.source == SOURCE_KALSHI_DISCOVERY)
                && a.commit_status == CommitStatus::Committed
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct IdentityRow {
    pub source: String,
    pub ticker: String,
    pub partition_id: String,
    pub mapping: IdentityMapping,
    pub observed_game_pk: Option<String>,
    pub notes: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct ChecksumReport {
    pub verified: usize,
    pub mismatches: usize,
    pub version_conflicts: usize,
    pub already_known: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct IngestRunReport {
    pub run_id: String,
    pub plane: String,
    pub artifact_version: String,
    pub generated_at: DateTime<Utc>,
    pub status: RunStatus,
    pub network_enabled: bool,
    pub coverage: Vec<CoverageRow>,
    pub watermarks: Vec<Watermark>,
    pub handoff: W1CommitHandoff,
    pub w2_games_attempted: usize,
    pub w2_reconstruction_ok: usize,
    pub w2_skipped_reason: Option<String>,
    pub alerts: Vec<String>,
    pub audit_path: String,
    #[serde(default)]
    pub execution_mode: String,
    #[serde(default)]
    pub window_coverage: Vec<WindowCoverage>,
    #[serde(default)]
    pub watermark_state: WatermarkState,
    #[serde(default)]
    pub identity_report: Vec<IdentityRow>,
    #[serde(default)]
    pub checksum_report: ChecksumReport,
    #[serde(default)]
    pub cloud_status: String,
    #[serde(default)]
    pub code_ready: bool,
    #[serde(default)]
    pub network_ready: bool,
    #[serde(default)]
    pub backfill_complete: bool,
    #[serde(default)]
    pub continuous_feed_operational: bool,
    #[serde(default)]
    pub corpus: CorpusCoverage,
}

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct CorpusCoverage {
    pub mlb_games_discovered: usize,
    pub pbp_games_committed: usize,
    pub kalshi_markets_discovered: usize,
    pub kalshi_artifacts_committed: usize,
    pub pairs_mapped: usize,
    pub pairs_unmatched: usize,
    pub pairs_ambiguous: usize,
    pub games_mapped: usize,
    pub games_unmatched: usize,
    pub games_ambiguous: usize,
    pub completeness: CompletenessCounts,
    pub target_min_pbp_games: usize,
    pub target_min_mapped_pairs: usize,
    pub pbp_target_met: bool,
    pub pair_target_met: bool,
    pub notes: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct CompletenessCounts {
    pub l2_complete: usize,
    pub l2_partial: usize,
    pub trades_only: usize,
    pub candles_only: usize,
    pub market_metadata_only: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GameMarketPair {
    pub game_pk: Option<String>,
    pub official_date: String,
    pub event_ticker: Option<String>,
    pub ticker: String,
    pub mapping: IdentityMapping,
    pub completeness: Option<MarketCompleteness>,
    pub notes: String,
}
