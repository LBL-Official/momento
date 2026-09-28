//! Idempotent ingest orchestrator with fail-closed W1 handoff.

use std::collections::BTreeSet;
use std::fs;

use chrono::{Duration, NaiveDate};
use momento_research_data::foundation::{
    LakeFileCapture, LakeWriteGuard, ProvenanceRecord, TimestampRole,
};

use crate::alerts::{Alert, AlertKind};
use crate::cloud::cloud_deployment_status;
use crate::commit::commit_artifacts;
use crate::corpus::corpus_from_pairs;
use crate::coverage::summarize_plan_windows;
use crate::error::IngestError;
use crate::fence::assert_ingest_root_allowed;
use crate::join::{ObservedMlbGame, join_game_market_pairs};
use crate::kalshi::{
    BlockedNetworkKalshiSource, DiscoveredMarket, KalshiDiscoverySource,
    candles_payload_unavailable, candlesticks_array, catalog_kalshi_manifests,
    completeness_from_landed_bytes, completeness_from_payload, identity_row,
    land_historical_candles, land_historical_trades, land_kalshi_discovery, land_market_settlement,
    landed_candles_observed, landed_trades_observed, status_from_json, trades_array,
    wrap_historical_candles, wrap_historical_trades_sidecar, wrap_kalshi_discovery_envelope,
};
use crate::kalshi_live::artifact_window;
use crate::land::{LandResult, land_bytes};
use crate::lock::IngestLock;
use crate::paths::{IngestPaths, write_json_atomic};
use crate::planner::overlap_window;
use crate::schedule::weekly_window;
use crate::source::{DiscoveredPartition, FetchOutcome, PartitionSource, fetch_with_retries};
use crate::types::{
    ARTIFACT_VERSION, ChecksumReport, CommitStatus, CommittedArtifact, CoverageRow, DateWindow,
    ExecutionMode, GameMarketPair, IdentityMapping, IdentityRow, IngestPlan, IngestRunReport,
    MarketCompleteness, PLANE, PartitionStatus, RunStatus, SOURCE_KALSHI_DISCOVERY,
    SOURCE_STATSAPI,
};
use crate::w2_gate::canonicalize_committed;
use crate::watermarks::{as_report_vec, compute_state, load_watermarks, store_watermarks};

struct PartitionOutcome {
    row: CoverageRow,
    artifact: Option<CommittedArtifact>,
    provenance: Option<ProvenanceRecord>,
}

pub fn run_ingest(
    plan: &IngestPlan,
    pbp: &dyn PartitionSource,
) -> Result<IngestRunReport, IngestError> {
    run_ingest_with_sources(plan, pbp, &BlockedNetworkKalshiSource)
}

