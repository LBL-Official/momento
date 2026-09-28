//! Order state machine and per-game exposure: fills, partials, cancel races,
//! duplicates, ambiguity, overfill, and the reconcile-before-emergency rule.

use momento_strategy_nba::*;

const ORIG: &str = "KXNBAGAME-26OCT03AAABBB-AAA";
const OPP: &str = "KXNBAGAME-26OCT03AAABBB-BBB";

fn spec(
    id: &str,
    role: OrderRole,
    ticker: &str,
    side: BookSide,
    price: u16,
    count: u32,
) -> OrderSpec {
    OrderSpec {
        client_order_id: id.into(),
        role,
        ticker: ticker.into(),
        side,
        price_cents: price,
        count,
        tif: TimeInForce::GoodTillCanceled,
        post_only: role == OrderRole::Entry,
        reduce_only: false,
        expiration_ts: None,
        cancel_order_on_pause: false,
        subaccount: None,
    }
}

fn fill(id: &str, n: u32, price: u16) -> OrderEvent {
    OrderEvent::Fill(Fill {
        fill_id: id.into(),
        count: n,
        yes_price_centicents: u32::from(price) * 100,
        is_taker: Some(false),
        fee_centicents: Some(0),
        ts: 0,
    })
}

fn acked(o: &mut OrderRecord, fill_count: u32, remaining: u32) {
    o.apply(0, OrderEvent::Sending).unwrap();
    o.apply(
        1,
        OrderEvent::Acked {
            venue_order_id: format!("v-{}", o.spec.client_order_id),
            fill_count,
            remaining_count: remaining,
        },
    )
    .unwrap();
}

fn entry(count: u32) -> OrderRecord {
    OrderRecord::new(spec("e1", OrderRole::Entry, ORIG, BookSide::Bid, 78, count)).unwrap()
}

fn hedge(id: &str, price: u16, count: u32) -> OrderRecord {
    OrderRecord::new(spec(id, OrderRole::Hedge, OPP, BookSide::Bid, price, count)).unwrap()
}

// ---------- spec validation ----------

#[test]
fn spec_rejects_malformed_orders() {
    let ok = spec("nba001-abc", OrderRole::Hedge, OPP, BookSide::Bid, 33, 10);
    assert_eq!(ok.validate(), Ok(()));
    let mut s = ok.clone();
    s.price_cents = 0;
    assert_eq!(s.validate(), Err(SpecError::PriceOutOfRange(0)));
    s.price_cents = 100;
    assert_eq!(s.validate(), Err(SpecError::PriceOutOfRange(100)));
    let mut s = ok.clone();
    s.count = 0;
    assert_eq!(s.validate(), Err(SpecError::ZeroCount));
    let mut s = ok.clone();
    s.reduce_only = true;
    assert_eq!(s.validate(), Err(SpecError::ReduceOnlyRequiresIoc));
    let mut s = ok.clone();
    s.tif = TimeInForce::ImmediateOrCancel;
    s.expiration_ts = Some(1);
    assert_eq!(s.validate(), Err(SpecError::ExpirationRequiresGtc));
    let mut s = ok.clone();
    s.tif = TimeInForce::ImmediateOrCancel;
    s.post_only = true;
    assert_eq!(s.validate(), Err(SpecError::PostOnlyWithImmediate));
    let mut s = ok.clone();
    s.client_order_id = "has space".into();
    assert_eq!(s.validate(), Err(SpecError::ClientIdInvalid));
    let mut s = ok;
    s.subaccount = Some(64);
    assert_eq!(s.validate(), Err(SpecError::SubaccountOutOfRange(64)));
}

// ---------- fills ----------

#[test]
fn full_fill_on_ack() {
    let mut o = entry(10);
    acked(&mut o, 10, 0);
    assert_eq!(o.status, OrderStatus::Filled);
    assert!(!o.is_settled(), "fill records not yet received");
    o.apply(2, fill("f1", 10, 78)).unwrap();
    assert!(o.is_settled());
    assert_eq!(o.confirmed_filled(), 10);
}

