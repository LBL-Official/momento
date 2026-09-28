//! Apply AS-OF sync to market observations. No lookahead. No interpolation.

use sha2::{Digest, Sha256};

use crate::as_of::{AsOfReject, as_of, classify_success, game_window};
use crate::types::{
    IdentityStatus, MarketObservation, SyncParams, SyncQuality, SyncStatus,
    SynchronizedMarketObservation, TimestampRelation,
};
use crate::versions::{DATASET_VERSION, METHOD_AS_OF_PRIOR_EVENT};

pub fn synchronize_market_observation(
    params: SyncParams<'_>,
    obs: &MarketObservation,
) -> SynchronizedMarketObservation {
    let mut row = base_row(
        params.game_id,
        params.game_pk,
        obs,
        params.contract_side,
        params.first_observed_price_cents,
    );

    match params.identity {
        IdentityStatus::Unmatched => {
            row.synchronization_status = SyncStatus::IdentityUnmatched;
            row.synchronization_quality = SyncQuality::Unmatched;
            stamp_id(&mut row);
            return row;
        }
        IdentityStatus::Ambiguous => {
            row.synchronization_status = SyncStatus::IdentityAmbiguous;
            row.synchronization_quality = SyncQuality::Ambiguous;
            stamp_id(&mut row);
            return row;
        }
        IdentityStatus::Matched => {}
    }

    let Some(t) = obs.normalized_market_time else {
        row.synchronization_status = SyncStatus::MissingTimestamp;
        row.synchronization_quality = SyncQuality::Unavailable;
        row.timestamp_relation = TimestampRelation::NotApplicable;
        stamp_id(&mut row);
        return row;
    };

    if params.events.is_empty() {
        row.synchronization_status = SyncStatus::SourceDataInvalid;
        row.synchronization_quality = SyncQuality::Unavailable;
        stamp_id(&mut row);
        return row;
    }
    let window = game_window(params.events);
    match as_of(params.events, t, window.as_ref()) {
        Err(AsOfReject::NoPriorEvent { next }) => {
            row.synchronization_status = SyncStatus::BeforeFirstEvent;
            row.synchronization_quality = SyncQuality::Unavailable;
            row.timestamp_relation = TimestampRelation::BeforeEvent;
            row.next_event_id = next.as_ref().map(|n| n.event_id.clone());
            row.next_event_timestamp_utc = next.as_ref().map(|n| n.normalized_event_time);
            if let Some(n) = next.as_ref() {
                row.market_to_next_event_ms =
                    Some((n.normalized_event_time - t).num_milliseconds());
            }
        }
        Err(AsOfReject::OutsideWindow { last }) => {
            row.synchronization_status = SyncStatus::AfterLastEvent;
            row.synchronization_quality = SyncQuality::Unavailable;
            row.timestamp_relation = TimestampRelation::AfterEvent;
            row.prior_event_id = Some(last.event_id.clone());
            row.prior_event_timestamp_utc = Some(last.normalized_event_time);
            row.event_to_market_lag_ms = Some((t - last.normalized_event_time).num_milliseconds());
            // Diagnostic only — do not attach last game state.
        }
        Ok(hit) => {
            if params.ambiguous_clock {
                row.synchronization_status = SyncStatus::AmbiguousTimestamp;
                row.synchronization_quality = SyncQuality::Ambiguous;
                row.timestamp_relation = TimestampRelation::AmbiguousTimestamp;
                fill_hit(&mut row, &hit);
                row.game_state = None;
                row.pre_event_state = None;
                row.post_event_state = None;
            } else {
                let (status, quality, relation) = classify_success(hit.lag_ms);
                row.synchronization_status = status;
                row.synchronization_quality = quality;
                row.timestamp_relation = relation;
                fill_hit(&mut row, &hit);
            }
        }
    }
    stamp_id(&mut row);
    row
}