pub fn run_ingest_with_sources(
    plan: &IngestPlan,
    pbp: &dyn PartitionSource,
    kalshi: &dyn KalshiDiscoverySource,
) -> Result<IngestRunReport, IngestError> {
    let guard = LakeWriteGuard::new(&plan.lake_root);
    guard
        .assert_not_lake_path(&plan.ingest_root)
        .map_err(IngestError::LakeWriteForbidden)?;
    assert_ingest_root_allowed(
        &plan.ingest_root,
        &plan.lake_root,
        &plan.forbidden_write_roots,
    )?;

    let paths = IngestPaths::new(&plan.ingest_root);
    let run_id = plan.run_id();
    let run_dir = paths.ensure_run(&run_id)?;
    let _lock = IngestLock::acquire(paths.lock_path())?;

    let persisted = if plan.persist_watermarks {
        load_watermarks(&paths.watermark_path())?
    } else {
        Default::default()
    };
    let windows = collect_windows(plan, &persisted);
    let mut coverage = Vec::new();
    let mut alerts: Vec<Alert> = Vec::new();
    let mut pending = Vec::new();
    let mut provenance = Vec::new();
    let mut identity = Vec::new();
    let mut seen_partitions = BTreeSet::new();
    let mut observed_games: Vec<ObservedMlbGame> = Vec::new();
    let mut kalshi_markets: Vec<crate::kalshi::DiscoveredMarket> = Vec::new();
    let mut dates_budget: BTreeSet<NaiveDate> = BTreeSet::new();

    for window in &windows {
        let listed = pbp.list_partitions(window)?;
        eprintln!(
            "pbp list {} {}..{} partitions={}",
            window.label,
            window.start,
            window.end,
            listed.len()
        );
        let mut seen_dates = BTreeSet::new();
        if listed.is_empty() && !plan.fill_unlisted_dates {
            coverage.push(CoverageRow {
                date: window.start.to_string(),
                source: SOURCE_STATSAPI.into(),
                partition_id: window.label.clone(),
                status: PartitionStatus::Unavailable,
                sha256: None,
                path: None,
                notes: format!(
                    "source listed 0 partitions for {} ({}..{}); not fabricated COMPLETE",
                    window.label, window.start, window.end
                ),
            });
            alerts.push(Alert::new(
                AlertKind::SourceUnavailable,
                format!("MLB source listed 0 partitions for {}", window.label),
            ));
            continue;
        }
        for part in listed {
            seen_dates.insert(part.date);
            if let Some(max) = plan.max_days {
                if !dates_budget.contains(&part.date) && dates_budget.len() >= max as usize {
                    continue;
                }
                dates_budget.insert(part.date);
            }
            if !seen_partitions.insert(part.partition_id.clone()) {
                alerts.push(Alert::new(
                    AlertKind::DuplicateLogicalArtifact,
                    format!("duplicate discovery {}", part.partition_id),
                ));
                continue;
            }
            match process_partition(plan, &paths, pbp, &part, &mut alerts) {
                Ok(out) => {
                    if matches!(
                        out.row.status,
                        PartitionStatus::Complete
                            | PartitionStatus::AlreadyKnown
                            | PartitionStatus::VersionConflict
                    ) {
                        observed_games.push(ObservedMlbGame::from_partition(&part));
                    }
                    coverage.push(out.row);
                    if let Some(a) = out.artifact {
                        pending.push(a);
                    }
                    if let Some(p) = out.provenance {
                        provenance.push(p);
                    }
                }
                Err(e) => {
                    coverage.push(CoverageRow {
                        date: part.date.to_string(),
                        source: part.source.clone(),
                        partition_id: part.partition_id.clone(),
                        status: PartitionStatus::Failed,
                        sha256: None,
                        path: None,
                        notes: e.to_string(),
                    });
                    alerts.push(Alert::new(AlertKind::RepeatedSourceFailure, e.to_string()));
                }
            }
        }
        if plan.fill_unlisted_dates {
            for date in dates_inclusive(window.start, window.end) {
                if !seen_dates.contains(&date) {
                    coverage.push(CoverageRow {
                        date: date.to_string(),
                        source: SOURCE_STATSAPI.into(),
                        partition_id: date.to_string(),
                        status: PartitionStatus::Unavailable,
                        sha256: None,
                        path: None,
                        notes: "source did not return this date; not fabricated COMPLETE".into(),
                    });
                }
            }
        }
    }

    if plan.kalshi_catalog {
        match catalog_kalshi_manifests(&plan.lake_root, "2025-2026") {
            Ok(rows) => coverage.extend(rows),
            Err(e) => alerts.push(Alert::new(
                AlertKind::SourceUnavailable,
                format!("kalshi catalog: {e}"),
            )),
        }
    }

    if plan.kalshi_discover {
        let mut sink = KalshiSink {
            coverage: &mut coverage,
            pending: &mut pending,
            provenance: &mut provenance,
            identity: &mut identity,
            alerts: &mut alerts,
            markets: &mut kalshi_markets,
        };
        process_kalshi(plan, &paths, &windows, kalshi, &mut sink)?;
    } else if !plan.network_enabled {
        coverage.push(CoverageRow {
            date: plan.as_of_date().to_string(),
            source: SOURCE_KALSHI_DISCOVERY.into(),
            partition_id: "kalshi_live_discovery".into(),
            status: PartitionStatus::Unavailable,
            sha256: None,
            path: None,
            notes: "Kalshi live discovery BLOCKED (network disabled); not COMPLETE".into(),
        });
    }

    let handoff = match commit_artifacts(&run_id, plan.generated_at, pending) {
        Ok(h) => h,
        Err(e) => {
            alerts.push(Alert::new(AlertKind::W1CommitFailure, e.to_string()));
            return Err(e);
        }
    };

    let (w2_attempted, w2_ok, w2_skip) = if plan.invoke_w2 {
        match canonicalize_committed(&handoff, &plan.lake_root) {
            Ok(Some(rep)) => (rep.games_attempted, rep.reconstruction_ok, None),
            Ok(None) => (0, 0, Some("no committed StatsAPI artifacts".into())),
            Err(e) => {
                alerts.push(Alert::new(
                    AlertKind::DownstreamHandoffRefusal,
                    e.to_string(),
                ));
                return Err(e);
            }
        }
    } else {
        (
            0,
            0,
            Some("invoke_w2=false; COMMITTED refs available for W2/W3".into()),
        )
    };

    let status = run_status(&coverage, &alerts);
    let mut watermark_state = compute_state(&coverage);
    watermark_state = merge_watermark_dates(&persisted, watermark_state);
    if plan.persist_watermarks {
        store_watermarks(&paths.watermark_path(), &watermark_state)?;
    }
    let pairs = join_game_market_pairs(&observed_games, &kalshi_markets);
    let pbp_committed = coverage
        .iter()
        .filter(|r| {
            r.source == SOURCE_STATSAPI
                && matches!(
                    r.status,
                    PartitionStatus::Complete
                        | PartitionStatus::AlreadyKnown
                        | PartitionStatus::VersionConflict
                )
        })
        .count();
    let kalshi_committed = coverage
        .iter()
        .filter(|r| {
            r.source == SOURCE_KALSHI_DISCOVERY
                && matches!(
                    r.status,
                    PartitionStatus::Complete
                        | PartitionStatus::AlreadyKnown
                        | PartitionStatus::VersionConflict
                        | PartitionStatus::Unmatched
                        | PartitionStatus::Ambiguous
                )
        })
        .count();
    let corpus = corpus_from_pairs(
        observed_games.len(),
        pbp_committed,
        kalshi_markets.len(),
        kalshi_committed,
        &pairs,
    );
    let network_ready = plan.network_enabled
        && (pbp_committed > 0 || kalshi_committed > 0 || !kalshi_markets.is_empty());
    let watermarks = as_report_vec(&watermark_state);
    let window_coverage = summarize_plan_windows(&windows, &coverage);
    let checksum_report = checksum_from(&coverage);
    let alert_msgs: Vec<String> = alerts
        .iter()
        .map(|a| format!("{:?}: {}", a.kind, a.message))
        .collect();
    let audit_path = run_dir.join("audit_report.json");
    let report = IngestRunReport {
        run_id: run_id.clone(),
        plane: PLANE.into(),
        artifact_version: ARTIFACT_VERSION.into(),
        generated_at: plan.generated_at,
        status,
        network_enabled: plan.network_enabled,
        coverage,
        watermarks,
        handoff,
        w2_games_attempted: w2_attempted,
        w2_reconstruction_ok: w2_ok,
        w2_skipped_reason: w2_skip,
        alerts: alert_msgs,
        audit_path: audit_path.display().to_string(),
        execution_mode: crate::orchestrator::execution_mode_label(plan.execution_mode).into(),
        window_coverage,
        watermark_state,
        identity_report: identity,
        checksum_report,
        cloud_status: cloud_deployment_status(),
        code_ready: true,
        network_ready,
        backfill_complete: false,
        continuous_feed_operational: false,
        corpus,
    };
    write_run_files(&run_dir, &report, &provenance, &alerts, &pairs)?;
    Ok(report)
}

