//! Join W5 synchronized observations to W6 canonical states.
//!
//! W5 owns AS-OF classification. W6 owns GameState identity.
//! W7 does not re-run AS-OF and does not reconstruct PBP.

use std::collections::HashMap;

use momento_research_state::{StoredState, StoredTransition};
use momento_research_sync::types::{SyncStatus, SynchronizedMarketObservation};
use sha2::{Digest, Sha256};

use crate::error::W7Error;
use crate::types::{PathJoinStatus, PathObservation};
use crate::versions::{ARTIFACT_VERSION, CAUSAL_VERSION, JOIN_VERSION, OBSERVATION_KIND_TRADE};

#[derive(Clone, Debug)]
pub struct W6Index {
    pub game_id: String,
    by_event_id: HashMap<String, StoredState>,
    by_state_id: HashMap<String, StoredState>,
    by_seq: HashMap<u32, StoredState>,
    by_resulting: HashMap<String, StoredTransition>,
    ordered: Vec<StoredState>,
}

impl W6Index {
    pub fn from_rows(
        game_id: &str,
        states: Vec<StoredState>,
        transitions: Vec<StoredTransition>,
    ) -> Self {
        let mut by_event_id = HashMap::new();
        let mut by_state_id = HashMap::new();
        let mut by_seq = HashMap::new();
        for s in &states {
            if let Some(eid) = &s.event_id {
                by_event_id.insert(eid.clone(), s.clone());
            }
            by_state_id.insert(s.state_id.clone(), s.clone());
            by_seq.insert(s.state_seq, s.clone());
        }
        let mut by_resulting = HashMap::new();
        for t in transitions {
            by_resulting.insert(t.resulting_state_id.clone(), t);
        }
        Self {
            game_id: game_id.to_string(),
            by_event_id,
            by_state_id,
            by_seq,
            by_resulting,
            ordered: states,
        }
    }

    pub fn is_empty(&self) -> bool {
        self.ordered.is_empty()
    }

    fn next_after(&self, seq: u32) -> Option<&StoredState> {
        self.ordered.iter().find(|s| s.state_seq == seq + 1)
    }
}

pub fn path_id(game_id: &str, market_id: &str, side: &str, w5_ver: &str, w6_ver: &str) -> String {
    hex_id(
        "w7.path",
        &[game_id, market_id, side, w5_ver, w6_ver, ARTIFACT_VERSION],
    )
}

pub fn path_observation_id(path_id: &str, w5_sync_id: &str, state_id: &str) -> String {
    hex_id("w7.path.obs", &[path_id, w5_sync_id, state_id])
}

fn hex_id(kind: &str, parts: &[&str]) -> String {
    let mut h = Sha256::new();
    h.update(kind.as_bytes());
    for p in parts {
        h.update([0u8]);
        h.update(p.as_bytes());
    }
    format!("{:x}", h.finalize())
}

fn map_status(s: SyncStatus) -> PathJoinStatus {
    match s {
        SyncStatus::Synchronized => PathJoinStatus::Synchronized,
        SyncStatus::AtEvent => PathJoinStatus::AtEvent,
        SyncStatus::SynchronizedWithTimestampGap => PathJoinStatus::SynchronizedWithTimestampGap,
        SyncStatus::BeforeFirstEvent => PathJoinStatus::BeforeFirstEvent,
        SyncStatus::AfterLastEvent => PathJoinStatus::AfterLastEvent,
        SyncStatus::MissingTimestamp | SyncStatus::AmbiguousTimestamp => {
            PathJoinStatus::Unsynchronizable
        }
        SyncStatus::IdentityUnmatched | SyncStatus::IdentityAmbiguous => PathJoinStatus::Unjoinable,
        SyncStatus::SourceDataInvalid => PathJoinStatus::Rejected,
    }
}

/// Attach W6 state using W5's already-chosen prior event. Never uses next_event for assignment.
pub fn join_observation(
    obs: &SynchronizedMarketObservation,
    w6: Option<&W6Index>,
    path_id: &str,
    w5_ver: &str,
    w6_ver: &str,
) -> Result<PathObservation, W7Error> {
    if obs.game_id.is_empty() {
        return Err(W7Error::unjoinable(
            "MISSING_GAME_ID",
            "W5 row has empty GameId",
        ));
    }
    let mut join_status = map_status(obs.synchronization_status);
    let mut state: Option<&StoredState> = None;
    let mut prev: Option<&StoredState> = None;
    let mut next: Option<&StoredState> = None;
    let mut transition: Option<&StoredTransition> = None;

    if obs.synchronization_status.is_success() {
        let Some(idx) = w6 else {
            join_status = PathJoinStatus::NoGameState;
            return Ok(base_row(obs, path_id, join_status, w5_ver, w6_ver));
        };
        if idx.is_empty() || idx.game_id != obs.game_id {
            join_status = if idx.is_empty() {
                PathJoinStatus::NoGameState
            } else {
                PathJoinStatus::Unjoinable
            };
            return Ok(base_row(obs, path_id, join_status, w5_ver, w6_ver));
        }
        let Some(eid) = obs.prior_event_id.as_deref() else {
            join_status = PathJoinStatus::ValidationFailure;
            return Ok(base_row(obs, path_id, join_status, w5_ver, w6_ver));
        };
        match idx.by_event_id.get(eid) {
            Some(s) => {
                if let (Some(st), Some(mt)) = (s.canonical_timestamp, obs.market_timestamp_utc) {
                    if st > mt {
                        return Err(W7Error::validation(
                            "FUTURE_STATE",
                            format!("state {st} > market {mt}"),
                        ));
                    }
                }
                state = Some(s);
                transition = idx.by_resulting.get(&s.state_id);
                if let Some(tr) = transition {
                    prev = idx.by_state_id.get(&tr.previous_state_id);
                } else {
                    prev = idx.by_seq.get(&s.state_seq.saturating_sub(1));
                }
                next = idx.next_after(s.state_seq);
            }
            None => {
                join_status = PathJoinStatus::NoGameState;
            }
        }
    }

    let mut row = base_row(obs, path_id, join_status, w5_ver, w6_ver);
    if let Some(s) = state {
        if !join_status.has_applicable_state() {
            // AFTER_LAST may carry a diagnostic prior_event; it is not applicable.
        } else {
            fill_state(&mut row, s, prev, next, transition);
        }
    }
    if obs.observation_type != momento_research_sync::ObservationType::Trade {
        row.observation_kind = obs.observation_type.as_str().to_string();
    }
    row.path_observation_id = path_observation_id(
        path_id,
        &obs.synchronization_id,
        row.state_id.as_deref().unwrap_or(""),
    );
    Ok(row)
}

