//! Multi-sport event adapter trait. Only MLB is implemented in W2.

use crate::EventError;
use crate::event::CanonicalMlbEvent;
use crate::event_time::EventTimeState;
use crate::state::{MlbGameState, MlbPbpTransition};

/// Sport-agnostic remaining-opportunity view. MLB fills this with outs.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RemainingOpportunities {
    pub sport: &'static str,
    pub unit: &'static str,
    pub elapsed: u16,
    pub regulation_budget: u16,
    /// Present only when knowable at t without lookahead (e.g. terminal state).
    pub remaining_known: Option<u16>,
    pub extra_period: bool,
    pub definition_version: &'static str,
}

pub trait EventStateAdapter {
    type Event;
    type State;
    type EventTime;

    fn sport_code(&self) -> &'static str;
    fn apply(
        &self,
        before: &Self::State,
        event: &Self::Event,
    ) -> Result<MlbPbpTransition, EventError>;
    fn remaining_opportunities(&self, state: &Self::State) -> RemainingOpportunities;
    fn event_time(&self, state: &Self::State, event: &Self::Event) -> Self::EventTime;
}

#[derive(Clone, Copy, Debug, Default)]
pub struct MlbEventAdapter;

impl EventStateAdapter for MlbEventAdapter {
    type Event = CanonicalMlbEvent;
    type State = MlbGameState;
    type EventTime = EventTimeState;

    fn sport_code(&self) -> &'static str {
        "MLB"
    }

    fn apply(
        &self,
        before: &Self::State,
        event: &Self::Event,
    ) -> Result<MlbPbpTransition, EventError> {
        crate::state::apply(before, event)
    }

    fn remaining_opportunities(&self, state: &Self::State) -> RemainingOpportunities {
        crate::event_time::remaining_opportunities(state)
    }

    fn event_time(&self, state: &Self::State, event: &Self::Event) -> Self::EventTime {
        crate::event_time::from_state(state, event, None, None)
    }
}

/// Stubs for later sports. Not implemented in W2.
#[derive(Clone, Copy, Debug)]
pub struct NbaEventAdapter;
#[derive(Clone, Copy, Debug)]
pub struct NcaabEventAdapter;
#[derive(Clone, Copy, Debug)]
pub struct NhlEventAdapter;
