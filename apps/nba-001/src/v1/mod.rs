//! Isolated replay runner plus supervised V1 runtime. It never calls a
//! production order transport from this module.
pub mod alerts;
pub mod discovery;
pub mod espn;
pub mod kalshi;
pub mod outbox;
pub mod runtime;
mod wal;
use momento_strategy_nba::live_v1::{Engine, Input, Policy};
use serde::{Deserialize, Serialize};
use std::io::BufRead;
use std::path::Path;
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Envelope {
    pub at_ms: i64,
    pub input: Input,
}
/// v1-replay POLICY_JSON INPUT_JSONL STATE_DIR
pub fn replay(args: &[String]) -> Result<(), (i32, String)> {
    let run = || -> Result<(), String> {
        if args.len() != 3 {
            return Err("usage: v1-replay POLICY_JSON INPUT_JSONL STATE_DIR".into());
        }
        let policy: Policy =
            serde_json::from_slice(&std::fs::read(&args[0]).map_err(|e| e.to_string())?)
                .map_err(|e| e.to_string())?;
        let engine = Engine::new(policy, 0)?;
        let mut wal = wal::ReplayLog::open(Path::new(&args[2]), engine)?;
        let f = std::fs::File::open(&args[1]).map_err(|e| e.to_string())?;
        for line in std::io::BufReader::new(f).lines() {
            let line = line.map_err(|e| e.to_string())?;
            let event: Envelope = serde_json::from_str(&line).map_err(|e| e.to_string())?;
            let actions = wal.apply(event)?;
            // Explicitly labeled hypothetical; no fabricated fills.
            println!(
                "{}",
                serde_json::json!({"mode":"REPLAY_ONLY","actions":actions})
            );
        }
        Ok(())
    };
    run().map_err(|e| (78, e))
}