fn fill_state(
    row: &mut PathObservation,
    s: &StoredState,
    prev: Option<&StoredState>,
    next: Option<&StoredState>,
    tr: Option<&StoredTransition>,
) {
    row.matched_state_timestamp_utc = s.canonical_timestamp;
    row.state_id = Some(s.state_id.clone());
    row.state_seq = Some(s.state_seq);
    row.previous_state_id = prev.map(|p| p.state_id.clone());
    row.previous_state_seq = prev.map(|p| p.state_seq);
    row.transition_id = tr.map(|t| t.transition_id.clone());
    row.transition_event_type = tr.map(|t| t.event_type.clone()).or(s.event_type.clone());
    row.next_state_id = next.map(|n| n.state_id.clone());
    row.next_state_seq = next.map(|n| n.state_seq);
    row.inning = Some(s.inning);
    row.half = Some(s.half.clone());
    row.outs = Some(s.outs);
    row.score_home = Some(s.score_home);
    row.score_away = Some(s.score_away);
    row.run_differential = Some(s.run_differential);
    row.bases_bitmask = Some(s.bases_bitmask);
    row.batter_id = s.batter_id.clone();
    row.pitcher_id = s.pitcher_id.clone();
    row.balls = s.balls;
    row.strikes = s.strikes;
    row.game_status = Some(s.game_status.clone());
    if let (Some(st), Some(mt)) = (s.canonical_timestamp, row.market_timestamp_utc) {
        row.time_since_state_transition_ms = Some((mt - st).num_milliseconds());
    }
}

fn base_row(
    obs: &SynchronizedMarketObservation,
    path_id: &str,
    join_status: PathJoinStatus,
    w5_ver: &str,
    w6_ver: &str,
) -> PathObservation {
    PathObservation {
        path_observation_id: String::new(),
        path_id: path_id.to_string(),
        game_id: obs.game_id.clone(),
        game_pk: obs.game_pk.clone(),
        market_id: obs.market_id.clone(),
        ticker: obs.ticker.clone(),
        contract_id: obs.contract_id.clone(),
        contract_side: obs.contract_side.clone(),
        observation_id: obs.observation_id.clone(),
        w5_synchronization_id: obs.synchronization_id.clone(),
        observation_kind: OBSERVATION_KIND_TRADE.to_string(),
        market_timestamp_utc: obs.market_timestamp_utc,
        matched_state_timestamp_utc: None,
        event_lag_ms: obs.event_to_market_lag_ms,
        synchronization_status: obs.synchronization_status.as_str().to_string(),
        synchronization_quality: obs.synchronization_quality.as_str().to_string(),
        join_status,
        timestamp_relation: obs.timestamp_relation.as_str().to_string(),
        trade_price_cents: obs.last_trade_cents,
        trade_size_hundredths: None,
        source_observation_id: obs.source_id.clone(),
        source_lineage: obs.source_lineage.clone(),
        state_id: None,
        state_seq: None,
        previous_state_id: None,
        previous_state_seq: None,
        transition_id: None,
        transition_event_type: None,
        next_state_id: None,
        next_state_seq: None,
        inning: None,
        half: None,
        outs: None,
        score_home: None,
        score_away: None,
        run_differential: None,
        bases_bitmask: None,
        batter_id: None,
        pitcher_id: None,
        balls: None,
        strikes: None,
        game_status: None,
        chrono_index: 0,
        previous_trade_price_cents: None,
        price_change_cents: None,
        cumulative_trade_count: 0,
        time_since_previous_trade_ms: None,
        time_since_state_transition_ms: None,
        observed_high_cents_so_far: None,
        observed_low_cents_so_far: None,
        distance_from_high_cents: None,
        distance_from_low_cents: None,
        prior_price_changes: 0,
        causal_version: CAUSAL_VERSION.to_string(),
        join_version: JOIN_VERSION.to_string(),
        w5_dataset_version: w5_ver.to_string(),
        w6_dataset_version: w6_ver.to_string(),
        w7_version: ARTIFACT_VERSION.to_string(),
    }
}

/// Sort by market time then source observation id. Retrieval time is ignored.
pub fn sort_path_observations(rows: &mut [PathObservation]) {
    rows.sort_by(|a, b| {
        a.market_timestamp_utc
            .cmp(&b.market_timestamp_utc)
            .then_with(|| a.observation_id.cmp(&b.observation_id))
    });
}
