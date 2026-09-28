//! Adapter + executor against the fixture exchange: submission, partial fills,
//! cancel/replace races, ambiguous responses, restart reconciliation, and
//! emergency residual handling. Fixture results are not venue evidence.

use momento_strategy_nba::{
    BookSide, EmergencyPolicy, GameBook, OrderRole, OrderSpec, OrderStatus, PlanStep, Residual,
    TimeInForce,
};
use serde_json::json;

use crate::executor::{self, ExecError, ExecEvent, NOT_FOUND_GRACE_S, READ_VISIBILITY_GRACE_S};
use crate::fake::{FakeExchange, Fault};
use crate::venue::{NbaVenue, PRODUCTION_ORDERS_COMPILED, create_body, production_permit};

const ORIG: &str = "KXNBAGAME-26OCT03AAABBB-AAA";
const OPP: &str = "KXNBAGAME-26OCT03AAABBB-BBB";

struct Rig {
    venue: NbaVenue<FakeExchange>,
    book: GameBook,
    persisted: Vec<String>,
}

impl Rig {
    fn new() -> Self {
        let mut fx = FakeExchange::default();
        fx.book(ORIG, 76, 0, 80, 0);
        fx.book(OPP, 30, 0, 50, 0);
        Self {
            venue: NbaVenue::fixture(fx),
            book: GameBook::new("EV", ORIG, OPP),
            persisted: Vec::new(),
        }
    }

    fn fx(&mut self) -> &mut FakeExchange {
        self.venue.transport_mut()
    }

    fn submit(&mut self, spec: OrderSpec, now: i64) -> Result<(), ExecError> {
        let persisted = &mut self.persisted;
        executor::submit(
            &mut self.book,
            &mut self.venue,
            spec,
            now,
            &mut |b: &GameBook, e: ExecEvent| {
                if matches!(e, ExecEvent::BeforeSend { .. }) {
                    persisted.push(serde_json::to_string(b).unwrap());
                }
                Ok(())
            },
        )
    }

    fn cancel(&mut self, cid: &str, now: i64) -> Result<(), ExecError> {
        executor::cancel(
            &mut self.book,
            &mut self.venue,
            cid,
            now,
            &mut |_, _| Ok(()),
        )
    }

    fn amend(&mut self, cid: &str, price: u16, total: u32, now: i64) -> Result<(), ExecError> {
        executor::amend(
            &mut self.book,
            &mut self.venue,
            cid,
            price,
            total,
            now,
            &mut |_, _| Ok(()),
        )
    }

    fn reconcile(&mut self, now: i64) -> Vec<(String, ExecError)> {
        executor::reconcile_book(&mut self.book, &mut self.venue, now, &mut |_, _| Ok(()))
    }

    fn status(&self, cid: &str) -> OrderStatus {
        self.book.order(cid).unwrap().status.clone()
    }

    fn venue_position(&mut self, t: &str) -> i64 {
        self.venue.position(t).unwrap()
    }
}

fn entry(cid: &str, count: u32) -> OrderSpec {
    OrderSpec {
        client_order_id: cid.into(),
        role: OrderRole::Entry,
        ticker: ORIG.into(),
        side: BookSide::Bid,
        price_cents: 78,
        count,
        tif: TimeInForce::GoodTillCanceled,
        post_only: true,
        reduce_only: false,
        expiration_ts: None,
        cancel_order_on_pause: true,
        subaccount: None,
    }
}

fn hedge(cid: &str, price: u16, count: u32) -> OrderSpec {
    OrderSpec {
        role: OrderRole::Hedge,
        ticker: OPP.into(),
        price_cents: price,
        post_only: false,
        cancel_order_on_pause: false,
        ..entry(cid, count)
    }
}

/// Resting entry filled by counterparties, reconciled with fill records.
fn filled_entry(r: &mut Rig, n: u32) {
    r.submit(entry("e1", n), 0).unwrap();
    let vid = r.book.order("e1").unwrap().venue_order_id.clone().unwrap();
    assert_eq!(r.fx().trade_against(&vid, n), n);
    assert!(r.reconcile(1).is_empty());
    assert!(r.book.order("e1").unwrap().is_settled());
}

// ---------- request shape ----------