#[test]
fn partial_then_complete_fill_while_resting() {
    let mut o = entry(10);
    acked(&mut o, 0, 10);
    assert_eq!(o.status, OrderStatus::Resting);
    o.apply(2, fill("f1", 4, 78)).unwrap();
    assert_eq!(o.status, OrderStatus::Resting);
    assert_eq!(o.potential_additional(), 6);
    o.apply(3, fill("f2", 6, 78)).unwrap();
    assert_eq!(o.status, OrderStatus::Filled);
    assert!(o.is_settled());
}

#[test]
fn no_fill_then_cancel() {
    let mut o = entry(10);
    acked(&mut o, 0, 10);
    o.apply(2, OrderEvent::CancelSent).unwrap();
    assert_eq!(o.status, OrderStatus::CancelRequested);
    assert_eq!(o.potential_additional(), 10, "still live until confirmed");
    o.apply(3, OrderEvent::CancelAcked { reduced_by: 10 })
        .unwrap();
    assert_eq!(o.status, OrderStatus::Cancelled);
    assert!(o.is_settled());
    assert_eq!(o.confirmed_filled(), 0);
}

#[test]
fn ioc_remainder_is_cancelled_with_partial_fill() {
    let mut o = OrderRecord::new(OrderSpec {
        tif: TimeInForce::ImmediateOrCancel,
        post_only: false,
        ..spec("x1", OrderRole::Emergency, ORIG, BookSide::Ask, 1, 10)
    })
    .unwrap();
    acked(&mut o, 7, 0);
    assert_eq!(o.status, OrderStatus::Cancelled);
    assert!(o.final_count_known);
    assert_eq!(o.venue_fill_count, 7);
}

#[test]
fn duplicate_fill_and_duplicate_ack_are_ignored_or_refused() {
    let mut o = entry(10);
    acked(&mut o, 0, 10);
    o.apply(2, fill("f1", 4, 78)).unwrap();
    o.apply(3, fill("f1", 4, 78)).unwrap();
    assert_eq!(o.confirmed_filled(), 4);
    let dup_ack = o.apply(
        4,
        OrderEvent::Acked {
            venue_order_id: "v-e1".into(),
            fill_count: 0,
            remaining_count: 10,
        },
    );
    assert!(matches!(dup_ack, Err(OrderError::InvalidTransition { .. })));
    assert_eq!(o.status, OrderStatus::Resting);
}

#[test]
fn overfill_holds_and_never_repairs() {
    let mut o = entry(10);
    acked(&mut o, 0, 10);
    o.apply(2, fill("f1", 8, 78)).unwrap();
    let r = o.apply(3, fill("f2", 3, 78));
    assert_eq!(
        r,
        Err(OrderError::Overfill {
            max: 10,
            would_be: 11
        })
    );
    assert!(matches!(o.status, OrderStatus::Inconsistent { .. }));
    assert!(
        o.apply(4, OrderEvent::CancelAcked { reduced_by: 0 })
            .is_err()
    );
    assert!(matches!(o.status, OrderStatus::Inconsistent { .. }));
}

// ---------- ambiguity and reconciliation ----------

#[test]
fn timeout_is_unknown_not_rejected_then_found() {
    let mut o = entry(10);
    o.apply(0, OrderEvent::Sending).unwrap();
    o.apply(
        1,
        OrderEvent::Ambiguous {
            reason: "timeout".into(),
        },
    )
    .unwrap();
    assert!(matches!(o.status, OrderStatus::Unknown { .. }));
    assert_eq!(o.potential_additional(), 10);
    o.apply(
        2,
        OrderEvent::Snapshot {
            venue_order_id: "v1".into(),
            status: VenueStatus::Resting,
            fill_count: 3,
            remaining_count: 7,
        },
    )
    .unwrap();
    assert_eq!(o.status, OrderStatus::Resting);
    assert_eq!(o.confirmed_filled(), 3);
}

