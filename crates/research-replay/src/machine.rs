//! FIRST01 replay machine.
//!
//! Sequencing mirrors live `MlbStrategy::observe` (strategies/mlb/src/strategy.rs):
//! 89 lock is checked before first-80; first_80 binds GameId+MarketId+side;
//! opponent prints cannot confirm; same-observation 81 confirm is allowed
//! (live clock); >83 pauses; >=89 locks; no liquidation.
//!
//! Qualifying price is the W7 TRADE print, observability TRADE_PRINT_NOT_YES_BID.
//! Ask is UNAVAILABLE; maker bid<ask is not applied (not invented).

use std::collections::{BTreeSet, HashSet};

use momento_research_path::PathObservation;
use momento_research_strategies::FIRST01_DEFAULT_ENTRY;

use crate::ids::opportunity_id;
use crate::types::{First01Opportunity, ReplayEvent, ReplayEventType, ReplayOutcome, ReplayPhase};
use crate::versions::{ENGINE_VERSION, OBSERVABILITY};

#[derive(Clone, Debug)]
struct Bound {
    market_id: String,
    side: String,
}

#[derive(Clone, Debug)]
struct GameMachine {
    phase: ReplayPhase,
    paused: bool,
    bound: Option<Bound>,
    confirmed: bool,
    intent_proposed: bool,
    opportunity: Option<First01Opportunity>,
    last_ts: Option<chrono::DateTime<chrono::Utc>>,
    seen: HashSet<String>,
}

impl GameMachine {
    fn new() -> Self {
        Self {
            phase: ReplayPhase::Watching,
            paused: false,
            bound: None,
            confirmed: false,
            intent_proposed: false,
            opportunity: None,
            last_ts: None,
            seen: HashSet::new(),
        }
    }

    fn display_phase(&self) -> ReplayPhase {
        if self.phase == ReplayPhase::EntryEligible && self.paused {
            ReplayPhase::PricePaused
        } else {
            self.phase
        }
    }
}

pub fn replay_path(observations: &[PathObservation], w7_ver: &str) -> ReplayOutcome {
    let mut rows: Vec<&PathObservation> = observations.iter().collect();
    rows.sort_by(|a, b| {
        a.market_timestamp_utc
            .cmp(&b.market_timestamp_utc)
            .then_with(|| a.observation_id.cmp(&b.observation_id))
    });
    let mut machines: std::collections::BTreeMap<String, GameMachine> =
        std::collections::BTreeMap::new();
    let mut out = ReplayOutcome::default();
    let mut sides: BTreeSet<(String, String)> = BTreeSet::new();
    for obs in rows {
        out.observations += 1;
        sides.insert((obs.market_id.clone(), obs.contract_side.clone()));
        if obs.trade_price_cents == Some(80) {
            out.prints_80 += 1;
        }
        let game = machines
            .entry(obs.game_id.clone())
            .or_insert_with(GameMachine::new);
        apply_observation(game, obs, w7_ver, &mut out);
    }
    out.sides = sides.len();
    for m in machines.values() {
        if let Some(op) = &m.opportunity {
            out.opportunities.push(op.clone());
        }
    }
    out.opportunities
        .sort_by(|a, b| a.opportunity_id.cmp(&b.opportunity_id));
    out
}

