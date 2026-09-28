//! CTO-W4 CLI. Reconstructs committed Kalshi market paths. Does not download. Does not trade.

use chrono::NaiveDate;
use momento_research_market::{
    W4RunConfig, run_matched_trade_reconstruction, run_price_path_reconstruction,
    run_universe_inventory, run_w4_reconstruction,
};
use tracing::info;
use tracing_subscriber::EnvFilter;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("info".parse().unwrap()))
        .init();
    let args: Vec<String> = std::env::args().collect();
    let mut cfg = W4RunConfig::defaults();
    let mut inventory_only = false;
    let mut reconstruct_price_paths = false;
    let mut reconstruct_matched = false;
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
            "--ingest" => {
                cfg.ingest_root = args.get(i + 1).expect("--ingest PATH").into();
                i += 2;
            }
            "--handoff" => {
                cfg.handoff = Some(args.get(i + 1).expect("--handoff PATH").into());
                i += 2;
            }
            "--pairs" => {
                cfg.pairs = Some(args.get(i + 1).expect("--pairs PATH").into());
                i += 2;
            }
            "--date" => {
                let raw = args.get(i + 1).expect("--date YYYY-MM-DD");
                cfg.date = NaiveDate::parse_from_str(raw, "%Y-%m-%d").expect("date");
                i += 2;
            }
            "--skip-lake" => {
                cfg.include_lake_raw = false;
                i += 1;
            }
            "--universe-inventory" => {
                inventory_only = true;
                i += 1;
            }
            "--reconstruct-price-paths" => {
                reconstruct_price_paths = true;
                i += 1;
            }
            "--reconstruct-matched-price-paths" => {
                reconstruct_matched = true;
                i += 1;
            }
            other => {
                eprintln!("unknown arg {other}");
                std::process::exit(2);
            }
        }
    }
    if reconstruct_matched {
        let report = run_matched_trade_reconstruction(
            &cfg.ingest_root,
            &cfg.lake_root,
            &cfg.out_dir,
            cfg.handoff.as_deref(),
            cfg.pairs.as_deref(),
        )
        .expect("w4 matched reconstruct");
        info!(
            matched = report.total_matched_markets,
            with_trades = report.matched_with_trades,
            metadata_only = report.matched_metadata_only,
            eighty = report.matched_with_exact_80_print,
            eighty_one = report.matched_with_exact_81_print,
            eighty_nine = report.matched_with_exact_89_print,
            "W4-D MATCHED trade reconstruction"
        );
        return;
    }
    if reconstruct_price_paths {
        let report = run_price_path_reconstruction(
            &cfg.ingest_root,
            &cfg.lake_root,
            &cfg.out_dir,
            cfg.handoff.as_deref(),
            cfg.pairs.as_deref(),
        )
        .expect("w4 price-path reconstruct");
        info!(
            markets = report.unique_markets_inventoried,
            reconstructed = report.reconstructed,
            trades_only = report.reconstructable_trades_only,
            eighty = report.funnel_reconstructed_markets.eighty_observable,
            gate = %report.w4_gate,
            "W4 price-path reconstruction"
        );
        return;
    }
    if inventory_only {
        let inv = run_universe_inventory(
            &cfg.ingest_root,
            &cfg.lake_root,
            &cfg.out_dir,
            cfg.handoff.as_deref(),
            cfg.pairs.as_deref(),
        )
        .expect("w4 inventory");
        info!(
            markets = inv.unique_markets,
            events = inv.unique_event_tickers,
            gate = %inv.w4_gate,
            "W4 universe inventory"
        );
        return;
    }
    let result = run_w4_reconstruction(&cfg).expect("w4");
    info!(
        run_id = %result.run_id,
        date = %result.date,
        reconstructed = result.reconstructed,
        failed = result.failed,
        claimed = result.completeness_claimed,
        "W4 reconstruction"
    );
}
