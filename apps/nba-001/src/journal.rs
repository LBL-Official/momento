//! Append-only JSONL journal. Records are never rewritten. Rotates by rename.

use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};

use serde_json::{Value, json};

const ROTATE_BYTES: u64 = 20 * 1024 * 1024;

pub struct Journal {
    path: PathBuf,
    seq: u64,
    pub write_errors: u64,
}

impl Journal {
    pub fn new(state_dir: &Path) -> Self {
        Self {
            path: state_dir.join("journal.jsonl"),
            seq: 0,
            write_errors: 0,
        }
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    /// Returns the event id.
    pub fn record(
        &mut self,
        now_ms: i64,
        kind: &str,
        game: Option<&str>,
        ticker: Option<&str>,
        payload: Value,
    ) -> String {
        self.seq += 1;
        let event_id = format!("nba-001-{now_ms}-{}", self.seq);
        let line = json!({
            "event_id": event_id,
            "ts_ms": now_ms,
            "bot_id": "nba-001",
            "strategy_id": "FIRST78_67",
            "kind": kind,
            "game_id": game,
            "market_id": ticker,
            "payload": payload,
        });
        if let Ok(meta) = std::fs::metadata(&self.path)
            && meta.len() > ROTATE_BYTES
        {
            let rotated = self.path.with_extension(format!("jsonl.{now_ms}"));
            if std::fs::rename(&self.path, rotated).is_err() {
                self.write_errors += 1;
            }
        }
        let ok = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)
            .and_then(|mut f| writeln!(f, "{line}"));
        if ok.is_err() {
            self.write_errors += 1;
        }
        event_id
    }
}

/// Atomic JSON write: temp file then rename.
pub fn write_json_atomic(path: &Path, value: &Value) -> Result<(), String> {
    let tmp = path.with_extension("tmp");
    let body = serde_json::to_vec_pretty(value).map_err(|e| e.to_string())?;
    std::fs::write(&tmp, body).map_err(|e| format!("{}: {e}", tmp.display()))?;
    std::fs::rename(&tmp, path).map_err(|e| format!("{}: {e}", path.display()))
}
