//! Event-time foundation. Does **not** invent Event Theta values.

use serde::{Deserialize, Serialize};

use crate::adapter::RemainingOpportunities;
use crate::event::{CanonicalMlbEvent, GameStatus, HalfInning};
use crate::field::DataField;
use crate::state::MlbGameState;
use crate::versions::{EVENT_TIME_DEFINITION_VERSION, REMAINING_OUTS_DEFINITION_VERSION};

pub const REGULATION_OUTS: u16 = 54;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct OpportunityFraction {
    pub consumed_outs: u16,
    pub regulation_outs: u16,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventTimeState {
    pub definition_version: String,
    pub current_inning: u8,
    pub current_half: HalfInning,
    pub current_outs: u8,
    pub outs_elapsed: u16,
    pub regulation_outs: u16,
    pub regulation_outs_remaining: u16,
    /// Only Some when knowable at t (terminal). Extra innings / in-progress: Unavailable.
    pub actual_outs_remaining: DataField<u16>,
    pub extra_inning_state: bool,
    pub plate_appearance_position: DataField<u32>,
    pub event_sequence: u32,
    pub time_since_game_start_ms: DataField<i64>,
    pub time_since_previous_event_ms: DataField<i64>,
    pub event_opportunity_count: u16,
    pub event_opportunity_fraction: OpportunityFraction,
    pub event_opportunity_delta: i16,
    pub event_theta: EventThetaFoundation,
}

/// Placeholder for later empirical θ. W2 stores ADR-0010 **inputs** only.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventThetaFoundation {
    /// ESTIMATOR_DEFERRED_W9 — no closed-form theta in W2 (ADR-0010).
    pub status: String,
    pub inputs: EventThetaInputs,
    pub notes: String,
}

/// ADR-0010 input pack. `theta_value` stays UNAVAILABLE until Waterfall 9.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventThetaInputs {
    pub remaining_opportunities_elapsed: u16,
    pub remaining_opportunities_regulation_budget: u16,
    pub remaining_known: Option<u16>,
    pub extra_period: bool,
    pub definition_version: String,
    pub information_rate_proxy: DataField<i16>,
    pub state_significance_proxy: DataField<String>,
    pub theta_value: DataField<String>,
    pub method: String,
    pub version: String,
}

pub const EVENT_THETA_INPUTS_VERSION: &str = "W2.EVENT_THETA_INPUTS.1.0.0";

pub fn remaining_opportunities(state: &MlbGameState) -> RemainingOpportunities {
    let elapsed = outs_elapsed(state);
    let remaining_known = if state.game_status == GameStatus::Final {
        Some(0)
    } else {
        None
    };
    RemainingOpportunities {
        sport: "MLB",
        unit: "outs",
        elapsed,
        regulation_budget: REGULATION_OUTS,
        remaining_known,
        extra_period: state.extra_inning,
        definition_version: REMAINING_OUTS_DEFINITION_VERSION,
    }
}

pub fn outs_elapsed(state: &MlbGameState) -> u16 {
    let completed_full_innings = u16::from(state.inning.saturating_sub(1));
    let halves_done = match state.half {
        HalfInning::Top => 0,
        HalfInning::Bottom => 1,
    };
    completed_full_innings * 6 + halves_done * 3 + u16::from(state.outs)
}

pub fn from_state(
    state: &MlbGameState,
    event: &CanonicalMlbEvent,
    game_start_ms: Option<i64>,
    prev_event_ms: Option<i64>,
) -> EventTimeState {
    let elapsed = outs_elapsed(state);
    let regulation_remaining = REGULATION_OUTS.saturating_sub(elapsed.min(REGULATION_OUTS));
    let src_ms = event
        .source_timestamp
        .as_value()
        .map(|t| t.timestamp_millis());
    let since_start = match (src_ms, game_start_ms) {
        (Some(now), Some(start)) if now >= start => {
            DataField::derived(now - start, EVENT_TIME_DEFINITION_VERSION)
        }
        _ => DataField::unavailable("missing source timestamps"),
    };
    let since_prev = match (src_ms, prev_event_ms) {
        (Some(now), Some(prev)) if now >= prev => {
            DataField::derived(now - prev, EVENT_TIME_DEFINITION_VERSION)
        }
        _ => DataField::unavailable("missing previous source timestamp"),
    };
    let actual_remaining = if state.game_status == GameStatus::Final {
        DataField::derived(0, REMAINING_OUTS_DEFINITION_VERSION)
    } else {
        DataField::unavailable(
            "actual remaining outs requires future game length; not knowable at t",
        )
    };
    let delta = if state.state_seq <= 1 {
        i16::try_from(elapsed).unwrap_or(0)
    } else {
        0
    };

    let rem = remaining_opportunities(state);
    EventTimeState {
        definition_version: EVENT_TIME_DEFINITION_VERSION.to_string(),
        current_inning: state.inning,
        current_half: state.half,
        current_outs: state.outs,
        outs_elapsed: elapsed,
        regulation_outs: REGULATION_OUTS,
        regulation_outs_remaining: regulation_remaining,
        actual_outs_remaining: actual_remaining,
        extra_inning_state: state.extra_inning,
        plate_appearance_position: DataField::unavailable(
            "PA index not forced when source omits it",
        ),
        event_sequence: event.sequence,
        time_since_game_start_ms: since_start,
        time_since_previous_event_ms: since_prev,
        event_opportunity_count: regulation_remaining,
        event_opportunity_fraction: OpportunityFraction {
            consumed_outs: elapsed,
            regulation_outs: REGULATION_OUTS,
        },
        event_opportunity_delta: delta,
        event_theta: EventThetaFoundation {
            status: "ESTIMATOR_DEFERRED_W9".into(),
            inputs: EventThetaInputs {
                remaining_opportunities_elapsed: rem.elapsed,
                remaining_opportunities_regulation_budget: rem.regulation_budget,
                remaining_known: rem.remaining_known,
                extra_period: rem.extra_period,
                definition_version: rem.definition_version.to_string(),
                information_rate_proxy: DataField::derived(delta, EVENT_THETA_INPUTS_VERSION),
                state_significance_proxy: DataField::unavailable(
                    "state significance / WE / leverage is W9 MODELED, not OBSERVED",
                ),
                theta_value: DataField::unavailable(
                    "Event Theta estimator deferred to Waterfall 9 (ADR-0010); no invented formula",
                ),
                method: "NONE".into(),
                version: EVENT_THETA_INPUTS_VERSION.into(),
            },
            notes:
                "W2-F stores remaining-opportunity inputs from PBP. Theta value is not computed."
                    .into(),
        },
    }
}

/// How later empirical Event Theta should be estimated (documentation, not a formula).
pub const EVENT_THETA_LATER: &str = "\
EVENT_TIME = observed/derived baseball clock (inning, half, outs, outs_elapsed, regulation remaining). \
EVENT_THETA = later empirical/model quantity: rate of change of event uncertainty as opportunity decays. \
Estimation (future): fit from W5 StateTransition paths joined to W3 market path (W4+), \
conditioned on outs_remaining / extra_inning_state, never using future PBP at t. \
No closed-form theta is stored in W2.";