fn fill_hit(row: &mut SynchronizedMarketObservation, hit: &crate::types::AsOfHit) {
    row.prior_event_id = Some(hit.matched.event_id.clone());
    row.prior_event_timestamp_utc = Some(hit.matched.normalized_event_time);
    row.next_event_id = hit.next.as_ref().map(|n| n.event_id.clone());
    row.next_event_timestamp_utc = hit.next.as_ref().map(|n| n.normalized_event_time);
    row.event_to_market_lag_ms = Some(hit.lag_ms);
    row.market_to_next_event_ms = hit.lead_ms;
    row.pre_event_state = Some(hit.matched.state_before.clone());
    row.post_event_state = Some(hit.matched.state_after.clone());
    // Applicable state is post(prior). For AT_EVENT this is W3 effective-after;
    // timestamp_relation distinguishes the collision.
    row.game_state = Some(hit.matched.state_after.clone());
}

fn base_row(
    game_id: &str,
    game_pk: &str,
    obs: &MarketObservation,
    contract_side: &str,
    first_observed_price_cents: Option<i32>,
) -> SynchronizedMarketObservation {
    SynchronizedMarketObservation {
        synchronization_id: String::new(),
        game_id: game_id.to_string(),
        game_pk: game_pk.to_string(),
        market_id: obs.market_id.clone(),
        ticker: obs.ticker.clone(),
        contract_id: obs.ticker.clone(),
        contract_side: contract_side.to_string(),
        observation_id: obs.observation_id.clone(),
        observation_type: obs.observation_type,
        market_timestamp_source: obs.source_market_time.clone(),
        source_timestamp_kind: obs.source_timestamp_kind.clone(),
        market_timestamp_utc: obs.normalized_market_time,
        retrieval_timestamp: obs.retrieval_time,
        prior_event_id: None,
        prior_event_timestamp_utc: None,
        next_event_id: None,
        next_event_timestamp_utc: None,
        timestamp_relation: TimestampRelation::NotApplicable,
        event_to_market_lag_ms: None,
        market_to_next_event_ms: None,
        synchronization_status: SyncStatus::SourceDataInvalid,
        synchronization_method: METHOD_AS_OF_PRIOR_EVENT.into(),
        synchronization_quality: SyncQuality::Unavailable,
        game_state: None,
        pre_event_state: None,
        post_event_state: None,
        prior_market_observation_id: None,
        next_market_observation_id: None,
        elapsed_from_prior_obs_ms: None,
        elapsed_to_next_obs_ms: None,
        last_trade_cents: obs.last_trade_cents,
        first_observed_price_cents,
        source_id: obs.source_id.clone(),
        source_lineage: obs.source_lineage.clone(),
        dataset_version: DATASET_VERSION.into(),
    }
}

fn stamp_id(row: &mut SynchronizedMarketObservation) {
    row.synchronization_id = format!(
        "{:x}",
        Sha256::digest(
            format!(
                "sync\0{}\0{}\0{}\0{}\0{}",
                row.observation_id,
                row.prior_event_id.as_deref().unwrap_or(""),
                row.synchronization_status.as_str(),
                row.timestamp_relation.as_str(),
                row.synchronization_method
            )
            .as_bytes()
        )
    );
}

/// Link chronological market path. Does not interpolate price or time.
pub fn link_market_path(rows: &mut [SynchronizedMarketObservation]) {
    let n = rows.len();
    for i in 0..n {
        if i > 0 {
            rows[i].prior_market_observation_id = Some(rows[i - 1].observation_id.clone());
            if let (Some(t), Some(p)) = (
                rows[i].market_timestamp_utc,
                rows[i - 1].market_timestamp_utc,
            ) {
                rows[i].elapsed_from_prior_obs_ms = Some((t - p).num_milliseconds());
            }
        }
        if i + 1 < n {
            rows[i].next_market_observation_id = Some(rows[i + 1].observation_id.clone());
            if let (Some(t), Some(nxt)) = (
                rows[i].market_timestamp_utc,
                rows[i + 1].market_timestamp_utc,
            ) {
                rows[i].elapsed_to_next_obs_ms = Some((nxt - t).num_milliseconds());
            }
        }
    }
}

pub fn synchronize_market(
    params: SyncParams<'_>,
    observations: &[MarketObservation],
) -> Vec<SynchronizedMarketObservation> {
    let mut rows: Vec<SynchronizedMarketObservation> = observations
        .iter()
        .map(|o| synchronize_market_observation(params, o))
        .collect();
    link_market_path(&mut rows);
    rows
}
