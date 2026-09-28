//! B1 invariants: causality, side orientation, L2 unavailable, determinism.

use chrono::{TimeZone, Utc};
use momento_research_features::a1_targets::{EXIT_HOLD_TO_SETTLEMENT, EXIT_LIVE_50PCT_STOP};
use momento_research_features::analysis::{a1_bucket_matrix, a1_exit_return_cents};
use momento_research_features::availability::FeatureAvailability;
use momento_research_features::dataset::{W8EntryInput, extract_snapshot};
use momento_research_features::game_state::state_at_or_before;
use momento_research_features::identity::{TeamIdentity, bound_team_lead, normalize_abbr};
use momento_research_features::ids::snapshot_id;
use momento_research_features::microstructure::current_microstructure;
use momento_research_features::outcomes::settlement_from_w6;
use momento_research_features::price_history::{path_stats, priced_at_or_before};
use momento_research_features::types::{
    A1EntryTarget, BaseballRegime, SettlementOutcome, StartSentiment, baseball_regime,
};
use momento_research_features::validation::{validate_batch, validate_snapshot};
use momento_research_features::versions::{DATASET_VERSION, EXECUTION_STATUS};
use momento_research_path::{PathJoinStatus, PathObservation};
use momento_research_state::StoredState;

fn ts(h: u32, m: u32, s: u32) -> chrono::DateTime<Utc> {
    Utc.with_ymd_and_hms(2025, 6, 1, h, m, s).unwrap()
}

fn trade(oid: &str, h: u32, m: u32, s: u32, px: i32) -> PathObservation {
    PathObservation {
        path_observation_id: format!("po-{oid}"),
        path_id: "path1".into(),
        game_id: "g1".into(),
        game_pk: "100".into(),
        market_id: "m1".into(),
        ticker: "KXMLBGAME-25JUN01TORNYY-TOR".into(),
        contract_id: "c1".into(),
        contract_side: "TOR".into(),
        observation_id: oid.into(),
        w5_synchronization_id: "s".into(),
        observation_kind: "TRADE".into(),
        market_timestamp_utc: Some(ts(h, m, s)),
        matched_state_timestamp_utc: Some(ts(h, m, s)),
        event_lag_ms: Some(0),
        synchronization_status: "SYNCHRONIZED".into(),
        synchronization_quality: "OK".into(),
        join_status: PathJoinStatus::Synchronized,
        timestamp_relation: "AT_OR_AFTER".into(),
        trade_price_cents: Some(px),
        trade_size_hundredths: None,
        source_observation_id: None,
        source_lineage: "W5".into(),
        state_id: Some("st1".into()),
        state_seq: Some(1),
        previous_state_id: None,
        previous_state_seq: None,
        transition_id: None,
        transition_event_type: None,
        next_state_id: None,
        next_state_seq: None,
        inning: Some(6),
        half: Some("TOP".into()),
        outs: Some(1),
        score_home: Some(3),
        score_away: Some(1),
        run_differential: Some(2),
        bases_bitmask: Some(0),
        batter_id: None,
        pitcher_id: None,
        balls: Some(0),
        strikes: Some(0),
        game_status: Some("IN_PROGRESS".into()),
        chrono_index: 0,
        previous_trade_price_cents: None,
        price_change_cents: None,
        cumulative_trade_count: 1,
        time_since_previous_trade_ms: None,
        time_since_state_transition_ms: None,
        observed_high_cents_so_far: Some(px),
        observed_low_cents_so_far: Some(px),
        distance_from_high_cents: Some(0),
        distance_from_low_cents: Some(0),
        prior_price_changes: 0,
        causal_version: "W7.CAUSAL.1.0.0".into(),
        join_version: "W7.JOIN.1.0.0".into(),
        w5_dataset_version: "W5".into(),
        w6_dataset_version: "W6".into(),
        w7_version: "W7".into(),
    }
}

fn state(seq: u32, hour: u32, inn: u8, sh: u16, sa: u16) -> StoredState {
    StoredState {
        state_id: format!("st{seq}"),
        game_id: "g1".into(),
        game_pk: "100".into(),
        state_seq: seq,
        event_id: None,
        event_sequence: seq,
        canonical_timestamp: Some(ts(hour, 0, 0)),
        inning: inn,
        half: "TOP".into(),
        outs: 1,
        score_home: sh,
        score_away: sa,
        run_differential: i32::from(sh) - i32::from(sa),
        bases_bitmask: 0,
        batter_id: None,
        pitcher_id: None,
        balls: Some(0),
        strikes: Some(0),
        game_status: "IN_PROGRESS".into(),
        extra_inning: false,
        event_type: Some("SINGLE".into()),
    }
}

