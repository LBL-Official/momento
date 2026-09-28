//! Write local W2 artifacts (outside the Kalshi lake).

use chrono::TimeZone;

fn main() {
    let mut cfg = momento_research_event::W2RunConfig::defaults();
    cfg.generated_at = chrono::Utc.with_ymd_and_hms(2026, 8, 26, 7, 40, 0).unwrap();
    match momento_research_event::run_w2_event_reconstruction(&cfg) {
        Ok(r) => {
            println!("{}", serde_json::to_string_pretty(&r).expect("json"));
        }
        Err(e) => {
            eprintln!("{e}");
            std::process::exit(1);
        }
    }
}
