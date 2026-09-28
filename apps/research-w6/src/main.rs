//! CTO-W6 CLI. Reconstructs canonical MLB game states from committed PBP. No network.

use momento_research_state::{W6RunConfig, run_w6_batch};
use tracing::info;
use tracing_subscriber::EnvFilter;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("info".parse().unwrap()))
        .init();
    let args: Vec<String> = std::env::args().collect();
    let mut cfg = W6RunConfig::defaults();
    let mut i = 1usize;
    while i < args.len() {
        match args[i].as_str() {
            "--reconstruct" => {
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
    let report = run_w6_batch(&cfg).expect("w6");
    info!(
        discovered = report.games_discovered,
        ok = report.games_successful,
        failed = report.games_failed,
        states = report.states,
        transitions = report.transitions,
        gate = %report.w6_gate,
        "W6 canonical MLB state reconstruction"
    );
}