#[test]
fn timeout_then_proven_absent_is_rejected_without_exposure() {
    let mut o = entry(10);
    o.apply(0, OrderEvent::Sending).unwrap();
    o.apply(
        1,
        OrderEvent::Ambiguous {
            reason: "503".into(),
        },
    )
    .unwrap();
    o.apply(2, OrderEvent::NotFoundOnVenue).unwrap();
    assert!(matches!(
        o.status,
        OrderStatus::Rejected { http_status: 0, .. }
    ));
    assert!(o.is_settled());
}

#[test]
fn not_found_with_evidence_is_inconsistent() {
    let mut o = entry(10);
    acked(&mut o, 0, 10);
    o.apply(2, OrderEvent::Ambiguous { reason: "x".into() })
        .unwrap();
    assert!(o.apply(3, OrderEvent::NotFoundOnVenue).is_err());
    assert!(matches!(o.status, OrderStatus::Inconsistent { .. }));
}

#[test]
fn rejected_order_has_no_exposure() {
    let mut o = entry(10);
    o.apply(0, OrderEvent::Sending).unwrap();
    o.apply(
        1,
        OrderEvent::Rejected {
            http_status: 400,
            code: "insufficient_balance".into(),
        },
    )
    .unwrap();
    assert!(o.is_settled());
    assert_eq!(o.potential_additional(), 0);
    let late = o.apply(2, fill("f1", 1, 78));
    assert!(late.is_err());
    assert!(matches!(o.status, OrderStatus::Inconsistent { .. }));
}

#[test]
fn local_refusal_never_left_the_process() {
    let mut o = entry(10);
    o.apply(
        0,
        OrderEvent::LocalRefusal {
            reason: "PRODUCTION_ORDERS_NOT_COMPILED".into(),
        },
    )
    .unwrap();
    assert!(matches!(o.status, OrderStatus::NotSent { .. }));
    assert!(o.is_settled());
}

// ---------- cancel races ----------

#[test]
fn late_fill_during_cancel_is_counted_from_reduced_by() {
    let mut h = hedge("h1", 33, 1538);
    acked(&mut h, 0, 1538);
    h.apply(2, fill("f1", 600, 33)).unwrap();
    h.apply(3, OrderEvent::CancelSent).unwrap();
    // 200 more filled before the cancel was processed: reduced_by = 738.
    h.apply(4, OrderEvent::CancelAcked { reduced_by: 738 })
        .unwrap();
    assert_eq!(h.status, OrderStatus::Cancelled);
    assert_eq!(h.venue_fill_count, 800);
    assert!(!h.is_settled(), "200 fill records still owed");
    h.apply(5, fill("f2", 200, 33)).unwrap();
    assert_eq!(h.late_fill_count, 200);
    assert!(h.is_settled());
    assert_eq!(h.confirmed_filled(), 800);
}

#[test]
fn cancel_404_means_final_count_unknown_until_snapshot() {
    let mut h = hedge("h1", 33, 100);
    acked(&mut h, 0, 100);
    h.apply(2, OrderEvent::CancelSent).unwrap();
    h.apply(3, OrderEvent::CancelNotFound).unwrap();
    assert!(matches!(h.status, OrderStatus::Unknown { .. }));
    assert_eq!(h.potential_additional(), 100);
    h.apply(
        4,
        OrderEvent::Snapshot {
            venue_order_id: "v-h1".into(),
            status: VenueStatus::Executed,
            fill_count: 100,
            remaining_count: 0,
        },
    )
    .unwrap();
    assert_eq!(h.status, OrderStatus::Filled);
}

#[test]
fn cancel_reduced_by_contradicting_fill_records_holds() {
    let mut h = hedge("h1", 33, 100);
    acked(&mut h, 0, 100);
    h.apply(2, fill("f1", 50, 33)).unwrap();
    h.apply(3, OrderEvent::CancelSent).unwrap();
    assert!(
        h.apply(4, OrderEvent::CancelAcked { reduced_by: 60 })
            .is_err()
    );
    assert!(matches!(h.status, OrderStatus::Inconsistent { .. }));
}

