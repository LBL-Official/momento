//! Read-only EventMarketPath query API. Does not imply L2 availability.

use chrono::{DateTime, Utc};

use crate::error::W7Error;
use crate::store::PathStore;
use crate::types::PathObservation;

pub fn path_for_game(store: &PathStore, game_id: &str) -> Result<Vec<PathObservation>, W7Error> {
    store.path_for_game(game_id)
}

pub fn path_for_market(
    store: &PathStore,
    market_id: &str,
) -> Result<Vec<PathObservation>, W7Error> {
    store.path_for_market(market_id)
}

pub fn path_for_contract(
    store: &PathStore,
    market_id: &str,
    side: &str,
) -> Result<Vec<PathObservation>, W7Error> {
    store.path_for_contract(market_id, side)
}

pub fn observations_at_state(
    store: &PathStore,
    game_id: &str,
    state_id: &str,
) -> Result<Vec<PathObservation>, W7Error> {
    store.observations_at_state(game_id, state_id)
}

pub fn observations_in_state_seq_range(
    store: &PathStore,
    game_id: &str,
    start_seq: u32,
    end_seq: u32,
) -> Result<Vec<PathObservation>, W7Error> {
    store.observations_in_state_seq_range(game_id, start_seq, end_seq)
}

pub fn observations_at_or_before(
    store: &PathStore,
    game_id: &str,
    timestamp: DateTime<Utc>,
) -> Result<Vec<PathObservation>, W7Error> {
    store.observations_at_or_before(game_id, timestamp)
}

pub fn state_at_market_observation(
    store: &PathStore,
    observation_id: &str,
) -> Result<Option<PathObservation>, W7Error> {
    store.state_at_market_observation(observation_id)
}

pub fn market_observations_before(
    store: &PathStore,
    observation_id: &str,
) -> Result<Vec<PathObservation>, W7Error> {
    store.market_observations_before(observation_id)
}

pub fn market_observations_after(
    store: &PathStore,
    observation_id: &str,
) -> Result<Vec<PathObservation>, W7Error> {
    store.market_observations_after(observation_id)
}

/// Observational 80¢ print query. Not FIRST01 entry logic.
pub fn observations_where_price_equals(
    store: &PathStore,
    cents: i32,
) -> Result<Vec<PathObservation>, W7Error> {
    store.observations_where_price_equals(cents)
}