#[test]
fn create_body_matches_v2_contract() {
    let mut s = entry("nba001-0011223344556677", 1538);
    s.expiration_ts = Some(1_790_000_000);
    s.subaccount = Some(1);
    let b = create_body(&s);
    assert_eq!(
        b,
        json!({
            "ticker": ORIG,
            "client_order_id": "nba001-0011223344556677",
            "side": "bid",
            "count": "1538.00",
            "price": "0.7800",
            "time_in_force": "good_till_canceled",
            "self_trade_prevention_type": "taker_at_cross",
            "post_only": true,
            "reduce_only": false,
            "cancel_order_on_pause": true,
            "expiration_time": 1_790_000_000,
            "subaccount": 1,
        })
    );
    assert!(b.get("exchange_index").is_none(), "auto-route by ticker");
}

// ---------- production gate ----------

#[test]
fn production_permit_is_impossible_in_this_build() {
    const { assert!(!PRODUCTION_ORDERS_COMPILED) };
    let all_green = production_permit(&[], true, true, true, true);
    let Err(why) = all_green else {
        panic!("permit issued");
    };
    // Behaviour change (2026-09-27): fractional production fills (host
    // evidence) are a second build-level blocker until counts are hundredths.
    assert_eq!(
        why,
        vec![
            "PRODUCTION_ORDERS_NOT_COMPILED".to_string(),
            "FRACTIONAL_FILLS_UNSUPPORTED".to_string()
        ]
    );
    let Err(why) = production_permit(&["entry_order".into()], false, false, false, false) else {
        panic!()
    };
    assert_eq!(why.len(), 7);
}

// ---------- submission and fills ----------

#[test]
fn full_fill_on_submit_then_fill_records() {
    let mut r = Rig::new();
    r.fx().book(OPP, 30, 0, 40, 5000);
    r.submit(hedge("h1", 40, 1538), 0).unwrap();
    assert_eq!(r.status("h1"), OrderStatus::Filled);
    assert!(!r.book.order("h1").unwrap().is_settled());
    assert!(r.reconcile(1).is_empty());
    let h = r.book.order("h1").unwrap();
    assert!(h.is_settled());
    assert_eq!(h.fills[0].is_taker, Some(true));
    // 0.07 × 1538 × 0.40 × 0.60 = $25.8384 exactly.
    assert_eq!(h.fills[0].fee_centicents, Some(258_384));
    assert_eq!(r.persisted.len(), 1, "persisted before send");
}

#[test]
fn partial_fills_while_resting_then_complete() {
    let mut r = Rig::new();
    r.submit(entry("e1", 1538), 0).unwrap();
    assert_eq!(r.status("e1"), OrderStatus::Resting);
    let vid = r.book.order("e1").unwrap().venue_order_id.clone().unwrap();
    r.fx().trade_against(&vid, 500);
    assert!(r.reconcile(1).is_empty());
    assert_eq!(r.status("e1"), OrderStatus::Resting);
    assert_eq!(r.book.order("e1").unwrap().confirmed_filled(), 500);
    assert_eq!(r.book.order("e1").unwrap().fills[0].is_taker, Some(false));
    r.fx().trade_against(&vid, 5000);
    assert!(r.reconcile(2).is_empty());
    assert_eq!(r.status("e1"), OrderStatus::Filled);
    assert!(r.book.order("e1").unwrap().is_settled());
    assert_eq!(r.venue_position(ORIG), 1538);
}

#[test]
fn post_only_cross_is_rejected_without_exposure() {
    let mut r = Rig::new();
    r.fx().book(ORIG, 76, 10, 78, 10);
    r.submit(entry("e1", 10), 0).unwrap();
    assert!(matches!(
        r.status("e1"),
        OrderStatus::Rejected {
            http_status: 400,
            ..
        }
    ));
    assert_eq!(r.book.exposure().original_long, 0);
}

#[test]
fn no_fill_then_cancel() {
    let mut r = Rig::new();
    r.submit(entry("e1", 10), 0).unwrap();
    r.cancel("e1", 1).unwrap();
    assert_eq!(r.status("e1"), OrderStatus::Cancelled);
    assert!(r.book.order("e1").unwrap().is_settled());
    // Second cancel: venue says 404; the order is already terminal.
    r.book.order_mut("e1").unwrap();
    assert!(r.cancel("e1", 2).is_err());
}

