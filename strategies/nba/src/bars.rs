//! One-minute TRADABLE_YES_BID bars. Integer cents. A close is not a fill.

use serde::{Deserialize, Serialize};

use crate::MAX_SPREAD_CENTS;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MinuteBar {
    /// Kalshi `end_period_ts` (unix seconds). The close is known at this time.
    pub end_ts: i64,
    pub yes_bid_close: Option<u16>,
    pub yes_ask_close: Option<u16>,
    pub yes_bid_low: Option<u16>,
    /// Volume in hundredths of a contract (`volume_fp` × 100). Only `> 0`
    /// matters. `None` when the source omitted it.
    pub volume: Option<u64>,
}

impl MinuteBar {
    /// Same filter as `ROLLER/roller/choosin_texas/first78/eligibility.py::quality`.
    /// `had_quality` is true once any earlier bar of this contract passed.
    pub fn is_quality(&self, had_quality: bool) -> bool {
        let (Some(bid), Some(ask)) = (self.yes_bid_close, self.yes_ask_close) else {
            return false;
        };
        if bid > ask || ask - bid > MAX_SPREAD_CENTS {
            return false;
        }
        match self.volume {
            Some(v) if v > 0 => true,
            _ => had_quality,
        }
    }

    pub fn spread(&self) -> Option<u16> {
        match (self.yes_bid_close, self.yes_ask_close) {
            (Some(b), Some(a)) if a >= b => Some(a - b),
            _ => None,
        }
    }
}
