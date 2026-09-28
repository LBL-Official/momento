//! Canonical lake catalog v1 (W1-A6). Derived artifact — never stored inside raw/.

use chrono::{DateTime, NaiveDate, Utc};
use serde::{Deserialize, Serialize};

use super::coverage::PartitionCoverage;
use super::observability::ObservabilityKind;
use super::{ARTIFACT_VERSION, CATALOG_VERSION, WATERFALL};
use crate::manifest::CompletenessStatus;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum LakeLayer {
    Raw,
    Metadata,
    Orderbook,
    Trades,
    Manifest,
    Other,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LakeFileEntry {
    pub sport: String,
    pub league: String,
    pub season_label: String,
    pub partition_date: Option<NaiveDate>,
    pub layer: LakeLayer,
    pub path: String,
    pub bytes: u64,
    pub sha256: Option<String>,
    pub completeness_v1: Option<CompletenessStatus>,
    pub coverage_v2: Option<PartitionCoverage>,
    pub markets: Option<u32>,
    pub games_est: Option<u32>,
    pub trades: Option<u64>,
    pub ob_events: Option<u64>,
    pub observability: ObservabilityKind,
    pub notes: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MarketEvidence {
    pub game_id: String,
    pub market_id: String,
    pub ticker: String,
    pub event_ticker: String,
    pub partition_date: NaiveDate,
    pub sport: String,
    pub mlb_game_pk: Option<String>,
    pub files: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LakeCatalogV1 {
    pub catalog_version: String,
    pub waterfall: String,
    pub artifact_version: String,
    pub lake_content_digest: String,
    pub generated_at: DateTime<Utc>,
    pub lake_root: String,
    pub lake_class: String,
    pub entries: Vec<LakeFileEntry>,
    pub market_evidence: Vec<MarketEvidence>,
}

impl LakeCatalogV1 {
    pub fn new(
        digest: String,
        generated_at: DateTime<Utc>,
        lake_root: String,
        lake_class: String,
        mut entries: Vec<LakeFileEntry>,
        mut market_evidence: Vec<MarketEvidence>,
    ) -> Self {
        entries.sort_by(|a, b| a.path.cmp(&b.path));
        market_evidence.sort_by(|a, b| {
            a.partition_date
                .cmp(&b.partition_date)
                .then(a.ticker.cmp(&b.ticker))
        });
        Self {
            catalog_version: CATALOG_VERSION.to_string(),
            waterfall: WATERFALL.to_string(),
            artifact_version: ARTIFACT_VERSION.to_string(),
            lake_content_digest: digest,
            generated_at,
            lake_root,
            lake_class,
            entries,
            market_evidence,
        }
    }

    /// Equality-relevant body: omits generated_at so two runs on an unchanged lake match.
    pub fn canonical_body(&self) -> serde_json::Value {
        serde_json::json!({
            "catalog_version": self.catalog_version,
            "waterfall": self.waterfall,
            "artifact_version": self.artifact_version,
            "lake_content_digest": self.lake_content_digest,
            "lake_root": self.lake_root,
            "lake_class": self.lake_class,
            "entries": self.entries,
            "market_evidence": self.market_evidence,
        })
    }
}

/// Manifest-only catalog of the LEGACY demo tree. Never labeled REAL.
pub fn catalog_demo_manifest_slice(
    demo_root: &std::path::Path,
    season: &crate::sport::ResearchSeason,
    generated_at: DateTime<Utc>,
) -> Result<LakeCatalogV1, String> {
    use crate::manifest::{DailyManifest, list_manifest_dates};
    use crate::paths::ResearchPaths;
    use crate::sport::ResearchSport;

    let demo_root = demo_root
        .canonicalize()
        .unwrap_or_else(|_| demo_root.to_path_buf());
    let mut paths = ResearchPaths::from_env_or_default();
    paths.root = demo_root.clone();
    paths.season = season.clone();

    let mut entries = Vec::new();
    for sport in [ResearchSport::Mlb, ResearchSport::Wnba] {
        let dates = list_manifest_dates(&paths, sport).map_err(|e| e.to_string())?;
        for date in dates {
            let path = paths.manifest_path(sport, date);
            let bytes = std::fs::metadata(&path).map(|m| m.len()).unwrap_or(0);
            let notes = DailyManifest::read(&paths, sport, date)
                .ok()
                .flatten()
                .map(|m| {
                    let mut n = m.notes;
                    n.push("DEMO — not 2025-2026 MLB/WNBA history".into());
                    n
                })
                .unwrap_or_else(|| vec!["DEMO — not 2025-2026 MLB/WNBA history".into()]);
            entries.push(LakeFileEntry {
                sport: sport.dir_name().to_string(),
                league: sport.dir_name().to_string(),
                season_label: season.label.clone(),
                partition_date: Some(date),
                layer: LakeLayer::Manifest,
                path: path.display().to_string(),
                bytes,
                sha256: None,
                completeness_v1: None,
                coverage_v2: None,
                markets: None,
                games_est: None,
                trades: None,
                ob_events: None,
                observability: ObservabilityKind::Modeled,
                notes,
            });
        }
    }
    Ok(LakeCatalogV1::new(
        "demo-manifest-slice".into(),
        generated_at,
        demo_root.display().to_string(),
        "DEMO".into(),
        entries,
        Vec::new(),
    ))
}
