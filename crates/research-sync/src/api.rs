//! Public W5 research API.

use chrono::{DateTime, Utc};

use crate::apply::synchronize_market;
use crate::batch::{SyncReport, W5RunConfig, game_state_at_market_time, run_w5_batch};
use crate::error::W5Error;
use crate::store::SyncStore;
use crate::types::{
    GameStateSnapshot, IdentityStatus, MarketObservation, SyncParams,
    SynchronizedMarketObservation, TimedEvent,
};

pub fn synchronize_game(
    game_id: &str,
    game_pk: &str,
    identity: IdentityStatus,
    events: &[TimedEvent],
    tapes: &[(String, Vec<MarketObservation>, Option<i32>)],
) -> Vec<SynchronizedMarketObservation> {
    synchronize_game_with_clock(game_id, game_pk, identity, events, tapes, false)
}

pub fn synchronize_game_with_clock(
    game_id: &str,
    game_pk: &str,
    identity: IdentityStatus,
    events: &[TimedEvent],
    tapes: &[(String, Vec<MarketObservation>, Option<i32>)],
    ambiguous_clock: bool,
) -> Vec<SynchronizedMarketObservation> {
    let mut out = Vec::new();
    for (side, obs, first) in tapes {
        out.extend(synchronize_market(
            SyncParams {
                game_id,
                game_pk,
                identity,
                events,
                contract_side: side,
                first_observed_price_cents: *first,
                ambiguous_clock,
            },
            obs,
        ));
    }
    out
}

pub fn synchronized_observations_for_game(
    store: &SyncStore,
    game_id: &str,
) -> Result<Vec<SynchronizedMarketObservation>, W5Error> {
    store.observations_for_game(game_id)
}

pub fn synchronized_observations_for_market(
    store: &SyncStore,
    market_id: &str,
) -> Result<Vec<SynchronizedMarketObservation>, W5Error> {
    store.observations_for_market(market_id)
}

pub fn synchronized_observations_for_event(
    store: &SyncStore,
    game_id: &str,
    event_id: &str,
) -> Result<Vec<SynchronizedMarketObservation>, W5Error> {
    store.observations_for_event_interval(game_id, event_id)
}

pub fn synchronization_report(cfg: &W5RunConfig) -> Result<SyncReport, W5Error> {
    run_w5_batch(cfg)
}

pub fn game_state_at(
    events: &[TimedEvent],
    timestamp: DateTime<Utc>,
) -> Result<GameStateSnapshot, W5Error> {
    game_state_at_market_time(events, timestamp)
}
