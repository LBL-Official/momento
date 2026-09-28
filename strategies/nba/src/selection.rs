//! One candidate per game: earliest signal minute, then ticker (UTF-8).

use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Candidate {
    pub ticker: String,
    pub signal_ts: i64,
}

pub fn select_candidate(candidates: &[Candidate]) -> Option<&Candidate> {
    candidates
        .iter()
        .min_by(|a, b| (a.signal_ts, &a.ticker).cmp(&(b.signal_ts, &b.ticker)))
}