#[test]
fn amend_caps_total_so_a_race_cannot_overfill() {
    let mut h = hedge("h1", 33, 1538);
    acked(&mut h, 0, 1538);
    h.apply(2, fill("f1", 500, 33)).unwrap();
    h.apply(
        3,
        OrderEvent::Amended {
            price_cents: 34,
            max_count: 1538,
            client_order_id: None,
        },
    )
    .unwrap();
    assert_eq!(h.spec.price_cents, 34);
    assert_eq!(h.potential_additional(), 1038);
    // A fill beyond the total cap is an overfill, never silently accepted.
    assert!(h.apply(4, fill("f2", 1039, 34)).is_err());
}

// Behaviour change (2026-09-27, demo evidence + create/amend V2 docs): the
// amend response's fill_count counts only fills caused by the amend and is
// omitted when the size is unchanged. The event no longer carries counts, so
// an amend after earlier fills must not read as "fewer fills than recorded".
#[test]
fn amend_after_prior_fills_is_not_a_contradiction() {
    let mut h = hedge("h1", 33, 1538);
    acked(&mut h, 0, 1538);
    h.apply(2, fill("f1", 400, 33)).unwrap();
    h.apply(
        3,
        OrderEvent::Amended {
            price_cents: 36,
            max_count: 1538,
            client_order_id: None,
        },
    )
    .unwrap();
    assert_eq!(h.status, OrderStatus::Resting);
    assert_eq!(h.confirmed_filled(), 400);
    assert_eq!(h.potential_additional(), 1138);
}

#[test]
fn amend_total_below_confirmed_fills_holds() {
    let mut h = hedge("h1", 33, 1538);
    acked(&mut h, 0, 1538);
    h.apply(2, fill("f1", 400, 33)).unwrap();
    assert!(
        h.apply(
            3,
            OrderEvent::Amended {
                price_cents: 36,
                max_count: 399,
                client_order_id: None,
            },
        )
        .is_err()
    );
    assert!(matches!(h.status, OrderStatus::Inconsistent { .. }));
}

// ---------- exposure and residual ----------

fn book_with(orders: Vec<OrderRecord>) -> GameBook {
    let mut b = GameBook::new("EV", ORIG, OPP);
    b.orders = orders;
    b
}

fn filled_entry(n: u32) -> OrderRecord {
    let mut e = entry(n);
    acked(&mut e, 0, n);
    e.apply(2, fill("ef", n, 78)).unwrap();
    e
}

#[test]
fn residual_requires_every_order_settled() {
    let mut h = hedge("h1", 33, 1538);
    acked(&mut h, 0, 1538);
    h.apply(2, fill("hf1", 600, 33)).unwrap();
    let b = book_with(vec![filled_entry(1538), h]);
    let e = b.exposure();
    assert_eq!(e.original_long, 1538);
    assert_eq!(e.opponent_long, 600);
    assert_eq!(e.unhedged_original, 938);
    assert_eq!(e.potential_opponent_buy, 938);
    assert!(matches!(
        b.reconciled_residual(),
        Residual::NotReconciled { .. }
    ));
}

#[test]
fn partial_hedge_then_emergency_cancels_reconciles_then_sells_residual_only() {
    let mut h = hedge("h1", 45, 1538);
    acked(&mut h, 0, 1538);
    h.apply(2, fill("hf1", 600, 45)).unwrap();
    let mut b = book_with(vec![filled_entry(1538), h]);
    let policy = EmergencyPolicy::SellOriginal { floor_cents: 1 };

    // 1. Working hedge → cancel first.
    assert_eq!(
        b.plan_emergency(policy, "x1", None),
        PlanStep::CancelWorking {
            client_order_ids: vec!["h1".into()]
        }
    );
    b.order_mut("h1")
        .unwrap()
        .apply(3, OrderEvent::CancelSent)
        .unwrap();
    // 2. Cancel in flight → wait; no sale on a stale 938.
    assert!(matches!(
        b.plan_emergency(policy, "x1", None),
        PlanStep::AwaitReconciliation { .. }
    ));
    // 3. Cancel confirms 150 more filled late (reduced_by 788).
    b.order_mut("h1")
        .unwrap()
        .apply(4, OrderEvent::CancelAcked { reduced_by: 788 })
        .unwrap();
    assert!(matches!(
        b.plan_emergency(policy, "x1", None),
        PlanStep::AwaitReconciliation { .. }
    ));
    b.order_mut("h1")
        .unwrap()
        .apply(5, fill("hf2", 150, 45))
        .unwrap();
    // 4. Reconciled: 1538 − 750 = 788, not 938.
    assert_eq!(
        b.reconciled_residual(),
        Residual::Reconciled {
            original_long: 1538,
            opponent_long: 750,
            unhedged: 788
        }
    );
    let PlanStep::Submit(sale) = b.plan_emergency(policy, "x1", None) else {
        panic!("expected sale");
    };
    assert_eq!(sale.ticker, ORIG);
    assert_eq!(sale.side, BookSide::Ask);
    assert_eq!(sale.count, 788);
    assert_eq!(sale.price_cents, 1);
    assert!(sale.reduce_only);
    assert_eq!(sale.tif, TimeInForce::ImmediateOrCancel);
    assert_eq!(sale.validate(), Ok(()));
}

