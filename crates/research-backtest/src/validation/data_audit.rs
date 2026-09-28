//! Real MLB dataset audit (excludes demo fixtures).

use chrono::NaiveDate;
use momento_research_data::{
    CompletenessStatus, DailyManifest, NormalizedSource, OrderbookEvent, ReplayDataset,
    ResearchPaths, ResearchSport,
};
use serde::{Deserialize, Serialize};

use crate::dataset::dates_inclusive;

const DEMO_MARKER: &str = "DEMO FIXTURE";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DayAuditRow {
    pub date: String,
    pub manifest_status: String,
    pub is_demo: bool,
    pub market_count: u32,
    pub event_count: u64,
    pub orderbook_event_count: u64,
    pub trade_count: u64,
    pub full_l2_events: u64,
    pub top_of_book_events: u64,
    pub candlestick_events: u64,
    pub no_execution_data_events: u64,
    pub sequence_gaps: u64,
    pub missing_markets: u32,
    pub invalid_partitions: u32,
    pub eligible: bool,
    pub exclusion_reason: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct MlbDataAudit {
    pub data_root: String,
    pub season: String,
    pub total_dates_scanned: u32,
    pub complete_dates: u32,
    pub partial_dates: u32,
    pub missing_dates: u32,
    pub invalid_dates: u32,
    pub demo_dates: u32,
    pub eligible_dates: u32,
    pub market_days: u64,
    pub eligible_market_days: u64,
    pub contiguous_eligible_start: Option<String>,
    pub contiguous_eligible_end: Option<String>,
    pub rows: Vec<DayAuditRow>,
}

fn is_demo_manifest(m: &DailyManifest) -> bool {
    m.notes.iter().any(|n| n.contains(DEMO_MARKER))
}

pub fn audit_mlb_data(paths: &ResearchPaths, season_label: &str) -> Result<MlbDataAudit, String> {
    let start = NaiveDate::from_ymd_opt(2025, 3, 1).unwrap();
    let end = chrono::Utc::now().date_naive();
    let dates = dates_inclusive(start, end);
    let mut audit = MlbDataAudit {
        data_root: paths.root.display().to_string(),
        season: season_label.to_string(),
        total_dates_scanned: dates.len() as u32,
        ..Default::default()
    };

    let mut eligible_dates_list: Vec<NaiveDate> = Vec::new();

    for date in dates {
        let manifest =
            DailyManifest::read(paths, ResearchSport::Mlb, date).map_err(|e| e.to_string())?;
        let Some(m) = manifest else {
            audit.missing_dates += 1;
            audit.rows.push(DayAuditRow {
                date: date.to_string(),
                manifest_status: "MISSING".into(),
                is_demo: false,
                market_count: 0,
                event_count: 0,
                orderbook_event_count: 0,
                trade_count: 0,
                full_l2_events: 0,
                top_of_book_events: 0,
                candlestick_events: 0,
                no_execution_data_events: 0,
                sequence_gaps: 0,
                missing_markets: 0,
                invalid_partitions: 0,
                eligible: false,
                exclusion_reason: "NO_MANIFEST".into(),
            });
            continue;
        };

        let demo = is_demo_manifest(&m);
        if demo {
            audit.demo_dates += 1;
        }

        match m.completeness_status {
            CompletenessStatus::Complete => audit.complete_dates += 1,
            CompletenessStatus::Partial => audit.partial_dates += 1,
            CompletenessStatus::Missing => audit.missing_dates += 1,
            CompletenessStatus::Invalid => audit.invalid_dates += 1,
        }

        let (full_l2, top, candle, none, seq_gaps) =
            if let Ok(ds) = ReplayDataset::load(paths, ResearchSport::Mlb, date) {
                let mut full_l2 = 0u64;
                let mut top = 0u64;
                let mut candle = 0u64;
                let mut none = 0u64;
                for ob in &ds.orderbook_events {
                    match classify_quality(ob) {
                        "FULL_L2" => full_l2 += 1,
                        "TOP_OF_BOOK_ONLY" => top += 1,
                        "CANDLESTICK_ONLY" => candle += 1,
                        _ => none += 1,
                    }
                }
                (full_l2, top, candle, none, m.sequence_gaps as u64)
            } else {
                (0, 0, 0, 0, m.sequence_gaps as u64)
            };

        let mut eligible = m.completeness_status == CompletenessStatus::Complete
            && !demo
            && m.markets_collected > 0
            && m.orderbook_event_count > 0;
        let mut exclusion = String::new();
        if demo {
            eligible = false;
            exclusion = "DEMO_FIXTURE".into();
        } else if m.completeness_status != CompletenessStatus::Complete {
            eligible = false;
            exclusion = format!("{:?}", m.completeness_status).to_uppercase();
        } else if m.markets_collected == 0 {
            eligible = false;
            exclusion = "NO_MARKETS".into();
        } else if m.orderbook_event_count == 0 {
            eligible = false;
            exclusion = "INSUFFICIENT_DATA".into();
        }

        if eligible {
            audit.eligible_dates += 1;
            audit.eligible_market_days += u64::from(m.markets_collected);
            eligible_dates_list.push(date);
        }
        audit.market_days += u64::from(m.markets_discovered.max(m.markets_collected));

        audit.rows.push(DayAuditRow {
            date: date.to_string(),
            manifest_status: format!("{:?}", m.completeness_status).to_uppercase(),
            is_demo: demo,
            market_count: m.markets_collected,
            event_count: m.normalized_event_count,
            orderbook_event_count: m.orderbook_event_count,
            trade_count: m.trade_count,
            full_l2_events: full_l2,
            top_of_book_events: top,
            candlestick_events: candle,
            no_execution_data_events: none,
            sequence_gaps: seq_gaps,
            missing_markets: m.missing_markets.len() as u32,
            invalid_partitions: m.invalid_records,
            eligible,
            exclusion_reason: exclusion,
        });
    }

    if let (Some(first), Some(last)) = (eligible_dates_list.first(), eligible_dates_list.last()) {
        audit.contiguous_eligible_start = Some(first.to_string());
        audit.contiguous_eligible_end = Some(last.to_string());
    }

    Ok(audit)
}

fn classify_quality(ob: &OrderbookEvent) -> &'static str {
    if ob.sequence_gap {
        return "NO_EXECUTION_DATA";
    }
    if ob.source == NormalizedSource::RestCandlestick {
        return "CANDLESTICK_ONLY";
    }
    if !ob.levels.is_empty()
        && matches!(
            ob.source,
            NormalizedSource::WebSocketDelta | NormalizedSource::WebSocketSnapshot
        )
    {
        return "FULL_L2";
    }
    if ob.yes_bid_cents.is_some() && ob.yes_ask_cents.is_some() {
        return "TOP_OF_BOOK_ONLY";
    }
    "NO_EXECUTION_DATA"
}
