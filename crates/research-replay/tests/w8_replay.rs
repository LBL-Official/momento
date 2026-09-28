//! W8 FIRST01 replay tests — anti-lookahead, bind, pause vs lock, truncation.

use chrono::{DateTime, Utc};
use momento_research_path::{PathJoinStatus, PathObservation};
use momento_research_replay::WATERFALL;
use momento_research_replay::firewall::W8_FORBIDDEN_CONCEPTS;
use momento_research_replay::machine::replay_path;
use momento_research_replay::types::ReplayEventType;

fn ts(s: &str) -> DateTime<Utc> {
    DateTime::parse_from_rfc3339(s).unwrap().with_timezone(&Utc)
}

fn obs(id: &str, t: &str, px: i32, side: &str, market: &str) -> PathObservation {
    PathObservation {
        path_observation_id: id.into(),
        path_id: "p".into(),
        game_id: "g1".into(),
        game_pk: "1".into(),
        market_id: market.into(),
        ticker: format!("T-{side}"),
        contract_id: side.into(),
        contract_side: side.into(),
        observation_id: id.into(),
        w5_synchronization_id: id.into(),
        observation_kind: "TRADE".into(),
        market_timestamp_utc: Some(ts(t)),
        matched_state_timestamp_utc: Some(ts(t)),
        event_lag_ms: Some(0),
        synchronization_status: "SYNCHRONIZED".into(),
        synchronization_quality: "WITHIN_INNING".into(),
        join_status: PathJoinStatus::SynchronizedWithTimestampGap,
        timestamp_relation: "AFTER_EVENT".into(),
        trade_price_cents: Some(px),
        trade_size_hundredths: None,
        source_observation_id: Some(id.into()),
        source_lineage: "fixture".into(),
        state_id: Some("S1".into()),
        state_seq: Some(1),
        previous_state_id: None,
        previous_state_seq: None,
        transition_id: None,
        transition_event_type: None,
        next_state_id: Some("S2".into()),
        next_state_seq: Some(2),
        inning: Some(1),
        half: Some("TOP".into()),
        outs: Some(0),
        score_home: Some(0),
        score_away: Some(0),
        run_differential: Some(0),
        bases_bitmask: Some(0),
        batter_id: Some("b".into()),
        pitcher_id: Some("p".into()),
        balls: Some(0),
        strikes: Some(0),
        game_status: Some("IN_PROGRESS".into()),
        chrono_index: 0,
        previous_trade_price_cents: None,
        price_change_cents: None,
        cumulative_trade_count: 1,
        time_since_previous_trade_ms: None,
        time_since_state_transition_ms: Some(0),
        observed_high_cents_so_far: Some(px),
        observed_low_cents_so_far: Some(px),
        distance_from_high_cents: Some(0),
        distance_from_low_cents: Some(0),
        prior_price_changes: 0,
        causal_version: "c".into(),
        join_version: "j".into(),
        w5_dataset_version: "w5".into(),
        w6_dataset_version: "w6".into(),
        w7_version: "w7".into(),
    }
}

fn kinds(out: &momento_research_replay::ReplayOutcome) -> Vec<ReplayEventType> {
    out.events.iter().map(|e| e.event_type).collect()
}

#[test]
fn waterfall_is_cto_w8() {
    assert_eq!(WATERFALL, "CTO-W8");
}

#[test]
fn first80_is_first_qualifying_threshold() {
    let rows = vec![
        obs("a", "2025-07-15T18:00:01Z", 79, "AAA", "m1"),
        obs("b", "2025-07-15T18:00:02Z", 80, "AAA", "m1"),
        obs("c", "2025-07-15T18:00:03Z", 80, "AAA", "m1"),
    ];
    let out = replay_path(&rows, "w7");
    assert_eq!(out.prints_80, 2);
    assert_eq!(out.first80, 1);
    let first = out
        .events
        .iter()
        .find(|e| e.event_type == ReplayEventType::First80Observed)
        .unwrap();
    assert_eq!(first.observation_id, "b");
    assert_eq!(first.price_cents, Some(80));
}