#[test]
fn emergency_policy_unresolved_never_submits() {
    let b = book_with(vec![filled_entry(100)]);
    assert_eq!(
        b.plan_emergency(EmergencyPolicy::Unresolved, "x1", None),
        PlanStep::PolicyUnresolved { unhedged: 100 }
    );
}

#[test]
fn emergency_buy_opponent_uses_bound_and_residual() {
    let b = book_with(vec![filled_entry(100)]);
    let PlanStep::Submit(s) = b.plan_emergency(
        EmergencyPolicy::BuyOpponent {
            worst_price_cents: 55,
        },
        "x1",
        Some(1),
    ) else {
        panic!()
    };
    assert_eq!(
        (s.ticker.as_str(), s.side, s.count, s.price_cents),
        (OPP, BookSide::Bid, 100, 55)
    );
    assert_eq!(s.subaccount, Some(1));
}

#[test]
fn over_hedge_holds_without_automatic_action() {
    let mut h = hedge("h1", 33, 120);
    acked(&mut h, 120, 0);
    h.apply(2, fill("hf", 120, 33)).unwrap();
    let b = book_with(vec![filled_entry(100), h]);
    assert_eq!(b.reconciled_residual(), Residual::OverHedged { excess: 20 });
    assert!(matches!(
        b.plan_emergency(EmergencyPolicy::SellOriginal { floor_cents: 1 }, "x", None),
        PlanStep::Hold { .. }
    ));
}

#[test]
fn inconsistent_order_holds_the_game() {
    let mut e = entry(10);
    acked(&mut e, 0, 10);
    e.apply(2, fill("a", 8, 78)).unwrap();
    let _ = e.apply(3, fill("b", 8, 78));
    let b = book_with(vec![e]);
    assert!(matches!(
        b.reconciled_residual(),
        Residual::Inconsistent { .. }
    ));
    assert!(matches!(b.plan_hedge(33, "h", None), PlanStep::Hold { .. }));
}

#[test]
fn fully_hedged_is_flat() {
    let mut h = hedge("h1", 33, 100);
    acked(&mut h, 100, 0);
    h.apply(2, fill("hf", 100, 33)).unwrap();
    let b = book_with(vec![filled_entry(100), h]);
    assert_eq!(
        b.plan_emergency(EmergencyPolicy::SellOriginal { floor_cents: 1 }, "x", None),
        PlanStep::Flat { hedged_pairs: 100 }
    );
}

// ---------- hedge planner ----------

#[test]
fn hedge_cancels_a_working_entry_first() {
    let mut e = entry(1538);
    acked(&mut e, 0, 1538);
    e.apply(2, fill("ef", 900, 78)).unwrap();
    let b = book_with(vec![e]);
    assert_eq!(
        b.plan_hedge(33, "h1", None),
        PlanStep::CancelWorking {
            client_order_ids: vec!["e1".into()]
        }
    );
}

