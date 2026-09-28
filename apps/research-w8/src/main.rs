//! CTO-W8 CLI. Replays FIRST01 over W7 paths. No network.

use momento_research_replay::{W8RunConfig, run_w8_batch};
use tracing::info;
use tracing_subscriber::EnvFilter;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("info".parse().unwrap()))
        .init();
    let args: Vec<String> = std::env::args().collect();
    let mut cfg = W8RunConfig::defaults();
    let mut i = 1usize;
    while i < args.len() {
        match args[i].as_str() {
            "--replay" | "--reconstruct" => {
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
            "--w7" => {
                cfg.w7_sqlite = args.get(i + 1).expect("--w7 PATH").into();
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
    let report = run_w8_batch(&cfg).expect("w8");
    info!(
        games = report.games_processed,
        observations = report.observations_processed,
        prints_80 = report.prints_80,
        first80 = report.first80_events,
        confirm81 = report.confirm81_events,
        eligible = report.entry_eligible_events,
        lock = report.game_lock_events,
        gate = %report.w8_gate,
        "W8 FIRST01 replay"
    );
}