fn identity() -> TeamIdentity {
    TeamIdentity {
        home: "TOR".into(),
        away: "NYY".into(),
        source: "TEST".into(),
    }
}

fn input() -> W8EntryInput {
    W8EntryInput {
        opportunity_id: "opp1".into(),
        game_id: "g1".into(),
        market_id: "m1".into(),
        side: "TOR".into(),
        entry_timestamp: ts(19, 0, 0),
        entry_observation_id: "e1".into(),
        entry_price_cents: 81,
        first80_observation_id: Some("f80".into()),
        first80_timestamp: Some(ts(18, 59, 0)),
        confirm_observation_id: Some("c81".into()),
        official_date: Some("2025-06-01".into()),
        game_pk: Some("100".into()),
        game_status: Some("OK".into()),
    }
}

#[test]
fn execution_status_is_observational_not_fill() {
    let snap = extract_snapshot(
        &input(),
        &[trade("e1", 19, 0, 0, 81)],
        &[state(1, 18, 6, 3, 1)],
        &[],
        Some(&identity()),
    );
    assert_eq!(snap.execution_status, EXECUTION_STATUS);
    assert_ne!(snap.execution_status, "FILLED_ENTRY");
}

#[test]
fn home_away_lead_is_side_aware() {
    assert_eq!(bound_team_lead("TOR", "TOR", "NYY", 2), Some(2));
    assert_eq!(bound_team_lead("NYY", "TOR", "NYY", 2), Some(-2));
    assert_eq!(bound_team_lead("BOS", "TOR", "NYY", 2), None);
    assert_eq!(normalize_abbr("ARI"), "AZ");
}

#[test]
fn score_diff_uses_bound_side_not_always_home() {
    let away_id = TeamIdentity {
        home: "TOR".into(),
        away: "NYY".into(),
        source: "TEST".into(),
    };
    let mut inp = input();
    inp.side = "NYY".into();
    let snap = extract_snapshot(
        &inp,
        &[trade("e1", 19, 0, 0, 81)],
        &[state(1, 18, 6, 3, 1)],
        &[],
        Some(&away_id),
    );
    assert_eq!(snap.baseball.bound_team_lead, Some(-2));
    assert_eq!(snap.baseball.bound_team_score, Some(1));
}

#[test]
fn no_future_w6_state() {
    let states = vec![state(1, 18, 6, 3, 1), state(2, 20, 7, 4, 1)];
    let chosen = state_at_or_before(&states, ts(19, 0, 0)).unwrap();
    assert_eq!(chosen.state_seq, 1);
    assert!(chosen.canonical_timestamp.unwrap() <= ts(19, 0, 0));
}

#[test]
fn lookbacks_never_use_future_trades() {
    let path = vec![
        trade("a", 18, 0, 0, 55),
        trade("e1", 19, 0, 0, 81),
        trade("z", 19, 10, 0, 90),
    ];
    let prior = priced_at_or_before(&path, "g1", "m1", "TOR", ts(19, 0, 0));
    assert!(prior.iter().all(|t| t.ts <= ts(19, 0, 0)));
    assert!(!prior.iter().any(|t| t.observation_id == "z"));
}

#[test]
fn start_to_entry_and_path_are_deterministic() {
    let path = vec![
        trade("s", 17, 0, 0, 56),
        trade("m", 18, 0, 0, 70),
        trade("e1", 19, 0, 0, 80),
    ];
    let prior = priced_at_or_before(&path, "g1", "m1", "TOR", ts(19, 0, 0));
    let hist = path_stats(&prior);
    assert_eq!(hist.start_to_entry_move_cents, Some(24));
    assert_eq!(hist.path_distance_cents, Some(24));
    assert_eq!(hist.path_efficiency_bps, Some(10_000));
    assert_eq!(hist.reversal_count, Some(0));
}

#[test]
fn path_efficiency_none_when_distance_zero() {
    let path = vec![trade("e1", 19, 0, 0, 81)];
    let prior = priced_at_or_before(&path, "g1", "m1", "TOR", ts(19, 0, 0));
    let hist = path_stats(&prior);
    assert_eq!(hist.path_distance_cents, Some(0));
    assert!(hist.path_efficiency_bps.is_none());
}