#[test]
fn hedge_sizes_to_confirmed_original_and_amends_with_total_cap() {
    let mut b = book_with(vec![filled_entry(1538)]);
    let PlanStep::Submit(s) = b.plan_hedge(40, "h1", None) else {
        panic!()
    };
    assert_eq!((s.count, s.price_cents, s.side), (1538, 40, BookSide::Bid));
    assert!(!s.post_only && !s.cancel_order_on_pause);
    let mut h = OrderRecord::new(s).unwrap();
    acked(&mut h, 0, 1538);
    h.apply(2, fill("hf1", 500, 40)).unwrap();
    b.orders.push(h);
    // Same limit → nothing to do.
    assert_eq!(b.plan_hedge(40, "h2", None), PlanStep::Nothing);
    // Ladder rises to 42 → amend in place, total = 500 filled + 1038 need.
    assert_eq!(
        b.plan_hedge(42, "h2", None),
        PlanStep::Amend {
            client_order_id: "h1".into(),
            price_cents: 42,
            total_count: 1538
        }
    );
    // A lower ladder price never lowers the resting limit.
    assert_eq!(b.plan_hedge(35, "h2", None), PlanStep::Nothing);
}

#[test]
fn hedge_waits_while_any_order_is_unknown() {
    let mut h = hedge("h1", 33, 100);
    h.apply(0, OrderEvent::Sending).unwrap();
    h.apply(
        1,
        OrderEvent::Ambiguous {
            reason: "timeout".into(),
        },
    )
    .unwrap();
    let b = book_with(vec![filled_entry(100), h]);
    assert!(matches!(
        b.plan_hedge(40, "h2", None),
        PlanStep::AwaitReconciliation { .. }
    ));
}

// ---------- stale reads (demo evidence 2026-09-27) ----------

fn snap(status: VenueStatus, fill_count: u32, remaining_count: u32, vid: &str) -> OrderEvent {
    OrderEvent::Snapshot {
        venue_order_id: vid.into(),
        status,
        fill_count,
        remaining_count,
    }
}

fn amend(total: u32, price: u16) -> OrderEvent {
    OrderEvent::Amended {
        price_cents: price,
        max_count: total,
        client_order_id: None,
    }
}

// Demo run 3: rest 2, amend total to 1, the lagging GET still shows 0 + 2,
// cancel reduced_by 1. The book previously let the stale read raise the cap
// back to 2 and booked 2 - 1 = 1 fill that never happened.
#[test]
fn stale_pre_amend_snapshot_cannot_raise_the_cap_or_invent_a_fill() {
    let mut h = hedge("h1", 34, 2);
    acked(&mut h, 0, 2);
    h.apply(2, amend(1, 35)).unwrap();
    h.apply(3, snap(VenueStatus::Resting, 0, 2, "v-h1"))
        .unwrap();
    assert_eq!(h.max_count, 1);
    assert_eq!(h.status, OrderStatus::Resting);
    h.apply(4, OrderEvent::CancelSent).unwrap();
    h.apply(5, OrderEvent::CancelAcked { reduced_by: 1 })
        .unwrap();
    assert_eq!(h.status, OrderStatus::Cancelled);
    assert_eq!(h.confirmed_filled(), 0);
    assert!(h.is_settled());
}

#[test]
fn stale_snapshot_never_lowers_fills_or_reopens_a_cancelled_order() {
    let mut h = hedge("h1", 33, 10);
    acked(&mut h, 0, 10);
    h.apply(2, snap(VenueStatus::Resting, 4, 6, "v-h1"))
        .unwrap();
    h.apply(3, snap(VenueStatus::Resting, 1, 9, "v-h1"))
        .unwrap();
    assert_eq!(h.venue_fill_count, 4);
    h.apply(4, OrderEvent::CancelSent).unwrap();
    h.apply(5, OrderEvent::CancelAcked { reduced_by: 6 })
        .unwrap();
    h.apply(6, snap(VenueStatus::Resting, 4, 6, "v-h1"))
        .unwrap();
    assert_eq!(h.status, OrderStatus::Cancelled);
    assert_eq!(h.venue_fill_count, 4);
}