fn apply_observation(
    game: &mut GameMachine,
    obs: &PathObservation,
    w7_ver: &str,
    out: &mut ReplayOutcome,
) {
    if !game.seen.insert(obs.observation_id.clone()) {
        return;
    }
    if obs.market_timestamp_utc.is_none() {
        out.skipped += 1;
        emit(
            game,
            obs,
            w7_ver,
            ReplayEventType::SkippedMissingTimestamp,
            "MISSING_TIMESTAMP",
            out,
        );
        return;
    }
    if obs.trade_price_cents.is_none() {
        out.skipped += 1;
        emit(
            game,
            obs,
            w7_ver,
            ReplayEventType::SkippedMissingPrice,
            "MISSING_PRICE",
            out,
        );
        return;
    }
    let px = obs.trade_price_cents.unwrap();
    if let (Some(prev), Some(t)) = (game.last_ts, obs.market_timestamp_utc) {
        if t < prev && reaches_lock(px) {
            out.ambiguous += 1;
            emit(
                game,
                obs,
                w7_ver,
                ReplayEventType::AmbiguousReplayOrder,
                "BACKWARD_TIMESTAMP_WITH_LOCK",
                out,
            );
        }
    }
    game.last_ts = obs.market_timestamp_utc.or(game.last_ts);

    if game.phase == ReplayPhase::GameLocked {
        return;
    }

    if reaches_lock(px) {
        let relevant = match &game.bound {
            None => true,
            Some(b) => b.market_id == obs.market_id && b.side == obs.contract_side,
        };
        if relevant {
            let before = game.display_phase();
            game.phase = ReplayPhase::GameLocked;
            game.paused = false;
            out.game_locks += 1;
            push_event(
                obs,
                w7_ver,
                before,
                ReplayPhase::GameLocked,
                ReplayEventType::GameLocked,
                "FIRST01_LOCK_THRESHOLD",
                out,
            );
            if let Some(op) = game.opportunity.as_mut() {
                op.game_lock_timestamp_utc = obs.market_timestamp_utc;
                op.game_lock_observation_id = Some(obs.observation_id.clone());
                op.game_lock_price_cents = Some(px);
                op.lock_sync_class = Some(obs.join_status.as_str().to_string());
                op.replay_terminal_state = ReplayPhase::GameLocked.as_str().to_string();
            }
            return;
        }
    }

    if game.bound.is_none() {
        if reaches_first(px) {
            record_first80(game, obs, w7_ver, out);
        } else {
            game.phase = ReplayPhase::Watching;
            return;
        }
    } else if let Some(b) = &game.bound {
        if b.market_id != obs.market_id || b.side != obs.contract_side {
            return;
        }
    }

    if !game.confirmed {
        game.phase = ReplayPhase::WaitingFor81Confirmation;
        if bound_matches(game, obs) && reaches_confirm(px) {
            game.confirmed = true;
            out.confirm81 += 1;
            if let Some(op) = game.opportunity.as_mut() {
                op.confirmation_timestamp_utc = obs.market_timestamp_utc;
                op.confirmation_observation_id = Some(obs.observation_id.clone());
                op.confirmation_price_cents = Some(px);
                op.confirmation_state_id = obs.state_id.clone();
                op.confirmation_state_seq = obs.state_seq;
                op.confirmation_sync_quality = Some(obs.synchronization_quality.clone());
                op.confirmation_sync_class = Some(obs.join_status.as_str().to_string());
                op.replay_terminal_state =
                    ReplayPhase::WaitingFor81Confirmation.as_str().to_string();
            }
            let before = ReplayPhase::WaitingFor81Confirmation;
            game.phase = ReplayPhase::EntryEligible;
            push_event(
                obs,
                w7_ver,
                before,
                ReplayPhase::EntryEligible,
                ReplayEventType::Confirm81Observed,
                "FIRST01_SAME_SIDE_CONFIRM",
                out,
            );
        } else {
            return;
        }
    }

    maybe_pause_or_intent(game, obs, w7_ver, px, out);
}

fn record_first80(
    game: &mut GameMachine,
    obs: &PathObservation,
    w7_ver: &str,
    out: &mut ReplayOutcome,
) {
    let before = game.display_phase();
    game.bound = Some(Bound {
        market_id: obs.market_id.clone(),
        side: obs.contract_side.clone(),
    });
    game.phase = ReplayPhase::First80Triggered;
    out.first80 += 1;
    let oid = opportunity_id(
        w7_ver,
        &obs.game_id,
        &obs.market_id,
        &obs.contract_side,
        &obs.observation_id,
    );
    game.opportunity = Some(First01Opportunity {
        opportunity_id: oid,
        game_id: obs.game_id.clone(),
        market_id: obs.market_id.clone(),
        side: obs.contract_side.clone(),
        first80_timestamp_utc: obs.market_timestamp_utc,
        first80_observation_id: Some(obs.observation_id.clone()),
        first80_price_cents: obs.trade_price_cents,
        first80_state_id: obs.state_id.clone(),
        first80_state_seq: obs.state_seq,
        first80_sync_quality: Some(obs.synchronization_quality.clone()),
        confirmation_timestamp_utc: None,
        confirmation_observation_id: None,
        confirmation_price_cents: None,
        confirmation_state_id: None,
        confirmation_state_seq: None,
        confirmation_sync_quality: None,
        entry_eligible_timestamp_utc: None,
        entry_observation_id: None,
        entry_price_cents: None,
        intent_proposed: false,
        game_lock_timestamp_utc: None,
        game_lock_observation_id: None,
        game_lock_price_cents: None,
        replay_terminal_state: ReplayPhase::First80Triggered.as_str().to_string(),
        first80_sync_class: Some(obs.join_status.as_str().to_string()),
        confirmation_sync_class: None,
        entry_sync_class: None,
        lock_sync_class: None,
        observability: OBSERVABILITY.to_string(),
        strategy: momento_research_strategies::FIRST01_NAME.to_string(),
        strategy_version: momento_research_strategies::FIRST01_VERSION,
        w7_dataset_version: w7_ver.to_string(),
        w8_engine_version: ENGINE_VERSION.to_string(),
    });
    push_event(
        obs,
        w7_ver,
        before,
        ReplayPhase::First80Triggered,
        ReplayEventType::First80Observed,
        "FIRST01_FIRST_THRESHOLD",
        out,
    );
    game.phase = ReplayPhase::WaitingFor81Confirmation;
    if let Some(op) = game.opportunity.as_mut() {
        op.replay_terminal_state = ReplayPhase::WaitingFor81Confirmation.as_str().to_string();
    }
}