#[test]
fn duplicate_client_id_is_refused_locally() {
    let mut r = Rig::new();
    r.submit(entry("e1", 10), 0).unwrap();
    assert_eq!(
        r.submit(entry("e1", 10), 1),
        Err(ExecError::DuplicateClientId("e1".into()))
    );
    assert_eq!(r.fx().orders.len(), 1);
}

#[test]
fn persist_failure_sends_nothing() {
    let mut r = Rig::new();
    let res = executor::submit(
        &mut r.book,
        &mut r.venue,
        entry("e1", 10),
        0,
        &mut |_, e| match e {
            ExecEvent::BeforeSend { .. } => Err("disk full".into()),
            _ => Ok(()),
        },
    );
    assert_eq!(res, Err(ExecError::Persist("disk full".into())));
    assert!(matches!(r.status("e1"), OrderStatus::NotSent { .. }));
    assert!(r.fx().log.is_empty());
}

// ---------- ambiguous responses ----------

#[test]
fn timeout_after_venue_accepted_is_found_by_client_id() {
    let mut r = Rig::new();
    r.fx().fault("POST", Fault::Timeout { apply: true });
    r.submit(entry("e1", 10), 0).unwrap();
    assert!(matches!(r.status("e1"), OrderStatus::Unknown { .. }));
    assert_eq!(r.book.exposure().potential_original_buy, 10);
    assert!(r.reconcile(1).is_empty());
    assert_eq!(r.status("e1"), OrderStatus::Resting);
    assert!(r.book.order("e1").unwrap().venue_order_id.is_some());
}

#[test]
fn timeout_never_accepted_waits_for_grace_then_rejects() {
    let mut r = Rig::new();
    r.fx().fault("POST", Fault::Timeout { apply: false });
    r.submit(entry("e1", 10), 100).unwrap();
    assert!(r.reconcile(100 + NOT_FOUND_GRACE_S - 1).is_empty());
    assert!(matches!(r.status("e1"), OrderStatus::Unknown { .. }));
    assert!(r.reconcile(100 + NOT_FOUND_GRACE_S).is_empty());
    assert!(matches!(
        r.status("e1"),
        OrderStatus::Rejected { ref code, .. } if code == "NOT_FOUND_ON_VENUE"
    ));
    assert_eq!(r.book.exposure().potential_original_buy, 0);
}

#[test]
fn ghost_order_after_not_found_holds_the_game() {
    let mut r = Rig::new();
    r.fx().fault("POST", Fault::Timeout { apply: false });
    r.submit(entry("e1", 10), 0).unwrap();
    r.reconcile(NOT_FOUND_GRACE_S);
    // The delayed request lands after all.
    let body = create_body(&entry("e1", 10)).to_string();
    let _ = momento_kalshi::KalshiTransport::execute(
        r.fx(),
        momento_kalshi::KalshiHttpRequest {
            method: "POST".into(),
            path: momento_kalshi::CREATE_ORDER_PATH.into(),
            body: Some(body),
        },
    );
    let errs = r.reconcile(NOT_FOUND_GRACE_S + 5);
    assert_eq!(errs.len(), 1);
    assert!(matches!(r.status("e1"), OrderStatus::Inconsistent { .. }));
    assert!(matches!(
        r.book.reconciled_residual(),
        Residual::Inconsistent { .. }
    ));
}

#[test]
fn server_error_after_apply_and_409_duplicate_are_reconciled() {
    let mut r = Rig::new();
    r.fx().fault(
        "POST",
        Fault::Status {
            code: 500,
            body: "{}".into(),
            apply: true,
        },
    );
    r.submit(entry("e1", 10), 0).unwrap();
    assert!(matches!(r.status("e1"), OrderStatus::Unknown { .. }));
    r.reconcile(1);
    assert_eq!(r.status("e1"), OrderStatus::Resting);

    // A retry that collides with an accepted order returns 409 → Unknown.
    r.fx().fault(
        "POST",
        Fault::Status {
            code: 409,
            body: json!({"error": {"code": "duplicate_client_order_id"}}).to_string(),
            apply: true,
        },
    );
    r.submit(entry("e2", 10), 2).unwrap();
    assert!(matches!(r.status("e2"), OrderStatus::Unknown { .. }));
    r.reconcile(3);
    assert_eq!(r.status("e2"), OrderStatus::Resting);
}

