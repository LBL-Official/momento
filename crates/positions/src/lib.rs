//! Position identity, fill-authoritative tracker, and reconciliation.

#![forbid(unsafe_code)]

mod error;
mod events;
mod identity;
mod tracker;

pub use error::TrackerError;
pub use events::{ApplyStatus, PositionEvent};
pub use identity::{GamePositionIndex, PositionIndexError};
pub use tracker::{InMemoryPositionTracker, PersistedOrder, PositionTracker, TrackerPersist};
