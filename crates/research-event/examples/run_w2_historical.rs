//! Collect StatsAPI PBP (outside Data-Real) and reconstruct W2-E/W2-B/W2-F.

use chrono::TimeZone;

fn main() {
    let out = std::path::PathBuf::from("Backtesting Suite/Foundation/W2");
    let collect_cfg = momento_research_event::collect::CollectConfig::kalshi_window(&out);
    match momento_research_event::collect::collect_statsapi_window(&collect_cfg) {
        Ok(c) => {
            println!(
                "collected={} skipped_existing={} skipped_status={} errors={}",
                c.games_collected,
                c.games_skipped_existing,
                c.games_skipped_status,
                c.errors.len()
            );
            for e in &c.errors {
                eprintln!("collect error: {e}");
            }
        }
        Err(e) => {
            eprintln!("collect failed: {e}");
            std::process::exit(1);
        }
    }
    let mut cfg = momento_research_event::W2RunConfig::defaults();
    cfg.generated_at = chrono::Utc.with_ymd_and_hms(2026, 8, 26, 8, 30, 0).unwrap();
    match momento_research_event::run_w2_event_reconstruction(&cfg) {
        Ok(r) => println!("{}", serde_json::to_string_pretty(&r).expect("json")),
        Err(e) => {
            eprintln!("{e}");
            std::process::exit(1);
        }
    }
}