// Demo evidence 2026-09-27: GET /portfolio/orders/{id} returned 404 for about
// a second after create and after amend. Inside the grace window that is not
// yet visible; past it, an error that stops the lane.
#[test]
fn known_order_404_inside_visibility_grace_is_pending_not_error() {
    let mut r = Rig::new();
    r.submit(hedge("h1", 40, 10), 100).unwrap();
    let not_found = || Fault::Status {
        code: 404,
        body: json!({"error": {"code": "not_found"}}).to_string(),
        apply: false,
    };
    r.fx().fault("GET", not_found());
    assert!(r.reconcile(101).is_empty());
    assert_eq!(r.status("h1"), OrderStatus::Resting);
    r.fx().fault("GET", not_found());
    let errs = r.reconcile(100 + READ_VISIBILITY_GRACE_S);
    assert_eq!(errs.len(), 1);
    assert_eq!(
        r.status("h1"),
        OrderStatus::Resting,
        "no state change on a read error"
    );
    assert!(r.reconcile(100 + READ_VISIBILITY_GRACE_S + 1).is_empty());
}

// Demo evidence 2026-09-27: a client id stays reserved after its order was
// cancelled (409 order_already_exists). After lost state, the retry collides
// and reconciliation must find the old order without a time window.
#[test]
fn retry_after_lost_state_collides_and_finds_the_old_cancelled_order() {
    let mut r = Rig::new();
    r.submit(entry("e1", 10), 0).unwrap();
    r.cancel("e1", 1).unwrap();
    assert_eq!(r.status("e1"), OrderStatus::Cancelled);
    r.book = GameBook::new("EV", ORIG, OPP);
    r.submit(entry("e1", 10), 5_000).unwrap();
    assert!(matches!(r.status("e1"), OrderStatus::Unknown { .. }));
    assert!(r.reconcile(5_001).is_empty());
    let o = r.book.order("e1").unwrap();
    assert_eq!(o.status, OrderStatus::Cancelled);
    assert_eq!(o.confirmed_filled(), 0);
    assert_eq!(r.book.exposure().potential_original_buy, 0);
    assert_eq!(r.fx().orders.len(), 1, "no second order created");
}

#[test]
fn rate_limit_is_ambiguous_not_rejected() {
    let mut r = Rig::new();
    r.fx().fault(
        "POST",
        Fault::Status {
            code: 429,
            body: "{}".into(),
            apply: false,
        },
    );
    r.submit(entry("e1", 10), 0).unwrap();
    assert!(matches!(r.status("e1"), OrderStatus::Unknown { .. }));
}

#[test]
fn venue_rejection_is_terminal_without_exposure() {
    let mut r = Rig::new();
    r.fx().fault(
        "POST",
        Fault::Status {
            code: 400,
            body: json!({"error": {"code": "insufficient_balance"}}).to_string(),
            apply: false,
        },
    );
    r.submit(entry("e1", 10), 0).unwrap();
    assert_eq!(
        r.status("e1"),
        OrderStatus::Rejected {
            http_status: 400,
            code: "insufficient_balance".into()
        }
    );
    assert!(r.book.order("e1").unwrap().is_settled());
}

// ---------- cancel / replace races ----------

#[test]
fn late_fill_during_cancel_is_reconciled_before_replacement() {
    let mut r = Rig::new();
    filled_entry(&mut r, 1538);
    r.submit(hedge("h1", 33, 1538), 10).unwrap();
    let vid = r.book.order("h1").unwrap().venue_order_id.clone().unwrap();
    r.fx().trade_against(&vid, 600);
    r.reconcile(11);
    r.fx()
        .fault("DELETE", Fault::FillBeforeCancel { count: 200 });
    r.cancel("h1", 12).unwrap();
    let h = r.book.order("h1").unwrap();
    assert_eq!(h.status, OrderStatus::Cancelled);
    assert_eq!(h.venue_fill_count, 800);
    assert!(!h.is_settled());
    // No replacement until the 200 late fill records are in.
    assert!(matches!(
        r.book.plan_hedge(34, "h2", None),
        PlanStep::AwaitReconciliation { .. }
    ));
    r.reconcile(13);
    assert_eq!(r.book.order("h1").unwrap().late_fill_count, 200);
    let PlanStep::Submit(s) = r.book.plan_hedge(34, "h2", None) else {
        panic!()
    };
    assert_eq!(s.count, 738);
    assert_eq!(r.venue_position(OPP), 800);
}