pub fn replay_run(run_dir: &std::path::Path) -> Result<IngestRunReport, IngestError> {
    let body = fs::read_to_string(run_dir.join("ingest_manifest.json"))?;
    Ok(serde_json::from_str(&body)?)
}

fn write_run_files(
    run_dir: &std::path::Path,
    report: &IngestRunReport,
    provenance: &[ProvenanceRecord],
    alerts: &[Alert],
    pairs: &[GameMarketPair],
) -> Result<(), IngestError> {
    write_json_atomic(&run_dir.join("ingest_manifest.json"), report)?;
    write_json_atomic(&run_dir.join("audit_report.json"), report)?;
    write_json_atomic(&run_dir.join("w1_handoff.json"), &report.handoff)?;
    write_json_atomic(&run_dir.join("provenance_index.json"), provenance)?;
    write_json_atomic(&run_dir.join("coverage.json"), &report.window_coverage)?;
    write_json_atomic(&run_dir.join("watermarks.json"), &report.watermark_state)?;
    write_json_atomic(
        &run_dir.join("checksum_report.json"),
        &report.checksum_report,
    )?;
    write_json_atomic(
        &run_dir.join("identity_discovery.json"),
        &report.identity_report,
    )?;
    write_json_atomic(&run_dir.join("alerts.json"), alerts)?;
    let failures: Vec<&CoverageRow> = report
        .coverage
        .iter()
        .filter(|r| r.status == PartitionStatus::Failed)
        .collect();
    write_json_atomic(&run_dir.join("failure_report.json"), &failures)?;
    let dups: Vec<&CoverageRow> = report
        .coverage
        .iter()
        .filter(|r| r.status == PartitionStatus::AlreadyKnown)
        .collect();
    write_json_atomic(&run_dir.join("duplicate_report.json"), &dups)?;
    let source_manifest = serde_json::json!({
        "run_id": report.run_id,
        "timestamp": report.generated_at,
        "source": ["mlb_statsapi", "kalshi_v1_lake", "kalshi_discovery"],
        "requested_windows": report.window_coverage,
        "artifact_counts": report.handoff.artifacts.len(),
        "commit_status": "COMMITTED_CHECKSUM_VERIFIED",
        "network_enabled": report.network_enabled,
    });
    write_json_atomic(&run_dir.join("source_manifest.json"), &source_manifest)?;
    write_json_atomic(&run_dir.join("corpus.json"), &report.corpus)?;
    write_json_atomic(&run_dir.join("game_market_pairs.json"), pairs)?;
    Ok(())
}

fn collect_windows(plan: &IngestPlan, persisted: &crate::types::WatermarkState) -> Vec<DateWindow> {
    let mut windows = plan.pbp_windows.clone();
    if plan.include_weekly {
        windows.push(weekly_window(plan.generated_at, plan.weekly_lookback_days));
    }
    if plan.overlap_days > 0 {
        if let Some(wm) = persisted
            .mlb_pbp_acquisition
            .as_deref()
            .and_then(|s| NaiveDate::parse_from_str(s, "%Y-%m-%d").ok())
        {
            windows.push(overlap_window(
                wm,
                plan.overlap_days,
                plan.as_of_date(),
                "mlb-pbp",
            ));
        }
    }
    windows
}

fn dates_inclusive(start: NaiveDate, end: NaiveDate) -> Vec<NaiveDate> {
    let mut out = Vec::new();
    let mut d = start;
    while d <= end {
        out.push(d);
        d += Duration::days(1);
    }
    out
}

