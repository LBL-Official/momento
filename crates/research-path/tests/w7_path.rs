//! W7 EventMarketPath tests — anti-lookahead, causal descriptors, two sides, idempotence.

use chrono::{DateTime, Utc};
use momento_research_path::causal::{apply_causal_descriptors, assemble_paths, state_segments};
use momento_research_path::firewall::W7_FORBIDDEN_CONCEPTS;
use momento_research_path::join::{W6Index, join_observation, path_id, sort_path_observations};
use momento_research_path::store::PathStore;
use momento_research_path::types::PathJoinStatus;
use momento_research_path::{WATERFALL, observations_where_price_equals, path_for_contract};
use momento_research_state::{StoredState, StoredTransition};
use momento_research_sync::apply::synchronize_market_observation;
use momento_research_sync::types::{
    GameStateSnapshot, IdentityStatus, KIND_KALSHI_TRADE_CREATED, KIND_PBP_OFFICIAL,
    MarketObservation, ObservationType, SyncParams, TimedEvent,
};

fn ts(s: &str) -> DateTime<Utc> {
    DateTime::parse_from_rfc3339(s).unwrap().with_timezone(&Utc)
}

fn snap(event_id: &str, seq: u32, inning: u8, outs: u8) -> GameStateSnapshot {
    GameStateSnapshot {
        game_id: "g1".into(),
        event_id: event_id.into(),
        state_seq: seq,
        inning,
        half: "TOP".into(),
        outs,
        score_home: 0,
        score_away: 0,
        run_differential: 0,
        runner_first: None,
        runner_second: None,
        runner_third: None,
        batter: Some("batter".into()),
        pitcher: Some("pitcher".into()),
        balls: 0,
        strikes: 0,
        count: "0-0".into(),
        game_status: "INPROGRESS".into(),
        extra_inning: false,
    }
}

fn ev(id: &str, t: &str, seq: u32, outs: u8) -> TimedEvent {
    let after = snap(id, seq, 1, outs);
    let mut before = after.clone();
    before.outs = outs.saturating_sub(1);
    before.state_seq = seq.saturating_sub(1);
    TimedEvent {
        event_id: id.into(),
        sequence: seq,
        source_event_time: t.into(),
        source_timestamp_kind: KIND_PBP_OFFICIAL.into(),
        normalized_event_time: ts(t),
        previous_event_id: None,
        next_event_id: None,
        state_before: before,
        state_after: after,
    }
}

fn timeline() -> Vec<TimedEvent> {
    vec![
        ev("A", "2025-07-15T18:42:10Z", 1, 0),
        ev("B", "2025-07-15T18:42:27Z", 2, 1),
    ]
}

fn market_obs(id: &str, t: &str, cents: i32, market: &str) -> MarketObservation {
    MarketObservation {
        observation_id: id.into(),
        market_id: market.into(),
        ticker: "KXMLBGAME-25JUL15AAABBB-AAA".into(),
        game_pk: Some("1".into()),
        observation_type: ObservationType::Trade,
        source_market_time: t.into(),
        source_timestamp_kind: KIND_KALSHI_TRADE_CREATED.into(),
        normalized_market_time: Some(ts(t)),
        retrieval_time: Some(ts("2026-08-26T19:00:00Z")),
        last_trade_cents: Some(cents),
        yes_bid_cents: None,
        yes_ask_cents: None,
        quantity_hundredths: Some(100),
        source_id: Some(id.into()),
        source_lineage: "fixture".into(),
    }
}

fn params<'a>(events: &'a [TimedEvent], side: &'a str) -> SyncParams<'a> {
    SyncParams {
        game_id: "g1",
        game_pk: "1",
        identity: IdentityStatus::Matched,
        events,
        contract_side: side,
        first_observed_price_cents: Some(80),
        ambiguous_clock: false,
    }
}

fn st(
    id: &str,
    seq: u32,
    event_id: Option<&str>,
    t: Option<&str>,
    inning: u8,
    outs: u8,
) -> StoredState {
    StoredState {
        state_id: id.into(),
        game_id: "g1".into(),
        game_pk: "1".into(),
        state_seq: seq,
        event_id: event_id.map(str::to_string),
        event_sequence: seq,
        canonical_timestamp: t.map(ts),
        inning,
        half: "TOP".into(),
        outs,
        score_home: 0,
        score_away: 0,
        run_differential: 0,
        bases_bitmask: 0,
        batter_id: Some("batter".into()),
        pitcher_id: Some("pitcher".into()),
        balls: Some(0),
        strikes: Some(0),
        game_status: "INPROGRESS".into(),
        extra_inning: false,
        event_type: Some("PLAY".into()),
    }
}

