//! Build one B1 snapshot from W8 entry + W7 path + W6 state.

use chrono::{DateTime, Utc};
use momento_research_path::PathObservation;
use momento_research_state::{StoredState, StoredTransition};

use crate::a1_targets::a1_targets;
use crate::event_response::event_responses;
use crate::game_state::baseball_features;
use crate::identity::TeamIdentity;
use crate::ids::snapshot_id;
use crate::interactions::interactions;
use crate::microstructure::current_microstructure;
use crate::normalization::chronological_split;
use crate::outcomes::forward_outcomes;
use crate::price_history::{
    attach_volatility, path_stats, price_dynamics, priced_after, priced_at_or_before,
    refine_personality,
};
use crate::starting_market::starting_market;
use crate::types::{B1EntrySnapshot, CurrentMarketFeatures, FairValueFeatures};
use crate::versions::{
    DATASET_VERSION, DEFAULT_SPLIT_CUTOFF_DATE, EXECUTION_STATUS, FEATURE_SCHEMA_VERSION,
    OBSERVABILITY,
};

#[derive(Clone, Debug)]
pub struct W8EntryInput {
    pub opportunity_id: String,
    pub game_id: String,
    pub market_id: String,
    pub side: String,
    pub entry_timestamp: DateTime<Utc>,
    pub entry_observation_id: String,
    pub entry_price_cents: i32,
    pub first80_observation_id: Option<String>,
    pub first80_timestamp: Option<DateTime<Utc>>,
    pub confirm_observation_id: Option<String>,
    pub official_date: Option<String>,
    pub game_pk: Option<String>,
    pub game_status: Option<String>,
}

pub fn extract_snapshot(
    input: &W8EntryInput,
    path: &[PathObservation],
    states: &[StoredState],
    transitions: &[StoredTransition],
    identity: Option<&TeamIdentity>,
) -> B1EntrySnapshot {
    let entry = input.entry_timestamp;
    let entry_px = input.entry_price_cents;
    let prior = priced_at_or_before(path, &input.game_id, &input.market_id, &input.side, entry);
    let future = priced_after(path, &input.game_id, &input.market_id, &input.side, entry);
    let start = starting_market(path, &input.game_id, &input.market_id, &input.side, entry);
    let baseball = baseball_features(states, entry, &input.side, identity);
    let mut hist = path_stats(&prior);
    attach_volatility(&mut hist, &prior, entry);
    let dyns = price_dynamics(&prior, entry, entry_px);
    refine_personality(&mut hist, &dyns);
    let events = event_responses(transitions, &prior, entry);
    let final_state = states.last();
    let outcomes = forward_outcomes(
        &future,
        entry,
        entry_px,
        final_state,
        input.game_status.as_deref(),
        identity,
        &input.side,
    );
    let a1 = a1_targets(&future, entry, entry_px, &outcomes);
    let ix = interactions(
        &baseball,
        start.start_bias_cents,
        start.start_sentiment,
        a1.entry_target,
        &hist,
        &dyns,
    );
    let split_date = input
        .official_date
        .clone()
        .unwrap_or_else(|| entry.date_naive().to_string());
    let ticker = path
        .iter()
        .find(|o| o.market_id == input.market_id)
        .map(|o| o.ticker.clone());
    let path_id = path
        .iter()
        .find(|o| o.observation_id == input.entry_observation_id)
        .map(|o| o.path_id.clone());
    let entry_obs = path
        .iter()
        .find(|o| o.observation_id == input.entry_observation_id);
    B1EntrySnapshot {
        snapshot_id: snapshot_id(
            DATASET_VERSION,
            &input.opportunity_id,
            &input.entry_observation_id,
        ),
        game_id: input.game_id.clone(),
        market_id: input.market_id.clone(),
        ticker,
        contract_side: input.side.clone(),
        entry_timestamp: entry,
        entry_signal_price_cents: entry_px,
        entry_trade_price_cents: entry_px,
        execution_status: EXECUTION_STATUS.to_string(),
        observability: OBSERVABILITY.to_string(),
        entry_state_id: baseball.state_id.clone(),
        entry_state_seq: baseball.state_seq,
        w5_observation_id: input.entry_observation_id.clone(),
        w5_prior_event_id: entry_obs.and_then(|o| o.transition_id.clone()),
        w7_path_id: path_id,
        w8_opportunity_id: input.opportunity_id.clone(),
        first80_observation_id: input.first80_observation_id.clone(),
        first80_timestamp: input.first80_timestamp,
        confirm_observation_id: input.confirm_observation_id.clone(),
        official_date: input.official_date.clone(),
        split_group: chronological_split(&split_date, DEFAULT_SPLIT_CUTOFF_DATE),
        baseball,
        starting_market: start,
        current_market: CurrentMarketFeatures::from_entry_trade(entry_px),
        market_history: hist,
        price_dynamics: dyns,
        event_response: events,
        microstructure: current_microstructure(),
        fair_value: FairValueFeatures::reserved(),
        a1_targets: a1,
        outcomes,
        interactions: ix,
        feature_schema_version: FEATURE_SCHEMA_VERSION.to_string(),
    }
}
