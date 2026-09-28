//! Local W2 research artifacts. Drive/Sheets publication is not assumed.

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

use chrono::{DateTime, Utc};
use serde::Serialize;

use crate::coverage::CoverageReport;
use crate::ledger::W2Ledger;
use crate::replay::GameValidation;
use crate::source::SourceContract;
use crate::versions::{ARTIFACT_VERSION, WATERFALL};

pub struct W2ArtifactPaths {
    pub dir: PathBuf,
}

impl W2ArtifactPaths {
    pub fn create(dir: impl Into<PathBuf>) -> std::io::Result<Self> {
        let dir = dir.into();
        fs::create_dir_all(&dir)?;
        Ok(Self { dir })
    }

    pub fn write_json<T: Serialize + ?Sized>(
        &self,
        name: &str,
        value: &T,
    ) -> std::io::Result<PathBuf> {
        let path = self.dir.join(name);
        let body = serde_json::to_string_pretty(value).map_err(std::io::Error::other)?;
        fs::write(&path, body)?;
        Ok(path)
    }
}

pub fn write_artifacts(
    out: &W2ArtifactPaths,
    ledger: &W2Ledger,
    coverage: &CoverageReport,
    source: &SourceContract,
    validations: &[GameValidation],
    generated_at: DateTime<Utc>,
    google_status: &str,
) -> std::io::Result<Vec<PathBuf>> {
    let mut written = vec![
        out.write_json("ledger.json", ledger)?,
        out.write_json("coverage.json", coverage)?,
        out.write_json("source_contract.json", source)?,
        out.write_json("validations.json", validations)?,
    ];

    let ledger_md = out.dir.join("W2_STEP_LEDGER.md");
    fs::write(&ledger_md, ledger.markdown())?;
    written.push(ledger_md);

    let cov_csv = out.dir.join("w2_coverage.csv");
    write_coverage_csv(&cov_csv, coverage)?;
    written.push(cov_csv);

    let sheets = out.dir.join("sheets_w2_index.csv");
    write_sheets_index(&sheets, generated_at, coverage, google_status)?;
    written.push(sheets);

    let err_csv = out.dir.join("w2_errors_warnings.csv");
    write_errors_csv(&err_csv, validations)?;
    written.push(err_csv);

    let dict = out.dir.join("w2_data_dictionary.csv");
    write_dictionary_csv(&dict)?;
    written.push(dict);

    let src_csv = out.dir.join("w2_source_coverage.csv");
    write_source_csv(&src_csv, source)?;
    written.push(src_csv);

    Ok(written)
}

fn write_coverage_csv(path: &Path, coverage: &CoverageReport) -> std::io::Result<()> {
    let mut f = fs::File::create(path)?;
    writeln!(
        f,
        "season,date,game_id,home_team,away_team,pbp,pitch,timestamps,score,runners,batter,pitcher,outcome,reconstruction,warnings,notes"
    )?;
    for r in &coverage.rows {
        writeln!(
            f,
            "{},{},{},{},{},{:?},{:?},{:?},{:?},{:?},{:?},{:?},{:?},{:?},{},{}",
            r.season,
            r.date,
            csv(&r.game_id),
            csv(&r.home_team),
            csv(&r.away_team),
            r.pbp_available,
            r.pitch_level_available,
            r.timestamps_available,
            r.score_available,
            r.runner_state_available,
            r.batter_available,
            r.pitcher_available,
            r.final_outcome_available,
            r.reconstruction_valid,
            csv(&r.reconstruction_warnings),
            csv(&r.notes)
        )?;
    }
    Ok(())
}

fn write_sheets_index(
    path: &Path,
    generated_at: DateTime<Utc>,
    coverage: &CoverageReport,
    google_status: &str,
) -> std::io::Result<()> {
    let mut f = fs::File::create(path)?;
    writeln!(
        f,
        "run_id,waterfall,artifact_version,generated_at,mlb_2025,mlb_2026,pbp_files,coverage_rows,google_status"
    )?;
    writeln!(
        f,
        "w2-local,{WATERFALL},{ARTIFACT_VERSION},{},{},{},{},{},{}",
        generated_at.to_rfc3339(),
        csv(&coverage.mlb_2025),
        csv(&coverage.mlb_2026),
        coverage.historical_pbp_files,
        coverage.rows.len(),
        google_status
    )?;
    Ok(())
}

fn write_errors_csv(path: &Path, validations: &[GameValidation]) -> std::io::Result<()> {
    let mut f = fs::File::create(path)?;
    writeln!(f, "game_id,valid,invalid,error,warnings,missing_fields")?;
    for v in validations {
        writeln!(
            f,
            "{},{},{},{},{},{}",
            csv(&v.game_id),
            v.valid,
            v.invalid,
            csv(v.error.as_deref().unwrap_or("")),
            csv(&v.warnings.join(";")),
            csv(&v.missing_fields.join(";"))
        )?;
    }
    Ok(())
}

fn write_dictionary_csv(path: &Path) -> std::io::Result<()> {
    let mut f = fs::File::create(path)?;
    writeln!(f, "field,layer,observability,notes")?;
    writeln!(
        f,
        "canonical_game_id,identity,DERIVED,SHA-256 of source+source_game_id; never invented"
    )?;
    writeln!(
        f,
        "mlb_game_pk,identity,OBSERVED_OR_UNMAPPED,Null until official source observed"
    )?;
    writeln!(
        f,
        "outs_elapsed,event_time,DERIVED,{0}",
        crate::versions::REMAINING_OUTS_DEFINITION_VERSION
    )?;
    writeln!(
        f,
        "actual_outs_remaining,event_time,UNAVAILABLE_AT_T,Knowable only at terminal without lookahead"
    )?;
    writeln!(
        f,
        "event_theta,event_time,NOT_COMPUTED,Empirical later; no W2 formula"
    )?;
    writeln!(f, "winner,outcome,OUTCOME_LABEL,Never on MlbGameState")?;
    writeln!(
        f,
        "source_event_timestamp,clock,OBSERVED_OR_UNAVAILABLE,Not collector time; not Kalshi trade time"
    )?;
    Ok(())
}

fn write_source_csv(path: &Path, source: &SourceContract) -> std::io::Result<()> {
    let mut f = fs::File::create(path)?;
    writeln!(f, "provider,api,role,present_locally,limitations")?;
    for s in &source.sources {
        writeln!(
            f,
            "{},{},{:?},{},{}",
            csv(&s.provider),
            csv(&s.api_or_source_name),
            s.role,
            s.present_in_repository,
            csv(&s.limitations)
        )?;
    }
    Ok(())
}

fn csv(s: &str) -> String {
    if s.contains(',') || s.contains('"') || s.contains('\n') {
        format!("\"{}\"", s.replace('"', "\"\""))
    } else {
        s.to_string()
    }
}