fn w6_index() -> W6Index {
    let states = vec![
        st("S0", 0, None, None, 1, 0),
        st("S1", 1, Some("A"), Some("2025-07-15T18:42:10Z"), 1, 0),
        st("S2", 2, Some("B"), Some("2025-07-15T18:42:27Z"), 1, 1),
    ];
    let transitions = vec![
        StoredTransition {
            transition_id: "T1".into(),
            sequence: 1,
            event_id: "A".into(),
            previous_state_id: "S0".into(),
            resulting_state_id: "S1".into(),
            event_timestamp: Some(ts("2025-07-15T18:42:10Z")),
            event_type: "PLAY".into(),
        },
        StoredTransition {
            transition_id: "T2".into(),
            sequence: 2,
            event_id: "B".into(),
            previous_state_id: "S1".into(),
            resulting_state_id: "S2".into(),
            event_timestamp: Some(ts("2025-07-15T18:42:27Z")),
            event_type: "PLAY".into(),
        },
    ];
    W6Index::from_rows("g1", states, transitions)
}

fn join_at(t: &str, cents: i32, side: &str, oid: &str) -> momento_research_path::PathObservation {
    let events = timeline();
    let o = market_obs(oid, t, cents, "m1");
    let mut obs = o.clone();
    obs.ticker = format!("KXMLBGAME-25JUL15AAABBB-{side}");
    let synced = synchronize_market_observation(params(&events, side), &obs);
    let idx = w6_index();
    let pid = path_id("g1", "m1", side, "w5", "w6");
    join_observation(&synced, Some(&idx), &pid, "w5", "w6").unwrap()
}

#[test]
fn waterfall_is_cto_w7() {
    assert_eq!(WATERFALL, "CTO-W7");
}

#[test]
fn observation_cannot_reference_future_state() {
    let events = timeline();
    let o = market_obs("t_between", "2025-07-15T18:42:20Z", 80, "m1");
    let synced = synchronize_market_observation(params(&events, "AAA"), &o);
    let idx = w6_index();
    let pid = path_id("g1", "m1", "AAA", "w5", "w6");
    let row = join_observation(&synced, Some(&idx), &pid, "w5", "w6").unwrap();
    assert_eq!(row.state_id.as_deref(), Some("S1"));
    assert!(row.matched_state_timestamp_utc.unwrap() <= row.market_timestamp_utc.unwrap());
    assert_ne!(row.state_id.as_deref(), Some("S2"));
}

#[test]
fn future_w6_timestamp_is_validation_failure() {
    let events = timeline();
    let o = market_obs("t_early", "2025-07-15T18:42:20Z", 80, "m1");
    let synced = synchronize_market_observation(params(&events, "AAA"), &o);
    let mut states = vec![st("S1", 1, Some("A"), Some("2025-07-15T18:42:30Z"), 1, 0)];
    states[0].game_id = "g1".into();
    let idx = W6Index::from_rows("g1", states, vec![]);
    let pid = path_id("g1", "m1", "AAA", "w5", "w6");
    let err = join_observation(&synced, Some(&idx), &pid, "w5", "w6").unwrap_err();
    assert!(err.to_string().contains("FUTURE_STATE"));
}

#[test]
fn exact_event_timestamp_uses_w5_post_event_state() {
    let row = join_at("2025-07-15T18:42:10Z", 80, "AAA", "t_at");
    assert_eq!(row.join_status, PathJoinStatus::AtEvent);
    assert_eq!(row.state_id.as_deref(), Some("S1"));
    assert_eq!(row.state_seq, Some(1));
    assert_eq!(row.timestamp_relation, "AT_EVENT");
}

#[test]
fn between_events_uses_earlier_applicable_state() {
    let row = join_at("2025-07-15T18:42:20Z", 81, "AAA", "t_mid");
    assert!(row.join_status.has_applicable_state());
    assert_eq!(row.state_id.as_deref(), Some("S1"));
    assert_eq!(row.next_state_id.as_deref(), Some("S2"));
}

#[test]
fn next_state_does_not_change_current_assignment() {
    let a = join_at("2025-07-15T18:42:20Z", 80, "AAA", "t1");
    assert_eq!(a.state_id.as_deref(), Some("S1"));
    assert_eq!(a.next_state_id.as_deref(), Some("S2"));
    assert_ne!(a.state_id, a.next_state_id);
}