fn process_partition(
    plan: &IngestPlan,
    paths: &IngestPaths,
    pbp: &dyn PartitionSource,
    part: &DiscoveredPartition,
    alerts: &mut Vec<Alert>,
) -> Result<PartitionOutcome, IngestError> {
    if plan.skip_existing {
        let dest = paths.landing_game(part.date, &part.partition_id);
        if dest.exists() {
            let sha = crate::paths::sha256_file(&dest)?;
            return Ok(committed_outcome(
                part,
                dest,
                sha,
                PartitionStatus::AlreadyKnown,
                "skip_existing: landing present; not re-fetched",
            ));
        }
    }
    let fetched = match fetch_with_retries(pbp, part, plan.max_retries, plan.retry_sleep_ms) {
        Ok(o) => o,
        Err(e) => {
            return Ok(PartitionOutcome {
                row: CoverageRow {
                    date: part.date.to_string(),
                    source: part.source.clone(),
                    partition_id: part.partition_id.clone(),
                    status: PartitionStatus::Failed,
                    sha256: None,
                    path: None,
                    notes: e.to_string(),
                },
                artifact: None,
                provenance: None,
            });
        }
    };
    match fetched {
        FetchOutcome::Missing => Ok(PartitionOutcome {
            row: CoverageRow {
                date: part.date.to_string(),
                source: part.source.clone(),
                partition_id: part.partition_id.clone(),
                status: PartitionStatus::Skipped,
                sha256: None,
                path: None,
                notes: format!(
                    "source status {} — SKIPPED (not a fake zero-event game)",
                    part.status_hint
                ),
            },
            artifact: None,
            provenance: None,
        }),
        FetchOutcome::Failure(msg) => Ok(PartitionOutcome {
            row: CoverageRow {
                date: part.date.to_string(),
                source: part.source.clone(),
                partition_id: part.partition_id.clone(),
                status: PartitionStatus::Failed,
                sha256: None,
                path: None,
                notes: msg,
            },
            artifact: None,
            provenance: None,
        }),
        FetchOutcome::Bytes(raw) => land_ok(plan, paths, part, &raw, alerts),
    }
}

fn land_ok(
    plan: &IngestPlan,
    paths: &IngestPaths,
    part: &DiscoveredPartition,
    raw: &[u8],
    alerts: &mut Vec<Alert>,
) -> Result<PartitionOutcome, IngestError> {
    let bytes = normalize_payload(part, raw, plan.generated_at)?;
    match land_bytes(paths, part, &bytes)? {
        LandResult::Written { path, sha256 } => Ok(committed_outcome(
            part,
            path,
            sha256,
            PartitionStatus::Complete,
            "landed and checksum-verified",
        )),
        LandResult::AlreadyKnown { path, sha256 } => {
            alerts.push(Alert::new(
                AlertKind::DuplicateLogicalArtifact,
                format!("ALREADY_KNOWN {}", part.partition_id),
            ));
            Ok(committed_outcome(
                part,
                path,
                sha256,
                PartitionStatus::AlreadyKnown,
                "same bytes; no overwrite",
            ))
        }
        LandResult::VersionConflict {
            original,
            original_sha: _,
            new_path,
            new_sha,
        } => {
            alerts.push(Alert::new(
                AlertKind::VersionConflict,
                format!(
                    "VERSION_CONFLICT {} new version {}; original preserved at {}",
                    part.partition_id,
                    new_sha,
                    original.display()
                ),
            ));
            Ok(committed_outcome(
                part,
                new_path,
                new_sha,
                PartitionStatus::VersionConflict,
                "new version stored; original not overwritten",
            ))
        }
    }
}

fn committed_outcome(
    part: &DiscoveredPartition,
    path: std::path::PathBuf,
    sha256: String,
    status: PartitionStatus,
    notes: &str,
) -> PartitionOutcome {
    let prov = ProvenanceRecord::for_lake_file(
        part.source.clone(),
        path.display().to_string(),
        Some(sha256.clone()),
        LakeFileCapture {
            collector_version: Some(ARTIFACT_VERSION.into()),
            schema_version: Some("W2.RAW.1.0.0".into()),
            retrieval_timestamp: None,
        },
        format!("{status:?}"),
        TimestampRole::Ingestion,
        vec![notes.into()],
    );
    PartitionOutcome {
        row: CoverageRow {
            date: part.date.to_string(),
            source: part.source.clone(),
            partition_id: part.partition_id.clone(),
            status,
            sha256: Some(sha256.clone()),
            path: Some(path.display().to_string()),
            notes: notes.into(),
        },
        artifact: Some(CommittedArtifact {
            artifact_id: format!("{}:{}", part.source, part.partition_id),
            source: part.source.clone(),
            path: path.display().to_string(),
            sha256,
            partition_id: part.partition_id.clone(),
            date: part.date.to_string(),
            commit_status: CommitStatus::Pending,
        }),
        provenance: Some(prov),
    }
}

