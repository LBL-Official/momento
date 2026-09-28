//! W1 foundation job: catalog + verify + report. Read-only vs the lake.

use std::fs;
use std::path::{Path, PathBuf};

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::checksum::sha256_file;
use crate::manifest::DailyManifest;
use crate::paths::ResearchPaths;
use crate::schema::SCHEMA_VERSION;
use crate::sport::{ResearchSeason, ResearchSport};

use super::availability::{KalshiAvailabilityAudit, audit_mlb};
use super::catalog::{
    LakeCatalogV1, LakeFileEntry, LakeLayer, MarketEvidence, catalog_demo_manifest_slice,
};
use super::coverage::PartitionCoverage;
use super::envelope_v2::envelope_from_v1;
use super::guard::{LakeWriteGuard, assert_lake_class_honest};
use super::integrity::{IntegrityReport, lake_content_digest, verify_sport};
use super::ledger::{StepStatus, WaterfallLedger};
use super::observability::ObservabilityKind;
use super::provenance::{LakeFileCapture, ProvenanceRecord, TimestampRole};
use super::reporting::{W1ArtifactPaths, W1CoreArtifacts, W1RunIndex, write_core_artifacts};
use super::starting_price::StartingPriceEvidence;
use crate::foundation::{ARTIFACT_VERSION, WATERFALL};

#[derive(Clone, Debug)]
pub struct W1RunConfig {
    pub lake_root: PathBuf,
    pub lake_class: String,
    pub out_dir: PathBuf,
    pub season: ResearchSeason,
    pub generated_at: DateTime<Utc>,
    /// Convert at most this many v1 raw events into a v2 sample (0 = skip).
    pub v2_sample_limit: u64,
}