#[test]
fn before_first_and_after_last_retained_without_applicable_state() {
    let before = join_at("2025-07-15T18:41:00Z", 50, "AAA", "t_pre");
    assert_eq!(before.join_status, PathJoinStatus::BeforeFirstEvent);
    assert!(before.state_id.is_none());
    let after = join_at("2025-07-15T18:50:00Z", 95, "AAA", "t_post");
    assert_eq!(after.join_status, PathJoinStatus::AfterLastEvent);
    assert!(after.state_id.is_none());
}

#[test]
fn causal_descriptors_do_not_use_future_prices_or_extrema() {
    let mut rows = vec![
        join_at("2025-07-15T18:42:12Z", 80, "AAA", "c1"),
        join_at("2025-07-15T18:42:15Z", 90, "AAA", "c2"),
        join_at("2025-07-15T18:42:18Z", 70, "AAA", "c3"),
    ];
    sort_path_observations(&mut rows);
    apply_causal_descriptors(&mut rows);
    assert_eq!(rows[0].observed_high_cents_so_far, Some(80));
    assert_eq!(rows[0].previous_trade_price_cents, None);
    assert_eq!(rows[1].previous_trade_price_cents, Some(80));
    assert_eq!(rows[1].observed_high_cents_so_far, Some(90));
    assert_eq!(rows[1].price_change_cents, Some(10));
    assert_eq!(rows[2].observed_high_cents_so_far, Some(90));
    assert_eq!(rows[2].observed_low_cents_so_far, Some(70));
    assert_eq!(rows[0].prior_price_changes, 0);
    assert_eq!(rows[1].prior_price_changes, 0);
    assert_eq!(rows[2].prior_price_changes, 1);
    assert_eq!(rows[0].chrono_index, 0);
    assert_eq!(rows[2].cumulative_trade_count, 3);
}

#[test]
fn retrieval_timestamp_does_not_affect_path_ordering() {
    let later_market = join_at("2025-07-15T18:42:20Z", 82, "AAA", "ord_b");
    let earlier_market = join_at("2025-07-15T18:42:12Z", 80, "AAA", "ord_a");
    let mut rows = vec![later_market, earlier_market];
    sort_path_observations(&mut rows);
    assert_eq!(rows[0].observation_id, "ord_a");
    assert_eq!(rows[1].observation_id, "ord_b");
}

#[test]
fn duplicate_source_observations_are_idempotent() {
    let a = join_at("2025-07-15T18:42:20Z", 80, "AAA", "dup");
    let b = join_at("2025-07-15T18:42:20Z", 80, "AAA", "dup");
    assert_eq!(a.path_observation_id, b.path_observation_id);
    let now = ts("2026-08-26T00:00:00Z");
    let mut store = PathStore::open_memory("run", now).unwrap();
    let paths = assemble_paths(vec![a.clone(), b]);
    for p in &paths {
        let segs = state_segments(&p.path_id, &p.observations);
        store.insert_path(p, &segs).unwrap();
    }
    let got = path_for_contract(&store, "m1", "AAA").unwrap();
    assert_eq!(got.len(), 1);
}

#[test]
fn two_contract_sides_share_game_timeline_independently() {
    let yes = join_at("2025-07-15T18:42:20Z", 80, "AAA", "yes1");
    let no = join_at("2025-07-15T18:42:20Z", 19, "BBB", "no1");
    assert_eq!(yes.game_id, no.game_id);
    assert_eq!(yes.state_id, no.state_id);
    assert_eq!(yes.state_seq, no.state_seq);
    assert_ne!(yes.path_id, no.path_id);
    assert_eq!(yes.trade_price_cents, Some(80));
    assert_eq!(no.trade_price_cents, Some(19));
    assert_ne!(
        yes.trade_price_cents.unwrap() + no.trade_price_cents.unwrap(),
        100
    );
}

#[test]
fn missing_side_is_not_synthesized() {
    let yes = join_at("2025-07-15T18:42:20Z", 80, "AAA", "only");
    let paths = assemble_paths(vec![yes]);
    assert_eq!(paths.len(), 1);
    assert_eq!(paths[0].contract_side, "AAA");
    let now = ts("2026-08-26T00:00:00Z");
    let mut store = PathStore::open_memory("run2", now).unwrap();
    for p in &paths {
        store
            .insert_path(p, &state_segments(&p.path_id, &p.observations))
            .unwrap();
    }
    let other = path_for_contract(&store, "m1", "BBB").unwrap();
    assert!(other.is_empty());
}

