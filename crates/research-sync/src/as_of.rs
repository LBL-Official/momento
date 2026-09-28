//! Deterministic AS-OF join: latest event with effective time <= T.
//!
//! Interval: prior_event_time <= t < next_event_time identifies the prior event.
//! Exact equality (`t == event_time`) is `AT_EVENT` (not silent before/after).
//! `next_event` is diagnostic and never used as applicable state.

use chrono::{DateTime, Utc};

use crate::types::{
    AsOfHit, GAP_THRESHOLD_MS, GameWindow, SyncQuality, SyncStatus, TimedEvent, TimestampRelation,
};

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum AsOfReject {
    NoPriorEvent { next: Option<Box<TimedEvent>> },
    OutsideWindow { last: Box<TimedEvent> },
}

/// Timed events MUST be sorted by (normalized_event_time, sequence).
pub fn assert_sorted(events: &[TimedEvent]) -> bool {
    events.windows(2).all(|w| {
        w[0].normalized_event_time < w[1].normalized_event_time
            || (w[0].normalized_event_time == w[1].normalized_event_time
                && w[0].sequence <= w[1].sequence)
    })
}

pub fn game_window(events: &[TimedEvent]) -> Option<GameWindow> {
    let first = events.first()?;
    let last = events.last()?;
    Some(GameWindow {
        start: first.normalized_event_time,
        end: last.normalized_event_time,
    })
}

/// Latest event with `effective_time <= t`, using canonical sequence as a
/// tie-break when timestamps are identical.
pub fn as_of(
    events: &[TimedEvent],
    t: DateTime<Utc>,
    window: Option<&GameWindow>,
) -> Result<AsOfHit, AsOfReject> {
    if events.is_empty() {
        return Err(AsOfReject::NoPriorEvent { next: None });
    }
    if let Some(w) = window {
        if t > w.end {
            return Err(AsOfReject::OutsideWindow {
                last: Box::new(events[events.len() - 1].clone()),
            });
        }
    }

    match last_at_or_before(events, t) {
        None => Err(AsOfReject::NoPriorEvent {
            next: events.first().cloned().map(Box::new),
        }),
        Some(idx) => Ok(hit_at(events, idx, t)),
    }
}

fn last_at_or_before(events: &[TimedEvent], t: DateTime<Utc>) -> Option<usize> {
    let mut lo = 0usize;
    let mut hi = events.len();
    while lo < hi {
        let mid = (lo + hi) / 2;
        if events[mid].normalized_event_time <= t {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    if lo == 0 { None } else { Some(lo - 1) }
}

fn hit_at(events: &[TimedEvent], idx: usize, t: DateTime<Utc>) -> AsOfHit {
    let matched = events[idx].clone();
    let previous = if idx > 0 {
        Some(events[idx - 1].clone())
    } else {
        None
    };
    let next = events.get(idx + 1).cloned();
    let lag_ms = (t - matched.normalized_event_time).num_milliseconds();
    let lead_ms = next
        .as_ref()
        .map(|n| (n.normalized_event_time - t).num_milliseconds());
    let relation = if lag_ms == 0 {
        TimestampRelation::AtEvent
    } else {
        TimestampRelation::AfterEvent
    };
    AsOfHit {
        matched,
        previous,
        next,
        lag_ms,
        lead_ms,
        relation,
    }
}

pub fn classify_success(lag_ms: i64) -> (SyncStatus, SyncQuality, TimestampRelation) {
    if lag_ms == 0 {
        return (
            SyncStatus::AtEvent,
            SyncQuality::Exact,
            TimestampRelation::AtEvent,
        );
    }
    let quality = if lag_ms <= 1_000 {
        SyncQuality::Within1s
    } else if lag_ms <= 3_000 {
        SyncQuality::Within3s
    } else if lag_ms <= 5_000 {
        SyncQuality::Within5s
    } else {
        SyncQuality::WithinInning
    };
    let status = if lag_ms > GAP_THRESHOLD_MS {
        SyncStatus::SynchronizedWithTimestampGap
    } else {
        SyncStatus::Synchronized
    };
    (status, quality, TimestampRelation::AfterEvent)
}

/// Two-pointer AS-OF indexes. Observations after the last event are `None`
/// (caller must classify AFTER_LAST_EVENT; do not snap to the last event).
pub fn two_pointer_indexes(events: &[TimedEvent], times: &[DateTime<Utc>]) -> Vec<Option<usize>> {
    let end = events.last().map(|e| e.normalized_event_time);
    let mut i = 0usize;
    let mut out = Vec::with_capacity(times.len());
    for t in times {
        if let Some(end) = end {
            if *t > end {
                out.push(None);
                continue;
            }
        }
        while i + 1 < events.len() && events[i + 1].normalized_event_time <= *t {
            i += 1;
        }
        if !events.is_empty() && events[i].normalized_event_time <= *t {
            out.push(Some(i));
        } else {
            out.push(None);
        }
    }
    out
}