struct KalshiSink<'a> {
    coverage: &'a mut Vec<CoverageRow>,
    pending: &'a mut Vec<CommittedArtifact>,
    provenance: &'a mut Vec<ProvenanceRecord>,
    identity: &'a mut Vec<IdentityRow>,
    alerts: &'a mut Vec<Alert>,
    markets: &'a mut Vec<crate::kalshi::DiscoveredMarket>,
}

fn process_kalshi(
    plan: &IngestPlan,
    paths: &IngestPaths,
    windows: &[DateWindow],
    kalshi: &dyn KalshiDiscoverySource,
    sink: &mut KalshiSink<'_>,
) -> Result<(), IngestError> {
    let mut seen = BTreeSet::new();
    for window in windows {
        let markets = kalshi.discover(window)?;
        if markets.is_empty() {
            sink.coverage.push(CoverageRow {
                date: window.start.to_string(),
                source: SOURCE_KALSHI_DISCOVERY.into(),
                partition_id: format!("discover:{}", window.label),
                status: PartitionStatus::Unavailable,
                sha256: None,
                path: None,
                notes: "Kalshi discovery returned 0 tickers; not fabricated".into(),
            });
            continue;
        }
        let n_markets = markets.len();
        for (i, market) in markets.into_iter().enumerate() {
            if market.ticker.trim().is_empty() {
                return Err(IngestError::SourceFailure(
                    "Kalshi ticker empty; refusing to fabricate".into(),
                ));
            }
            if market.mapping == IdentityMapping::Ambiguous {
                sink.alerts.push(Alert::new(
                    AlertKind::IdentityAmbiguity,
                    format!("AMBIGUOUS ticker {}", market.ticker),
                ));
            }
            sink.identity.push(identity_row(&market));
            if !seen.insert(market.ticker.clone()) {
                sink.alerts.push(Alert::new(
                    AlertKind::DuplicateLogicalArtifact,
                    format!("duplicate ticker {}", market.ticker),
                ));
                continue;
            }
            let (out, completeness) =
                match land_kalshi_market(plan, paths, kalshi, &market, sink.alerts) {
                    Ok(v) => v,
                    Err(e) => {
                        eprintln!(
                            "kalshi land failed {} {e}; continuing remaining markets",
                            market.ticker
                        );
                        sink.alerts.push(Alert::new(
                            AlertKind::RepeatedSourceFailure,
                            format!("{}: {e}", market.ticker),
                        ));
                        sink.coverage.push(CoverageRow {
                            date: market.date.to_string(),
                            source: SOURCE_KALSHI_DISCOVERY.into(),
                            partition_id: market.ticker.clone(),
                            status: PartitionStatus::Failed,
                            sha256: None,
                            path: None,
                            notes: e.to_string(),
                        });
                        continue;
                    }
                };
            if i == 0 || (i + 1) % 25 == 0 || i + 1 == n_markets {
                eprintln!(
                    "kalshi land {}/{} {} {:?}",
                    i + 1,
                    n_markets,
                    market.ticker,
                    completeness
                );
            }
            let mut landed = market;
            if let Some(c) = completeness {
                landed.completeness = Some(c);
            }
            sink.markets.push(landed);
            sink.coverage.push(out.row);
            if let Some(a) = out.artifact {
                sink.pending.push(a);
            }
            if let Some(p) = out.provenance {
                sink.provenance.push(p);
            }
        }
    }
    Ok(())
}

