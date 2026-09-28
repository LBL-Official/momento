//! Local W1 reporting artifacts for Drive/Sheets (W1-A8).
//! Google Drive is an archive, not the canonical database.

use std::fs;
use std::io::Write;
use std::path::Path;

use chrono::{DateTime, Utc};

use super::availability::KalshiAvailabilityAudit;
use super::catalog::LakeCatalogV1;
use super::integrity::IntegrityReport;
use super::ledger::WaterfallLedger;
use super::{ARTIFACT_VERSION, WATERFALL};

#[derive(Clone, Debug)]
pub struct W1ArtifactPaths {
    pub dir: std::path::PathBuf,
}

impl W1ArtifactPaths {
    pub fn create(dir: impl Into<std::path::PathBuf>) -> std::io::Result<Self> {
        let dir = dir.into();
        fs::create_dir_all(&dir)?;
        Ok(Self { dir })
    }

    fn write_json<T: serde::Serialize>(
        &self,
        name: &str,
        value: &T,
    ) -> std::io::Result<std::path::PathBuf> {
        let path = self.dir.join(name);
        let tmp = path.with_extension("json.tmp");
        let body = serde_json::to_string_pretty(value).map_err(std::io::Error::other)?;
        fs::write(&tmp, body)?;
        fs::rename(tmp, &path)?;
        Ok(path)
    }
}

#[derive(Clone, Copy, Debug)]
pub struct W1CoreArtifacts<'a> {
    pub catalog: &'a LakeCatalogV1,
    pub integrity: &'a IntegrityReport,
    pub availability: &'a KalshiAvailabilityAudit,
    pub ledger: &'a WaterfallLedger,
}

#[derive(Clone, Copy, Debug)]
pub struct W1RunIndex<'a> {
    pub generated_at: DateTime<Utc>,
    pub run_id: &'a str,
    pub source_coverage: &'a str,
    pub status: &'a str,
}

pub fn write_core_artifacts(
    out: &W1ArtifactPaths,
    reports: W1CoreArtifacts<'_>,
    run: W1RunIndex<'_>,
) -> std::io::Result<Vec<std::path::PathBuf>> {
    let mut written = Vec::new();
    written.push(out.write_json("lake_catalog.json", reports.catalog)?);
    written.push(out.write_json("integrity_report.json", reports.integrity)?);
    written.push(out.write_json("availability_audit.json", reports.availability)?);
    written.push(out.write_json("ledger.json", reports.ledger)?);
    written.push(
        out.write_json(
            "observability_contract.json",
            &super::observability::OBSERVABILITY_CONTRACT
                .iter()
                .map(|r| {
                    serde_json::json!({
                        "field": r.field,
                        "kind": r.kind,
                        "notes": r.notes,
                    })
                })
                .collect::<Vec<_>>(),
        )?,
    );

    let coverage_csv = out.dir.join("coverage_matrix.csv");
    write_coverage_csv(&coverage_csv, reports.integrity)?;
    written.push(coverage_csv);

    let sheets = out.dir.join("sheets_w1_index.csv");
    write_sheets_index(&sheets, reports, run)?;
    written.push(sheets);

    let missing = out.dir.join("missing_data.csv");
    write_missing_csv(&missing, reports.availability)?;
    written.push(missing);

    let anomalies = out.dir.join("anomalies.csv");
    write_anomalies_csv(&anomalies, reports.integrity)?;
    written.push(anomalies);

    Ok(written)
}

fn write_coverage_csv(path: &Path, integrity: &IntegrityReport) -> std::io::Result<()> {
    let mut f = fs::File::create(path)?;
    writeln!(
        f,
        "sport,date,completeness_v1,partition_coverage,markets,games,trades,ob_events,market_discovered,market_fully_observed,settlement,lifetime_path,tick_history,candle_1m,top_of_book,l2,pbp,synchronized_state,starting_price"
    )?;
    for p in &integrity.partitions {
        let c = &p.coverage;
        writeln!(
            f,
            "{},{},{:?},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}",
            p.sport,
            p.date,
            p.v1_completeness,
            c.partition.as_str(),
            p.unique_tickers,
            p.unique_event_tickers,
            p.trade_count,
            p.orderbook_event_count,
            c.market_discovered.as_str(),
            c.market_fully_observed.as_str(),
            c.settlement_observed.as_str(),
            c.lifetime_path.as_str(),
            c.tick_history.as_str(),
            c.candle_1m.as_str(),
            c.top_of_book.as_str(),
            c.l2.as_str(),
            c.pbp.as_str(),
            c.synchronized_state.as_str(),
            c.starting_price.as_str(),
        )?;
    }
    Ok(())
}

fn write_sheets_index(
    path: &Path,
    reports: W1CoreArtifacts<'_>,
    run: W1RunIndex<'_>,
) -> std::io::Result<()> {
    let mut f = fs::File::create(path)?;
    writeln!(
        f,
        "run_id,waterfall,artifact_version,generated_at,source_coverage,status,lake_class,lake_content_digest,mlb_2025_complete_days,mlb_2026_complete_days,mlb_2026_games,mlb_2026_markets,checksum_mismatches,gzip_failures,pairing_failures,l2_status,pbp_status,starting_price_status"
    )?;
    writeln!(
        f,
        "{},{WATERFALL},{ARTIFACT_VERSION},{},{},{},{},{},{},{},{},{},{},{},{},UNAVAILABLE,UNAVAILABLE,UNAVAILABLE",
        run.run_id,
        run.generated_at.to_rfc3339(),
        run.source_coverage,
        run.status,
        csv_escape(&reports.catalog.lake_class),
        reports.catalog.lake_content_digest,
        reports.availability.mlb_2025.partition_complete_v1_dates,
        reports.availability.mlb_2026.partition_complete_v1_dates,
        reports.availability.mlb_2026.games,
        reports.availability.mlb_2026.markets,
        reports.integrity.checksum_mismatches,
        reports.integrity.gzip_failures,
        reports.integrity.pairing_failures,
    )?;
    Ok(())
}

fn write_missing_csv(path: &Path, availability: &KalshiAvailabilityAudit) -> std::io::Result<()> {
    let mut f = fs::File::create(path)?;
    writeln!(f, "missing,source,query,limitations,launched")?;
    for q in &availability.recovery_queries {
        writeln!(
            f,
            "{},{},{},{},{}",
            csv_escape(&q.missing),
            csv_escape(&q.source),
            csv_escape(&q.query),
            csv_escape(&q.limitations),
            q.launched,
        )?;
    }
    Ok(())
}

fn write_anomalies_csv(path: &Path, integrity: &IntegrityReport) -> std::io::Result<()> {
    let mut f = fs::File::create(path)?;
    writeln!(f, "severity,code,partition_date,path,message")?;
    for finding in &integrity.findings {
        writeln!(
            f,
            "{:?},{},{},{},{}",
            finding.severity,
            finding.code,
            finding.partition_date.clone().unwrap_or_default(),
            csv_escape(&finding.path.clone().unwrap_or_default()),
            csv_escape(&finding.message),
        )?;
    }
    Ok(())
}

fn csv_escape(s: &str) -> String {
    if s.contains(',') || s.contains('"') || s.contains('\n') {
        format!("\"{}\"", s.replace('"', "\"\""))
    } else {
        s.to_string()
    }
}
