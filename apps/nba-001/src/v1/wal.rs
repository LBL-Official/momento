//! Replay-only WAL: hash-chain integrity, deterministic recovery, single writer.
//! fsync precedes state publication. Not an exchange order dispatcher.
use super::Envelope;
use momento_strategy_nba::live_v1::{Action, Engine};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs::{File, OpenOptions};
use std::io::{BufRead, Write};
use std::path::Path;
#[derive(Serialize, Deserialize)]
struct Row {
    seq: u64,
    previous: String,
    policy_hash: String,
    event: Envelope,
    actions: Vec<Action>,
    hash: String,
}
fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn row_hash(r: &Row) -> Result<String, String> {
    serde_json::to_vec(&(r.seq, &r.previous, &r.policy_hash, &r.event, &r.actions))
        .map(|v| digest(&v))
        .map_err(|e| e.to_string())
}
pub struct ReplayLog {
    _lease: crate::lease::Lease,
    file: File,
    state: Engine,
    seq: u64,
    previous: String,
    policy_hash: String,
    healthy: bool,
    last_ms: Option<i64>,
}
impl ReplayLog {
    pub fn open(dir: &Path, mut initial: Engine) -> Result<Self, String> {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
        let lease = crate::lease::Lease::acquire(dir)?;
        let policy_hash = digest(&serde_json::to_vec(&initial.policy).map_err(|e| e.to_string())?);
        let path = dir.join("replay.jsonl");
        let mut seq = 0;
        let mut previous = String::new();
        let mut last_ms = None;
        if path.exists() {
            let bytes = std::fs::read(&path).map_err(|e| e.to_string())?;
            if !bytes.is_empty() && bytes.last() != Some(&b'\n') {
                return Err("WAL_TORN_TAIL_REQUIRES_REPAIR".into());
            }
            for line in std::io::BufReader::new(bytes.as_slice()).lines() {
                let row: Row = serde_json::from_str(&line.map_err(|e| e.to_string())?)
                    .map_err(|e| e.to_string())?;
                if row.seq != seq + 1
                    || row.previous != previous
                    || row.policy_hash != policy_hash
                    || row.hash != row_hash(&row)?
                    || last_ms.is_some_and(|last| row.event.at_ms < last)
                {
                    return Err("WAL_INTEGRITY_FAILURE".into());
                }
                let actions = initial.apply(row.event.at_ms, row.event.input.clone())?;
                if serde_json::to_value(&actions).unwrap()
                    != serde_json::to_value(&row.actions).unwrap()
                {
                    return Err("REPLAY_DIVERGENCE".into());
                }
                seq = row.seq;
                previous = row.hash;
                last_ms = Some(row.event.at_ms);
            }
        }
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .map_err(|e| e.to_string())?;
        file.sync_all().map_err(|e| e.to_string())?;
        File::open(dir)
            .and_then(|f| f.sync_all())
            .map_err(|e| e.to_string())?;
        Ok(Self {
            _lease: lease,
            file,
            state: initial,
            seq,
            previous,
            policy_hash,
            healthy: true,
            last_ms,
        })
    }
    pub fn apply(&mut self, event: Envelope) -> Result<Vec<Action>, String> {
        if !self.healthy {
            return Err("WAL_UNHEALTHY_REOPEN_REQUIRED".into());
        }
        if self.last_ms.is_some_and(|last| event.at_ms < last) {
            return Err("EVENT_TIME_REGRESSION".into());
        }
        let mut next = self.state.clone();
        let actions = next.apply(event.at_ms, event.input.clone())?;
        let mut row = Row {
            seq: self.seq.checked_add(1).ok_or("SEQUENCE_OVERFLOW")?,
            previous: self.previous.clone(),
            policy_hash: self.policy_hash.clone(),
            event,
            actions: actions.clone(),
            hash: String::new(),
        };
        row.hash = row_hash(&row)?;
        let mut bytes = serde_json::to_vec(&row).map_err(|e| e.to_string())?;
        bytes.push(b'\n');
        if let Err(e) = self
            .file
            .write_all(&bytes)
            .and_then(|_| self.file.sync_all())
        {
            self.healthy = false;
            return Err(format!("WAL_COMMIT_FAILED:{e}"));
        }
        self.state = next;
        self.seq = row.seq;
        self.previous = row.hash;
        self.last_ms = Some(row.event.at_ms);
        Ok(actions)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use momento_strategy_nba::{
        BalancePrecision, FeeModel, FeeType,
        live_v1::{Input, Policy},
    };
    fn engine() -> Engine {
        Engine::new(
            Policy {
                quote_max_age_ms: 1000,
                sports_max_age_ms: 1000,
                entry_reprice_ms: 1000,
                emergency_floor_cents: None,
                fee_model: FeeModel::new(FeeType::Quadratic, 1000, BalancePrecision::Cent),
                fee_version: "fixture".into(),
            },
            0,
        )
        .unwrap()
    }
    #[test]
    fn restart_replays_and_corruption_fails_closed() {
        let dir = std::env::temp_dir().join(format!("momento-v1-wal-{}", std::process::id()));
        std::fs::create_dir(&dir).unwrap();
        {
            let mut w = ReplayLog::open(&dir, engine()).unwrap();
            assert!(ReplayLog::open(&dir, engine()).is_err());
            w.apply(Envelope {
                at_ms: 100,
                input: Input::Account {
                    clean: true,
                    cash_centicents: 200_000,
                    equity_cents: 2000,
                    snapshot_id: "a".into(),
                    observed_ms: 100,
                },
            })
            .unwrap();
        }
        {
            let w = ReplayLog::open(&dir, engine()).unwrap();
            assert_eq!(
                w.state.epochs.as_ref().unwrap().active().trade_budget_cents,
                120
            );
        }
        OpenOptions::new()
            .append(true)
            .open(dir.join("replay.jsonl"))
            .unwrap()
            .write_all(b"{torn")
            .unwrap();
        assert!(ReplayLog::open(&dir, engine()).is_err());
        std::fs::remove_dir_all(dir).unwrap();
    }
}