#[test]
fn final_snapshot_contradicting_a_cancel_count_holds() {
    let mut h = hedge("h1", 33, 10);
    acked(&mut h, 0, 10);
    h.apply(2, OrderEvent::CancelSent).unwrap();
    h.apply(3, OrderEvent::CancelAcked { reduced_by: 10 })
        .unwrap();
    assert!(
        h.apply(4, snap(VenueStatus::Canceled, 1, 0, "v-h1"))
            .is_err()
    );
    assert!(matches!(h.status, OrderStatus::Inconsistent { .. }));
}

#[test]
fn snapshot_above_the_cap_holds() {
    let mut h = hedge("h1", 33, 10);
    acked(&mut h, 0, 10);
    assert!(
        h.apply(2, snap(VenueStatus::Executed, 11, 0, "v-h1"))
            .is_err()
    );
    assert!(matches!(h.status, OrderStatus::Inconsistent { .. }));
}

#[test]
fn ambiguous_amend_down_keeps_the_larger_total_until_a_read_resolves_it() {
    let mut h = hedge("h1", 33, 10);
    acked(&mut h, 0, 10);
    h.apply(
        2,
        OrderEvent::AmendAmbiguous {
            requested_total: 4,
            reason: "timeout".into(),
        },
    )
    .unwrap();
    assert!(matches!(h.status, OrderStatus::Unknown { .. }));
    assert_eq!(
        h.potential_additional(),
        10,
        "exposure uses the larger total"
    );
    // The prior total may be a stale read: stays unresolved.
    h.apply(3, snap(VenueStatus::Resting, 0, 10, "v-h1"))
        .unwrap();
    assert!(h.amend_unresolved.is_some());
    assert_eq!(h.max_count, 10);
    // The requested total can only be a post-amend read.
    h.apply(4, snap(VenueStatus::Resting, 1, 3, "v-h1"))
        .unwrap();
    assert_eq!(h.amend_unresolved, None);
    assert_eq!(h.max_count, 4);
    assert_eq!(h.status, OrderStatus::Resting);
}

#[test]
fn cancel_with_amend_unresolved_waits_for_a_final_snapshot() {
    let mut h = hedge("h1", 33, 10);
    acked(&mut h, 0, 10);
    h.apply(
        2,
        OrderEvent::AmendAmbiguous {
            requested_total: 4,
            reason: "timeout".into(),
        },
    )
    .unwrap();
    h.apply(3, snap(VenueStatus::Resting, 0, 10, "v-h1"))
        .unwrap();
    h.apply(4, OrderEvent::CancelSent).unwrap();
    // reduced_by 3: fills are 1 (total 4) or 7 (total 10).
    h.apply(5, OrderEvent::CancelAcked { reduced_by: 3 })
        .unwrap();
    assert!(matches!(h.status, OrderStatus::Unknown { .. }));
    assert!(!h.final_count_known);
    assert_eq!(h.venue_fill_count, 1, "floor only");
    assert!(!h.is_settled());
    h.apply(6, snap(VenueStatus::Canceled, 1, 0, "v-h1"))
        .unwrap();
    assert_eq!(h.status, OrderStatus::Cancelled);
    assert!(h.final_count_known);
    assert_eq!(h.confirmed_filled(), 1);
    assert_eq!(h.amend_unresolved, None);
}

#[test]
fn executed_snapshot_resolves_an_ambiguous_amend_only_to_a_known_total() {
    let mut h = hedge("h1", 33, 10);
    acked(&mut h, 0, 10);
    h.apply(
        2,
        OrderEvent::AmendAmbiguous {
            requested_total: 4,
            reason: "timeout".into(),
        },
    )
    .unwrap();
    let mut g = h.clone();
    h.apply(3, snap(VenueStatus::Executed, 4, 0, "v-h1"))
        .unwrap();
    assert_eq!(h.status, OrderStatus::Filled);
    assert_eq!(h.max_count, 4);
    assert!(
        g.apply(3, snap(VenueStatus::Executed, 6, 0, "v-h1"))
            .is_err()
    );
    assert!(matches!(g.status, OrderStatus::Inconsistent { .. }));
}