fn land_kalshi_market(
    plan: &IngestPlan,
    paths: &IngestPaths,
    kalshi: &dyn KalshiDiscoverySource,
    market: &DiscoveredMarket,
    alerts: &mut Vec<Alert>,
) -> Result<(PartitionOutcome, Option<MarketCompleteness>), IngestError> {
    land_market_settlement(paths, market)?;
    if plan.skip_existing {
        let dest = paths.landing_kalshi_discovery(market.date, &market.ticker);
        if dest.exists() {
            let completeness = completeness_from_landed_bytes(&fs::read(&dest)?);
            let have_trades = landed_trades_observed(paths, market);
            let have_candles = landed_candles_observed(paths, market);
            if have_trades && have_candles {
                let sha = crate::paths::sha256_file(&dest)?;
                let part = DiscoveredPartition {
                    source: SOURCE_KALSHI_DISCOVERY.into(),
                    date: market.date,
                    partition_id: market.ticker.clone(),
                    status_hint: format!("{:?}", market.mapping),
                    home_abbreviation: String::new(),
                    away_abbreviation: String::new(),
                    game_number: 1,
                };
                return Ok((
                    committed_outcome(
                        &part,
                        dest,
                        sha,
                        PartitionStatus::AlreadyKnown,
                        "skip_existing: trades and 1m candles already landed; envelope not overwritten",
                    ),
                    completeness,
                ));
            }
            if plan.fetch_kalshi_artifacts {
                return upgrade_kalshi_sidecars(
                    plan,
                    paths,
                    kalshi,
                    market,
                    have_trades,
                    have_candles,
                    alerts,
                );
            }
            let sha = crate::paths::sha256_file(&dest)?;
            let part = DiscoveredPartition {
                source: SOURCE_KALSHI_DISCOVERY.into(),
                date: market.date,
                partition_id: market.ticker.clone(),
                status_hint: format!("{:?}", market.mapping),
                home_abbreviation: String::new(),
                away_abbreviation: String::new(),
                game_number: 1,
            };
            return Ok((
                committed_outcome(
                    &part,
                    dest,
                    sha,
                    PartitionStatus::AlreadyKnown,
                    "skip_existing: Kalshi landing present; not re-fetched",
                ),
                completeness,
            ));
        }
    }
    if !plan.fetch_kalshi_artifacts {
        let payload = serde_json::json!({
            "source": SOURCE_KALSHI_DISCOVERY,
            "ticker": market.ticker,
            "event_ticker": market.event_ticker,
            "series": market.series,
            "completeness": MarketCompleteness::MarketMetadataOnly,
            "l2": "HISTORICAL_L2_UNAVAILABLE",
            "trades_status": "NOT_REQUESTED",
            "candles_status": "NOT_REQUESTED",
            "result": market.result,
            "settlement_ts": market.settlement_ts,
            "settlement_value_dollars": market.settlement_value_dollars,
            "open_time": market.open_time,
            "close_time": market.close_time,
            "status": market.status,
        });
        return land_kalshi_bytes(
            plan,
            paths,
            market,
            payload,
            Some(MarketCompleteness::MarketMetadataOnly),
            alerts,
        );
    }
    let fetched = kalshi.fetch_artifact(market)?;
    match fetched {
        FetchOutcome::Missing => Ok((
            PartitionOutcome {
                row: CoverageRow {
                    date: market.date.to_string(),
                    source: SOURCE_KALSHI_DISCOVERY.into(),
                    partition_id: market.ticker.clone(),
                    status: PartitionStatus::Unavailable,
                    sha256: None,
                    path: None,
                    notes: "Kalshi artifact UNAVAILABLE".into(),
                },
                artifact: None,
                provenance: None,
            },
            None,
        )),
        FetchOutcome::Failure(msg) => Ok((
            PartitionOutcome {
                row: CoverageRow {
                    date: market.date.to_string(),
                    source: SOURCE_KALSHI_DISCOVERY.into(),
                    partition_id: market.ticker.clone(),
                    status: PartitionStatus::Failed,
                    sha256: None,
                    path: None,
                    notes: msg,
                },
                artifact: None,
                provenance: None,
            },
            None,
        )),
        FetchOutcome::Bytes(raw) => {
            let payload: serde_json::Value = serde_json::from_slice(&raw).unwrap_or(
                serde_json::Value::String(String::from_utf8_lossy(&raw).into()),
            );
            let completeness = completeness_from_payload(&payload);
            let (start_ts, end_ts) = artifact_window(market);
            if let Some(trades) = trades_array(&payload) {
                let status = status_from_json(&payload, "trades_status")
                    .unwrap_or_else(|| "OBSERVED_HISTORICAL".into());
                if status != "UNAVAILABLE" {
                    let bytes =
                        wrap_historical_trades_sidecar(market, trades, &status, plan.generated_at)?;
                    let _ = land_historical_trades(paths, market, &bytes)?;
                }
            }
            land_candles_sidecar_from_value(
                plan, paths, market, &payload, start_ts, end_ts, alerts,
            )?;
            land_kalshi_bytes(plan, paths, market, payload, completeness, alerts)
        }
    }
}