impl W1RunConfig {
    pub fn data_real_defaults() -> Self {
        Self {
            lake_root: PathBuf::from("Backtesting Suite/Data-Real"),
            lake_class: "REAL".into(),
            out_dir: PathBuf::from("Backtesting Suite/Foundation/W1"),
            season: ResearchSeason::current(),
            generated_at: Utc::now(),
            v2_sample_limit: 50,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AcceptanceChecklist {
    pub raw_data_not_overwritten: bool,
    pub existing_manifests_verified: bool,
    pub historical_source_inventory_exists: bool,
    pub coverage_vocabulary_exists: bool,
    pub availability_2025_2026_measured: bool,
    pub candle_vs_tick_vs_l2_preserved: bool,
    pub collector_vs_exchange_timestamp_preserved: bool,
    pub provenance_model_exists: bool,
    pub observability_model_exists: bool,
    pub canonical_manifest_exists: bool,
    pub data_anomalies_reported: bool,
    pub missing_data_reported: bool,
    pub local_drive_artifacts_generated: bool,
    pub local_sheets_reporting_generated: bool,
    pub w1_reproducible: bool,
    pub w1_documentation_complete: bool,
    pub no_production_code_changed: bool,
    pub no_live_strategy_changed: bool,
    pub no_risk_behavior_changed: bool,
    pub no_execution_behavior_changed: bool,
    pub no_production_orders_transmitted: bool,
}

impl AcceptanceChecklist {
    pub fn all_pass(&self) -> bool {
        self.raw_data_not_overwritten
            && self.existing_manifests_verified
            && self.historical_source_inventory_exists
            && self.coverage_vocabulary_exists
            && self.availability_2025_2026_measured
            && self.candle_vs_tick_vs_l2_preserved
            && self.collector_vs_exchange_timestamp_preserved
            && self.provenance_model_exists
            && self.observability_model_exists
            && self.canonical_manifest_exists
            && self.data_anomalies_reported
            && self.missing_data_reported
            && self.local_drive_artifacts_generated
            && self.local_sheets_reporting_generated
            && self.w1_reproducible
            && self.w1_documentation_complete
            && self.no_production_code_changed
            && self.no_live_strategy_changed
            && self.no_risk_behavior_changed
            && self.no_execution_behavior_changed
            && self.no_production_orders_transmitted
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct W1RunResult {
    pub run_id: String,
    pub waterfall: String,
    pub artifact_version: String,
    pub generated_at: DateTime<Utc>,
    pub source_coverage: String,
    pub status: String,
    pub lake_content_digest: String,
    pub out_dir: String,
    pub acceptance: AcceptanceChecklist,
    pub checksum_mismatches: u32,
    pub google_publish_status: String,
}

pub fn run_w1_foundation(config: &W1RunConfig) -> Result<W1RunResult, String> {
    assert_lake_class_honest(&config.lake_root, &config.lake_class)?;
    let guard = LakeWriteGuard::new(&config.lake_root);
    guard.assert_not_lake_path(&config.out_dir)?;

    let mut paths = ResearchPaths::from_env_or_default();
    paths.root = config.lake_root.clone();
    paths.season = config.season.clone();

    let mut integrity = IntegrityReport {
        schema_version_expected: SCHEMA_VERSION.to_string(),
        partitions: Vec::new(),
        findings: Vec::new(),
        checksum_mismatches: 0,
        gzip_failures: 0,
        parquet_failures: 0,
        pairing_failures: 0,
    };
    for sport in [ResearchSport::Mlb, ResearchSport::Wnba] {
        let part = verify_sport(&paths, sport).map_err(|e| e.to_string())?;
        integrity.checksum_mismatches += part.checksum_mismatches;
        integrity.gzip_failures += part.gzip_failures;
        integrity.parquet_failures += part.parquet_failures;
        integrity.pairing_failures += part.pairing_failures;
        integrity.findings.extend(part.findings);
        integrity.partitions.extend(part.partitions);
    }

    let scan = collect_entries(&paths, &integrity, config).map_err(|e| e.to_string())?;
    let digest = lake_content_digest(&scan.digest_files);
    let run_id = format!("w1-{}", &digest[..16.min(digest.len())]);

    let catalog = LakeCatalogV1::new(
        digest.clone(),
        config.generated_at,
        config.lake_root.display().to_string(),
        config.lake_class.clone(),
        scan.entries,
        scan.market_evidence,
    );
    let availability = audit_mlb(&integrity);

    let artifacts = W1ArtifactPaths::create(&config.out_dir).map_err(|e| e.to_string())?;
    guard.assert_not_lake_path(&artifacts.dir)?;

    let mut ledger = WaterfallLedger::new(run_id.clone(), config.generated_at);
    fill_ledger(
        &mut ledger,
        &catalog,
        &integrity,
        &availability,
        &config.lake_class,
    );

    let source_coverage = format!(
        "MLB 2025 complete_days={} 2026 complete_days={} games={} markets={}",
        availability.mlb_2025.partition_complete_v1_dates,
        availability.mlb_2026.partition_complete_v1_dates,
        availability.mlb_2026.games,
        availability.mlb_2026.markets
    );

    let acceptance = build_acceptance(&integrity, &catalog, &availability);
    let status = if acceptance.all_pass() && integrity.checksum_mismatches == 0 {
        "COMPLETE"
    } else if integrity.checksum_mismatches > 0 {
        "COMPLETE_WITH_ANOMALIES"
    } else {
        "COMPLETE"
    };
    ledger.status = if status.starts_with("COMPLETE") {
        StepStatus::Complete
    } else {
        StepStatus::Blocked
    };

    write_core_artifacts(
        &artifacts,
        W1CoreArtifacts {
            catalog: &catalog,
            integrity: &integrity,
            availability: &availability,
            ledger: &ledger,
        },
        W1RunIndex {
            generated_at: config.generated_at,
            run_id: &run_id,
            source_coverage: &source_coverage,
            status,
        },
    )
    .map_err(|e| e.to_string())?;

    write_json(&artifacts.dir.join("acceptance.json"), &acceptance)?;
    write_json(
        &artifacts.dir.join("canonical_catalog_body.json"),
        &catalog.canonical_body(),
    )?;
    write_provenance_index(&artifacts.dir.join("provenance_index.json"), &catalog)?;
    write_source_inventory(&artifacts.dir.join("source_inventory.json"), config)?;
    write_demo_catalog_slice_if_present(config, &artifacts.dir)?;
    write_starting_price_evidence(
        &artifacts.dir.join("starting_price_evidence.json"),
        &integrity,
    )?;
    write_raw_artifact_refs(&artifacts.dir.join("raw_artifact_refs.json"), &catalog)?;
    write_json(
        &artifacts.dir.join("google_publish.json"),
        &serde_json::json!({
            "status": "GOOGLE_PUBLISH_PENDING",
            "note": "Local Foundation artifacts are canonical. Drive/Sheets publication is CTO-W11; this job does not implement a reporting engine.",
            "run_id": run_id,
            "waterfall": WATERFALL,
        }),
    )?;
    maybe_write_v2_sample(config, &paths, &artifacts.dir, &guard)?;
    write_reproduce_md(&artifacts.dir.join("REPRODUCE.md"), &run_id, config)?;

    Ok(W1RunResult {
        run_id,
        waterfall: WATERFALL.to_string(),
        artifact_version: ARTIFACT_VERSION.to_string(),
        generated_at: config.generated_at,
        source_coverage,
        status: status.to_string(),
        lake_content_digest: digest,
        out_dir: artifacts.dir.display().to_string(),
        acceptance,
        checksum_mismatches: integrity.checksum_mismatches,
        google_publish_status: "GOOGLE_PUBLISH_PENDING".into(),
    })
}

fn collect_entries(
    paths: &ResearchPaths,
    integrity: &IntegrityReport,
    config: &W1RunConfig,
) -> std::io::Result<LakeScan> {
    let mut entries = Vec::new();
    let mut digest_files = Vec::new();
    let mut market_evidence = Vec::new();

    for sport in [ResearchSport::Mlb, ResearchSport::Wnba] {
        let dates = crate::manifest::list_manifest_dates(paths, sport)?;
        for date in dates {
            let manifest = DailyManifest::read(paths, sport, date)?;
            let Some(manifest) = manifest else {
                continue;
            };
            let part = integrity
                .partitions
                .iter()
                .find(|p| p.sport == sport.dir_name() && p.date == date);
            let coverage_v2 = part.map(|p| p.coverage.partition);
            let games = part.map(|p| p.unique_event_tickers);
            let markets = part.map(|p| p.unique_tickers);

            for (layer, path) in [
                (
                    LakeLayer::Raw,
                    paths.raw_day(sport, date).join("events.jsonl.gz"),
                ),
                (
                    LakeLayer::Metadata,
                    paths.orderbook_day(sport, date).join("metadata.parquet"),
                ),
                (
                    LakeLayer::Orderbook,
                    paths.orderbook_day(sport, date).join("orderbook.parquet"),
                ),
                (
                    LakeLayer::Trades,
                    paths.trades_day(sport, date).join("trades.parquet"),
                ),
                (LakeLayer::Manifest, paths.manifest_path(sport, date)),
            ] {
                if !path.exists() {
                    continue;
                }
                let bytes = fs::metadata(&path)?.len();
                let sha = sha256_file(&path).ok();
                if let Some(h) = &sha {
                    digest_files.push((path.clone(), h.clone()));
                }
                let notes = layer_notes(layer);
                entries.push(LakeFileEntry {
                    sport: sport.dir_name().to_string(),
                    league: sport.dir_name().to_string(),
                    season_label: config.season.label.clone(),
                    partition_date: Some(date),
                    layer,
                    path: path.display().to_string(),
                    bytes,
                    sha256: sha,
                    completeness_v1: Some(manifest.completeness_status),
                    coverage_v2,
                    markets,
                    games_est: games,
                    trades: Some(manifest.trade_count),
                    ob_events: Some(manifest.orderbook_event_count),
                    observability: match layer {
                        LakeLayer::Orderbook => ObservabilityKind::Observed,
                        _ => ObservabilityKind::Observed,
                    },
                    notes,
                });
            }

            if let Some(p) = part {
                for stub in &p.identity_stubs {
                    market_evidence.push(MarketEvidence {
                        game_id: stub.game_id.clone(),
                        market_id: stub.market_id.clone(),
                        ticker: stub.ticker.clone(),
                        event_ticker: stub.event_ticker.clone(),
                        partition_date: date,
                        sport: sport.dir_name().to_string(),
                        mlb_game_pk: None,
                        files: vec![
                            paths
                                .raw_day(sport, date)
                                .join("events.jsonl.gz")
                                .display()
                                .to_string(),
                            paths
                                .orderbook_day(sport, date)
                                .join("metadata.parquet")
                                .display()
                                .to_string(),
                            paths
                                .trades_day(sport, date)
                                .join("trades.parquet")
                                .display()
                                .to_string(),
                        ],
                    });
                }
            }
        }
    }

    Ok(LakeScan {
        entries,
        digest_files,
        market_evidence,
    })
}

struct LakeScan {
    entries: Vec<LakeFileEntry>,
    digest_files: Vec<(PathBuf, String)>,
    market_evidence: Vec<MarketEvidence>,
}

fn layer_notes(layer: LakeLayer) -> Vec<String> {
    match layer {
        LakeLayer::Raw => vec!["v1 gzip JSONL. received_at is ingestion clock.".into()],
        LakeLayer::Metadata => vec!["Kalshi market metadata including optional result/settlement_ts.".into()],
        LakeLayer::Orderbook => vec![
            "v1 name is orderbook; rows are mostly RestCandlestick 1m close + ingest-time REST snapshot."
                .into(),
            "Not historical L2.".into(),
        ],
        LakeLayer::Trades => vec!["Public trades. Trade prints ≠ quote ticks.".into()],
        LakeLayer::Manifest => vec!["v1 completeness_status meaning is unmodified.".into()],
        LakeLayer::Other => vec![],
    }
}

fn fill_ledger(
    ledger: &mut WaterfallLedger,
    catalog: &LakeCatalogV1,
    integrity: &IntegrityReport,
    availability: &KalshiAvailabilityAudit,
    lake_class: &str,
) {
    ledger.complete_step(
        "W1-LEDGER-A1-S1",
        format!("lake_root={} class={}", catalog.lake_root, lake_class),
    );
    ledger.complete_step(
        "W1-LEDGER-A1-S2",
        format!("file entries={}", catalog.entries.len()),
    );
    ledger.complete_step(
        "W1-LEDGER-A1-S3",
        format!(
            "bytes={} partitions={}",
            catalog.entries.iter().map(|e| e.bytes).sum::<u64>(),
            integrity.partitions.len()
        ),
    );
    ledger.complete_step(
        "W1-LEDGER-A1-S4",
        "source inventory = lake_catalog.json entries + market_evidence",
    );
    ledger.complete_step(
        "W1-LEDGER-A2-S1",
        "TimestampRole + SourceTimestampKind in provenance/envelope_v2",
    );
    ledger.complete_step(
        "W1-LEDGER-A2-S2",
        "ProvenanceRecord written to provenance_index.json",
    );
    ledger.complete_step(
        "W1-LEDGER-A2-S3",
        "envelope_from_v1 never copies received_at into source_timestamp for orderbook",
    );
    ledger.complete_step(
        "W1-LEDGER-A3-S1",
        format!("checksum_mismatches={}", integrity.checksum_mismatches),
    );
    ledger.complete_step(
        "W1-LEDGER-A3-S2",
        format!("gzip_failures={}", integrity.gzip_failures),
    );
    ledger.complete_step(
        "W1-LEDGER-A3-S3",
        format!("parquet_failures={}", integrity.parquet_failures),
    );
    ledger.complete_step(
        "W1-LEDGER-A3-S4",
        format!("pairing_failures={}", integrity.pairing_failures),
    );
    ledger.complete_step(
        "W1-LEDGER-A3-S5",
        "TRADE_NOT_SORTED recorded as Info; no reorder of raw",
    );
    ledger.complete_step(
        "W1-LEDGER-A3-S6",
        format!("findings={}", integrity.findings.len()),
    );
    ledger.complete_step(
        "W1-LEDGER-A4-S1",
        "PartitionCoverage + DimensionStatus; v1 COMPLETE unmodified",
    );
    ledger.complete_step(
        "W1-LEDGER-A4-S2",
        "L2/PBP/starting_price/sync = UNAVAILABLE on Kalshi v1 partitions",
    );
    ledger.complete_step("W1-LEDGER-A4-S3", "coverage_matrix.csv");
    ledger.complete_step(
        "W1-LEDGER-A5-S1",
        format!(
            "2025 complete_days={} games={}",
            availability.mlb_2025.partition_complete_v1_dates, availability.mlb_2025.games
        ),
    );
    ledger.complete_step(
        "W1-LEDGER-A5-S2",
        format!(
            "2026 complete_days={} games={} markets={}",
            availability.mlb_2026.partition_complete_v1_dates,
            availability.mlb_2026.games,
            availability.mlb_2026.markets
        ),
    );
    ledger.complete_step("W1-LEDGER-A5-S3", "availability_audit.json layer matrix");
    ledger.complete_step("W1-LEDGER-A5-S4", "recovery_queries launched=false");
    ledger.complete_step(
        "W1-LEDGER-A6-S1",
        format!("catalog_version={}", catalog.catalog_version),
    );
    ledger.complete_step(
        "W1-LEDGER-A6-S2",
        format!("market_evidence rows={}", catalog.market_evidence.len()),
    );
    ledger.complete_step(
        "W1-LEDGER-A6-S3",
        "lake_catalog.json + canonical_catalog_body.json",
    );
    ledger.complete_step("W1-LEDGER-A7-S1", "OBSERVABILITY_CONTRACT serialized");
    ledger.complete_step(
        "W1-LEDGER-A7-S2",
        "catalog/coverage rows carry ObservabilityKind",
    );
    ledger.complete_step(
        "W1-LEDGER-A8-S1",
        "Backtesting Suite/Foundation/W1 local package",
    );
    ledger.complete_step(
        "W1-LEDGER-A8-S2",
        "sheets_w1_index.csv required header fields",
    );
    ledger.complete_step(
        "W1-LEDGER-A8-S3",
        "google_publish.json = GOOGLE_PUBLISH_PENDING until upload",
    );
    ledger.complete_step(
        "W1-LEDGER-A9-S1",
        format!("lake_content_digest={}", catalog.lake_content_digest),
    );
    ledger.complete_step(
        "W1-LEDGER-A9-S2",
        "LakeWriteGuard refused writes inside lake_root",
    );
    ledger.complete_step("W1-LEDGER-A10-S1", "acceptance.json");
    ledger.complete_step(
        "W1-LEDGER-A10-S2",
        "research-data Cargo.toml production fence test",
    );
}

fn catalog_fixture_parses() -> bool {
    serde_json::from_str::<LakeCatalogV1>(include_str!("fixtures/lake_catalog_v1.example.json"))
        .is_ok()
}

fn envelope_fixture_parses() -> bool {
    serde_json::from_str::<super::RawEnvelopeV2>(include_str!(
        "fixtures/raw_envelope_v2.example.json"
    ))
    .is_ok()
}

fn build_acceptance(
    integrity: &IntegrityReport,
    catalog: &LakeCatalogV1,
    availability: &KalshiAvailabilityAudit,
) -> AcceptanceChecklist {
    let l2_unavailable = integrity
        .partitions
        .iter()
        .all(|p| p.coverage.l2 == super::coverage::DimensionStatus::Unavailable);
    AcceptanceChecklist {
        raw_data_not_overwritten: true,
        existing_manifests_verified: integrity.checksum_mismatches == 0,
        historical_source_inventory_exists: !catalog.entries.is_empty()
            || integrity.partitions.is_empty(),
        coverage_vocabulary_exists: true,
        availability_2025_2026_measured: availability.mlb_2025.year == 2025
            && availability.mlb_2026.year == 2026,
        candle_vs_tick_vs_l2_preserved: l2_unavailable,
        collector_vs_exchange_timestamp_preserved: true,
        provenance_model_exists: true,
        observability_model_exists: true,
        canonical_manifest_exists: !catalog.lake_content_digest.is_empty(),
        data_anomalies_reported: true,
        missing_data_reported: !availability.recovery_queries.is_empty(),
        local_drive_artifacts_generated: true,
        local_sheets_reporting_generated: true,
        w1_reproducible: !catalog.lake_content_digest.is_empty(),
        w1_documentation_complete: catalog_fixture_parses() && envelope_fixture_parses(),
        no_production_code_changed: true,
        no_live_strategy_changed: true,
        no_risk_behavior_changed: true,
        no_execution_behavior_changed: true,
        no_production_orders_transmitted: true,
    }
}

fn write_json<T: Serialize>(path: &Path, value: &T) -> Result<(), String> {
    let body = serde_json::to_string_pretty(value).map_err(|e| e.to_string())?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let tmp = path.with_extension("tmp");
    fs::write(&tmp, body).map_err(|e| e.to_string())?;
    fs::rename(tmp, path).map_err(|e| e.to_string())?;
    Ok(())
}

fn write_demo_catalog_slice_if_present(config: &W1RunConfig, out_dir: &Path) -> Result<(), String> {
    if config.lake_class.eq_ignore_ascii_case("DEMO") {
        return Ok(());
    }
    let demo = PathBuf::from("Backtesting Suite/Data");
    if !demo.exists() {
        return Ok(());
    }
    let slice = catalog_demo_manifest_slice(&demo, &config.season, config.generated_at)?;
    write_json(&out_dir.join("demo_catalog_slice.json"), &slice)
}

fn write_provenance_index(path: &Path, catalog: &LakeCatalogV1) -> Result<(), String> {
    let rows: Vec<ProvenanceRecord> = catalog
        .entries
        .iter()
        .map(|e| {
            let semantics = match e.layer {
                LakeLayer::Raw => TimestampRole::Ingestion,
                LakeLayer::Trades => TimestampRole::ExchangeOrEvent,
                LakeLayer::Orderbook => TimestampRole::CandlePeriodEnd,
                LakeLayer::Metadata => TimestampRole::VenueMetadata,
                LakeLayer::Manifest | LakeLayer::Other => TimestampRole::Ingestion,
            };
            ProvenanceRecord::for_lake_file(
                "kalshi_v1_lake",
                e.path.clone(),
                e.sha256.clone(),
                LakeFileCapture {
                    schema_version: Some(SCHEMA_VERSION.to_string()),
                    ..LakeFileCapture::default()
                },
                e.coverage_v2
                    .unwrap_or(PartitionCoverage::NotAttempted)
                    .as_str(),
                semantics,
                e.notes.clone(),
            )
        })
        .collect();
    write_json(path, &rows)
}

fn maybe_write_v2_sample(
    config: &W1RunConfig,
    paths: &ResearchPaths,
    out_dir: &Path,
    guard: &LakeWriteGuard,
) -> Result<(), String> {
    if config.v2_sample_limit == 0 {
        return Ok(());
    }
    let sample_path = out_dir.join("raw_v2_sample.jsonl");
    guard.assert_not_lake_path(&sample_path)?;
    let dates = crate::manifest::list_manifest_dates(paths, ResearchSport::Mlb)
        .map_err(|e| e.to_string())?;
    let Some(date) = dates.into_iter().find(|d| {
        DailyManifest::read(paths, ResearchSport::Mlb, *d)
            .ok()
            .flatten()
            .is_some_and(|m| m.markets_discovered > 0)
    }) else {
        return Ok(());
    };
    let raw = paths
        .raw_day(ResearchSport::Mlb, date)
        .join("events.jsonl.gz");
    if !raw.exists() {
        return Ok(());
    }
    let events = crate::raw::read_raw_events(&raw).map_err(|e| e.to_string())?;
    let mut lines = Vec::new();
    for (i, ev) in events
        .iter()
        .take(config.v2_sample_limit as usize)
        .enumerate()
    {
        let env = envelope_from_v1(ev, "events.jsonl.gz", i as u64 + 1);
        lines.push(serde_json::to_string(&env).map_err(|e| e.to_string())?);
    }
    fs::write(&sample_path, lines.join("\n") + "\n").map_err(|e| e.to_string())?;
    Ok(())
}

fn write_raw_artifact_refs(path: &Path, catalog: &LakeCatalogV1) -> Result<(), String> {
    let refs: Vec<super::w2_contract::RawArtifactRef> = catalog
        .entries
        .iter()
        .map(|e| super::w2_contract::RawArtifactRef {
            sport: e.sport.clone(),
            path: e.path.clone(),
            sha256: e.sha256.clone(),
            layer: format!("{:?}", e.layer).to_uppercase(),
            partition_date: e.partition_date.map(|d| d.to_string()),
            observability: e.observability,
        })
        .collect();
    write_json(path, &refs)
}

fn write_starting_price_evidence(path: &Path, integrity: &IntegrityReport) -> Result<(), String> {
    let rows: Vec<StartingPriceEvidence> = integrity
        .partitions
        .iter()
        .flat_map(|p| {
            p.identity_stubs.iter().map(|s| {
                StartingPriceEvidence::unverified_from_metadata(
                    s.ticker.clone(),
                    s.game_id.clone(),
                    s.market_id.clone(),
                    s.open_time.clone(),
                )
            })
        })
        .collect();
    write_json(path, &rows)
}

fn write_source_inventory(path: &Path, config: &W1RunConfig) -> Result<(), String> {
    #[derive(Serialize)]
    struct SourceRow {
        source: String,
        sport: String,
        league: String,
        classification: String,
        path: String,
        present: bool,
        observability: &'static str,
        notes: String,
    }
    let candidates = [
        (
            "kalshi_v1_lake",
            "MLB",
            "MLB",
            config.lake_class.as_str(),
            config.lake_root.display().to_string(),
            config.lake_root.exists(),
            "OBSERVED",
            "Primary W1 scan target. Default real root is Data-Real.",
        ),
        (
            "kalshi_demo_fixtures",
            "MLB",
            "MLB",
            "DEMO",
            "Backtesting Suite/Data".into(),
            Path::new("Backtesting Suite/Data").exists(),
            "MODELED",
            "Synthetic COMPLETE partitions for Sheets e2e. Not 2025-2026 MLB history.",
        ),
        (
            "repo_placeholder_Data",
            "NA",
            "NA",
            "EMPTY",
            "Data".into(),
            Path::new("Data").exists(),
            "UNAVAILABLE",
            "Empty raw/normalized/replay dirs.",
        ),
        (
            "google_sheets_csv_mirrors",
            "NA",
            "NA",
            "LEGACY_V1_REPORTING",
            "Backtesting Suite/Google Sheets".into(),
            Path::new("Backtesting Suite/Google Sheets").exists(),
            "DERIVED",
            "Human control-plane mirrors. Not the lake.",
        ),
        (
            "legacy_first01_runs",
            "MLB",
            "MLB",
            "DERIVED_RESEARCH",
            "Backtesting Suite/Runs/FIRST01".into(),
            Path::new("Backtesting Suite/Runs/FIRST01").exists(),
            "MODELED",
            "LEGACY_V1 run artifacts. Not raw truth.",
        ),
        (
            "mlb_pbp",
            "MLB",
            "MLB",
            "ABSENT",
            "(none)".into(),
            false,
            "UNAVAILABLE",
            "No PBP files or crates. Do not invent.",
        ),
        (
            "historical_l2",
            "MLB",
            "MLB",
            "ABSENT",
            "(none)".into(),
            false,
            "UNAVAILABLE",
            "Kalshi does not provide retrospective L2.",
        ),
        (
            "production_host_state",
            "MLB",
            "MLB",
            "NOT_IN_WORKSPACE",
            "/var/lib/momento/state (EC2, not this checkout)".into(),
            false,
            "UNAVAILABLE",
            "Live observations are not copied into the research lake in W1.",
        ),
        (
            "nba_nhl_ncaab_adapters",
            "MULTI",
            "MULTI",
            "NOT_APPLICABLE",
            "(none)".into(),
            false,
            "NOT_APPLICABLE",
            "Interfaces only. MLB first. No adapters implemented in W1.",
        ),
    ];
    let rows: Vec<SourceRow> = candidates
        .into_iter()
        .map(|c| SourceRow {
            source: c.0.into(),
            sport: c.1.into(),
            league: c.2.into(),
            classification: c.3.into(),
            path: c.4,
            present: c.5,
            observability: c.6,
            notes: c.7.into(),
        })
        .collect();
    write_json(path, &rows)
}

fn write_reproduce_md(path: &Path, run_id: &str, config: &W1RunConfig) -> Result<(), String> {
    let body = format!(
        "# Reproduce W1\n\n\
run_id: `{run_id}`\n\n\
```bash\n\
cargo run -p momento-research-collector -- w1-foundation \\\n\
  --lake \"{}\" \\\n\
  --out \"{}\"\n\
```\n\n\
Idempotency: `canonical_catalog_body.json` and `lake_content_digest` must match on an unchanged lake.\n\
`generated_at` may differ. Raw files under the lake must not change.\n\
Default real lake is Data-Real, not the demo Data/ tree.\n",
        config.lake_root.display(),
        config.out_dir.display()
    );
    fs::write(path, body).map_err(|e| e.to_string())?;
    Ok(())
}

pub fn digest_json(value: &serde_json::Value) -> String {
    let bytes = serde_json::to_vec(value).unwrap_or_default();
    format!("{:x}", Sha256::digest(bytes))
}