#[test]
fn reversal_ignores_flat() {
    let path = vec![
        trade("a", 17, 0, 0, 50),
        trade("b", 17, 30, 0, 50),
        trade("c", 18, 0, 0, 70),
        trade("d", 18, 30, 0, 60),
        trade("e1", 19, 0, 0, 80),
    ];
    let prior = priced_at_or_before(&path, "g1", "m1", "TOR", ts(19, 0, 0));
    let hist = path_stats(&prior);
    assert_eq!(hist.reversal_count, Some(2));
}

#[test]
fn settlement_from_w6_not_last_trade() {
    let mut fin = state(9, 22, 9, 5, 2);
    fin.game_status = "FINAL".into();
    let (out, _, _) = settlement_from_w6(Some(&fin), Some("OK"), Some(&identity()), "TOR");
    assert_eq!(out, SettlementOutcome::Win);
    let (tie, _, _) = settlement_from_w6(Some(&fin), Some("FINAL_TIE"), Some(&identity()), "TOR");
    assert_eq!(tie, SettlementOutcome::FinalTie);
}

#[test]
fn l2_is_unavailable() {
    let m = current_microstructure();
    assert_eq!(m.bid, FeatureAvailability::UnavailableSource);
    assert_eq!(m.ofi_1m, FeatureAvailability::UnavailableSource);
    assert_eq!(m.obi_z, FeatureAvailability::UnavailableSource);
    assert_eq!(m.microprice, FeatureAvailability::UnavailableSource);
}

#[test]
fn snapshot_ids_are_deterministic() {
    let a = snapshot_id(DATASET_VERSION, "opp1", "e1");
    let b = snapshot_id(DATASET_VERSION, "opp1", "e1");
    assert_eq!(a, b);
    assert_ne!(a, snapshot_id(DATASET_VERSION, "opp2", "e1"));
}

#[test]
fn validate_rejects_future_state() {
    let mut snap = extract_snapshot(
        &input(),
        &[trade("e1", 19, 0, 0, 81)],
        &[state(1, 18, 6, 3, 1)],
        &[],
        Some(&identity()),
    );
    snap.baseball.state_timestamp = Some(ts(21, 0, 0));
    assert!(validate_snapshot(&snap).is_err());
}

#[test]
fn one_primary_entry_per_game() {
    let snap = extract_snapshot(
        &input(),
        &[trade("e1", 19, 0, 0, 81)],
        &[state(1, 18, 6, 3, 1)],
        &[],
        Some(&identity()),
    );
    let mut dup = snap.clone();
    dup.snapshot_id = "other".into();
    let err = validate_batch(&[snap, dup], 2).unwrap_err();
    assert!(err.to_string().contains("DUPLICATE_GAME"));
}

#[test]
fn late_lead_filter_matches_prior_study_definition() {
    let snap = extract_snapshot(
        &input(),
        &[trade("e1", 19, 0, 0, 81)],
        &[state(1, 18, 6, 3, 1)],
        &[],
        Some(&identity()),
    );
    assert_eq!(snap.baseball.inning, Some(6));
    assert_eq!(snap.baseball.bound_team_lead, Some(2));
    assert_eq!(snap.baseball.regime, BaseballRegime::MidLead);
    assert!((6..=9).contains(&snap.baseball.inning.unwrap()));
    assert!(snap.baseball.bound_team_lead.unwrap() >= 2);
}

#[test]
fn regimes_documented() {
    assert_eq!(
        baseball_regime(Some(2), Some(0)),
        BaseballRegime::EarlyClose
    );
    assert_eq!(baseball_regime(Some(6), Some(2)), BaseballRegime::MidLead);
    assert_eq!(
        baseball_regime(Some(8), Some(-3)),
        BaseballRegime::LateTrail
    );
    assert_eq!(
        baseball_regime(Some(9), Some(1)),
        BaseballRegime::NinthClose
    );
    assert_eq!(
        baseball_regime(Some(11), Some(4)),
        BaseballRegime::ExtraInnings
    );
}

