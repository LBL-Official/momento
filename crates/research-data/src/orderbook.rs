//! Orderbook reconstruction with explicit gap metadata.

use momento_core::error::VenueError;
use momento_kalshi::{
    ApplyResult, BookDepth, LocalOrderBook, OrderbookDeltaMsg, OrderbookSnapshotMsg, SeqOutcome,
    SeqTracker,
};

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct GapState {
    pub sequence_gap: bool,
    pub resync_count: u32,
    pub first_missing_sequence: Option<u64>,
    pub last_valid_sequence: Option<u64>,
}

#[derive(Clone, Debug)]
pub struct OrderbookReconstructor {
    book: LocalOrderBook,
    gap: GapState,
    sid: Option<u64>,
}

impl OrderbookReconstructor {
    pub fn new() -> Self {
        Self {
            book: LocalOrderBook::new(),
            gap: GapState::default(),
            sid: None,
        }
    }

    pub fn gap_state(&self) -> &GapState {
        &self.gap
    }

    pub fn book(&self) -> &LocalOrderBook {
        &self.book
    }

    pub fn apply_snapshot(
        &mut self,
        sid: u64,
        seq: u64,
        msg: &OrderbookSnapshotMsg,
        resync: bool,
    ) -> Result<ApplyResult, VenueError> {
        self.sid = Some(sid);
        let result = if resync {
            let resync_count = self.gap.resync_count.saturating_add(1);
            self.gap = GapState {
                resync_count,
                ..GapState::default()
            };
            self.book.resync_snapshot(sid, seq, msg)?
        } else {
            self.book.apply_snapshot(sid, seq, msg)?
        };
        self.record_seq(sid, seq, &result);
        Ok(result)
    }

    pub fn apply_delta(
        &mut self,
        sid: u64,
        seq: u64,
        msg: &OrderbookDeltaMsg,
    ) -> Result<ApplyResult, VenueError> {
        let result = self.book.apply_delta(sid, seq, msg)?;
        self.record_seq(sid, seq, &result);
        if matches!(result, ApplyResult::Gap) {
            self.book.mark_stale(&msg.market_ticker);
        }
        Ok(result)
    }

    pub fn depth(&self, ticker: &str) -> Option<BookDepth> {
        if self.gap.sequence_gap {
            return None;
        }
        self.book.depth(ticker)
    }

    fn record_seq(&mut self, sid: u64, seq: u64, result: &ApplyResult) {
        if matches!(result, ApplyResult::Gap) {
            self.gap.sequence_gap = true;
            self.gap.first_missing_sequence.get_or_insert(seq);
            return;
        }
        if matches!(result, ApplyResult::Updated { .. } | ApplyResult::Ignored) {
            self.gap.last_valid_sequence = Some(seq);
            let mut tracker = SeqTracker::new();
            if let Some(prev) = self.gap.last_valid_sequence {
                if prev > 0 {
                    let _ = tracker.check(sid, prev);
                }
            }
            let _ = tracker.check(sid, seq);
        }
    }
}

impl Default for OrderbookReconstructor {
    fn default() -> Self {
        Self::new()
    }
}

/// Standalone sequence continuity check for tests.
pub fn detect_sequence_gap(last: Option<u64>, seq: u64) -> SeqOutcome {
    let mut tracker = SeqTracker::new();
    if let Some(prev) = last.filter(|p| *p > 0) {
        let _ = tracker.check(1, prev);
    }
    tracker.check(1, seq)
}
