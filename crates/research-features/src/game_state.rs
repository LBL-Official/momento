//! Layer 1 — W6 baseball state at or before entry. Never a future state.

use chrono::{DateTime, Utc};
use momento_research_path::occupancy_label;
use momento_research_state::StoredState;

use crate::availability::FeatureAvailability;
use crate::identity::{TeamIdentity, bound_team_lead};
use crate::types::{
    BaseClass, BaseballRegime, BaseballStateFeatures, ScoreBucket, baseball_regime,
};

pub fn state_at_or_before(states: &[StoredState], entry: DateTime<Utc>) -> Option<&StoredState> {
    states
        .iter()
        .filter(|s| s.canonical_timestamp.is_some_and(|t| t <= entry))
        .max_by_key(|s| (s.canonical_timestamp, s.state_seq))
}

pub fn baseball_features(
    states: &[StoredState],
    entry: DateTime<Utc>,
    side: &str,
    identity: Option<&TeamIdentity>,
) -> BaseballStateFeatures {
    let Some(st) = state_at_or_before(states, entry) else {
        return BaseballStateFeatures {
            availability: FeatureAvailability::InsufficientHistory,
            state_id: None,
            state_seq: None,
            state_timestamp: None,
            inning: None,
            half_inning: None,
            outs: None,
            score_home: None,
            score_away: None,
            home_run_differential: None,
            bound_team_score: None,
            opponent_score: None,
            bound_team_lead: None,
            score_diff: None,
            abs_score_diff: None,
            leading_flag: None,
            trailing_flag: None,
            tied_flag: None,
            score_bucket: ScoreBucket::Unavailable,
            bases_bitmask: None,
            base_state: None,
            base_class: BaseClass::Unavailable,
            base_out_state: None,
            balls: None,
            strikes: None,
            batter_id: None,
            pitcher_id: None,
            batter_available: FeatureAvailability::UnavailableSource,
            pitcher_available: FeatureAvailability::UnavailableSource,
            regime: BaseballRegime::NoState,
            home_abbr: identity.map(|i| i.home.clone()),
            away_abbr: identity.map(|i| i.away.clone()),
            identity_source: identity.map(|i| i.source.clone()),
        };
    };

    let lead =
        identity.and_then(|id| bound_team_lead(side, &id.home, &id.away, st.run_differential));
    let (bound_score, opp_score) = match (identity, lead) {
        (Some(id), Some(l)) => {
            let s = crate::identity::normalize_abbr(side);
            if s == id.home {
                (Some(st.score_home), Some(st.score_away))
            } else if s == id.away {
                (Some(st.score_away), Some(st.score_home))
            } else {
                let _ = l;
                (None, None)
            }
        }
        _ => (None, None),
    };

    let mask = Some(st.bases_bitmask);
    let base_label = occupancy_label(st.bases_bitmask);
    BaseballStateFeatures {
        availability: FeatureAvailability::Available,
        state_id: Some(st.state_id.clone()),
        state_seq: Some(st.state_seq),
        state_timestamp: st.canonical_timestamp,
        inning: Some(st.inning),
        half_inning: Some(st.half.clone()),
        outs: Some(st.outs),
        score_home: Some(st.score_home),
        score_away: Some(st.score_away),
        home_run_differential: Some(st.run_differential),
        bound_team_score: bound_score,
        opponent_score: opp_score,
        bound_team_lead: lead,
        score_diff: lead,
        abs_score_diff: lead.map(|v| v.abs()),
        leading_flag: lead.map(|v| v > 0),
        trailing_flag: lead.map(|v| v < 0),
        tied_flag: lead.map(|v| v == 0),
        score_bucket: ScoreBucket::from_abs_lead(lead.map(|v| v.abs())),
        bases_bitmask: mask,
        base_state: Some(base_label.clone()),
        base_class: BaseClass::from_mask(mask),
        base_out_state: Some(format!("{base_label}|{}", st.outs)),
        balls: st.balls,
        strikes: st.strikes,
        batter_id: st.batter_id.clone(),
        pitcher_id: st.pitcher_id.clone(),
        batter_available: if st.batter_id.is_some() {
            FeatureAvailability::Available
        } else {
            FeatureAvailability::UnavailableSource
        },
        pitcher_available: if st.pitcher_id.is_some() {
            FeatureAvailability::Available
        } else {
            FeatureAvailability::UnavailableSource
        },
        regime: baseball_regime(Some(st.inning), lead),
        home_abbr: identity.map(|i| i.home.clone()),
        away_abbr: identity.map(|i| i.away.clone()),
        identity_source: identity.map(|i| i.source.clone()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    fn st(seq: u32, ts: DateTime<Utc>, inn: u8, rd: i32) -> StoredState {
        StoredState {
            state_id: format!("s{seq}"),
            game_id: "g".into(),
            game_pk: "1".into(),
            state_seq: seq,
            event_id: None,
            event_sequence: seq,
            canonical_timestamp: Some(ts),
            inning: inn,
            half: "TOP".into(),
            outs: 1,
            score_home: 3,
            score_away: 1,
            run_differential: rd,
            bases_bitmask: 2,
            batter_id: None,
            pitcher_id: None,
            balls: Some(0),
            strikes: Some(0),
            game_status: "IN_PROGRESS".into(),
            extra_inning: false,
            event_type: Some("SINGLE".into()),
        }
    }

    #[test]
    fn refuses_future_state() {
        let t0 = Utc.with_ymd_and_hms(2025, 6, 1, 18, 0, 0).unwrap();
        let t1 = Utc.with_ymd_and_hms(2025, 6, 1, 19, 0, 0).unwrap();
        let states = vec![st(1, t0, 6, 2), st(2, t1, 7, 3)];
        let chosen = state_at_or_before(&states, t0).unwrap();
        assert_eq!(chosen.state_seq, 1);
        assert!(chosen.canonical_timestamp.unwrap() <= t0);
    }
}