#[test]
fn trades_remain_trade_kind() {
    let row = join_at("2025-07-15T18:42:20Z", 80, "AAA", "tr");
    assert_eq!(row.observation_kind, "TRADE");
    assert!(row.trade_size_hundredths.is_none());
}

#[test]
fn state_segments_split_on_w6_state_id() {
    let a = join_at("2025-07-15T18:42:12Z", 80, "AAA", "s1");
    let b = join_at("2025-07-15T18:42:20Z", 81, "AAA", "s2");
    let c = join_at("2025-07-15T18:42:27Z", 82, "AAA", "s3");
    let mut rows = vec![a, b, c];
    sort_path_observations(&mut rows);
    apply_causal_descriptors(&mut rows);
    let segs = state_segments(&rows[0].path_id, &rows);
    assert!(segs.len() >= 2);
    assert_eq!(segs[0].state_id, "S1");
}

#[test]
fn eighty_cent_query_is_observational_not_first01() {
    let a = join_at("2025-07-15T18:42:12Z", 80, "AAA", "p80");
    let b = join_at("2025-07-15T18:42:20Z", 81, "AAA", "p81");
    let now = ts("2026-08-26T00:00:00Z");
    let mut store = PathStore::open_memory("run3", now).unwrap();
    let paths = assemble_paths(vec![a, b]);
    for p in &paths {
        store
            .insert_path(p, &state_segments(&p.path_id, &p.observations))
            .unwrap();
    }
    let hits = observations_where_price_equals(&store, 80).unwrap();
    assert_eq!(hits.len(), 1);
    assert_eq!(hits[0].trade_price_cents, Some(80));
}

#[test]
fn gap_quality_is_not_upgraded_to_exact() {
    let row = join_at("2025-07-15T18:42:20Z", 80, "AAA", "gap");
    assert_ne!(row.synchronization_quality, "EXACT");
    assert!(
        row.join_status == PathJoinStatus::SynchronizedWithTimestampGap
            || row.join_status == PathJoinStatus::Synchronized
            || row.join_status == PathJoinStatus::AtEvent
    );
}

#[test]
fn firewall_forbids_strategy_l2_and_ml() {
    let lib = include_str!("../src/lib.rs");
    let join = include_str!("../src/join.rs");
    let causal = include_str!("../src/causal.rs");
    for bad in W7_FORBIDDEN_CONCEPTS {
        assert!(!lib.contains(bad), "{bad} in lib");
        assert!(!join.contains(bad), "{bad} in join");
        assert!(!causal.contains(bad), "{bad} in causal");
    }
}

#[test]
fn smoke_join_real_w5_w6_if_present() {
    let w5p = std::path::Path::new("Backtesting Suite/Foundation/W5/sync.sqlite");
    let w6p = std::path::Path::new("Backtesting Suite/Foundation/W6/state.sqlite");
    if !w5p.exists() || !w6p.exists() {
        return;
    }
    let w5 = momento_research_sync::SyncStore::open_existing(w5p).unwrap();
    let w6 = momento_research_state::StateStore::open_existing(w6p).unwrap();
    let Ok(games) = w5.list_games() else {
        return;
    };
    let ok: std::collections::HashSet<String> =
        w6.list_ok_game_ids().unwrap().into_iter().collect();
    let Some((gid, _)) = games.into_iter().find(|(g, _)| ok.contains(g)) else {
        return;
    };
    let idx = W6Index::from_rows(
        &gid,
        w6.load_states(&gid).unwrap(),
        w6.load_transitions(&gid).unwrap(),
    );
    let rows = w5.observations_for_game(&gid).unwrap();
    let w5v = w5.dataset_version().unwrap();
    let w6v = w6.dataset_version().unwrap();
    let mut n = 0usize;
    for obs in rows.iter().take(200) {
        let pid = path_id(&obs.game_id, &obs.market_id, &obs.contract_side, &w5v, &w6v);
        let row = join_observation(obs, Some(&idx), &pid, &w5v, &w6v).unwrap();
        if let (Some(st), Some(mt)) = (row.matched_state_timestamp_utc, row.market_timestamp_utc) {
            assert!(st <= mt, "lookahead {st} > {mt}");
        }
        if row.join_status.has_applicable_state() {
            assert!(row.state_id.is_some());
            n += 1;
        }
        if matches!(
            row.join_status,
            PathJoinStatus::BeforeFirstEvent | PathJoinStatus::AfterLastEvent
        ) {
            assert!(row.state_id.is_none());
        }
        assert_eq!(row.observation_kind, "TRADE");
    }
    assert!(n > 0 || rows.is_empty());
}
