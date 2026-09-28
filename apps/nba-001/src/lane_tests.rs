//! Full-trade lane scenarios on the fixture exchange. The policies here are
//! test inputs that exercise each branch; none is an approved contract value.

use momento_strategy_nba::{EmergencyPolicy, HedgeAction, OrderStatus, PlanStep};

use crate::executor::{ExecEvent, Sink};
use crate::fake::{FakeExchange, Fault};
use crate::lane::{
    ExecutionLane, GameExec, GapPolicy, LadderPolicy, LanePolicy, OutageAction, OutagePolicy,
};
use crate::venue::NbaVenue;

const EV: &str = "KXNBAGAME-26OCT03AAABBB";
const ORIG: &str = "KXNBAGAME-26OCT03AAABBB-AAA";
const OPP: &str = "KXNBAGAME-26OCT03AAABBB-BBB";
const Q: u32 = 1538;

fn ok_sink() -> impl FnMut(&momento_strategy_nba::GameBook, ExecEvent) -> Result<(), String> {
    |_, _| Ok(())
}

fn test_policy() -> LanePolicy {
    LanePolicy {
        entry_post_only: true,
        entry_expiry_s: Some(600),
        gap: Some(GapPolicy::ObservedClose),
        ladder: Some(LadderPolicy::RepriceOnClose),
        emergency: EmergencyPolicy::SellOriginal { floor_cents: 1 },
        outage: Some(OutagePolicy {
            escalate_after_s: 300,
            action: OutageAction::HedgeAtCap,
        }),
        subaccount: None,
    }
}

fn lane(policy: LanePolicy) -> ExecutionLane<FakeExchange> {
    let mut fx = FakeExchange::default();
    fx.book(ORIG, 76, 0, 80, 0);
    fx.book(OPP, 20, 0, 50, 0);
    ExecutionLane::new(NbaVenue::fixture(fx), policy)
}

fn fx(l: &mut ExecutionLane<FakeExchange>) -> &mut FakeExchange {
    l.venue.transport_mut()
}

fn step(l: &mut ExecutionLane<FakeExchange>, now: i64) -> PlanStep {
    let mut s = ok_sink();
    let sink: &mut Sink<'_> = &mut s;
    l.step(EV, now, sink).unwrap()
}

/// Entry posted and fully filled by counterparties.
fn entered(policy: LanePolicy) -> ExecutionLane<FakeExchange> {
    let mut l = lane(policy);
    let mut s = ok_sink();
    l.enter(EV, ORIG, OPP, Q, 0, &mut s).unwrap();
    let cid = l.games[EV].book.orders[0].spec.client_order_id.clone();
    let vid = l.games[EV].book.orders[0].venue_order_id.clone().unwrap();
    assert!(cid.starts_with("nba001-"));
    fx(&mut l).trade_against(&vid, Q);
    step(&mut l, 1);
    assert_eq!(l.games[EV].exec, GameExec::Holding);
    l
}

fn hedge_order(l: &ExecutionLane<FakeExchange>) -> momento_strategy_nba::OrderRecord {
    l.games[EV]
        .book
        .orders
        .iter()
        .rev()
        .find(|o| o.spec.ticker == OPP)
        .unwrap()
        .clone()
}

// Example 1: first stop close at 67.
#[test]
fn stop_at_67_bids_33_for_the_full_position() {
    let mut l = entered(test_policy());
    assert!(matches!(l.on_close(EV, 70), Some(HedgeAction::None)));
    assert!(matches!(
        l.on_close(EV, 68),
        Some(HedgeAction::LocalPrepared { .. })
    ));
    assert_eq!(step(&mut l, 2), PlanStep::Nothing, "68 sends nothing");
    assert_eq!(fx(&mut l).orders.len(), 1);
    l.on_close(EV, 67);
    assert_eq!(l.games[EV].exec, GameExec::Hedging { limit_cents: 33 });
    let PlanStep::Submit(s) = step(&mut l, 3) else {
        panic!()
    };
    assert_eq!((s.ticker.as_str(), s.price_cents, s.count), (OPP, 33, Q));
    assert!(!s.cancel_order_on_pause);
    let h = hedge_order(&l);
    assert_eq!(h.status, OrderStatus::Resting);
}

// Example 2: first stop close gaps to 60.
#[test]
fn gap_to_60_starts_at_40_under_observed_close_or_33_under_first_rung() {
    let mut l = entered(test_policy());
    l.on_close(EV, 60);
    assert_eq!(l.games[EV].exec, GameExec::Hedging { limit_cents: 40 });
    let PlanStep::Submit(s) = step(&mut l, 2) else {
        panic!()
    };
    assert_eq!((s.price_cents, s.count), (40, Q));

    let mut p = test_policy();
    p.gap = Some(GapPolicy::FirstRung);
    let mut l = entered(p);
    l.on_close(EV, 60);
    assert_eq!(l.games[EV].exec, GameExec::Hedging { limit_cents: 33 });

    let mut p = test_policy();
    p.gap = None;
    let mut l = entered(p);
    l.on_close(EV, 60);
    assert!(matches!(l.games[EV].exec, GameExec::Hold { ref reason } if reason.contains("gap")));
    assert!(matches!(step(&mut l, 2), PlanStep::Hold { .. }));
    assert_eq!(
        fx(&mut l).orders.len(),
        1,
        "no hedge order without a gap policy"
    );
}