#[test]
fn cancel_timeout_then_reconcile() {
    let mut r = Rig::new();
    r.submit(entry("e1", 10), 0).unwrap();
    r.fx().fault("DELETE", Fault::Timeout { apply: true });
    r.cancel("e1", 1).unwrap();
    assert!(matches!(r.status("e1"), OrderStatus::Unknown { .. }));
    assert_eq!(r.book.exposure().potential_original_buy, 10);
    r.reconcile(2);
    assert_eq!(r.status("e1"), OrderStatus::Cancelled);
}

#[test]
fn cancel_404_after_full_fill_reads_final_count() {
    let mut r = Rig::new();
    r.submit(hedge("h1", 33, 100), 0).unwrap();
    let vid = r.book.order("h1").unwrap().venue_order_id.clone().unwrap();
    r.fx()
        .fault("DELETE", Fault::FillBeforeCancel { count: 100 });
    r.cancel("h1", 1).unwrap();
    assert!(matches!(r.status("h1"), OrderStatus::Unknown { .. }));
    r.reconcile(2);
    assert_eq!(r.status("h1"), OrderStatus::Filled);
    assert!(r.book.order("h1").unwrap().is_settled());
    assert_eq!(
        r.fx().orders.iter().find(|o| o.id == vid).unwrap().filled,
        100
    );
}

#[test]
fn amend_raises_price_with_total_cap_under_a_race() {
    let mut r = Rig::new();
    filled_entry(&mut r, 1538);
    r.submit(hedge("h1", 40, 1538), 10).unwrap();
    let vid = r.book.order("h1").unwrap().venue_order_id.clone().unwrap();
    r.fx().trade_against(&vid, 500);
    r.reconcile(11);
    let PlanStep::Amend {
        client_order_id,
        price_cents,
        total_count,
    } = r.book.plan_hedge(42, "h2", None)
    else {
        panic!()
    };
    assert_eq!((price_cents, total_count), (42, 1538));
    // Another 300 fill between plan and amend: the cap still holds at 1538.
    r.fx().trade_against(&vid, 300);
    r.amend(&client_order_id, price_cents, total_count, 12)
        .unwrap();
    let h = r.book.order("h1").unwrap();
    assert_eq!(h.spec.price_cents, 42);
    assert_eq!(h.potential_additional(), 738);
    assert_eq!(r.fx().trade_against(&vid, 5000), 738);
    r.reconcile(13);
    assert_eq!(r.book.exposure().opponent_long, 1538);
    assert_eq!(r.venue_position(OPP), 1538);
    assert_eq!(
        r.book.plan_hedge(45, "h3", None),
        PlanStep::Flat { hedged_pairs: 1538 }
    );
}

#[test]
fn amend_on_filled_order_is_ambiguous_then_reconciled() {
    let mut r = Rig::new();
    r.submit(hedge("h1", 40, 10), 0).unwrap();
    let vid = r.book.order("h1").unwrap().venue_order_id.clone().unwrap();
    r.fx().trade_against(&vid, 10);
    // Behaviour change (2026-09-27): amend is always followed by a snapshot,
    // so the refused amend (400, order filled) passes through UNKNOWN and is
    // resolved in the same call rather than on the next reconcile pass.
    r.amend("h1", 41, 10, 1).unwrap();
    let h = r.book.order("h1").unwrap();
    assert!(h.history.iter().any(|t| t.to == "UNKNOWN"));
    assert_eq!(h.status, OrderStatus::Filled);
    r.reconcile(2);
    assert_eq!(r.status("h1"), OrderStatus::Filled);
}