#[test]
fn outcomes_are_after_entry() {
    let path = vec![trade("s", 17, 0, 0, 56), trade("e1", 19, 0, 0, 81), {
        let mut t = trade("f", 19, 5, 0, 85);
        t.observation_id = "f".into();
        t
    }];
    let snap = extract_snapshot(
        &input(),
        &path,
        &[state(1, 18, 6, 3, 1)],
        &[],
        Some(&identity()),
    );
    validate_snapshot(&snap).unwrap();
    assert_eq!(snap.outcomes.future_5m.return_cents, Some(4));
    assert!(snap.outcomes.future_5m.outcome_timestamp.unwrap() > snap.entry_timestamp);
}

#[test]
fn extract_is_deterministic() {
    let path = vec![trade("s", 17, 0, 0, 56), trade("e1", 19, 0, 0, 81)];
    let states = vec![state(1, 18, 6, 3, 1)];
    let a = extract_snapshot(&input(), &path, &states, &[], Some(&identity()));
    let b = extract_snapshot(&input(), &path, &states, &[], Some(&identity()));
    assert_eq!(a, b);
}

#[test]
fn start_sentiment_keeps_raw_p_start() {
    assert_eq!(
        StartSentiment::from_p_start_cents(Some(44)),
        StartSentiment::Underdog
    );
    assert_eq!(
        StartSentiment::from_p_start_cents(Some(56)),
        StartSentiment::Favorite
    );
    assert_eq!(
        StartSentiment::from_p_start_cents(Some(72)),
        StartSentiment::StrongFavorite
    );
    let path = vec![trade("s", 17, 0, 0, 44), trade("e1", 19, 0, 0, 80)];
    let mut inp = input();
    inp.entry_price_cents = 80;
    let snap = extract_snapshot(
        &inp,
        &path,
        &[state(1, 18, 6, 3, 1)],
        &[],
        Some(&identity()),
    );
    assert_eq!(snap.starting_market.p_start_cents, Some(44));
    assert_eq!(
        snap.starting_market.start_sentiment,
        StartSentiment::Underdog
    );
    assert_eq!(snap.a1_targets.entry_target, A1EntryTarget::Entry80);
    assert_eq!(snap.current_market.d80_trade_cents, 0);
    assert_eq!(
        snap.current_market.d80_mid,
        FeatureAvailability::UnavailableSource
    );
}

#[test]
fn a1_fifty_pct_stop_uses_first_future_print() {
    let path = vec![
        trade("s", 17, 0, 0, 56),
        trade("e1", 19, 0, 0, 81),
        trade("z", 19, 10, 0, 40),
    ];
    let snap = extract_snapshot(
        &input(),
        &path,
        &[state(1, 18, 6, 3, 1)],
        &[],
        Some(&identity()),
    );
    let stop = snap
        .a1_targets
        .outcome(EXIT_LIVE_50PCT_STOP)
        .expect("50% target");
    assert!(stop.triggered);
    assert_eq!(stop.exit_price_cents, Some(40));
    assert_eq!(stop.return_cents, Some(-41));
    assert!(stop.exit_timestamp.unwrap() > snap.entry_timestamp);
    let hold = snap
        .a1_targets
        .outcome(EXIT_HOLD_TO_SETTLEMENT)
        .expect("hold");
    assert_eq!(hold.return_cents, Some(19));
    assert_eq!(a1_exit_return_cents(&snap, EXIT_LIVE_50PCT_STOP), Some(-41));
}

#[test]
fn event_history_never_after_entry() {
    let path = vec![trade("s", 17, 0, 0, 56), trade("e1", 19, 0, 0, 81)];
    let snap = extract_snapshot(
        &input(),
        &path,
        &[state(1, 18, 6, 3, 1)],
        &[],
        Some(&identity()),
    );
    assert!(
        snap.event_response
            .event_history
            .iter()
            .all(|e| e.event_timestamp <= snap.entry_timestamp)
    );
}

#[test]
fn a1_matrix_reports_game_counts() {
    let path = vec![trade("s", 17, 0, 0, 56), trade("e1", 19, 0, 0, 81)];
    let snap = extract_snapshot(
        &input(),
        &path,
        &[state(1, 18, 6, 3, 1)],
        &[],
        Some(&identity()),
    );
    let cells = a1_bucket_matrix(&[snap]);
    assert!(cells.iter().any(|c| c.condition.contains("ENTRY_81")
        && c.condition.contains("HOLD_TO_SETTLEMENT")
        && c.n_unique_games == 1));
}
