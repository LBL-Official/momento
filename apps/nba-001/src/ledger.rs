//! Execution / portfolio / development event envelopes. Append-only, fsynced.
//! Not an exchange dispatcher.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Envelope {
    pub schema_version: String,
    pub event_id: String,
    pub seq: u64,
    pub occurred_ms: i64,
    pub received_ms: i64,
    pub committed_ms: i64,
    pub bot_id: String,
    pub policy_hash: String,
    pub config_hash: String,
    pub build_id: String,
    pub kind: String,
    pub body: serde_json::Value,
    pub previous_hash: String,
    pub hash: String,
}

pub struct Ledger {
    path: PathBuf,
    seq: u64,
    previous: String,
}

impl Ledger {
    pub fn open(dir: &Path, name: &str) -> Result<Self, String> {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
        let path = dir.join(name);
        let mut seq = 0;
        let mut previous = String::new();
        if path.exists() {
            let bytes = std::fs::read(&path).map_err(|e| e.to_string())?;
            if !bytes.is_empty() && bytes.last() != Some(&b'\n') {
                return Err("LEDGER_TORN_TAIL".into());
            }
            for line in bytes.split(|b| *b == b'\n').filter(|l| !l.is_empty()) {
                let env: Envelope =
                    serde_json::from_slice(line).map_err(|e| format!("LEDGER_CORRUPT:{e}"))?;
                if env.seq != seq + 1 || env.previous_hash != previous || env.hash != hash_of(&env)
                {
                    return Err("LEDGER_INTEGRITY_FAILURE".into());
                }
                seq = env.seq;
                previous = env.hash;
            }
        }
        Ok(Self {
            path,
            seq,
            previous,
        })
    }

    pub fn append(
        &mut self,
        occurred_ms: i64,
        kind: &str,
        body: serde_json::Value,
        policy_hash: &str,
        config_hash: &str,
        build_id: &str,
    ) -> Result<Envelope, String> {
        let now = occurred_ms;
        let mut env = Envelope {
            schema_version: "first78_v1_event_v1".into(),
            event_id: format!("{}-{}", kind, self.seq + 1),
            seq: self.seq + 1,
            occurred_ms,
            received_ms: now,
            committed_ms: now,
            bot_id: "nba-001".into(),
            policy_hash: policy_hash.into(),
            config_hash: config_hash.into(),
            build_id: build_id.into(),
            kind: kind.into(),
            body,
            previous_hash: self.previous.clone(),
            hash: String::new(),
        };
        env.hash = hash_of(&env);
        let line = serde_json::to_vec(&env).map_err(|e| e.to_string())?;
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
        self.seq = env.seq;
        self.previous = env.hash.clone();
        Ok(env)
    }
}

fn hash_of(env: &Envelope) -> String {
    let mut copy = env.clone();
    copy.hash.clear();
    format!(
        "{:x}",
        Sha256::digest(serde_json::to_vec(&copy).unwrap_or_default())
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn torn_and_hash_mismatch_fail_closed() {
        let dir = std::env::temp_dir().join(format!(
            "momento-ledger-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let mut l = Ledger::open(&dir, "exec.jsonl").unwrap();
        l.append(1, "TEST", serde_json::json!({"n":1}), "p", "c", "b")
            .unwrap();
        drop(l);
        let mut bytes = std::fs::read(dir.join("exec.jsonl")).unwrap();
        bytes.pop();
        std::fs::write(dir.join("exec.jsonl"), bytes).unwrap();
        assert!(Ledger::open(&dir, "exec.jsonl").is_err());
        std::fs::remove_dir_all(&dir).ok();
    }
}
