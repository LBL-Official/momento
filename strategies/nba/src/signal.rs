//! Contract-wise 78 up-cross, the 67 stop, the 68 prepare level, and the
//! 85 top-out ceiling. Mirrors `first78/eligibility.py` bar-for-bar.

use serde::{Deserialize, Serialize};

use crate::bars::MinuteBar;
use crate::{ENTRY_CENTS, PREPARE_CENTS, STOP_CENTS, TOP_OUT_CENTS};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EntrySignal {
    pub signal_ts: i64,
    pub close_cents: u16,
    pub bar: MinuteBar,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "outcome", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum CrossOutcome {
    Pending,
    /// The first quality close was already at or above 78.
    UnprovenFirst,
    Crossed(EntrySignal),
    /// A bar arrived at or before the previous bar's timestamp.
    ChronologyUnresolved,
}

/// Feeds bars in strictly increasing `end_ts`. Terminal once not `Pending`.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CrossTracker {
    had_quality: bool,
    seen_below: bool,
    last_ts: Option<i64>,
    quality_bars: u32,
    outcome: CrossOutcome,
}

impl Default for CrossTracker {
    fn default() -> Self {
        Self::new()
    }
}

impl CrossTracker {
    pub fn new() -> Self {
        Self {
            had_quality: false,
            seen_below: false,
            last_ts: None,
            quality_bars: 0,
            outcome: CrossOutcome::Pending,
        }
    }

    pub fn outcome(&self) -> CrossOutcome {
        self.outcome
    }

    pub fn last_ts(&self) -> Option<i64> {
        self.last_ts
    }

    pub fn quality_bars(&self) -> u32 {
        self.quality_bars
    }

    /// Returns the outcome after this bar.
    pub fn push(&mut self, bar: &MinuteBar) -> CrossOutcome {
        if self.outcome != CrossOutcome::Pending {
            return self.outcome;
        }
        if let Some(last) = self.last_ts
            && bar.end_ts <= last
        {
            self.outcome = CrossOutcome::ChronologyUnresolved;
            return self.outcome;
        }
        self.last_ts = Some(bar.end_ts);
        if !bar.is_quality(self.had_quality) {
            return self.outcome;
        }
        let first_quality = !self.had_quality;
        self.had_quality = true;
        self.quality_bars += 1;
        let Some(bid) = bar.yes_bid_close else {
            return self.outcome;
        };
        if first_quality && bid >= ENTRY_CENTS {
            self.outcome = CrossOutcome::UnprovenFirst;
        } else if bid < ENTRY_CENTS {
            self.seen_below = true;
        } else if self.seen_below {
            self.outcome = CrossOutcome::Crossed(EntrySignal {
                signal_ts: bar.end_ts,
                close_cents: bid,
                bar: *bar,
            });
        }
        self.outcome
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "event", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum StopEvent {
    /// First later quality close at or below 68 and above 67. Local only.
    Prepare { ts: i64, close_cents: u16 },
    /// First later quality close at or below 67. The official trigger.
    Trigger { ts: i64, close_cents: u16 },
    /// A later quality close after the trigger. Drives the ladder proposal.
    PostTrigger { ts: i64, close_cents: u16 },
}

/// Post-entry path. Only quality bars strictly after the entry minute count.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StopTracker {
    entry_ts: i64,
    intrabar_ambiguity: bool,
    had_quality: bool,
    last_ts: i64,
    prepared: bool,
    triggered: Option<(i64, u16)>,
}

impl StopTracker {
    pub fn new(entry: &EntrySignal) -> Self {
        let ambiguous = entry.bar.yes_bid_low.is_some_and(|low| low <= STOP_CENTS);
        Self {
            entry_ts: entry.signal_ts,
            intrabar_ambiguity: ambiguous,
            had_quality: true,
            last_ts: entry.signal_ts,
            prepared: false,
            triggered: None,
        }
    }

    pub fn intrabar_ambiguity(&self) -> bool {
        self.intrabar_ambiguity
    }

    pub fn triggered(&self) -> Option<(i64, u16)> {
        self.triggered
    }

    pub fn prepared(&self) -> bool {
        self.prepared
    }

    pub fn push(&mut self, bar: &MinuteBar) -> Option<StopEvent> {
        if bar.end_ts <= self.last_ts || bar.end_ts <= self.entry_ts {
            return None;
        }
        self.last_ts = bar.end_ts;
        if !bar.is_quality(self.had_quality) {
            return None;
        }
        let bid = bar.yes_bid_close?;
        if self.triggered.is_some() {
            return Some(StopEvent::PostTrigger {
                ts: bar.end_ts,
                close_cents: bid,
            });
        }
        if bid <= STOP_CENTS {
            self.triggered = Some((bar.end_ts, bid));
            return Some(StopEvent::Trigger {
                ts: bar.end_ts,
                close_cents: bid,
            });
        }
        if bid <= PREPARE_CENTS && !self.prepared {
            self.prepared = true;
            return Some(StopEvent::Prepare {
                ts: bar.end_ts,
                close_cents: bid,
            });
        }
        None
    }
}

/// Entry ceiling at signal time: close or best ask at or above 85 skips.
pub fn top_out_at_signal(signal: &EntrySignal) -> bool {
    signal.close_cents >= TOP_OUT_CENTS
        || signal
            .bar
            .yes_ask_close
            .is_some_and(|ask| ask >= TOP_OUT_CENTS)
}

/// While an entry would rest: a YES bid close at or above 85 cancels it.
pub fn top_out_while_resting(bar: &MinuteBar) -> bool {
    bar.yes_bid_close.is_some_and(|bid| bid >= TOP_OUT_CENTS)
}
