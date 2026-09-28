//! W5 synchronization tests — anti-lookahead, collisions, identity, provenance.

use chrono::{DateTime, TimeZone, Utc};
use momento_research_sync::apply::{synchronize_market, synchronize_market_observation};
use momento_research_sync::as_of::{AsOfReject, as_of, game_window, two_pointer_indexes};
use momento_research_sync::firewall::W5_FORBIDDEN_CONCEPTS;
use momento_research_sync::store::SyncStore;
use momento_research_sync::time::normalize_source_timestamp;
use momento_research_sync::types::{
    GameStateSnapshot, IdentityStatus, KIND_KALSHI_TRADE_CREATED, KIND_PBP_OFFICIAL,
    MarketObservation, ObservationType, SyncParams, SyncQuality, SyncStatus, TimedEvent,
    TimestampRelation,
};
use momento_research_sync::{WATERFALL, synchronize_game};
use serde_json::json;

fn ts(s: &str) -> DateTime<Utc> {
    DateTime::parse_from_rfc3339(s).unwrap().with_timezone(&Utc)
}

fn snap(
    event_id: &str,
    inning: u8,
    outs: u8,
    home: u16,
    away: u16,
    extra: bool,
    status: &str,
) -> GameStateSnapshot {
    GameStateSnapshot {
        game_id: "g1".into(),
        event_id: event_id.into(),
        state_seq: event_id.chars().last().unwrap().to_digit(10).unwrap_or(0),
        inning,
        half: "TOP".into(),
        outs,
        score_home: home,
        score_away: away,
        run_differential: i32::from(home) - i32::from(away),
        runner_first: None,
        runner_second: None,
        runner_third: None,
        batter: Some("batter".into()),
        pitcher: Some("pitcher".into()),
        balls: 0,
        strikes: 0,
        count: "0-0".into(),
        game_status: status.into(),
        extra_inning: extra,
    }
}