fn maybe_pause_or_intent(
    game: &mut GameMachine,
    obs: &PathObservation,
    w7_ver: &str,
    px: i32,
    out: &mut ReplayOutcome,
) {
    if above_max(px) {
        let before = game.display_phase();
        game.paused = true;
        game.phase = ReplayPhase::EntryEligible;
        out.price_pauses += 1;
        if let Some(op) = game.opportunity.as_mut() {
            op.replay_terminal_state = ReplayPhase::PricePaused.as_str().to_string();
        }
        push_event(
            obs,
            w7_ver,
            before,
            ReplayPhase::PricePaused,
            ReplayEventType::PricePaused,
            "FIRST01_ABOVE_MAX_ENTRY",
            out,
        );
        return;
    }
    let was_paused = game.paused;
    game.paused = false;
    game.phase = ReplayPhase::EntryEligible;
    if !in_band(px) {
        return;
    }
    if game
        .opportunity
        .as_ref()
        .is_some_and(|o| o.entry_observation_id.is_none())
    {
        out.entry_eligible += 1;
        if let Some(op) = game.opportunity.as_mut() {
            op.entry_eligible_timestamp_utc = obs.market_timestamp_utc;
            op.entry_observation_id = Some(obs.observation_id.clone());
            op.entry_price_cents = Some(px);
            op.entry_sync_class = Some(obs.join_status.as_str().to_string());
            op.replay_terminal_state = ReplayPhase::EntryEligible.as_str().to_string();
        }
        push_event(
            obs,
            w7_ver,
            if was_paused {
                ReplayPhase::PricePaused
            } else {
                ReplayPhase::EntryEligible
            },
            ReplayPhase::EntryEligible,
            ReplayEventType::EntryEligible,
            "FIRST01_ENTRY_BAND",
            out,
        );
    } else if was_paused {
        if let Some(op) = game.opportunity.as_mut() {
            op.replay_terminal_state = ReplayPhase::EntryEligible.as_str().to_string();
        }
    }
    if !game.intent_proposed {
        game.intent_proposed = true;
        out.intents_proposed += 1;
        if let Some(op) = game.opportunity.as_mut() {
            op.intent_proposed = true;
        }
        push_event(
            obs,
            w7_ver,
            ReplayPhase::EntryEligible,
            ReplayPhase::EntryEligible,
            ReplayEventType::EntryIntentProposed,
            "FIRST01_MAKER_INTENT_REPLAY_ARTIFACT",
            out,
        );
    }
}

fn emit(
    game: &GameMachine,
    obs: &PathObservation,
    w7_ver: &str,
    kind: ReplayEventType,
    reason: &str,
    out: &mut ReplayOutcome,
) {
    push_event(
        obs,
        w7_ver,
        game.display_phase(),
        game.display_phase(),
        kind,
        reason,
        out,
    );
}

fn push_event(
    obs: &PathObservation,
    w7_ver: &str,
    before: ReplayPhase,
    after: ReplayPhase,
    kind: ReplayEventType,
    reason: &str,
    out: &mut ReplayOutcome,
) {
    out.events.push(ReplayEvent::from_obs(
        obs, before, after, kind, reason, w7_ver,
    ));
}

fn bound_matches(game: &GameMachine, obs: &PathObservation) -> bool {
    game.bound
        .as_ref()
        .is_some_and(|b| b.market_id == obs.market_id && b.side == obs.contract_side)
}

fn first() -> i32 {
    i32::from(FIRST01_DEFAULT_ENTRY.first_threshold_cents)
}
fn confirm() -> i32 {
    i32::from(FIRST01_DEFAULT_ENTRY.confirmation_threshold_cents)
}
fn max_entry() -> i32 {
    i32::from(FIRST01_DEFAULT_ENTRY.maximum_entry_price_cents)
}
fn lock() -> i32 {
    i32::from(FIRST01_DEFAULT_ENTRY.lock_threshold_cents)
}

fn reaches_first(px: i32) -> bool {
    px >= first()
}
fn reaches_confirm(px: i32) -> bool {
    px >= confirm()
}
fn reaches_lock(px: i32) -> bool {
    px >= lock()
}
fn above_max(px: i32) -> bool {
    px > max_entry()
}
fn in_band(px: i32) -> bool {
    px >= first() && px <= max_entry()
}