fn upgrade_kalshi_sidecars(
    plan: &IngestPlan,
    paths: &IngestPaths,
    kalshi: &dyn KalshiDiscoverySource,
    market: &DiscoveredMarket,
    have_trades: bool,
    have_candles: bool,
    alerts: &mut Vec<Alert>,
) -> Result<(PartitionOutcome, Option<MarketCompleteness>), IngestError> {
    let dest = paths.landing_kalshi_discovery(market.date, &market.ticker);
    let completeness = completeness_from_landed_bytes(&fs::read(&dest)?);
    let part = DiscoveredPartition {
        source: SOURCE_KALSHI_DISCOVERY.into(),
        date: market.date,
        partition_id: market.ticker.clone(),
        status_hint: format!("{:?}", market.mapping),
        home_abbreviation: String::new(),
        away_abbreviation: String::new(),
        game_number: 1,
    };
    let sha = crate::paths::sha256_file(&dest)?;
    let (start_ts, end_ts) = artifact_window(market);

    if !have_trades {
        match kalshi.fetch_artifact(market)? {
            FetchOutcome::Bytes(raw) => {
                let payload: serde_json::Value = serde_json::from_slice(&raw).unwrap_or(
                    serde_json::Value::String(String::from_utf8_lossy(&raw).into()),
                );
                if let Some(trades) = trades_array(&payload) {
                    let status = status_from_json(&payload, "trades_status")
                        .unwrap_or_else(|| "OBSERVED_HISTORICAL".into());
                    if status != "UNAVAILABLE" {
                        let bytes = wrap_historical_trades_sidecar(
                            market,
                            trades,
                            &status,
                            plan.generated_at,
                        )?;
                        let _ = land_historical_trades(paths, market, &bytes)?;
                    }
                }
                if !have_candles {
                    land_candles_sidecar_from_value(
                        plan, paths, market, &payload, start_ts, end_ts, alerts,
                    )?;
                }
            }
            FetchOutcome::Failure(msg) => {
                return Ok((
                    PartitionOutcome {
                        row: CoverageRow {
                            date: market.date.to_string(),
                            source: SOURCE_KALSHI_DISCOVERY.into(),
                            partition_id: market.ticker.clone(),
                            status: PartitionStatus::Failed,
                            sha256: Some(sha),
                            path: Some(dest.display().to_string()),
                            notes: msg,
                        },
                        artifact: None,
                        provenance: None,
                    },
                    completeness,
                ));
            }
            FetchOutcome::Missing => {}
        }
    } else if !have_candles {
        match kalshi.fetch_candlesticks(market)? {
            Some(FetchOutcome::Bytes(raw)) => {
                let payload: serde_json::Value = serde_json::from_slice(&raw).unwrap_or(
                    serde_json::Value::String(String::from_utf8_lossy(&raw).into()),
                );
                land_candles_sidecar_from_value(
                    plan, paths, market, &payload, start_ts, end_ts, alerts,
                )?;
            }
            Some(FetchOutcome::Failure(msg)) => {
                return Ok((
                    PartitionOutcome {
                        row: CoverageRow {
                            date: market.date.to_string(),
                            source: SOURCE_KALSHI_DISCOVERY.into(),
                            partition_id: market.ticker.clone(),
                            status: PartitionStatus::Failed,
                            sha256: Some(sha),
                            path: Some(dest.display().to_string()),
                            notes: msg,
                        },
                        artifact: None,
                        provenance: None,
                    },
                    completeness,
                ));
            }
            Some(FetchOutcome::Missing) | None => match kalshi.fetch_artifact(market)? {
                FetchOutcome::Bytes(raw) => {
                    let payload: serde_json::Value = serde_json::from_slice(&raw).unwrap_or(
                        serde_json::Value::String(String::from_utf8_lossy(&raw).into()),
                    );
                    land_candles_sidecar_from_value(
                        plan, paths, market, &payload, start_ts, end_ts, alerts,
                    )?;
                }
                FetchOutcome::Failure(msg) => {
                    return Ok((
                        PartitionOutcome {
                            row: CoverageRow {
                                date: market.date.to_string(),
                                source: SOURCE_KALSHI_DISCOVERY.into(),
                                partition_id: market.ticker.clone(),
                                status: PartitionStatus::Failed,
                                sha256: Some(sha),
                                path: Some(dest.display().to_string()),
                                notes: msg,
                            },
                            artifact: None,
                            provenance: None,
                        },
                        completeness,
                    ));
                }
                FetchOutcome::Missing => {}
            },
        }
    }

    let candles_now = landed_candles_observed(paths, market);
    let trades_now = landed_trades_observed(paths, market);
    let notes = if candles_now && trades_now {
        "sidecar upgrade: 1m candles/trades landed; discovery envelope not overwritten"
    } else if candles_now {
        "sidecar upgrade: 1m candles landed; trades still missing"
    } else if trades_now {
        "sidecar upgrade: trades present; 1m candles still missing"
    } else {
        "sidecar upgrade attempted; artifacts still missing"
    };
    Ok((
        committed_outcome(
            &part,
            dest,
            sha,
            if candles_now && trades_now {
                PartitionStatus::Complete
            } else {
                PartitionStatus::Failed
            },
            notes,
        ),
        completeness,
    ))
}

fn land_candles_sidecar_from_value(
    plan: &IngestPlan,
    paths: &IngestPaths,
    market: &DiscoveredMarket,
    payload: &serde_json::Value,
    start_ts: i64,
    end_ts: i64,
    alerts: &mut Vec<Alert>,
) -> Result<(), IngestError> {
    if candles_payload_unavailable(payload) {
        alerts.push(Alert::new(
            AlertKind::SourceUnavailable,
            format!("1m candles UNAVAILABLE for {}", market.ticker),
        ));
        return Ok(());
    }
    let sticks = candlesticks_array(payload);
    let status =
        status_from_json(payload, "candles_status").unwrap_or_else(|| "OBSERVED_HISTORICAL".into());
    let start = payload
        .get("window_start_ts")
        .and_then(|v| v.as_i64())
        .unwrap_or(start_ts);
    let end = payload
        .get("window_end_ts")
        .and_then(|v| v.as_i64())
        .unwrap_or(end_ts);
    let bytes = wrap_historical_candles(market, sticks, &status, start, end, plan.generated_at)?;
    match land_historical_candles(paths, market, &bytes)? {
        LandResult::VersionConflict { .. } => {
            alerts.push(Alert::new(
                AlertKind::VersionConflict,
                format!("VERSION_CONFLICT candles {}", market.ticker),
            ));
        }
        LandResult::Written { .. } | LandResult::AlreadyKnown { .. } => {}
    }
    Ok(())
}