fn ev(
    id: &str,
    t: &str,
    seq: u32,
    before: GameStateSnapshot,
    after: GameStateSnapshot,
) -> TimedEvent {
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

fn simple(id: &str, t: &str, seq: u32, inning: u8, outs: u8, home: u16, away: u16) -> TimedEvent {
    let after = snap(id, inning, outs, home, away, false, "INPROGRESS");
    let mut before = after.clone();
    before.outs = outs.saturating_sub(1);
    ev(id, t, seq, before, after)
}

fn obs(id: &str, t: &str, cents: i32) -> MarketObservation {
    MarketObservation {
        observation_id: id.into(),
        market_id: "m1".into(),
        ticker: "KXMLBGAME-25APR16AAABBB-AAA".into(),
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

fn timeline() -> Vec<TimedEvent> {
    vec![
        simple("A", "2025-07-15T18:42:10Z", 1, 1, 0, 0, 0),
        simple("B", "2025-07-15T18:42:27Z", 2, 1, 1, 0, 0),
    ]
}

fn params<'a>(
    events: &'a [TimedEvent],
    identity: IdentityStatus,
    ambiguous: bool,
) -> SyncParams<'a> {
    SyncParams {
        game_id: "g1",
        game_pk: "1",
        identity,
        events,
        contract_side: "AAA",
        first_observed_price_cents: Some(80),
        ambiguous_clock: ambiguous,
    }
}

fn sync_one(
    events: &[TimedEvent],
    o: &MarketObservation,
) -> momento_research_sync::SynchronizedMarketObservation {
    synchronize_market_observation(params(events, IdentityStatus::Matched, false), o)
}

#[test]
fn utc_and_offset_normalization() {
    let a = normalize_source_timestamp("2025-07-15T18:42:10Z").unwrap();
    let b = normalize_source_timestamp("2025-07-15T14:42:10-04:00").unwrap();
    assert_eq!(a.utc, b.utc);
    assert_eq!(b.offset_seconds, -4 * 3600);
    assert_eq!(a.fractional_digits, 0);
    let fine = normalize_source_timestamp("2025-07-15T18:42:10.123456Z").unwrap();
    assert_eq!(fine.fractional_digits, 6);
}

#[test]
fn missing_offset_is_invalid_not_host_tz() {
    assert!(normalize_source_timestamp("2025-07-15T18:42:10").is_err());
}

#[test]
fn timestamp_precision_mismatch_is_preserved() {
    let events = timeline();
    let o = obs("t1", "2025-07-15T18:42:20.123Z", 80);
    let row = sync_one(&events, &o);
    assert_eq!(row.market_timestamp_source, "2025-07-15T18:42:20.123Z");
    assert_eq!(row.prior_event_id.as_deref(), Some("A"));
}

#[test]
fn as_of_between_events_is_state_a() {
    let events = timeline();
    let hit = as_of(
        &events,
        ts("2025-07-15T18:42:20Z"),
        game_window(&events).as_ref(),
    )
    .unwrap();
    assert_eq!(hit.matched.event_id, "A");
    assert_eq!(hit.matched.state_after.outs, 0);
    assert_eq!(hit.next.as_ref().unwrap().event_id, "B");
    assert_eq!(hit.relation, TimestampRelation::AfterEvent);
}

#[test]
fn as_of_exact_b_boundary_is_at_event() {
    let events = timeline();
    let hit = as_of(
        &events,
        ts("2025-07-15T18:42:27Z"),
        game_window(&events).as_ref(),
    )
    .unwrap();
    assert_eq!(hit.matched.event_id, "B");
    assert_eq!(hit.relation, TimestampRelation::AtEvent);
    let row = sync_one(&events, &obs("tB", "2025-07-15T18:42:27Z", 80));
    assert_eq!(row.synchronization_status, SyncStatus::AtEvent);
    assert_eq!(row.timestamp_relation, TimestampRelation::AtEvent);
    assert_eq!(row.pre_event_state.as_ref().unwrap().outs, 0);
    assert_eq!(row.post_event_state.as_ref().unwrap().outs, 1);
}

#[test]
fn as_of_after_b_inside_window() {
    let mut events = timeline();
    events.push(simple("C", "2025-07-15T18:50:00Z", 3, 1, 2, 0, 0));
    let hit = as_of(
        &events,
        ts("2025-07-15T18:43:00Z"),
        game_window(&events).as_ref(),
    )
    .unwrap();
    assert_eq!(hit.matched.event_id, "B");
}

#[test]
fn as_of_before_first_is_before_first_event() {
    let events = timeline();
    let err = as_of(
        &events,
        ts("2025-07-15T18:00:00Z"),
        game_window(&events).as_ref(),
    )
    .unwrap_err();
    match err {
        AsOfReject::NoPriorEvent { next } => assert_eq!(next.unwrap().event_id, "A"),
        other => panic!("{other:?}"),
    }
    let row = sync_one(&events, &obs("t0", "2025-07-15T18:00:00Z", 80));
    assert_eq!(row.synchronization_status, SyncStatus::BeforeFirstEvent);
    assert!(row.game_state.is_none());
}

#[test]
fn as_of_after_last_is_after_last_event() {
    let events = timeline();
    let err = as_of(
        &events,
        ts("2025-07-15T19:00:00Z"),
        game_window(&events).as_ref(),
    )
    .unwrap_err();
    match err {
        AsOfReject::OutsideWindow { last } => assert_eq!(last.event_id, "B"),
        other => panic!("{other:?}"),
    }
    let row = sync_one(&events, &obs("t9", "2025-07-15T19:00:00Z", 80));
    assert_eq!(row.synchronization_status, SyncStatus::AfterLastEvent);
    assert!(row.game_state.is_none());
}

#[test]
fn market_closes_after_game_ends_not_snapped() {
    let events = timeline();
    let row = sync_one(&events, &obs("late", "2025-07-15T23:00:00Z", 99));
    assert_eq!(row.synchronization_status, SyncStatus::AfterLastEvent);
    assert!(row.game_state.is_none());
    assert_eq!(row.prior_event_id.as_deref(), Some("B"));
}

#[test]
fn no_future_event_leakage_or_final_score() {
    let events = vec![
        simple("A", "2025-07-15T18:42:10Z", 1, 1, 0, 0, 0),
        simple("Z", "2025-07-15T21:00:00Z", 90, 9, 3, 5, 2),
    ];
    let row = sync_one(&events, &obs("t1", "2025-07-15T18:42:20Z", 80));
    assert_eq!(row.prior_event_id.as_deref(), Some("A"));
    let st = row.game_state.unwrap();
    assert_eq!(st.score_home, 0);
    assert_eq!(st.score_away, 0);
    assert_ne!(st.score_home, 5);
}

#[test]
fn settlement_and_later_runners_do_not_leak() {
    let mut late_after = snap("Z", 9, 3, 4, 1, false, "FINAL");
    late_after.runner_first = Some("future_runner".into());
    let events = vec![
        simple("A", "2025-07-15T18:42:10Z", 1, 1, 0, 0, 0),
        ev(
            "Z",
            "2025-07-15T21:00:00Z",
            90,
            snap("Z", 9, 2, 4, 1, false, "INPROGRESS"),
            late_after,
        ),
    ];
    let row = sync_one(&events, &obs("t1", "2025-07-15T18:42:11Z", 81));
    let st = row.game_state.unwrap();
    assert!(st.runner_first.is_none());
    assert_eq!(st.outs, 0);
    assert_ne!(st.game_status, "FINAL");
}

#[test]
fn scoring_event_does_not_leak_backward() {
    let a = simple("A", "2025-07-15T18:42:10Z", 1, 1, 0, 0, 0);
    let b = ev(
        "B",
        "2025-07-15T18:42:27Z",
        2,
        snap("B", 1, 0, 0, 0, false, "INPROGRESS"),
        snap("B", 1, 0, 1, 0, false, "INPROGRESS"),
    );
    let events = vec![a, b];
    let mid = sync_one(&events, &obs("t1", "2025-07-15T18:42:20Z", 80));
    assert_eq!(mid.game_state.as_ref().unwrap().score_home, 0);
    let at_b = sync_one(&events, &obs("t2", "2025-07-15T18:42:27Z", 80));
    assert_eq!(at_b.synchronization_status, SyncStatus::AtEvent);
    assert_eq!(at_b.pre_event_state.as_ref().unwrap().score_home, 0);
    assert_eq!(at_b.post_event_state.as_ref().unwrap().score_home, 1);
}

#[test]
fn inning_transition_does_not_leak_backward() {
    let events = vec![
        simple("A", "2025-07-15T18:42:10Z", 1, 1, 2, 0, 0),
        simple("B", "2025-07-15T18:50:00Z", 2, 2, 0, 0, 0),
    ];
    let mid = sync_one(&events, &obs("t1", "2025-07-15T18:45:00Z", 80));
    assert_eq!(mid.game_state.as_ref().unwrap().inning, 1);
}

#[test]
fn rain_delay_timestamp_gap() {
    let events = vec![
        ev(
            "A",
            "2025-07-15T18:00:00Z",
            1,
            snap("A", 3, 1, 1, 1, false, "INPROGRESS"),
            snap("A", 3, 1, 1, 1, false, "DELAYED"),
        ),
        ev(
            "B",
            "2025-07-15T20:00:00Z",
            2,
            snap("B", 3, 1, 1, 1, false, "DELAYED"),
            snap("B", 3, 1, 1, 1, false, "INPROGRESS"),
        ),
    ];
    let row = sync_one(&events, &obs("t1", "2025-07-15T19:00:00Z", 80));
    assert_eq!(row.prior_event_id.as_deref(), Some("A"));
    assert_eq!(row.game_state.as_ref().unwrap().game_status, "DELAYED");
    assert_eq!(
        row.synchronization_status,
        SyncStatus::SynchronizedWithTimestampGap
    );
}

#[test]
fn extra_inning_game() {
    let events = vec![
        simple("A", "2025-07-15T18:42:10Z", 1, 9, 2, 3, 3),
        ev(
            "B",
            "2025-07-15T21:10:00Z",
            2,
            snap("B", 10, 0, 3, 3, true, "INPROGRESS"),
            snap("B", 10, 0, 3, 3, true, "INPROGRESS"),
        ),
    ];
    let early = sync_one(&events, &obs("t1", "2025-07-15T18:42:11Z", 80));
    assert!(!early.game_state.as_ref().unwrap().extra_inning);
    let late = sync_one(&events, &obs("t2", "2025-07-15T21:10:00Z", 80));
    assert!(late.game_state.as_ref().unwrap().extra_inning);
    assert_eq!(late.game_state.as_ref().unwrap().inning, 10);
}

#[test]
fn identical_pbp_timestamps_use_canonical_sequence() {
    let events = vec![
        simple("A", "2025-07-15T18:42:10Z", 1, 1, 0, 0, 0),
        simple("B", "2025-07-15T18:42:10Z", 2, 1, 1, 0, 0),
    ];
    let hit = as_of(
        &events,
        ts("2025-07-15T18:42:10Z"),
        game_window(&events).as_ref(),
    )
    .unwrap();
    assert_eq!(hit.matched.event_id, "B");
}

#[test]
fn out_of_order_raw_events_are_sorted() {
    let mut events = vec![
        simple("B", "2025-07-15T18:42:27Z", 2, 1, 1, 0, 0),
        simple("A", "2025-07-15T18:42:10Z", 1, 1, 0, 0, 0),
    ];
    events.sort_by(|a, b| {
        a.normalized_event_time
            .cmp(&b.normalized_event_time)
            .then(a.sequence.cmp(&b.sequence))
    });
    momento_research_sync::timeline::link_event_neighbors(&mut events);
    let row = sync_one(&events, &obs("t1", "2025-07-15T18:42:20Z", 80));
    assert_eq!(row.prior_event_id.as_deref(), Some("A"));
}

#[test]
fn unmatched_and_ambiguous_are_classified_not_joined() {
    let events = timeline();
    let u = synchronize_market_observation(
        SyncParams {
            identity: IdentityStatus::Unmatched,
            first_observed_price_cents: None,
            ..params(&events, IdentityStatus::Unmatched, false)
        },
        &obs("t1", "2025-07-15T18:42:20Z", 80),
    );
    assert_eq!(u.synchronization_status, SyncStatus::IdentityUnmatched);
    assert!(u.game_state.is_none());
    let a = synchronize_market_observation(
        SyncParams {
            identity: IdentityStatus::Ambiguous,
            first_observed_price_cents: None,
            ..params(&events, IdentityStatus::Ambiguous, false)
        },
        &obs("t1", "2025-07-15T18:42:20Z", 80),
    );
    assert_eq!(a.synchronization_status, SyncStatus::IdentityAmbiguous);
}

#[test]
fn empty_timeline_is_source_invalid() {
    let row = sync_one(&[], &obs("t1", "2025-07-15T18:42:20Z", 80));
    assert_eq!(row.synchronization_status, SyncStatus::SourceDataInvalid);
}

#[test]
fn missing_timestamp_retained() {
    let mut o = obs("t1", "2025-07-15T18:42:20Z", 80);
    o.normalized_market_time = None;
    o.source_market_time.clear();
    let row = sync_one(&timeline(), &o);
    assert_eq!(row.synchronization_status, SyncStatus::MissingTimestamp);
    assert!(row.game_state.is_none());
}

#[test]
fn single_event_game() {
    let events = vec![simple("A", "2025-07-15T18:42:10Z", 1, 1, 0, 0, 0)];
    let row = sync_one(&events, &obs("t1", "2025-07-15T18:42:10Z", 80));
    assert_eq!(row.synchronization_status, SyncStatus::AtEvent);
    assert_eq!(row.synchronization_quality, SyncQuality::Exact);
    assert_eq!(row.prior_event_id.as_deref(), Some("A"));
}

#[test]
fn multiple_market_observations_between_plays() {
    let events = timeline();
    let rows = synchronize_market(
        params(&events, IdentityStatus::Matched, false),
        &[
            obs("t1", "2025-07-15T18:42:12Z", 80),
            obs("t2", "2025-07-15T18:42:15Z", 81),
            obs("t3", "2025-07-15T18:42:20Z", 82),
        ],
    );
    assert_eq!(rows.len(), 3);
    assert!(
        rows.iter()
            .all(|r| r.prior_event_id.as_deref() == Some("A"))
    );
    assert_eq!(rows[1].prior_market_observation_id.as_deref(), Some("t1"));
    assert_eq!(rows[1].next_market_observation_id.as_deref(), Some("t3"));
    assert_eq!(rows[0].last_trade_cents, Some(80));
    assert_eq!(rows[2].last_trade_cents, Some(82));
}

#[test]
fn no_price_interpolation() {
    let events = timeline();
    let rows = synchronize_market(
        params(&events, IdentityStatus::Matched, false),
        &[
            obs("t1", "2025-07-15T18:42:12Z", 80),
            obs("t2", "2025-07-15T18:42:20Z", 82),
        ],
    );
    let prices: Vec<_> = rows.iter().map(|r| r.last_trade_cents).collect();
    assert_eq!(prices, vec![Some(80), Some(82)]);
    assert!(!prices.contains(&Some(81)));
}

#[test]
fn two_sides_same_game_independent_timestamps() {
    let events = timeline();
    let a = obs("tA", "2025-07-15T18:42:12Z", 80);
    let mut b = obs("tB", "2025-07-15T18:42:30Z", 20);
    b.market_id = "m2".into();
    b.ticker = "KXMLBGAME-25APR16AAABBB-BBB".into();
    let rows = synchronize_game(
        "g1",
        "1",
        IdentityStatus::Matched,
        &events,
        &[
            ("AAA".into(), vec![a], Some(80)),
            ("BBB".into(), vec![b], Some(20)),
        ],
    );
    assert_eq!(rows.len(), 2);
    assert_eq!(rows[0].prior_event_id.as_deref(), Some("A"));
    assert_eq!(rows[1].prior_event_id.as_deref(), Some("B"));
    assert_eq!(rows[0].game_id, rows[1].game_id);
    assert_ne!(rows[0].market_timestamp_utc, rows[1].market_timestamp_utc);
}

#[test]
fn no_game_id_cross_contamination() {
    let g1 = timeline();
    let g2 = vec![simple("X", "2025-07-15T18:42:10Z", 1, 5, 2, 9, 1)];
    let row = sync_one(&g1, &obs("t1", "2025-07-15T18:42:20Z", 80));
    assert_eq!(row.game_id, "g1");
    assert_ne!(row.prior_event_id.as_deref(), Some("X"));
    assert_eq!(row.game_state.as_ref().unwrap().inning, 1);
    let other = synchronize_market_observation(
        SyncParams {
            game_id: "g2",
            game_pk: "2",
            identity: IdentityStatus::Matched,
            events: &g2,
            contract_side: "BBB",
            first_observed_price_cents: Some(50),
            ambiguous_clock: false,
        },
        &obs("t2", "2025-07-15T18:42:10Z", 50),
    );
    assert_eq!(other.game_id, "g2");
    assert_eq!(other.prior_event_id.as_deref(), Some("X"));
}

#[test]
fn retrieval_time_does_not_order_or_select_state() {
    let events = timeline();
    let mut o = obs("t1", "2025-07-15T18:42:20Z", 80);
    o.retrieval_time = Some(ts("2025-07-15T18:50:00Z"));
    let row = sync_one(&events, &o);
    assert_eq!(row.prior_event_id.as_deref(), Some("A"));
    assert_eq!(row.retrieval_timestamp, o.retrieval_time);
    assert_eq!(row.market_timestamp_source, "2025-07-15T18:42:20Z");
}

#[test]
fn no_synthetic_quotes_or_open_or_starting_price_label() {
    let events = timeline();
    let row = sync_one(&events, &obs("t1", "2025-07-15T18:42:20Z", 80));
    assert_eq!(row.observation_type, ObservationType::Trade);
    assert!(row.game_state.is_some());
    let o = obs("t1", "2025-07-15T18:42:20Z", 80);
    assert!(o.yes_bid_cents.is_none());
    assert!(o.yes_ask_cents.is_none());
    assert_eq!(row.first_observed_price_cents, Some(80));
    let json = serde_json::to_string(&row).unwrap();
    assert!(!json.contains("market_open_price"));
    assert!(!json.contains("starting_price"));
    assert!(!json.contains("L2_SNAPSHOT"));
}

#[test]
fn deterministic_and_idempotent_store() {
    let events = timeline();
    let obs_a = obs("t1", "2025-07-15T18:42:20Z", 80);
    let a = synchronize_market(
        params(&events, IdentityStatus::Matched, false),
        std::slice::from_ref(&obs_a),
    );
    let b = synchronize_market(params(&events, IdentityStatus::Matched, false), &[obs_a]);
    assert_eq!(a, b);
    let t = Utc.with_ymd_and_hms(2026, 8, 26, 12, 0, 0).unwrap();
    let mut store = SyncStore::open_memory("run1", t).unwrap();
    store.insert_batch(&a).unwrap();
    store.insert_batch(&a).unwrap();
    let got = store.observations_for_game("g1").unwrap();
    assert_eq!(got.len(), 1);
    assert_eq!(got[0].synchronization_id, a[0].synchronization_id);
    assert!(!store.observations_for_market("m1").unwrap().is_empty());
    let interval = store.observations_for_event_interval("g1", "A").unwrap();
    assert_eq!(interval.len(), 1);
}

#[test]
fn two_pointer_matches_binary_search() {
    let events = timeline();
    let times = vec![
        ts("2025-07-15T18:42:10Z"),
        ts("2025-07-15T18:42:20Z"),
        ts("2025-07-15T18:42:27Z"),
        ts("2025-07-15T19:00:00Z"),
    ];
    let idx = two_pointer_indexes(&events, &times);
    assert_eq!(idx, vec![Some(0), Some(0), Some(1), None]);
}

#[test]
fn provenance_and_source_timestamp_preserved() {
    let events = timeline();
    let row = sync_one(&events, &obs("t1", "2025-07-15T18:42:20Z", 80));
    assert_eq!(row.source_lineage, "fixture");
    assert_eq!(row.market_timestamp_source, "2025-07-15T18:42:20Z");
    assert_eq!(row.source_timestamp_kind, KIND_KALSHI_TRADE_CREATED);
    assert!(!row.dataset_version.is_empty());
}

#[test]
fn duplicate_pbp_clock_is_ambiguous_not_guessed() {
    let events = timeline();
    let row = synchronize_market_observation(
        params(&events, IdentityStatus::Matched, true),
        &obs("t1", "2025-07-15T18:42:20Z", 80),
    );
    assert_eq!(row.synchronization_status, SyncStatus::AmbiguousTimestamp);
    assert!(row.game_state.is_none());
}

#[test]
fn firewall_forbids_w6_and_greeks() {
    let lib = include_str!("../src/lib.rs");
    for bad in W5_FORBIDDEN_CONCEPTS {
        assert!(!lib.contains(bad), "{bad}");
    }
    assert_eq!(WATERFALL, "CTO-W5");
}

#[test]
fn sidecar_rejects_wrong_ticker_and_keeps_trades_as_trades() {
    use momento_research_sync::market::parse_sidecar;
    let v = json!({
        "ticker": "OTHER",
        "retrieved_at": "2026-08-26T19:00:00Z",
        "trades": []
    });
    assert!(parse_sidecar(&v, "KXMLBGAME-X-AAA", "1", std::path::Path::new("x")).is_err());
    let ok = json!({
        "ticker": "KXMLBGAME-X-AAA",
        "retrieved_at": "2026-08-26T19:00:00Z",
        "trades": [{
            "trade_id": "t1",
            "ticker": "KXMLBGAME-X-AAA",
            "created_time": "2025-07-15T18:42:20Z",
            "yes_price_dollars": "0.8000",
            "count_fp": "1.00"
        },{
            "trade_id": "t1",
            "ticker": "KXMLBGAME-X-AAA",
            "created_time": "2025-07-15T18:42:20Z",
            "yes_price_dollars": "0.8000"
        },{
            "trade_id": "t2",
            "ticker": "KXMLBGAME-X-AAA",
            "yes_price_dollars": "0.8100"
        }]
    });
    let tape = parse_sidecar(&ok, "KXMLBGAME-X-AAA", "1", std::path::Path::new("x"))
        .unwrap()
        .unwrap();
    assert_eq!(tape.duplicates_dropped, 1);
    assert_eq!(tape.missing_timestamps, 1);
    assert_eq!(tape.observations.len(), 2);
    assert_eq!(
        tape.observations[1].observation_type,
        ObservationType::Trade
    );
    assert!(tape.observations.iter().all(|o| o.yes_bid_cents.is_none()));
    assert_eq!(tape.first_observed_price_cents, Some(80));
}

#[test]
fn production_fence() {
    let toml = include_str!("../Cargo.toml");
    assert!(!toml.contains("momento-risk"));
    assert!(!toml.contains("momento-execution"));
    assert!(!toml.contains("momento-strategy-mlb"));
    assert!(!toml.contains("momento-kalshi"));
}
