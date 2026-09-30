//! Durable order-intent outbox. Persist before any send. Not the replay WAL.

use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

use momento_strategy_nba::OrderSpec;
use momento_strategy_nba::live_v1::Action;

/// Compile-time reminder: this crate's production venue still refuses sends.
pub const PRODUCTION_SENDS_DISABLED: bool = true;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum OutboxState {
    Queued,
    Persisted,
    SendingBlockedProductionCompiledOut,
    Canceled,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OutboxItem {
    pub id: String,
    pub at_ms: i64,
    pub action: Action,
    pub state: OutboxState,
}

pub struct OrderOutbox {
    path: PathBuf,
    items: VecDeque<OutboxItem>,
    cap: usize,
}

impl OrderOutbox {
    pub fn open(dir: &Path, cap: usize) -> Result<Self, String> {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
        let path = dir.join("order_outbox.jsonl");
        let mut items = VecDeque::new();
        if path.exists() {
            let bytes = std::fs::read(&path).map_err(|e| e.to_string())?;
            if !bytes.is_empty() && bytes.last() != Some(&b'\n') {
                return Err("OUTBOX_TORN_TAIL".into());
            }
            for line in bytes.split(|b| *b == b'\n').filter(|l| !l.is_empty()) {
                let item: OutboxItem =
                    serde_json::from_slice(line).map_err(|e| format!("OUTBOX_CORRUPT:{e}"))?;
                items.push_back(item);
            }
        }
        Ok(Self { path, items, cap })
    }

    pub fn enqueue(&mut self, at_ms: i64, action: Action) -> Result<OutboxItem, String> {
        if self.items.len() >= self.cap {
            return Err("OUTBOX_BACKPRESSURE".into());
        }
        let item = OutboxItem {
            id: format!("obx-{}", self.items.len() + 1),
            at_ms,
            action,
            state: OutboxState::Persisted,
        };
        self.append(&item)?;
        self.items.push_back(item.clone());
        Ok(item)
    }

    /// Production adapter is compiled out. Intents stay persisted, never sent.
    pub fn dispatch_blocked(&self, spec: &OrderSpec) -> OutboxState {
        let _ = spec;
        OutboxState::SendingBlockedProductionCompiledOut
    }

    pub fn len(&self) -> usize {
        self.items.len()
    }

    fn append(&self, item: &OutboxItem) -> Result<(), String> {
        let line = serde_json::to_vec(item).map_err(|e| e.to_string())?;
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
    use momento_strategy_nba::live_v1::Action;

    #[test]
    fn persist_before_any_send_and_cap() {
        let dir = std::env::temp_dir().join(format!(
            "momento-outbox-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let mut box_ = OrderOutbox::open(&dir, 2).unwrap();
        box_.enqueue(
            1,
            Action::Block {
                event_id: "g".into(),
                reason: "TEST".into(),
            },
        )
        .unwrap();
        box_.enqueue(
            2,
            Action::Block {
                event_id: "g".into(),
                reason: "TEST2".into(),
            },
        )
        .unwrap();
        assert!(
            box_.enqueue(
                3,
                Action::Block {
                    event_id: "g".into(),
                    reason: "TEST3".into(),
                },
            )
            .is_err()
        );
        drop(box_);
        let box_ = OrderOutbox::open(&dir, 2).unwrap();
        assert_eq!(box_.len(), 2);
        std::fs::remove_dir_all(&dir).ok();
    }
}
