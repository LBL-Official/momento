//! Dataset quality computed from stored snapshots. Never hard-coded.

use momento_research_features::FeatureStore;

use crate::error::EngineError;

pub fn first83_quality_from_sqlite(
    path: &std::path::Path,
) -> Result<serde_json::Value, EngineError> {
    let store = FeatureStore::open_existing(path)?;
    let snaps = store.load_all()?;
    let n = snaps.len();
    if n == 0 {
        return Ok(serde_json::json!({
            "games": 0,
            "note": "empty feature store"
        }));
    }
    let mut settlement = 0usize;
    let mut inning = 0usize;
    let mut dated = 0usize;
    let mut price_83 = 0usize;
    let mut min_date = String::from("9999-99-99");
    let mut max_date = String::new();
    for s in &snaps {
        if s.entry_trade_price_cents == 83 {
            price_83 += 1;
        }
        if s.outcomes.settlement.as_str() != "SETTLEMENT_UNAVAILABLE" {
            settlement += 1;
        }
        if s.baseball.inning.is_some() {
            inning += 1;
        }
        if let Some(d) = &s.official_date {
            dated += 1;
            if d.as_str() < min_date.as_str() {
                min_date = d.clone();
            }
            if d.as_str() > max_date.as_str() {
                max_date = d.clone();
            }
        }
    }
    let pct = |k: usize| (k as f64) * 100.0 / n as f64;
    Ok(serde_json::json!({
        "games": n,
        "exact_83_entries": price_83,
        "settlement_label_coverage_pct": (pct(settlement) * 10.0).round() / 10.0,
        "game_state_inning_coverage_pct": (pct(inning) * 10.0).round() / 10.0,
        "official_date_coverage_pct": (pct(dated) * 10.0).round() / 10.0,
        "l2_coverage_pct": 0.0,
        "l2_status": "UNAVAILABLE_SOURCE",
        "trade_status": "TRADE_PRINT_MODELED",
        "date_min": min_date,
        "date_max": max_date,
        "computed_from": path.display().to_string()
    }))
}