// Ladder: a resting hedge is raised in place with a total cap.
#[test]
fn ladder_reprices_upward_with_amend() {
    let mut l = entered(test_policy());
    l.on_close(EV, 67);
    step(&mut l, 2);
    let vid = hedge_order(&l).venue_order_id.unwrap();
    fx(&mut l).trade_against(&vid, 400);
    l.on_close(EV, 64);
    assert_eq!(l.games[EV].exec, GameExec::Hedging { limit_cents: 36 });
    assert_eq!(
        step(&mut l, 3),
        PlanStep::Amend {
            client_order_id: hedge_order(&l).spec.client_order_id,
            price_cents: 36,
            total_count: Q
        }
    );
    assert_eq!(hedge_order(&l).spec.price_cents, 36);
    // A bounce never lowers the limit.
    l.on_close(EV, 66);
    assert_eq!(l.games[EV].exec, GameExec::Hedging { limit_cents: 36 });
    assert_eq!(step(&mut l, 4), PlanStep::Nothing);
}

// Example 3: first stop close below 55.
#[test]
fn first_close_below_55_goes_straight_to_emergency() {
    let mut l = entered(test_policy());
    fx(&mut l).book(ORIG, 50, 5000, 52, 0);
    l.on_close(EV, 50);
    assert_eq!(l.games[EV].exec, GameExec::Emergency);
    let PlanStep::Submit(s) = step(&mut l, 2) else {
        panic!()
    };
    assert_eq!(
        (s.ticker.as_str(), s.count, s.price_cents, s.reduce_only),
        (ORIG, Q, 1, true)
    );
    // Sold into the 50c bid (depth 5000): fully flat.
    assert_eq!(step(&mut l, 3), PlanStep::Flat { hedged_pairs: 0 });
    assert_eq!(l.venue.position(ORIG).unwrap(), 0);

    let mut p = test_policy();
    p.emergency = EmergencyPolicy::Unresolved;
    let mut l = entered(p);
    l.on_close(EV, 50);
    assert_eq!(step(&mut l, 2), PlanStep::PolicyUnresolved { unhedged: Q });
    assert!(
        matches!(l.games[EV].exec, GameExec::Hold { ref reason } if reason.contains("emergency"))
    );
}

// Example 4 + 5: partial hedge, then emergency with a late hedge fill.
#[test]
fn partial_hedge_then_emergency_with_late_fill() {
    let mut l = entered(test_policy());
    l.on_close(EV, 60);
    step(&mut l, 2);
    let vid = hedge_order(&l).venue_order_id.unwrap();
    fx(&mut l).trade_against(&vid, 600);
    fx(&mut l).book(ORIG, 40, 10_000, 42, 0);
    l.on_close(EV, 54);
    assert_eq!(l.games[EV].exec, GameExec::Emergency);
    fx(&mut l).fault("DELETE", Fault::FillBeforeCancel { count: 150 });
    assert!(matches!(step(&mut l, 3), PlanStep::CancelWorking { .. }));
    // Cancel confirmed reduced_by = 788 → final 750; records owed.
    assert!(matches!(step(&mut l, 4), PlanStep::Submit(ref s) if s.count == 788));
    assert_eq!(step(&mut l, 5), PlanStep::Flat { hedged_pairs: 750 });
    assert_eq!(l.venue.position(ORIG).unwrap(), 750);
    assert_eq!(l.venue.position(OPP).unwrap(), 750);
}

// Example 6: data outage with an open position.
#[test]
fn outage_escalates_only_under_a_policy() {
    let mut p = test_policy();
    p.outage = None;
    let mut l = entered(p);
    l.on_outage(EV, 180);
    assert!(matches!(l.games[EV].exec, GameExec::Hold { ref reason } if reason.contains("outage")));

    let mut l = entered(test_policy());
    l.on_close(EV, 67);
    step(&mut l, 2);
    l.on_outage(EV, 299);
    assert_eq!(l.games[EV].exec, GameExec::Hedging { limit_cents: 33 });
    l.on_outage(EV, 300);
    assert_eq!(l.games[EV].exec, GameExec::Hedging { limit_cents: 45 });
    assert!(matches!(
        step(&mut l, 3),
        PlanStep::Amend {
            price_cents: 45,
            total_count: Q,
            ..
        }
    ));
}

#[test]
fn inconsistent_venue_evidence_holds_the_lane() {
    let mut l = entered(test_policy());
    l.on_close(EV, 67);
    step(&mut l, 2);
    let vid = hedge_order(&l).venue_order_id.unwrap();
    fx(&mut l).trade_against(&vid, 10);
    // Venue reports an order with more fills than its cap: corrupt the fake.
    let o = fx(&mut l).orders.iter_mut().find(|o| o.id == vid).unwrap();
    o.fills.push(o.fills[0].clone());
    o.fills.last_mut().unwrap().id = "dup-count".into();
    o.fills.last_mut().unwrap().count = Q;
    let mut s = ok_sink();
    assert!(l.step(EV, 3, &mut s).is_err());
    assert!(matches!(l.games[EV].exec, GameExec::Hold { .. }));
}

#[test]
fn one_entry_per_game() {
    let mut l = entered(test_policy());
    let mut s = ok_sink();
    assert!(l.enter(EV, ORIG, OPP, Q, 5, &mut s).is_err());
}
