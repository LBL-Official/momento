//! CTO-W7 CLI. Joins accepted W5 observations onto W6 states. No network.

use momento_research_path::{W7RunConfig, run_w7_batch};
use tracing::info;
use tracing_subscriber::EnvFilter;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("info".parse().unwrap()))
        .init();
    let args: Vec<String> = std::env::args().collect();
    let mut cfg = W7RunConfig::defaults();
    let mut i = 1usize;
    while i < args.len() {
        match args[i].as_str() {
            "--reconstruct" | "--path" => {
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
            "--w5" => {
                cfg.w5_sqlite = args.get(i + 1).expect("--w5 PATH").into();
                i += 2;
            }
            "--w6" => {
                cfg.w6_sqlite = args.get(i + 1).expect("--w6 PATH").into();
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
    let report = run_w7_batch(&cfg).expect("w7");
    info!(
        games = report.games_attempted,
        markets = report.markets_attempted,
        observations = report.total_market_observations,
        synchronized = report.synchronized_observations,
        before_first = report.observations_before_first_event,
        after_last = report.observations_after_last_event,
        gate = %report.w7_gate,
        "W7 EventMarketPath join"
    );
}