fn land_kalshi_bytes(
    plan: &IngestPlan,
    paths: &IngestPaths,
    market: &DiscoveredMarket,
    payload: serde_json::Value,
    completeness: Option<MarketCompleteness>,
    alerts: &mut Vec<Alert>,
) -> Result<(PartitionOutcome, Option<MarketCompleteness>), IngestError> {
    let bytes = wrap_kalshi_discovery_envelope(market, payload, plan.generated_at)?;
    let part = DiscoveredPartition {
        source: SOURCE_KALSHI_DISCOVERY.into(),
        date: market.date,
        partition_id: market.ticker.clone(),
        status_hint: format!("{:?}", market.mapping),
        home_abbreviation: String::new(),
        away_abbreviation: String::new(),
        game_number: 1,
    };
    match land_kalshi_discovery(paths, market, &bytes)? {
        LandResult::Written { path, sha256 } => Ok((
            committed_outcome(
                &part,
                path,
                sha256,
                if market.mapping == IdentityMapping::Unmatched {
                    PartitionStatus::Unmatched
                } else if market.mapping == IdentityMapping::Ambiguous {
                    PartitionStatus::Ambiguous
                } else {
                    PartitionStatus::Complete
                },
                "kalshi discovery landed; not a MarketState",
            ),
            completeness,
        )),
        LandResult::AlreadyKnown { path, sha256 } => {
            alerts.push(Alert::new(
                AlertKind::DuplicateLogicalArtifact,
                format!("ALREADY_KNOWN ticker {}", market.ticker),
            ));
            Ok((
                committed_outcome(
                    &part,
                    path,
                    sha256,
                    PartitionStatus::AlreadyKnown,
                    "same bytes; no overwrite",
                ),
                completeness,
            ))
        }
        LandResult::VersionConflict {
            original,
            new_path,
            new_sha,
            ..
        } => {
            alerts.push(Alert::new(
                AlertKind::VersionConflict,
                format!(
                    "VERSION_CONFLICT ticker {} original {}",
                    market.ticker,
                    original.display()
                ),
            ));
            Ok((
                committed_outcome(
                    &part,
                    new_path,
                    new_sha,
                    PartitionStatus::VersionConflict,
                    "new version stored; original not overwritten",
                ),
                completeness,
            ))
        }
    }
}

fn normalize_payload(
    part: &DiscoveredPartition,
    raw: &[u8],
    at: chrono::DateTime<chrono::Utc>,
) -> Result<Vec<u8>, IngestError> {
    let v: serde_json::Value = serde_json::from_slice(raw)?;
    if v.get("envelope_version").is_some() {
        Ok(raw.to_vec())
    } else {
        crate::land::wrap_statsapi_envelope(part, raw.to_vec(), at)
    }
}

fn run_status(coverage: &[CoverageRow], alerts: &[Alert]) -> RunStatus {
    let pbp: Vec<_> = coverage
        .iter()
        .filter(|r| r.source == SOURCE_STATSAPI)
        .collect();
    let pbp_failed = pbp
        .iter()
        .filter(|r| r.status == PartitionStatus::Failed)
        .count();
    if !pbp.is_empty() && pbp_failed == pbp.len() {
        return RunStatus::Failed;
    }
    let gaps = pbp.iter().any(|r| {
        matches!(
            r.status,
            PartitionStatus::Failed
                | PartitionStatus::Unavailable
                | PartitionStatus::VersionConflict
        )
    });
    if gaps || !alerts.is_empty() {
        RunStatus::CompleteWithGaps
    } else {
        RunStatus::Complete
    }
}

fn checksum_from(coverage: &[CoverageRow]) -> ChecksumReport {
    let mut r = ChecksumReport::default();
    for row in coverage {
        match row.status {
            PartitionStatus::Complete | PartitionStatus::Unmatched | PartitionStatus::Ambiguous => {
                r.verified += 1
            }
            PartitionStatus::AlreadyKnown => {
                r.verified += 1;
                r.already_known += 1;
            }
            PartitionStatus::VersionConflict => {
                r.verified += 1;
                r.version_conflicts += 1;
            }
            PartitionStatus::Failed if row.notes.contains("checksum") => r.mismatches += 1,
            _ => {}
        }
    }
    r
}

fn merge_watermark_dates(
    prev: &crate::types::WatermarkState,
    mut next: crate::types::WatermarkState,
) -> crate::types::WatermarkState {
    next.mlb_pbp_committed_dates =
        union_dates(&prev.mlb_pbp_committed_dates, &next.mlb_pbp_committed_dates);
    next.kalshi_discovery_committed_dates = union_dates(
        &prev.kalshi_discovery_committed_dates,
        &next.kalshi_discovery_committed_dates,
    );
    next
}

fn union_dates(a: &[String], b: &[String]) -> Vec<String> {
    let mut s: BTreeSet<String> = a.iter().cloned().collect();
    s.extend(b.iter().cloned());
    s.into_iter().collect()
}

pub fn execution_mode_label(mode: ExecutionMode) -> &'static str {
    match mode {
        ExecutionMode::HistoricalBackfill => "historical_backfill",
        ExecutionMode::Weekly => "weekly",
        ExecutionMode::Manual => "manual",
        ExecutionMode::Replay => "replay",
        ExecutionMode::Recovery => "recovery",
    }
}
