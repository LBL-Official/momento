//! CTO-W5 CLI. Synchronizes committed PBP with MATCHED Kalshi trades. No network.

use momento_research_sync::{W5RunConfig, run_w5_batch};
use tracing::info;
use tracing_subscriber::EnvFilter;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("info".parse().unwrap()))
        .init();
    let args: Vec<String> = std::env::args().collect();
    let mut cfg = W5RunConfig::defaults();
    let mut i = 1usize;
    while i < args.len() {
        match args[i].as_str() {
            "--sync" => {
                i += 1;
            }
            "--out" => {
                cfg.out_dir = args.get(i + 1).expect("--out PATH").into();
                i += 2;
            }
            "--lake" => {
                cfg.lake_root = args.get(i + 1).expect("--lake PATH").into();
                i += 2;
            }
            "--ingest" => {
                cfg.ingest_root = args.get(i + 1).expect("--ingest PATH").into();
                i += 2;
            }
            "--pairs" => {
                cfg.pairs = args.get(i + 1).expect("--pairs PATH").into();
                i += 2;
            }
            "--games" => {
                let raw = args.get(i + 1).expect("--games LIST_OR_PATH");
                cfg.game_filter = Some(parse_list(raw));
                i += 2;
            }
            "--markets" => {
                let raw = args.get(i + 1).expect("--markets LIST_OR_PATH");
                cfg.market_filter = Some(parse_list(raw));
                i += 2;
            }
            "--max-games" => {
                cfg.max_games = Some(args.get(i + 1).expect("--max-games N").parse().expect("n"));
                i += 2;
            }
            other => {
                eprintln!("unknown arg {other}");
                std::process::exit(2);
            }
        }
    }
    let report = run_w5_batch(&cfg).expect("w5");
    info!(
        games = report.games_attempted,
        synced = report.observations_synchronized,
        at_event = report.observations_at_event,
        gate = %report.w5_gate,
        "W5 event↔market synchronization"
    );
}

fn parse_list(raw: &str) -> Vec<String> {
    let path = std::path::Path::new(raw);
    if path.exists() {
        if let Ok(body) = std::fs::read_to_string(path) {
            return body
                .lines()
                .map(|l| {
                    l.trim()
                        .trim_matches(|c| c == '"' || c == '[' || c == ']' || c == ',')
                        .to_string()
                })
                .filter(|l| !l.is_empty())
                .collect();
        }
    }
    raw.split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect()
}