#[test]
fn future_observation_cannot_affect_decision() {
    let early = vec![obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1")];
    let with_future = vec![
        obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1"),
        obs("z", "2025-07-15T19:00:00Z", 89, "AAA", "m1"),
    ];
    let a = replay_path(&early, "w7");
    let b = replay_path(&with_future, "w7");
    let a80 = a
        .events
        .iter()
        .find(|e| e.event_type == ReplayEventType::First80Observed)
        .unwrap();
    let b80 = b
        .events
        .iter()
        .find(|e| e.event_type == ReplayEventType::First80Observed)
        .unwrap();
    assert_eq!(a80.replay_event_id, b80.replay_event_id);
    assert_eq!(a80.observation_id, "a");
}

#[test]
fn next_state_does_not_assign_current() {
    let row = obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1");
    assert_eq!(row.next_state_id.as_deref(), Some("S2"));
    let out = replay_path(&[row], "w7");
    let e = out
        .events
        .iter()
        .find(|e| e.event_type == ReplayEventType::First80Observed)
        .unwrap();
    assert_eq!(e.state_id.as_deref(), Some("S1"));
}

#[test]
fn confirm_must_be_same_side_after_first80() {
    let rows = vec![
        obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1"),
        obs("b", "2025-07-15T18:00:03Z", 81, "BBB", "m2"),
        obs("c", "2025-07-15T18:00:04Z", 81, "AAA", "m1"),
    ];
    let out = replay_path(&rows, "w7");
    assert_eq!(out.confirm81, 1);
    let c = out
        .events
        .iter()
        .find(|e| e.event_type == ReplayEventType::Confirm81Observed)
        .unwrap();
    assert_eq!(c.observation_id, "c");
    assert_eq!(c.side, "AAA");
}

#[test]
fn opposite_side_81_does_not_confirm() {
    let rows = vec![
        obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1"),
        obs("b", "2025-07-15T18:00:03Z", 81, "BBB", "m1"),
    ];
    let out = replay_path(&rows, "w7");
    assert_eq!(out.confirm81, 0);
    assert_eq!(out.entry_eligible, 0);
}

#[test]
fn pause_above_83_is_not_game_lock() {
    let rows = vec![
        obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1"),
        obs("b", "2025-07-15T18:00:03Z", 81, "AAA", "m1"),
        obs("c", "2025-07-15T18:00:04Z", 84, "AAA", "m1"),
    ];
    let out = replay_path(&rows, "w7");
    assert!(kinds(&out).contains(&ReplayEventType::PricePaused));
    assert!(!kinds(&out).contains(&ReplayEventType::GameLocked));
    assert_eq!(out.game_locks, 0);
}

#[test]
fn eighty_nine_permanently_locks_entry() {
    let rows = vec![
        obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1"),
        obs("b", "2025-07-15T18:00:03Z", 89, "AAA", "m1"),
        obs("c", "2025-07-15T18:00:04Z", 81, "AAA", "m1"),
    ];
    let out = replay_path(&rows, "w7");
    assert_eq!(out.game_locks, 1);
    assert_eq!(out.confirm81, 0);
    assert_eq!(out.entry_eligible, 0);
}

#[test]
fn game_lock_does_not_create_liquidation_or_fill() {
    let src = include_str!("../src/machine.rs");
    assert!(!src.contains("ExecuteStop"));
    assert!(!src.contains("ORDER_FILLED"));
    assert!(!src.contains("realized_pnl"));
    let out = replay_path(&[obs("a", "2025-07-15T18:00:02Z", 89, "AAA", "m1")], "w7");
    assert_eq!(out.game_locks, 1);
    assert_eq!(out.first80, 0);
    assert_eq!(out.intents_proposed, 0);
}

#[test]
fn lock_before_80_prevents_entry() {
    let rows = vec![
        obs("a", "2025-07-15T18:00:02Z", 89, "AAA", "m1"),
        obs("b", "2025-07-15T18:00:03Z", 80, "AAA", "m1"),
        obs("c", "2025-07-15T18:00:04Z", 81, "AAA", "m1"),
    ];
    let out = replay_path(&rows, "w7");
    assert_eq!(out.first80, 0);
    assert_eq!(out.entry_eligible, 0);
}

#[test]
fn lock_between_80_and_81_prevents_entry() {
    let rows = vec![
        obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1"),
        obs("b", "2025-07-15T18:00:03Z", 89, "AAA", "m1"),
        obs("c", "2025-07-15T18:00:04Z", 81, "AAA", "m1"),
    ];
    let out = replay_path(&rows, "w7");
    assert_eq!(out.first80, 1);
    assert_eq!(out.confirm81, 0);
    assert_eq!(out.entry_eligible, 0);
}

#[test]
fn multiple_80_prints_one_first80() {
    let rows = vec![
        obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1"),
        obs("b", "2025-07-15T18:00:03Z", 80, "AAA", "m1"),
        obs("c", "2025-07-15T18:00:04Z", 80, "AAA", "m1"),
    ];
    let out = replay_path(&rows, "w7");
    assert_eq!(out.prints_80, 3);
    assert_eq!(out.first80, 1);
}

#[test]
fn confirmation_does_not_duplicate_opportunities() {
    let rows = vec![
        obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1"),
        obs("b", "2025-07-15T18:00:03Z", 81, "AAA", "m1"),
        obs("c", "2025-07-15T18:00:04Z", 82, "AAA", "m1"),
        obs("d", "2025-07-15T18:00:05Z", 80, "AAA", "m1"),
    ];
    let out = replay_path(&rows, "w7");
    assert_eq!(out.opportunities.len(), 1);
    assert_eq!(out.entry_eligible, 1);
    assert_eq!(out.intents_proposed, 1);
}

#[test]
fn two_sides_independent_prices_one_game_bind() {
    let rows = vec![
        obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1"),
        obs("b", "2025-07-15T18:00:03Z", 19, "BBB", "m2"),
    ];
    let out = replay_path(&rows, "w7");
    assert_eq!(out.first80, 1);
    assert_ne!(
        rows[0].trade_price_cents.unwrap() + rows[1].trade_price_cents.unwrap(),
        100
    );
    assert_eq!(out.opportunities[0].side, "AAA");
}

#[test]
fn missing_w6_state_is_not_fabricated() {
    let mut row = obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1");
    row.state_id = None;
    row.state_seq = None;
    row.join_status = PathJoinStatus::BeforeFirstEvent;
    let out = replay_path(&[row], "w7");
    let e = &out.events[0];
    assert!(e.state_id.is_none());
    assert_eq!(e.synchronization_class, "BEFORE_FIRST_EVENT");
}

#[test]
fn gap_quality_survives() {
    let out = replay_path(&[obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1")], "w7");
    assert_eq!(
        out.events[0].synchronization_class,
        "SYNCHRONIZED_WITH_TIMESTAMP_GAP"
    );
}

#[test]
fn exact_event_uses_w7_state() {
    let mut row = obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1");
    row.join_status = PathJoinStatus::AtEvent;
    row.synchronization_status = "AT_EVENT".into();
    let out = replay_path(&[row], "w7");
    assert_eq!(out.events[0].synchronization_class, "AT_EVENT");
    assert_eq!(out.events[0].state_id.as_deref(), Some("S1"));
}

#[test]
fn replay_is_deterministic_and_idempotent() {
    let rows = vec![
        obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1"),
        obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1"),
        obs("b", "2025-07-15T18:00:03Z", 81, "AAA", "m1"),
    ];
    let x = replay_path(&rows, "w7");
    let y = replay_path(&rows, "w7");
    let xid: Vec<_> = x.events.iter().map(|e| &e.replay_event_id).collect();
    let yid: Vec<_> = y.events.iter().map(|e| &e.replay_event_id).collect();
    assert_eq!(xid, yid);
    assert_eq!(x.first80, 1);
}

#[test]
fn truncation_matches_full_path_through_t() {
    let full = vec![
        obs("a", "2025-07-15T18:00:01Z", 79, "AAA", "m1"),
        obs("b", "2025-07-15T18:00:02Z", 80, "AAA", "m1"),
        obs("c", "2025-07-15T18:00:03Z", 81, "AAA", "m1"),
        obs("d", "2025-07-15T18:00:04Z", 82, "AAA", "m1"),
        obs("e", "2025-07-15T18:00:05Z", 89, "AAA", "m1"),
    ];
    let t = ts("2025-07-15T18:00:03Z");
    let trunc: Vec<_> = full
        .iter()
        .filter(|o| o.market_timestamp_utc.unwrap() <= t)
        .cloned()
        .collect();
    let full_out = replay_path(&full, "w7");
    let trunc_out = replay_path(&trunc, "w7");
    let full_through: Vec<_> = full_out
        .events
        .iter()
        .filter(|e| e.market_timestamp_utc.unwrap() <= t)
        .map(|e| {
            (
                e.replay_event_id.clone(),
                e.event_type,
                e.observation_id.clone(),
            )
        })
        .collect();
    let trunc_ids: Vec<_> = trunc_out
        .events
        .iter()
        .map(|e| {
            (
                e.replay_event_id.clone(),
                e.event_type,
                e.observation_id.clone(),
            )
        })
        .collect();
    assert_eq!(full_through, trunc_ids);
    let mut appended = trunc.clone();
    appended.push(obs("z", "2025-07-15T18:00:10Z", 90, "AAA", "m1"));
    let app = replay_path(&appended, "w7");
    let app_through: Vec<_> = app
        .events
        .iter()
        .filter(|e| e.market_timestamp_utc.unwrap() <= t)
        .map(|e| e.replay_event_id.clone())
        .collect();
    let trunc_eids: Vec<_> = trunc_out
        .events
        .iter()
        .map(|e| e.replay_event_id.clone())
        .collect();
    assert_eq!(app_through, trunc_eids);
}

#[test]
fn never_sends_to_risk_execution_or_pnl() {
    let lib = include_str!("../src/lib.rs");
    let machine = include_str!("../src/machine.rs");
    let batch = include_str!("../src/batch.rs");
    for bad in W8_FORBIDDEN_CONCEPTS {
        assert!(!lib.contains(bad), "{bad} in lib");
        assert!(!machine.contains(bad), "{bad} in machine");
        assert!(!batch.contains(bad), "{bad} in batch");
    }
    assert!(!machine.contains("momento_risk"));
    assert!(!machine.contains("momento_execution"));
}

#[test]
fn same_tick_81_confirms_like_live() {
    let out = replay_path(&[obs("a", "2025-07-15T18:00:02Z", 81, "AAA", "m1")], "w7");
    assert_eq!(out.first80, 1);
    assert_eq!(out.confirm81, 1);
    assert_eq!(out.entry_eligible, 1);
    assert_eq!(out.intents_proposed, 1);
}

#[test]
fn retrieval_order_does_not_override_source_order() {
    let later = obs("b", "2025-07-15T18:00:03Z", 80, "AAA", "m1");
    let earlier = obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1");
    let out = replay_path(&[later, earlier], "w7");
    let first = out
        .events
        .iter()
        .find(|e| e.event_type == ReplayEventType::First80Observed)
        .unwrap();
    assert_eq!(first.observation_id, "a");
}

#[test]
fn cargo_toml_has_no_risk_execution_kalshi() {
    let toml = include_str!("../Cargo.toml");
    assert!(!toml.contains("momento-risk"));
    assert!(!toml.contains("momento-execution"));
    assert!(!toml.contains("momento-kalshi"));
    assert!(!toml.contains("momento-pnl"));
    assert!(!toml.contains("momento-strategy-mlb"));
}

#[test]
fn same_timestamp_orders_by_observation_id() {
    let later_id = obs("z", "2025-07-15T18:00:02Z", 80, "AAA", "m1");
    let earlier_id = obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1");
    let out = replay_path(&[later_id, earlier_id], "w7");
    let first = out
        .events
        .iter()
        .find(|e| e.event_type == ReplayEventType::First80Observed)
        .unwrap();
    assert_eq!(first.observation_id, "a");
}

#[test]
fn pause_then_resume_does_not_duplicate_opportunity_or_lock() {
    let rows = vec![
        obs("a", "2025-07-15T18:00:02Z", 80, "AAA", "m1"),
        obs("b", "2025-07-15T18:00:03Z", 81, "AAA", "m1"),
        obs("c", "2025-07-15T18:00:04Z", 84, "AAA", "m1"),
        obs("d", "2025-07-15T18:00:05Z", 82, "AAA", "m1"),
    ];
    let out = replay_path(&rows, "w7");
    assert_eq!(out.opportunities.len(), 1);
    assert_eq!(out.entry_eligible, 1);
    assert_eq!(out.intents_proposed, 1);
    assert_eq!(out.game_locks, 0);
    assert!(kinds(&out).contains(&ReplayEventType::PricePaused));
}

#[test]
fn never_uses_settlement_outcome_or_next_state() {
    let machine = include_str!("../src/machine.rs");
    assert!(!machine.contains("settlement"));
    assert!(!machine.contains("next_state_id"));
    assert!(!machine.contains("realized_pnl"));
    assert!(!machine.contains("ORDER_FILLED"));
    assert!(!machine.contains("POSITION_OPEN"));
}

#[test]
fn lock_after_eligibility_records_both() {
    let rows = vec![
        obs("a", "2025-07-15T18:00:02Z", 81, "AAA", "m1"),
        obs("b", "2025-07-15T18:00:03Z", 89, "AAA", "m1"),
    ];
    let out = replay_path(&rows, "w7");
    assert_eq!(out.entry_eligible, 1);
    assert_eq!(out.game_locks, 1);
    let op = &out.opportunities[0];
    assert!(op.entry_observation_id.is_some());
    assert!(op.game_lock_observation_id.is_some());
    assert_eq!(op.replay_terminal_state, "GAME_LOCKED");
    let types = kinds(&out);
    let entry = types
        .iter()
        .position(|t| *t == ReplayEventType::EntryEligible)
        .unwrap();
    let lock = types
        .iter()
        .position(|t| *t == ReplayEventType::GameLocked)
        .unwrap();
    assert!(entry < lock);
}