// Demo run 3 (2026-09-27): after amending a 2-lot down to 1, the GET still
// showed 0 filled + 2 remaining. The cancel then returned reduced_by 1, and the
// book counted a fill that never happened.
#[test]
fn stale_get_after_amend_down_does_not_invent_a_fill_on_cancel() {
    let mut r = Rig::new();
    r.submit(hedge("h1", 34, 2), 0).unwrap();
    let vid = r.book.order("h1").unwrap().venue_order_id.clone().unwrap();
    let stale = |vid: &str| Fault::Status {
        code: 200,
        body: json!({"order": {
            "order_id": vid, "client_order_id": "h1", "ticker": OPP, "status": "resting",
            "book_side": "bid", "yes_price_dollars": "0.3400",
            "fill_count_fp": "0.00", "remaining_count_fp": "2.00", "initial_count_fp": "2.00"
        }})
        .to_string(),
        apply: false,
    };
    r.fx().fault("GET", stale(&vid));
    r.amend("h1", 35, 1, 1).unwrap();
    assert_eq!(r.book.order("h1").unwrap().max_count, 1);
    r.cancel("h1", 2).unwrap();
    r.fx().fault("GET", stale(&vid));
    assert!(r.reconcile(3).is_empty());
    let h = r.book.order("h1").unwrap();
    assert_eq!(h.status, OrderStatus::Cancelled);
    assert_eq!(h.confirmed_filled(), 0);
    assert_eq!(r.book.exposure().opponent_long, 0);
    assert_eq!(r.venue_position(OPP), 0);
}

#[test]
fn amend_timeout_that_applied_resolves_from_the_next_read() {
    let mut r = Rig::new();
    r.submit(hedge("h1", 34, 10), 0).unwrap();
    r.fx().fault("POST", Fault::Timeout { apply: true });
    r.amend("h1", 35, 4, 1).unwrap();
    let h = r.book.order("h1").unwrap();
    assert!(h.history.iter().any(|t| t.to == "UNKNOWN"));
    assert_eq!(h.amend_unresolved, None);
    assert_eq!(h.max_count, 4);
    assert_eq!(h.status, OrderStatus::Resting);
}

#[test]
fn amend_timeout_that_did_not_apply_cancels_to_a_final_read() {
    let mut r = Rig::new();
    r.submit(hedge("h1", 34, 10), 0).unwrap();
    let vid = r.book.order("h1").unwrap().venue_order_id.clone().unwrap();
    r.fx().fault("POST", Fault::Timeout { apply: false });
    r.amend("h1", 35, 4, 1).unwrap();
    let h = r.book.order("h1").unwrap();
    assert!(
        h.amend_unresolved.is_some(),
        "prior total may be a stale read"
    );
    assert_eq!(h.max_count, 10);
    assert_eq!(h.status, OrderStatus::Resting);
    r.fx().trade_against(&vid, 3);
    r.cancel("h1", 2).unwrap();
    // reduced_by 7: fills are 3 (total 10) or 0 (total 4) until the final read.
    assert!(r.reconcile(3).is_empty());
    let h = r.book.order("h1").unwrap();
    assert_eq!(h.status, OrderStatus::Cancelled);
    assert!(h.is_settled());
    assert_eq!(h.confirmed_filled(), 3);
    assert_eq!(r.book.exposure().opponent_long, 3);
    assert_eq!(r.venue_position(OPP), 3);
}

// Host evidence 2026-09-27: whole-contract orders receive fractional fills.
// Until counts are hundredths end to end, a fractional count is a read error:
// no state change, no invented exposure, and the lane holds on the error.
#[test]
fn fractional_fill_count_fails_closed_without_changing_state() {
    let mut r = Rig::new();
    r.submit(hedge("h1", 34, 7), 0).unwrap();
    let vid = r.book.order("h1").unwrap().venue_order_id.clone().unwrap();
    r.fx().fault(
        "GET",
        Fault::Status {
            code: 200,
            body: json!({"order": {
                "order_id": vid, "client_order_id": "h1", "ticker": OPP, "status": "resting",
                "book_side": "bid", "yes_price_dollars": "0.3400",
                "fill_count_fp": "0.30", "remaining_count_fp": "6.70", "initial_count_fp": "7.00"
            }})
            .to_string(),
            apply: false,
        },
    );
    let errs = r.reconcile(1);
    assert_eq!(errs.len(), 1, "{errs:?}");
    let h = r.book.order("h1").unwrap();
    assert_eq!(h.status, OrderStatus::Resting);
    assert_eq!(h.confirmed_filled(), 0);
    assert_eq!(h.potential_additional(), 7);
}

// ---------- restart ----------

