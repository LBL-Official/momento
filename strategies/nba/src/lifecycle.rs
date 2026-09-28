//! One position lifecycle. Exposure completion, settlement, cash release,
//! and slot release are separate transitions. Neutral exposure releases
//! nothing by itself. Fills are deduplicated by fill id.

use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum LifecycleState {
    Discovered,
    Eligible,
    EntryIntent,
    EntryBlocked,
    EntryPending,
    EntryPartial,
    EntryFilled,
    EntryCancelled,
    Monitoring,
    HedgePrepared,
    HedgePending,
    HedgePartial,
    HedgeComplete,
    Settled,
    CashAvailable,
    SlotReleased,
    ReconciliationHold,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "event", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum LifecycleEvent {
    Eligible,
    IntentStaged,
    Blocked {
        codes: Vec<String>,
    },
    EntrySubmitted {
        requested: u32,
    },
    EntryFill {
        fill_id: String,
        qty: u32,
    },
    /// Venue confirmed the entry order is no longer working.
    EntryDone,
    PrepareLevel,
    StopTrigger,
    HedgeSubmitted,
    HedgeFill {
        fill_id: String,
        qty: u32,
    },
    MarketSettled,
    CashConfirmed,
    SlotRelease,
    Unknown {
        reason: String,
    },
    Resume,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Transition {
    pub at: i64,
    pub from: LifecycleState,
    pub to: LifecycleState,
    pub event: LifecycleEvent,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum TransitionError {
    Invalid { from: LifecycleState, event: String },
    OverFill { requested: u32, filled: u32 },
    OverHedge { original: u32, opponent: u32 },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Lifecycle {
    pub game_id: String,
    pub ticker: String,
    state: LifecycleState,
    held_from: Option<LifecycleState>,
    requested: u32,
    filled: u32,
    hedged: u32,
    fill_ids: BTreeSet<String>,
    history: Vec<Transition>,
}

impl Lifecycle {
    pub fn new(game_id: impl Into<String>, ticker: impl Into<String>) -> Self {
        Self {
            game_id: game_id.into(),
            ticker: ticker.into(),
            state: LifecycleState::Discovered,
            held_from: None,
            requested: 0,
            filled: 0,
            hedged: 0,
            fill_ids: BTreeSet::new(),
            history: Vec::new(),
        }
    }

    pub fn state(&self) -> LifecycleState {
        self.state
    }

    pub fn filled(&self) -> u32 {
        self.filled
    }

    pub fn hedged(&self) -> u32 {
        self.hedged
    }

    pub fn residual(&self) -> u32 {
        self.filled.saturating_sub(self.hedged)
    }

    pub fn history(&self) -> &[Transition] {
        &self.history
    }

    /// Holds a slot from entry intent until the explicit slot release.
    pub fn holds_slot(&self) -> bool {
        use LifecycleState::*;
        !matches!(
            self.state,
            Discovered | Eligible | EntryBlocked | EntryCancelled | SlotReleased
        )
    }

    pub fn apply(
        &mut self,
        at: i64,
        event: LifecycleEvent,
    ) -> Result<LifecycleState, TransitionError> {
        use LifecycleEvent as E;
        use LifecycleState as S;
        if let E::EntryFill { fill_id, .. } | E::HedgeFill { fill_id, .. } = &event
            && self.fill_ids.contains(fill_id)
        {
            return Ok(self.state);
        }
        let invalid = |from: S, ev: &E| TransitionError::Invalid {
            from,
            event: format!("{ev:?}"),
        };
        let next = match (&self.state, &event) {
            (_, E::Unknown { .. }) if self.state != S::ReconciliationHold => {
                self.held_from = Some(self.state);
                S::ReconciliationHold
            }
            (S::ReconciliationHold, E::Resume) => {
                self.held_from.take().unwrap_or(S::ReconciliationHold)
            }
            (S::ReconciliationHold, _) => return Err(invalid(self.state, &event)),
            (S::Discovered, E::Eligible) => S::Eligible,
            (S::Eligible, E::IntentStaged) => S::EntryIntent,
            (S::Eligible | S::EntryIntent, E::Blocked { .. }) => S::EntryBlocked,
            (S::EntryIntent, E::EntrySubmitted { requested }) => {
                self.requested = *requested;
                S::EntryPending
            }
            (S::EntryPending | S::EntryPartial, E::EntryFill { fill_id, qty }) => {
                let filled = self.filled.saturating_add(*qty);
                if filled > self.requested {
                    return Err(TransitionError::OverFill {
                        requested: self.requested,
                        filled,
                    });
                }
                self.fill_ids.insert(fill_id.clone());
                self.filled = filled;
                if filled == self.requested {
                    S::EntryFilled
                } else {
                    S::EntryPartial
                }
            }
            (S::EntryPending, E::EntryDone) if self.filled == 0 => S::EntryCancelled,
            (S::EntryPartial, E::EntryDone) => S::Monitoring,
            (S::EntryFilled, E::EntryDone) => S::Monitoring,
            (S::Monitoring, E::PrepareLevel) => S::HedgePrepared,
            (S::Monitoring | S::HedgePrepared, E::StopTrigger) => S::HedgePending,
            (S::HedgePending, E::HedgeSubmitted) => S::HedgePending,
            (S::HedgePending | S::HedgePartial, E::HedgeFill { fill_id, qty }) => {
                let hedged = self.hedged.saturating_add(*qty);
                if hedged > self.filled {
                    self.held_from = Some(self.state);
                    self.state = S::ReconciliationHold;
                    return Err(TransitionError::OverHedge {
                        original: self.filled,
                        opponent: hedged,
                    });
                }
                self.fill_ids.insert(fill_id.clone());
                self.hedged = hedged;
                if hedged == self.filled {
                    S::HedgeComplete
                } else {
                    S::HedgePartial
                }
            }
            (
                S::Monitoring
                | S::HedgePrepared
                | S::HedgePending
                | S::HedgePartial
                | S::HedgeComplete,
                E::MarketSettled,
            ) => S::Settled,
            (S::Settled, E::CashConfirmed) => S::CashAvailable,
            (S::CashAvailable | S::EntryCancelled | S::EntryBlocked, E::SlotRelease) => {
                S::SlotReleased
            }
            _ => return Err(invalid(self.state, &event)),
        };
        self.history.push(Transition {
            at,
            from: self.state,
            to: next,
            event,
        });
        self.state = next;
        Ok(next)
    }
}
