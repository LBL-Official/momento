//! CTO-W3 CLI. Reconstructs committed PBP. Does not download. Does not trade.

use momento_research_reconstruction::{W3RunConfig, run_w3_reconstruction};
use tracing::info;
use tracing_subscriber::EnvFilter;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("info".parse().unwrap()))
        .init();
    let args: Vec<String> = std::env::args().collect();
    let mut cfg = W3RunConfig::defaults();
    let mut i = 1usize;
    while i < args.len() {
        match args[i].as_str() {
            "--out" => {
                cfg.out_dir = args.get(i + 1).expect("--out PATH").into();
                i += 2;
            }
            "--lake" => {
                cfg.lake_root = args.get(i + 1).expect("--lake PATH").into();
                i += 2;
            }
            "--manifest" => {
                cfg.collect_manifest = Some(args.get(i + 1).expect("--manifest PATH").into());
                i += 2;
            }
            other => {
                eprintln!("unknown arg {other}");
                std::process::exit(2);
            }
        }
    }
    let result = run_w3_reconstruction(&cfg).expect("w3");
    info!(
        run_id = %result.run_id,
        valid = result.valid,
        failed = result.failed,
        skipped = result.skipped,
        events = result.pbp_events,
        "W3 reconstruction"
    );
}
