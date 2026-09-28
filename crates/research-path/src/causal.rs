//! Causal path descriptors. At T, only observations with timestamp <= T.

use chrono::{DateTime, Utc};
use std::collections::BTreeMap;

use crate::join::sort_path_observations;
use crate::types::{EventMarketPath, PathObservation, StateSegment};

/// Fill causal market descriptors in chronological order for one contract path.
/// Does not read future prices, future extrema, or next-state for features.
pub fn apply_causal_descriptors(rows: &mut [PathObservation]) {
    let mut prev_price: Option<i32> = None;
    let mut prev_ts: Option<DateTime<Utc>> = None;
    let mut count = 0u32;
    let mut high: Option<i32> = None;
    let mut low: Option<i32> = None;
    let mut changes = 0u32;
    for (i, row) in rows.iter_mut().enumerate() {
        row.chrono_index = i as u32;
        row.previous_trade_price_cents = prev_price;
        if let Some(px) = row.trade_price_cents {
            count += 1;
            row.cumulative_trade_count = count;
            row.price_change_cents = prev_price.map(|p| px - p);
            row.prior_price_changes = changes;
            if let Some(p) = prev_price {
                if p != px {
                    changes += 1;
                }
            }
            high = Some(high.map_or(px, |h| h.max(px)));
            low = Some(low.map_or(px, |l| l.min(px)));
            row.observed_high_cents_so_far = high;
            row.observed_low_cents_so_far = low;
            row.distance_from_high_cents = high.map(|h| h - px);
            row.distance_from_low_cents = low.map(|l| px - l);
            prev_price = Some(px);
        } else {
            row.cumulative_trade_count = count;
            row.prior_price_changes = changes;
            row.observed_high_cents_so_far = high;
            row.observed_low_cents_so_far = low;
        }
        if let (Some(t), Some(p)) = (row.market_timestamp_utc, prev_ts) {
            row.time_since_previous_trade_ms = Some((t - p).num_milliseconds());
        }
        prev_ts = row.market_timestamp_utc.or(prev_ts);
    }
}

pub fn state_segments(path_id: &str, rows: &[PathObservation]) -> Vec<StateSegment> {
    let mut out = Vec::new();
    let mut cur: Option<StateSegment> = None;
    for r in rows {
        let Some(sid) = r.state_id.as_ref() else {
            if let Some(seg) = cur.take() {
                out.push(seg);
            }
            continue;
        };
        match cur.as_mut() {
            Some(seg) if &seg.state_id == sid => {
                seg.observation_count += 1;
                seg.last_market_timestamp_utc = r.market_timestamp_utc;
            }
            _ => {
                if let Some(seg) = cur.take() {
                    out.push(seg);
                }
                cur = Some(StateSegment {
                    path_id: path_id.to_string(),
                    game_id: r.game_id.clone(),
                    market_id: r.market_id.clone(),
                    contract_side: r.contract_side.clone(),
                    state_id: sid.clone(),
                    state_seq: r.state_seq.unwrap_or(0),
                    observation_count: 1,
                    first_market_timestamp_utc: r.market_timestamp_utc,
                    last_market_timestamp_utc: r.market_timestamp_utc,
                });
            }
        }
    }
    if let Some(seg) = cur {
        out.push(seg);
    }
    out
}

/// Group W7 rows into per-contract paths. Causal descriptors run independently per side.
pub fn assemble_paths(rows: Vec<PathObservation>) -> Vec<EventMarketPath> {
    let mut groups: BTreeMap<(String, String, String), Vec<PathObservation>> = BTreeMap::new();
    for row in rows {
        groups
            .entry((
                row.game_id.clone(),
                row.market_id.clone(),
                row.contract_side.clone(),
            ))
            .or_default()
            .push(row);
    }
    let mut out = Vec::new();
    for ((game_id, market_id, contract_side), mut obs) in groups {
        sort_path_observations(&mut obs);
        apply_causal_descriptors(&mut obs);
        let path_id = obs.first().map(|o| o.path_id.clone()).unwrap_or_default();
        let game_pk = obs.first().map(|o| o.game_pk.clone()).unwrap_or_default();
        out.push(EventMarketPath {
            path_id,
            game_id,
            game_pk,
            market_id,
            contract_side,
            observations: obs,
        });
    }
    out
}