#[test]
fn restart_mid_submit_reconciles_from_persisted_state() {
    let mut r = Rig::new();
    r.fx().fault("POST", Fault::Timeout { apply: true });
    r.submit(entry("e1", 1538), 0).unwrap();
    let vid = r.fx().order_by_cid("e1").unwrap().id.clone();
    r.fx().trade_against(&vid, 900);
    // Crash: only the pre-send snapshot survives (status SENDING).
    let saved = r.persisted.last().unwrap().clone();
    let mut restored: GameBook = serde_json::from_str(&saved).unwrap();
    assert_eq!(restored.order("e1").unwrap().status, OrderStatus::Sending);
    let errs = executor::reconcile_book(&mut restored, &mut r.venue, 5, &mut |_, _| Ok(()));
    assert!(errs.is_empty(), "{errs:?}");
    let e = restored.order("e1").unwrap();
    assert_eq!(e.status, OrderStatus::Resting);
    assert_eq!(e.confirmed_filled(), 900);
    assert_eq!(e.fill_record_count(), 900);
}

#[test]
fn restart_with_open_hedged_position_matches_venue() {
    let mut r = Rig::new();
    filled_entry(&mut r, 100);
    r.submit(hedge("h1", 35, 100), 10).unwrap();
    let vid = r.book.order("h1").unwrap().venue_order_id.clone().unwrap();
    r.fx().trade_against(&vid, 60);
    let saved = serde_json::to_string(&r.book).unwrap();
    let mut restored: GameBook = serde_json::from_str(&saved).unwrap();
    executor::reconcile_book(&mut restored, &mut r.venue, 20, &mut |_, _| Ok(()));
    let e = restored.exposure();
    assert_eq!(e.original_long, r.venue_position(ORIG));
    assert_eq!(e.opponent_long, r.venue_position(OPP));
    assert_eq!(e.unhedged_original, 40);
}

// ---------- emergency residual ----------

#[test]
fn partial_hedge_then_emergency_sale_of_reconciled_residual_only() {
    let mut r = Rig::new();
    filled_entry(&mut r, 1538);
    r.submit(hedge("h1", 45, 1538), 10).unwrap();
    let vid = r.book.order("h1").unwrap().venue_order_id.clone().unwrap();
    r.fx().trade_against(&vid, 600);
    r.reconcile(11);
    let policy = EmergencyPolicy::SellOriginal { floor_cents: 1 };

    let mut now = 12;
    let mut sales = 0;
    loop {
        now += 1;
        match r.book.plan_emergency(policy, &format!("x{sales}"), None) {
            PlanStep::CancelWorking { client_order_ids } => {
                for c in client_order_ids {
                    // A counterparty takes 150 more while the cancel is in flight.
                    r.fx()
                        .fault("DELETE", Fault::FillBeforeCancel { count: 150 });
                    r.cancel(&c, now).unwrap();
                }
            }
            PlanStep::AwaitReconciliation { .. } => {
                assert!(r.reconcile(now).is_empty());
            }
            PlanStep::Submit(s) => {
                if sales == 0 {
                    // 1538 − (600 + 150) = 788, never the stale 938.
                    assert_eq!(s.count, 788);
                    // Thin bid: only 500 sell now; the IOC remainder cancels.
                    r.fx().book(ORIG, 20, 500, 25, 0);
                } else {
                    assert_eq!(s.count, 288);
                    r.fx().book(ORIG, 10, 1000, 12, 0);
                }
                assert!(s.reduce_only && s.tif == TimeInForce::ImmediateOrCancel);
                r.submit(s, now).unwrap();
                sales += 1;
            }
            PlanStep::Flat { hedged_pairs } => {
                assert_eq!(hedged_pairs, 750);
                break;
            }
            other => panic!("unexpected {other:?}"),
        }
        assert!(now < 40, "did not converge");
    }
    assert_eq!(sales, 2);
    assert_eq!(r.venue_position(ORIG), 750);
    assert_eq!(r.venue_position(OPP), 750);
    let e = r.book.exposure();
    assert_eq!((e.original_long, e.opponent_long), (750, 750));
}

#[test]
fn reduce_only_sale_is_capped_by_the_venue_position() {
    let mut r = Rig::new();
    filled_entry(&mut r, 4);
    r.fx().book(ORIG, 50, 100, 52, 0);
    let mut s = entry("x1", 10);
    s.role = OrderRole::Emergency;
    s.side = BookSide::Ask;
    s.price_cents = 1;
    s.tif = TimeInForce::ImmediateOrCancel;
    s.post_only = false;
    s.reduce_only = true;
    r.submit(s, 5).unwrap();
    r.reconcile(6);
    assert_eq!(r.venue_position(ORIG), 0);
    assert_eq!(r.book.exposure().original_long, 0);
}
