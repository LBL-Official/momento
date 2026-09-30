//! Durable P0/P1/P2 alert outbox. Linear/Sunsama never block execution.

use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

use momento_strategy_nba::portfolio_v1::Priority;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Alert {
    pub id: String,
    pub at_ms: i64,
    pub priority: Priority,
    pub reason: String,
    pub evidence_id: String,
    pub delivered: bool,
    pub retries: u32,
}

pub struct AlertOutbox {
    path: PathBuf,
    items: VecDeque<Alert>,
    cap: usize,
}

impl AlertOutbox {
    pub fn open(dir: &Path, cap: usize) -> Result<Self, String> {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
        let path = dir.join("alert_outbox.jsonl");
        let mut items = VecDeque::new();
        if path.exists() {
            let bytes = std::fs::read(&path).map_err(|e| e.to_string())?;
            if !bytes.is_empty() && bytes.last() != Some(&b'\n') {
                return Err("ALERT_OUTBOX_TORN_TAIL".into());
            }
            for line in bytes.split(|b| *b == b'\n').filter(|l| !l.is_empty()) {
                items.push_back(
                    serde_json::from_slice(line).map_err(|e| format!("ALERT_CORRUPT:{e}"))?,
                );
            }
        }
        Ok(Self { path, items, cap })
    }

    pub fn raise(&mut self, alert: Alert) -> Result<(), String> {
        if self.items.iter().any(|a| a.id == alert.id) {
            return Ok(());
        }
        if self.items.len() >= self.cap {
            return Err("ALERT_OUTBOX_BACKPRESSURE".into());
        }
        self.append(&alert)?;
        self.items.push_back(alert);
        Ok(())
    }

    /// Delivery failure queues a retry. Execution continues.
    pub fn mark_delivery_failed(&mut self, id: &str) -> Result<(), String> {
        let updated = self.items.iter_mut().find(|a| a.id == id).map(|a| {
            a.retries = a.retries.saturating_add(1);
            a.delivered = false;
            a.clone()
        });
        if let Some(a) = updated {
            self.append(&a)?;
        }
        Ok(())
    }

    pub fn pending(&self) -> usize {
        self.items.iter().filter(|a| !a.delivered).count()
    }

    fn append(&self, alert: &Alert) -> Result<(), String> {
        let line = serde_json::to_vec(alert).map_err(|e| e.to_string())?;
        let mut f = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)
            .map_err(|e| e.to_string())?;
        f.write_all(&line).map_err(|e| e.to_string())?;
        f.write_all(b"\n").map_err(|e| e.to_string())?;
        f.sync_all().map_err(|e| e.to_string())?;
        File::open(self.path.parent().unwrap_or(Path::new(".")))
            .and_then(|d| d.sync_all())
            .ok();
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn linear_failure_does_not_drop_alert() {
        let dir = std::env::temp_dir().join(format!(
            "momento-alert-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let mut o = AlertOutbox::open(&dir, 8).unwrap();
        o.raise(Alert {
            id: "p0-1".into(),
            at_ms: 1,
            priority: Priority::P0,
            reason: "UNKNOWN_POSITION".into(),
            evidence_id: "e1".into(),
            delivered: false,
            retries: 0,
        })
        .unwrap();
        o.mark_delivery_failed("p0-1").unwrap();
        assert_eq!(o.pending(), 1);
        std::fs::remove_dir_all(&dir).ok();
    }
}
