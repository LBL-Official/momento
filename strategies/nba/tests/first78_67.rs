//! FIRST78_67 strategy, admission, hedge, lifecycle, and batch tests.

use momento_core::{Bps, Contracts, Money, Price};
use momento_strategy_nba::*;
use serde_json::Value;

fn bar(ts: i64, bid: u16, ask: u16, vol: u64) -> MinuteBar {
    MinuteBar {
        end_ts: ts,
        yes_bid_close: Some(bid),
        yes_ask_close: Some(ask),
        yes_bid_low: Some(bid),
        volume: Some(vol),
    }
}

fn cross_at(bid: u16) -> (CrossTracker, EntrySignal) {
    let mut t = CrossTracker::new();
    assert_eq!(t.push(&bar(60, 70, 72, 5)), CrossOutcome::Pending);
    let CrossOutcome::Crossed(sig) = t.push(&bar(120, bid, bid + 2, 5)) else {
        panic!("expected cross");
    };
    (t, sig)
}

fn fees() -> FeeSchedule {
    FeeSchedule::taker_bound(1000)
}

/// Production KXNBAGAME as observed 2026-09-27: quadratic_with_maker_fees, M = 1,
/// direct-member centicent balance.
fn nba_fees() -> FeeModel {
    FeeModel::new(
        FeeType::QuadraticWithMakerFees,
        1000,
        BalancePrecision::Centicent,
    )
}

fn p(c: u16) -> Price {
    Price::from_cents(c).unwrap()
}

// ---------- sizing ----------

#[test]
fn sizing_is_1538_at_20000_dollars() {
    let q = contracts_for_reference(
        Money::from_cents(2_000_000),
        Bps::from_bps(ALLOCATION_BPS),
        p(78),
    )
    .unwrap();
    assert_eq!(q.get(), 1538);
}

#[test]
fn sizing_boundary_at_exact_contract_multiple() {
    let at = |e| {
        contracts_for_reference(Money::from_cents(e), Bps::from_bps(600), p(78))
            .unwrap()
            .get()
    };
    // 1538 × 78 = 119,964 = 6% of 1,999,400.
    assert_eq!(at(1_999_400), 1538);
    assert_eq!(at(1_999_399), 1537);
    assert_eq!(at(1_999_401), 1538);
}

#[test]
fn sizing_rejects_malformed_inputs() {
    assert!(contracts_for_reference(Money::from_cents(-1), Bps::from_bps(600), p(78)).is_none());
    assert!(contracts_for_reference(Money::from_cents(1), Bps::from_bps(600), p(0)).is_none());
    assert!(contracts_for_reference(Money::from_cents(1), Bps::from_bps(600), p(100)).is_none());
}

// ---------- fees and reserve ----------

#[test]
fn fee_multiplier_parses_number_and_string() {
    assert_eq!(multiplier_milli(&serde_json::json!(1)), Some(1000));
    assert_eq!(multiplier_milli(&serde_json::json!("0.5")), Some(500));
    assert_eq!(multiplier_milli(&serde_json::json!("1.25")), Some(1250));
    assert_eq!(multiplier_milli(&serde_json::json!("1.2345")), None);
    assert_eq!(multiplier_milli(&serde_json::json!(null)), None);
    assert_eq!(multiplier_milli(&serde_json::json!("-1")), None);
}

#[test]
fn fee_bound_rounds_up_and_rejects_edges() {
    // 0.07 × 1538 × 0.78 × 0.22 = $18.4745 → 1848¢.
    assert_eq!(
        fee_bound_cents(Contracts::from_u32(1538), p(78), &fees())
            .unwrap()
            .cents(),
        1848
    );
    // 0.07 × 1 × 0.5 × 0.5 = 1.75¢ → 2¢.
    assert_eq!(
        fee_bound_cents(Contracts::from_u32(1), p(50), &fees())
            .unwrap()
            .cents(),
        2
    );
    assert!(fee_bound_cents(Contracts::from_u32(1), p(0), &fees()).is_none());
    assert!(fee_bound_cents(Contracts::from_u32(1), p(100), &fees()).is_none());
    assert!(!fees().verified);
}

#[test]
fn fee_model_taker_maker_and_rounding() {
    let m = nba_fees();
    // 0.07 × 1538 × 0.78 × 0.22 = $18.474456 → 184,745 cc.
    assert_eq!(
        m.order_fee_centicents(Liquidity::Taker, 1538, 78),
        Ok(184_745)
    );
    // 0.0175 × 1538 × 0.78 × 0.22 = $4.618614 → 46,187 cc.
    assert_eq!(
        m.order_fee_centicents(Liquidity::Maker, 1538, 78),
        Ok(46_187)
    );
    assert_eq!(
        m.order_fee_centicents(Liquidity::Taker, 1538, 45),
        Ok(266_459)
    );
    assert_eq!(
        m.order_fee_centicents(Liquidity::Taker, 1538, 33),
        Ok(238_037)
    );
    assert_eq!(
        m.order_fee_centicents(Liquidity::Taker, 1538, 40),
        Ok(258_384)
    );
    assert_eq!(
        m.order_fee_centicents(Liquidity::Taker, 1538, 1),
        Ok(10_659)
    );
    // 0.07 × 1 × 0.5 × 0.5 = $0.0175 → 175 cc exactly; one more contract rounds.
    assert_eq!(m.order_fee_centicents(Liquidity::Taker, 1, 50), Ok(175));
    assert_eq!(m.order_fee_centicents(Liquidity::Maker, 1, 50), Ok(44));
    let cent = FeeModel::new(
        FeeType::QuadraticWithMakerFees,
        1000,
        BalancePrecision::Cent,
    );
    assert_eq!(cent.order_fee_centicents(Liquidity::Taker, 1, 50), Ok(200));
    // quadratic: makers pay 0; flat and combo are not modelled.
    let q = FeeModel::new(FeeType::Quadratic, 1000, BalancePrecision::Centicent);
    assert_eq!(q.order_fee_centicents(Liquidity::Maker, 1538, 78), Ok(0));
    assert_eq!(
        q.order_fee_centicents(Liquidity::Taker, 1538, 78),
        Ok(184_745)
    );
    let flat = FeeModel::new(FeeType::Flat, 1000, BalancePrecision::Centicent);
    assert_eq!(
        flat.order_fee_centicents(Liquidity::Taker, 1, 50),
        Err(FeeError::Unsupported)
    );
    // MLB-style half multiplier.
    let half = FeeModel::new(
        FeeType::QuadraticWithMakerFees,
        500,
        BalancePrecision::Centicent,
    );
    assert_eq!(half.order_fee_centicents(Liquidity::Taker, 1, 50), Ok(88));
    assert_eq!(
        m.order_fee_centicents(Liquidity::Taker, 1, 0),
        Err(FeeError::InvalidPrice)
    );
    assert_eq!(
        m.order_fee_centicents(Liquidity::Taker, 1, 100),
        Err(FeeError::InvalidPrice)
    );
    // A sweep across [1, 99] is bounded at 50.
    assert_eq!(
        m.order_fee_bound_over(Liquidity::Taker, 1538, 1, 99),
        Ok(269_150)
    );
    assert_eq!(
        m.order_fee_bound_over(Liquidity::Taker, 1538, 33, 45),
        Ok(266_459)
    );
    assert_eq!(
        FeeType::parse("quadratic_with_maker_fees"),
        Some(FeeType::QuadraticWithMakerFees)
    );
    assert_eq!(FeeType::parse("mystery"), None);
}

#[test]
fn reserve_uses_ladder_cap_or_emergency_bound_whichever_is_worse() {
    let q = Contracts::from_u32(1538);
    let r = reserve_for_entry(
        q,
        p(78),
        Liquidity::Maker,
        p(45),
        ExitBound::Bounded {
            worst_price_cents: 40,
        },
        &nba_fees(),
    )
    .unwrap();
    assert_eq!(r.principal.cents(), 119_964);
    assert_eq!(r.entry_fee_centicents, 46_187);
    assert_eq!(r.entry_fee_bound.cents(), 462);
    assert_eq!(r.exit_price_cents, 45);
    assert_eq!(r.exit_cost.cents(), 69_210);
    assert_eq!(r.exit_fee_centicents, 266_459);
    assert_eq!(r.total_centicents, 19_230_046);
    assert_eq!(r.total.cents(), 192_301);

    let taker_entry = reserve_for_entry(
        q,
        p(78),
        Liquidity::Taker,
        p(45),
        ExitBound::Bounded {
            worst_price_cents: 40,
        },
        &nba_fees(),
    )
    .unwrap();
    assert_eq!(taker_entry.total_centicents, 19_368_604);
    assert_eq!(taker_entry.total.cents(), 193_687);

    let worse = reserve_for_entry(
        q,
        p(78),
        Liquidity::Maker,
        p(45),
        ExitBound::Bounded {
            worst_price_cents: 55,
        },
        &nba_fees(),
    )
    .unwrap();
    assert_eq!(worse.exit_price_cents, 55);
    // 11,996,400 + 46,187 + 8,459,000 + 266,459 cc.
    assert_eq!(worse.total_centicents, 20_768_046);
}

#[test]
fn reserve_sell_original_needs_only_the_ladder_cap() {
    let r = reserve_for_entry(
        Contracts::from_u32(1538),
        p(78),
        Liquidity::Maker,
        p(45),
        ExitBound::SellOriginal { floor_cents: 1 },
        &nba_fees(),
    )
    .unwrap();
    assert_eq!(r.exit_price_cents, 45);
    assert_eq!(r.total_centicents, 19_230_046);
}

#[test]
fn reserve_unbounded_emergency_blocks() {
    let r = reserve_for_entry(
        Contracts::from_u32(1538),
        p(78),
        Liquidity::Maker,
        p(45),
        ExitBound::Unbounded,
        &nba_fees(),
    );
    assert_eq!(r, Err(ReserveError::ExitCapacityUnbounded));
    let flat = FeeModel::new(FeeType::Flat, 1000, BalancePrecision::Centicent);
    let r = reserve_for_entry(
        Contracts::from_u32(1538),
        p(78),
        Liquidity::Maker,
        p(45),
        ExitBound::SellOriginal { floor_cents: 1 },
        &flat,
    );
    assert_eq!(r, Err(ReserveError::FeeUnsupported));
}

// ---------- slots and capacity ----------

fn std_reserve() -> EntryReserve {
    reserve_for_entry(
        Contracts::from_u32(1538),
        p(78),
        Liquidity::Maker,
        p(45),
        ExitBound::Bounded {
            worst_price_cents: 45,
        },
        &nba_fees(),
    )
    .unwrap()
}

#[test]
fn capacity_uses_real_cash_and_seven_slot_cap() {
    let r = std_reserve();
    let per = r.total.cents();
    let cap = |cash: i64, out: i64, open| {
        capacity_positions(
            Some(Money::from_cents(cash)),
            Money::from_cents(out),
            Ok(&r),
            open,
            7,
        )
    };
    assert_eq!(
        cap(500_000, 0, 0),
        Some(u32::try_from(500_000 / per).unwrap())
    );
    assert_eq!(cap(per * 2, 0, 0), Some(2));
    assert_eq!(cap(per * 2 - 1, 0, 0), Some(1));
    assert_eq!(cap(per * 20, 0, 0), Some(7));
    assert_eq!(cap(per * 20, 0, 5), Some(2));
    assert_eq!(cap(per * 20, 0, 7), Some(0));
    assert_eq!(cap(per * 3, per, 1), Some(2));
    assert_eq!(capacity_positions(None, Money::ZERO, Ok(&r), 0, 7), None);
    assert_eq!(
        capacity_positions(
            Some(Money::from_cents(per * 3)),
            Money::ZERO,
            Err(ReserveError::ExitCapacityUnbounded),
            0,
            7
        ),
        None
    );
}

fn green_input() -> AdmissionInput {
    AdmissionInput {
        unresolved_fields: vec![],
        fees_verified: true,
        route: Route::Verified {
            exchange_index: 0,
            series_index: Some(0),
        },
        pair: Ok(()),
        reserve: Ok(std_reserve()),
        collateral: CollateralPool::VerifiedIsolation {
            evidence: "subaccount".into(),
        },
        available_cash: Some(Money::from_cents(std_reserve().total.cents())),
        outstanding_reserved: Money::ZERO,
        open_slots: 0,
        max_slots: 7,
        live_gates_set: true,
        production_permit: Ok(()),
        reconciliation_healthy: true,
        paused: false,
        batch_number: 1,
        batch_resize_approved: false,
    }
}

fn codes(d: &AdmissionDecision) -> Vec<&'static str> {
    match d {
        AdmissionDecision::Admit => vec![],
        AdmissionDecision::Blocked(b) => b.iter().map(Blocker::code).collect(),
    }
}

#[test]
fn admission_positive_when_every_gate_passes() {
    assert_eq!(evaluate_admission(&green_input()), AdmissionDecision::Admit);
}

#[test]
fn admission_cash_boundary() {
    let total = std_reserve().total.cents();
    let mut i = green_input();
    i.available_cash = Some(Money::from_cents(total));
    assert_eq!(evaluate_admission(&i), AdmissionDecision::Admit);
    i.available_cash = Some(Money::from_cents(total - 1));
    assert_eq!(
        codes(&evaluate_admission(&i)),
        vec!["BLOCKED_INSUFFICIENT_CASH"]
    );
    i.available_cash = Some(Money::from_cents(total + 1));
    assert_eq!(evaluate_admission(&i), AdmissionDecision::Admit);
    i.available_cash = Some(Money::from_cents(total * 2));
    i.outstanding_reserved = Money::from_cents(total + 1);
    assert_eq!(
        codes(&evaluate_admission(&i)),
        vec!["BLOCKED_INSUFFICIENT_CASH"]
    );
}

#[test]
fn admission_unread_funds_are_not_zero() {
    let mut i = green_input();
    i.available_cash = None;
    assert_eq!(codes(&evaluate_admission(&i)), vec!["FUNDS_UNREAD"]);
}

#[test]
fn admission_slot_boundary() {
    let mut i = green_input();
    i.open_slots = 6;
    assert_eq!(evaluate_admission(&i), AdmissionDecision::Admit);
    i.open_slots = 7;
    assert_eq!(codes(&evaluate_admission(&i)), vec!["SLOTS_FULL"]);
}

#[test]
fn admission_names_every_blocker() {
    let mut i = green_input();
    i.unresolved_fields = vec!["entry_order".into()];
    i.fees_verified = false;
    i.route = route_for_pair(Some(3), Some(0), Some(3));
    i.pair = Err("bad".into());
    i.reserve = Err(ReserveError::ExitCapacityUnbounded);
    i.collateral = CollateralPool::SharedUnaccounted {
        other_submitters: vec!["momento-live".into()],
    };
    i.live_gates_set = false;
    i.production_permit = Err("PRODUCTION_ORDERS_NOT_COMPILED".into());
    i.reconciliation_healthy = false;
    i.paused = true;
    i.batch_number = 2;
    assert_eq!(
        codes(&evaluate_admission(&i)),
        vec![
            "CONTRACT_UNRESOLVED",
            "FEE_UNVERIFIED",
            "ROUTE_PAIR_MISMATCH",
            "HEDGE_PAIR_INVALID",
            "SHARED_COLLATERAL_UNACCOUNTED",
            "EXIT_CAPACITY_UNBOUNDED",
            "LIVE_GATES_UNSET",
            "PRODUCTION_SUBMISSION_DISABLED",
            "RECONCILIATION_HOLD",
            "CONTROL_PAUSED",
            "BATCH_RESIZE_UNAPPROVED",
        ]
    );
}

#[test]
fn admission_unknown_collateral_and_unread_reserve_inputs_block() {
    let mut i = green_input();
    i.collateral = CollateralPool::Unknown;
    i.reserve = Err(ReserveError::InputUnread);
    assert_eq!(
        codes(&evaluate_admission(&i)),
        vec!["SHARED_COLLATERAL_UNACCOUNTED", "STALE_DATA"]
    );
    let mut j = green_input();
    j.collateral = CollateralPool::AtomicAccountReservations {
        ledger: "ledger".into(),
    };
    assert_eq!(evaluate_admission(&j), AdmissionDecision::Admit);
}

// ---------- shard routing ----------

/// Behaviour change (2026-09-27): the series index names the shard for new
/// events only (docs exchange_sharding), so series ≠ market is no longer
/// ROUTE_CONFLICT. The market index is authoritative; legs must agree.
#[test]
fn routing_market_index_is_authoritative() {
    assert_eq!(
        route_for_pair(Some(0), Some(0), Some(0)),
        Route::Verified {
            exchange_index: 0,
            series_index: Some(0)
        }
    );
    let moved = route_for_pair(Some(3), Some(0), Some(0));
    assert_eq!(
        moved,
        Route::Verified {
            exchange_index: 0,
            series_index: Some(3)
        }
    );
    assert_eq!(moved.verified_index(), Some(0));
    assert_eq!(moved.market_index(), Some(0));
    assert_eq!(
        route_for_pair(None, Some(3), Some(3)).verified_index(),
        Some(3)
    );
    assert!(matches!(
        route_for_pair(Some(0), Some(0), Some(3)),
        Route::PairMismatch { .. }
    ));
    assert!(matches!(
        route_for_pair(Some(0), Some(0), None),
        Route::PairMismatch { .. }
    ));
    assert_eq!(route_for_pair(Some(0), None, None), Route::Unread);
}

#[test]
fn routing_blockers_in_admission() {
    let mut i = green_input();
    i.route = Route::Unread;
    assert_eq!(codes(&evaluate_admission(&i)), vec!["ROUTING_UNVERIFIED"]);
    i.route = route_for_pair(Some(0), Some(0), Some(3));
    assert_eq!(codes(&evaluate_admission(&i)), vec!["ROUTE_PAIR_MISMATCH"]);
    i.route = route_for_pair(Some(3), Some(0), Some(0));
    assert_eq!(evaluate_admission(&i), AdmissionDecision::Admit);
}

#[test]
fn admission_batch_two_needs_an_approved_formula() {
    let mut i = green_input();
    i.batch_number = 2;
    assert_eq!(
        codes(&evaluate_admission(&i)),
        vec!["BATCH_RESIZE_UNAPPROVED"]
    );
    i.batch_resize_approved = true;
    assert_eq!(evaluate_admission(&i), AdmissionDecision::Admit);
}

// ---------- crossing ----------

#[test]
fn crossing_requires_close_below_then_close_at_or_above_78() {
    let (_, sig) = cross_at(78);
    assert_eq!(sig.signal_ts, 120);
    assert_eq!(sig.close_cents, 78);
}

#[test]
fn touch_is_not_a_cross() {
    let mut t = CrossTracker::new();
    t.push(&bar(60, 70, 72, 5));
    let mut touch = bar(120, 77, 79, 5);
    touch.yes_bid_low = Some(70);
    assert_eq!(t.push(&touch), CrossOutcome::Pending);
    assert_eq!(t.push(&bar(180, 77, 78, 5)), CrossOutcome::Pending);
}

#[test]
fn first_quality_at_or_above_78_is_unproven() {
    let mut t = CrossTracker::new();
    assert_eq!(t.push(&bar(60, 78, 80, 5)), CrossOutcome::UnprovenFirst);
    assert_eq!(t.push(&bar(120, 70, 72, 5)), CrossOutcome::UnprovenFirst);
    let mut u = CrossTracker::new();
    assert_eq!(u.push(&bar(60, 77, 79, 5)), CrossOutcome::Pending);
}

#[test]
fn non_quality_bars_do_not_count() {
    let mut t = CrossTracker::new();
    // Zero volume before any quality bar.
    assert_eq!(t.push(&bar(60, 80, 82, 0)), CrossOutcome::Pending);
    // Spread 11.
    assert_eq!(t.push(&bar(120, 79, 90, 5)), CrossOutcome::Pending);
    // Crossed book.
    assert_eq!(t.push(&bar(180, 80, 79, 5)), CrossOutcome::Pending);
    assert_eq!(t.quality_bars(), 0);
    assert_eq!(t.push(&bar(240, 70, 80, 5)), CrossOutcome::Pending);
    // Zero volume after a quality bar still counts.
    assert!(matches!(
        t.push(&bar(300, 79, 81, 0)),
        CrossOutcome::Crossed(_)
    ));
}

#[test]
fn spread_boundary_10_vs_11() {
    assert!(bar(0, 70, 80, 1).is_quality(false));
    assert!(!bar(0, 70, 81, 1).is_quality(false));
}

#[test]
fn duplicate_or_old_bar_is_chronology_unresolved() {
    let mut t = CrossTracker::new();
    t.push(&bar(120, 70, 72, 5));
    assert_eq!(
        t.push(&bar(120, 79, 80, 5)),
        CrossOutcome::ChronologyUnresolved
    );
}

#[test]
fn signal_is_terminal_so_duplicates_do_not_re_signal() {
    let (mut t, sig) = cross_at(79);
    t.push(&bar(180, 70, 72, 5));
    assert_eq!(t.push(&bar(240, 80, 81, 5)), CrossOutcome::Crossed(sig));
}

#[test]
fn one_candidate_per_game_earliest_then_ticker() {
    let c = [
        Candidate {
            ticker: "KXNBAGAME-X-DET".into(),
            signal_ts: 200,
        },
        Candidate {
            ticker: "KXNBAGAME-X-BOS".into(),
            signal_ts: 200,
        },
        Candidate {
            ticker: "KXNBAGAME-X-AAA".into(),
            signal_ts: 260,
        },
    ];
    assert_eq!(select_candidate(&c).unwrap().ticker, "KXNBAGAME-X-BOS");
    assert!(select_candidate(&[]).is_none());
}

// ---------- top-out ----------

#[test]
fn top_out_boundary_on_close_and_ask() {
    let (_, mut s84) = cross_at(84);
    s84.bar.yes_ask_close = Some(84);
    assert!(!top_out_at_signal(&s84));
    s84.bar.yes_ask_close = Some(86);
    assert!(
        top_out_at_signal(&s84),
        "ask at or above 85 tops out even when the close is 84"
    );
    let (_, s85) = cross_at(85);
    assert!(top_out_at_signal(&s85));
    let (_, mut s80) = cross_at(80);
    s80.bar.yes_ask_close = Some(85);
    assert!(top_out_at_signal(&s80));
    s80.bar.yes_ask_close = Some(84);
    assert!(!top_out_at_signal(&s80));
    assert!(top_out_while_resting(&bar(0, 85, 86, 1)));
    assert!(!top_out_while_resting(&bar(0, 84, 86, 1)));
}

// ---------- stop and hedge ----------

#[test]
fn stop_triggers_on_first_later_close_at_or_below_67() {
    let (_, sig) = cross_at(78);
    let mut s = StopTracker::new(&sig);
    assert!(!s.intrabar_ambiguity());
    assert_eq!(s.push(&bar(120, 60, 62, 5)), None, "entry minute ignored");
    assert_eq!(s.push(&bar(180, 69, 70, 5)), None);
    assert_eq!(
        s.push(&bar(240, 68, 70, 5)),
        Some(StopEvent::Prepare {
            ts: 240,
            close_cents: 68
        })
    );
    assert_eq!(s.push(&bar(300, 68, 70, 5)), None, "prepare once");
    assert_eq!(
        s.push(&bar(360, 67, 69, 5)),
        Some(StopEvent::Trigger {
            ts: 360,
            close_cents: 67
        })
    );
    assert_eq!(
        s.push(&bar(420, 70, 72, 5)),
        Some(StopEvent::PostTrigger {
            ts: 420,
            close_cents: 70
        })
    );
    assert_eq!(s.triggered(), Some((360, 67)));
}

#[test]
fn entry_bar_low_at_or_below_67_is_intrabar_ambiguity() {
    let (_, mut sig) = cross_at(78);
    sig.bar.yes_bid_low = Some(67);
    assert!(StopTracker::new(&sig).intrabar_ambiguity());
    sig.bar.yes_bid_low = Some(68);
    assert!(!StopTracker::new(&sig).intrabar_ambiguity());
}

#[test]
fn path_zones_and_limits() {
    assert_eq!(path_zone(69), PathZone::AbovePrepare);
    assert_eq!(path_zone(68), PathZone::PrepareOnly { limit_cents: 32 });
    assert_eq!(path_zone(67), PathZone::Ladder { limit_cents: 33 });
    assert_eq!(path_zone(55), PathZone::Ladder { limit_cents: 45 });
    assert_eq!(path_zone(54), PathZone::MarketDump);
    assert_eq!(opponent_limit_for_path(68), None);
    assert_eq!(opponent_limit_for_path(60), Some(40));
}

#[test]
fn ladder_is_32_local_then_33_up_to_45_and_never_descends() {
    let mut h = HedgePlanner::default();
    let q = Contracts::from_u32(1538);
    assert_eq!(h.on_close(70, q), HedgeAction::None);
    assert_eq!(
        h.on_close(68, q),
        HedgeAction::LocalPrepared {
            limit_cents: 32,
            qty: 1538
        }
    );
    assert!(!h.triggered(), "68 never sends");
    assert_eq!(
        h.on_close(67, q),
        HedgeAction::TriggerProposal {
            limit_cents: 33,
            qty: 1538
        }
    );
    assert_eq!(
        h.on_close(60, q),
        HedgeAction::LadderProposal {
            limit_cents: 40,
            qty: 1538
        }
    );
    assert_eq!(
        h.on_close(66, q),
        HedgeAction::LadderProposal {
            limit_cents: 40,
            qty: 1538
        }
    );
    assert_eq!(
        h.on_close(72, q),
        HedgeAction::LadderProposal {
            limit_cents: 40,
            qty: 1538
        }
    );
    assert_eq!(
        h.on_close(55, q),
        HedgeAction::LadderProposal {
            limit_cents: 45,
            qty: 1538
        }
    );
    assert_eq!(
        h.on_close(54, q),
        HedgeAction::MarketDumpUnresolved { qty: 1538 }
    );
    assert_eq!(h.proposed_limit(), Some(45));
    assert_eq!(
        h.on_close(60, Contracts::from_u32(0)),
        HedgeAction::Complete
    );
}

#[test]
fn gap_through_trigger_below_55_is_market_dump_unresolved() {
    let mut h = HedgePlanner::default();
    assert_eq!(
        h.on_close(50, Contracts::from_u32(10)),
        HedgeAction::MarketDumpUnresolved { qty: 10 }
    );
}

#[test]
fn equal_quantity_complement_pays_the_same_either_way() {
    let q = Contracts::from_u32(1538);
    let win = complement_settlement_cents(q, q, true);
    let lose = complement_settlement_cents(q, q, false);
    assert_eq!(win, 153_800);
    assert_eq!(win, lose);
    let partial = Contracts::from_u32(1000);
    assert_eq!(
        complement_settlement_cents(q, partial, true)
            - complement_settlement_cents(q, partial, false),
        538 * 100
    );
}

#[test]
fn hedge_quantity_is_residual_and_over_hedge_is_error() {
    assert_eq!(
        hedge_quantity(Contracts::from_u32(1538), Contracts::from_u32(1000)),
        Ok(Contracts::from_u32(538))
    );
    assert_eq!(
        hedge_quantity(Contracts::from_u32(10), Contracts::from_u32(10)),
        Ok(Contracts::from_u32(0))
    );
    assert_eq!(
        hedge_quantity(Contracts::from_u32(10), Contracts::from_u32(12)),
        Err(Contracts::from_u32(2))
    );
}

// ---------- complement verification ----------

fn market(ticker: &str, team: &str) -> MarketDescriptor {
    MarketDescriptor {
        ticker: ticker.into(),
        event_ticker: "KXNBAGAME-26OCT20BOSDET".into(),
        status: Some("active".into()),
        yes_sub_title: Some(team.into()),
        rules_primary: Some(format!(
            "If {team} wins the Boston vs Detroit game, then the market resolves to Yes."
        )),
        rules_secondary: Some("Same secondary text.".into()),
        close_time: Some("2026-10-21T02:00:00Z".into()),
        expected_expiration_time: Some("2026-10-21T02:00:00Z".into()),
        settlement_timer_seconds: Some(300),
        exchange_index: Some(0),
    }
}

fn event() -> EventDescriptor {
    EventDescriptor {
        event_ticker: "KXNBAGAME-26OCT20BOSDET".into(),
        series_ticker: Some("KXNBAGAME".into()),
        mutually_exclusive: Some(true),
    }
}

fn pair() -> Vec<MarketDescriptor> {
    vec![
        market("KXNBAGAME-26OCT20BOSDET-BOS", "Boston"),
        market("KXNBAGAME-26OCT20BOSDET-DET", "Detroit"),
    ]
}

#[test]
fn complement_verified_for_exact_pair() {
    let p = verify_complement(&event(), &pair(), "KXNBAGAME-26OCT20BOSDET-DET").unwrap();
    assert_eq!(p.opponent, "KXNBAGAME-26OCT20BOSDET-BOS");
    assert_eq!(p.exchange_index, Some(0));
}

#[test]
fn wrong_contract_rejections() {
    let orig = "KXNBAGAME-26OCT20BOSDET-BOS";
    let mut ev = event();
    ev.mutually_exclusive = Some(false);
    assert!(verify_complement(&ev, &pair(), orig).is_err());
    let mut ev = event();
    ev.mutually_exclusive = None;
    assert!(verify_complement(&ev, &pair(), orig).is_err());

    let mut three = pair();
    three.push(market("KXNBAGAME-26OCT20BOSDET-TIE", "Tie"));
    assert!(verify_complement(&event(), &three, orig).is_err());

    assert!(verify_complement(&event(), &pair(), "KXNBAGAME-26OCT20PHINYK-PHI").is_err());

    let mut other_event = pair();
    other_event[1].event_ticker = "KXNBAGAME-26OCT20PHINYK".into();
    assert!(verify_complement(&event(), &other_event, orig).is_err());

    let mut same_team = pair();
    same_team[1] = market("KXNBAGAME-26OCT20BOSDET-DET", "Boston");
    assert!(verify_complement(&event(), &same_team, orig).is_err());

    let mut rules = pair();
    rules[1].rules_primary =
        Some("If Detroit wins the Boston vs Detroit game in overtime, then Yes.".into());
    assert!(verify_complement(&event(), &rules, orig).is_err());

    let mut secondary = pair();
    secondary[1].rules_secondary = Some("Different.".into());
    assert!(verify_complement(&event(), &secondary, orig).is_err());

    let mut timer = pair();
    timer[1].settlement_timer_seconds = Some(600);
    assert!(verify_complement(&event(), &timer, orig).is_err());

    let mut shard = pair();
    shard[1].exchange_index = Some(3);
    assert!(verify_complement(&event(), &shard, orig).is_err());
}

#[test]
fn suspended_or_closed_market_rejects_pair() {
    for status in ["paused", "closed", "settled", "suspended"] {
        let mut m = pair();
        m[1].status = Some(status.into());
        assert!(
            verify_complement(&event(), &m, "KXNBAGAME-26OCT20BOSDET-BOS").is_err(),
            "{status}"
        );
    }
    let mut m = pair();
    m[0].status = None;
    assert!(verify_complement(&event(), &m, "KXNBAGAME-26OCT20BOSDET-BOS").is_err());
}

// ---------- game slice ----------

fn obs(received: i64, status: &str, period: Option<u8>, remaining: &str) -> ClockObservation {
    ClockObservation {
        received_at: received,
        source_updated_at: Some(received - 5),
        status: status.into(),
        period,
        period_type: Some("quarter".into()),
        period_remaining: Some(remaining.into()),
    }
}

#[test]
fn only_q2_and_q3_are_eligible() {
    use momento_strategy_nba::slice::classify;
    assert_eq!(
        classify(&obs(0, "inprogress", Some(1), "05:00")),
        Bucket::Q1
    );
    assert!(classify(&obs(0, "inprogress", Some(2), "12:00")).eligible());
    assert!(classify(&obs(0, "inprogress", Some(3), "00:01")).eligible());
    assert_eq!(
        classify(&obs(0, "inprogress", Some(4), "11:59")),
        Bucket::Q4
    );
    assert_eq!(
        classify(&obs(0, "inprogress", Some(5), "04:00")),
        Bucket::Overtime
    );
    assert_eq!(
        classify(&obs(0, "inprogress", Some(2), "00:00")),
        Bucket::PeriodBreak
    );
    assert_eq!(
        classify(&obs(0, "halftime", Some(2), "00:00")),
        Bucket::PeriodBreak
    );
    assert_eq!(classify(&obs(0, "scheduled", None, "")), Bucket::Pregame);
    assert_eq!(classify(&obs(0, "closed", Some(4), "00:00")), Bucket::Final);
    assert!(!classify(&obs(0, "postponed", Some(2), "05:00")).eligible());
}

#[test]
fn preseason_game_uses_the_same_clock_rule() {
    // No stage filter: a preseason game in Q2 is eligible like any other.
    let mut h = ClockHistory::default();
    h.push(obs(1000, "inprogress", Some(2), "06:00"));
    assert_eq!(bucket_for(&h, 1010, 90), Bucket::Q2);
}

#[test]
fn stale_or_missing_clock_is_unavailable() {
    use momento_strategy_nba::slice::classify;
    let mut stale = obs(1000, "inprogress", Some(2), "06:00");
    stale.source_updated_at = Some(1000 - slice::SOURCE_MAX_LAG_S - 1);
    assert!(matches!(classify(&stale), Bucket::Unavailable(_)));
    stale.source_updated_at = Some(1000 - slice::SOURCE_MAX_LAG_S);
    assert_eq!(classify(&stale), Bucket::Q2);
    let mut halves = obs(0, "inprogress", Some(2), "06:00");
    halves.period_type = Some("half".into());
    assert!(matches!(classify(&halves), Bucket::Unavailable(_)));

    let h = ClockHistory::default();
    assert!(matches!(bucket_for(&h, 0, 90), Bucket::Unavailable(_)));
    let mut h = ClockHistory::default();
    h.push(obs(1000, "inprogress", Some(2), "06:00"));
    assert_eq!(bucket_for(&h, 1090, 90), Bucket::Q2);
    assert!(matches!(bucket_for(&h, 1091, 90), Bucket::Unavailable(_)));
}

#[test]
fn clock_history_is_bounded() {
    let mut h = ClockHistory::default();
    for i in 0..(ClockHistory::CAPACITY as i64 + 10) {
        h.push(obs(i, "inprogress", Some(2), "06:00"));
    }
    assert_eq!(h.nearest(0).unwrap().received_at, 10);
}

// ---------- lifecycle ----------

fn filled(n: u32) -> Lifecycle {
    let mut l = Lifecycle::new("G", "T");
    l.apply(1, LifecycleEvent::Eligible).unwrap();
    l.apply(2, LifecycleEvent::IntentStaged).unwrap();
    l.apply(3, LifecycleEvent::EntrySubmitted { requested: n })
        .unwrap();
    l.apply(
        4,
        LifecycleEvent::EntryFill {
            fill_id: "f1".into(),
            qty: n,
        },
    )
    .unwrap();
    l.apply(5, LifecycleEvent::EntryDone).unwrap();
    l
}

#[test]
fn full_lifecycle_keeps_completion_settlement_cash_and_slot_separate() {
    let mut l = filled(10);
    assert_eq!(l.state(), LifecycleState::Monitoring);
    l.apply(6, LifecycleEvent::PrepareLevel).unwrap();
    l.apply(7, LifecycleEvent::StopTrigger).unwrap();
    l.apply(
        8,
        LifecycleEvent::HedgeFill {
            fill_id: "h1".into(),
            qty: 10,
        },
    )
    .unwrap();
    assert_eq!(l.state(), LifecycleState::HedgeComplete);
    assert!(l.holds_slot(), "neutral exposure does not release a slot");
    assert!(l.apply(9, LifecycleEvent::SlotRelease).is_err());
    l.apply(9, LifecycleEvent::MarketSettled).unwrap();
    assert!(l.holds_slot());
    assert!(l.apply(10, LifecycleEvent::SlotRelease).is_err());
    l.apply(10, LifecycleEvent::CashConfirmed).unwrap();
    assert!(l.holds_slot());
    l.apply(11, LifecycleEvent::SlotRelease).unwrap();
    assert!(!l.holds_slot());
}

#[test]
fn partial_and_late_hedge_fills() {
    let mut l = filled(10);
    l.apply(6, LifecycleEvent::StopTrigger).unwrap();
    l.apply(
        7,
        LifecycleEvent::HedgeFill {
            fill_id: "h1".into(),
            qty: 4,
        },
    )
    .unwrap();
    assert_eq!(l.state(), LifecycleState::HedgePartial);
    assert_eq!(l.residual(), 6);
    l.apply(
        8,
        LifecycleEvent::HedgeFill {
            fill_id: "h2".into(),
            qty: 6,
        },
    )
    .unwrap();
    assert_eq!(l.state(), LifecycleState::HedgeComplete);
    // A late fill after completion is not a valid transition.
    assert!(
        l.apply(
            9,
            LifecycleEvent::HedgeFill {
                fill_id: "h3".into(),
                qty: 1
            }
        )
        .is_err()
    );
}

#[test]
fn over_hedge_goes_to_reconciliation_hold() {
    let mut l = filled(10);
    l.apply(6, LifecycleEvent::StopTrigger).unwrap();
    let err = l
        .apply(
            7,
            LifecycleEvent::HedgeFill {
                fill_id: "h1".into(),
                qty: 11,
            },
        )
        .unwrap_err();
    assert_eq!(
        err,
        TransitionError::OverHedge {
            original: 10,
            opponent: 11
        }
    );
    assert_eq!(l.state(), LifecycleState::ReconciliationHold);
}

#[test]
fn duplicate_fill_ids_are_ignored() {
    let mut l = Lifecycle::new("G", "T");
    l.apply(1, LifecycleEvent::Eligible).unwrap();
    l.apply(2, LifecycleEvent::IntentStaged).unwrap();
    l.apply(3, LifecycleEvent::EntrySubmitted { requested: 10 })
        .unwrap();
    l.apply(
        4,
        LifecycleEvent::EntryFill {
            fill_id: "f1".into(),
            qty: 4,
        },
    )
    .unwrap();
    l.apply(
        5,
        LifecycleEvent::EntryFill {
            fill_id: "f1".into(),
            qty: 4,
        },
    )
    .unwrap();
    assert_eq!(l.filled(), 4);
    assert_eq!(l.state(), LifecycleState::EntryPartial);
    assert_eq!(
        l.apply(
            6,
            LifecycleEvent::EntryFill {
                fill_id: "f2".into(),
                qty: 7
            }
        )
        .unwrap_err(),
        TransitionError::OverFill {
            requested: 10,
            filled: 11
        }
    );
}

#[test]
fn ambiguous_post_holds_until_reconciled() {
    let mut l = Lifecycle::new("G", "T");
    l.apply(1, LifecycleEvent::Eligible).unwrap();
    l.apply(2, LifecycleEvent::IntentStaged).unwrap();
    l.apply(3, LifecycleEvent::EntrySubmitted { requested: 10 })
        .unwrap();
    l.apply(
        4,
        LifecycleEvent::Unknown {
            reason: "POST timeout".into(),
        },
    )
    .unwrap();
    assert_eq!(l.state(), LifecycleState::ReconciliationHold);
    assert!(l.holds_slot());
    assert!(
        l.apply(
            5,
            LifecycleEvent::EntryFill {
                fill_id: "f1".into(),
                qty: 10
            }
        )
        .is_err()
    );
    assert_eq!(
        l.apply(6, LifecycleEvent::Resume).unwrap(),
        LifecycleState::EntryPending
    );
    l.apply(
        7,
        LifecycleEvent::EntryFill {
            fill_id: "f1".into(),
            qty: 10,
        },
    )
    .unwrap();
    assert_eq!(l.state(), LifecycleState::EntryFilled);
}

#[test]
fn cancel_races() {
    // Cancel confirmed with zero fills.
    let mut l = Lifecycle::new("G", "T");
    l.apply(1, LifecycleEvent::Eligible).unwrap();
    l.apply(2, LifecycleEvent::IntentStaged).unwrap();
    l.apply(3, LifecycleEvent::EntrySubmitted { requested: 10 })
        .unwrap();
    l.apply(4, LifecycleEvent::EntryDone).unwrap();
    assert_eq!(l.state(), LifecycleState::EntryCancelled);
    // A fill that arrives after the cancel confirmation is not silently absorbed.
    assert!(
        l.apply(
            5,
            LifecycleEvent::EntryFill {
                fill_id: "late".into(),
                qty: 3
            }
        )
        .is_err()
    );
    l.apply(6, LifecycleEvent::SlotRelease).unwrap();

    // Partial fill then cancel: the filled part is monitored.
    let mut m = Lifecycle::new("G", "T");
    m.apply(1, LifecycleEvent::Eligible).unwrap();
    m.apply(2, LifecycleEvent::IntentStaged).unwrap();
    m.apply(3, LifecycleEvent::EntrySubmitted { requested: 10 })
        .unwrap();
    m.apply(
        4,
        LifecycleEvent::EntryFill {
            fill_id: "f1".into(),
            qty: 3,
        },
    )
    .unwrap();
    m.apply(5, LifecycleEvent::EntryDone).unwrap();
    assert_eq!(m.state(), LifecycleState::Monitoring);
    assert_eq!(m.filled(), 3);
}

#[test]
fn blocked_intent_releases_without_exposure() {
    let mut l = Lifecycle::new("G", "T");
    l.apply(1, LifecycleEvent::Eligible).unwrap();
    l.apply(2, LifecycleEvent::IntentStaged).unwrap();
    l.apply(
        3,
        LifecycleEvent::Blocked {
            codes: vec!["EXIT_CAPACITY_UNBOUNDED".into()],
        },
    )
    .unwrap();
    assert_eq!(l.state(), LifecycleState::EntryBlocked);
    assert!(!l.holds_slot());
    assert!(
        l.apply(4, LifecycleEvent::EntrySubmitted { requested: 1 })
            .is_err()
    );
}

#[test]
fn restart_round_trips_state() {
    let (mut t, _) = cross_at(79);
    let restored: CrossTracker = serde_json::from_value(serde_json::to_value(&t).unwrap()).unwrap();
    assert_eq!(restored.outcome(), t.outcome());
    assert_eq!(restored.last_ts(), t.last_ts());
    assert_eq!(
        t.push(&bar(60, 70, 72, 5)),
        restored.outcome(),
        "old bar after restart does not re-signal"
    );

    let l = filled(10);
    let back: Lifecycle = serde_json::from_value(serde_json::to_value(&l).unwrap()).unwrap();
    assert_eq!(back.state(), l.state());
    assert_eq!(back.filled(), 10);
    let mut back = back;
    back.apply(9, LifecycleEvent::StopTrigger).unwrap();
    assert!(
        back.apply(
            10,
            LifecycleEvent::HedgeFill {
                fill_id: "f1".into(),
                qty: 1
            }
        )
        .is_ok_and(|s| s == back.state())
    );
    assert_eq!(back.hedged(), 0, "fill id f1 already seen before restart");
}

// ---------- batches and capital flows ----------

// Behaviour change (2026-09-27, owner objection): the v1 ledger opened batch
// 2 at exchange cash + open principal, which drops the disclosed $15,000
// external reserve and prices a two-leg position at one leg's principal. The
// equity ledger below replaces it (strategy/EQUITY_AND_BATCH_SIZING.md). The
// formula stays PROPOSED_NOT_APPROVED; admission blocks batch 2 until then.

fn settled_trade(id: &str, won: bool, hedged: u32) -> TradeEconomics {
    // 1538 @ 78 maker entry; `hedged` opponent contracts @ 33 taker.
    let entry_fee = nba_fees()
        .order_fee_centicents(Liquidity::Maker, 1538, 78)
        .unwrap();
    let hedge_fee = if hedged == 0 {
        0
    } else {
        nba_fees()
            .order_fee_centicents(Liquidity::Taker, hedged, 33)
            .unwrap()
    };
    let payout = if won { 1538 } else { i64::from(hedged) } * 10_000;
    TradeEconomics {
        trade_id: id.into(),
        original_bought: 1538,
        original_cost_centicents: 1538 * 7_800,
        opponent_bought: hedged,
        opponent_cost_centicents: i64::from(hedged) * 3_300,
        fees_centicents: entry_fee + hedge_fee,
        settlement: Some(Settlement {
            payout_centicents: payout,
            fee_centicents: 0,
        }),
        ..TradeEconomics::default()
    }
}

#[test]
fn equity_starts_at_twenty_thousand_including_external_reserve() {
    let b = EquityLedger::default();
    assert_eq!(b.reference_equity().cents(), 2_000_000);
    assert_eq!(
        FUNDED_INITIAL_CENTS + EXTERNAL_RESERVE_INITIAL_CENTS,
        2_000_000
    );
    assert_eq!(b.equity_centicents(), 200_000_000);
    assert_eq!(b.external_reserve_outstanding_cents(), 1_500_000);
    let q = contracts_for_reference(b.reference_equity(), Bps::from_bps(600), p(78)).unwrap();
    assert_eq!(q.get(), 1538);
}

#[test]
fn settled_win_and_hedged_loss_net_pnl() {
    let win = settled_trade("w", true, 0);
    // 1538 × 22¢ − 46,187 cc maker fee.
    assert_eq!(win.realized_centicents(), Some(1538 * 2_200 - 46_187));
    let hedged = settled_trade("h", false, 1538);
    // 1538 pairs pay 1538 × 100¢; cost 78 + 33; fees maker 46,187 + taker 238,037.
    assert_eq!(
        hedged.realized_centicents(),
        Some(1538 * 10_000 - 1538 * 7_800 - 1538 * 3_300 - 46_187 - 238_037)
    );
    assert_eq!(hedged.realized_centicents(), Some(-1_976_024));
}

#[test]
fn open_trades_count_locked_pairs_and_carry_unhedged_at_cost() {
    let mut open = settled_trade("o", false, 0);
    open.settlement = None;
    // Unhedged open: only the fee paid counts.
    assert_eq!(open.open_contribution_centicents(), -46_187);
    open.opponent_bought = 1538;
    open.opponent_cost_centicents = 1538 * 3_300;
    open.fees_centicents += 238_037;
    // Hedge-complete open: the locked result.
    assert_eq!(open.open_contribution_centicents(), -1_976_024);
    // Partial hedge: 600 pairs locked, 938 carried at cost.
    let mut part = settled_trade("p", false, 600);
    part.settlement = None;
    let fees = part.fees_centicents;
    assert_eq!(
        part.open_contribution_centicents(),
        600 * 10_000 - 600 * 7_800 - 600 * 3_300 - fees
    );
}

#[test]
fn a_trade_counts_once_open_or_settled() {
    let mut b = EquityLedger::default();
    let mut t = settled_trade("t", false, 1538);
    t.settlement = None;
    b.upsert_trade(t.clone());
    let open_e = b.equity_centicents();
    t.settlement = Some(Settlement {
        payout_centicents: 1538 * 10_000,
        fee_centicents: 0,
    });
    b.upsert_trade(t);
    assert_eq!(b.equity_centicents(), open_e);
    assert_eq!(b.equity_centicents(), 200_000_000 - 1_976_024);
}

#[test]
fn batch_closes_on_tenth_release_at_sizing_equity() {
    let mut b = EquityLedger::default();
    for i in 0..9 {
        let id = format!("t{i}");
        b.upsert_trade(settled_trade(&id, true, 0));
        assert_eq!(b.release(&id, i), None);
    }
    // Releasing the same trade twice does not count twice.
    assert_eq!(b.release("t0", 99), None);
    assert_eq!(b.reference_equity().cents(), 2_000_000);
    b.upsert_trade(settled_trade("t9", false, 1538));
    assert_eq!(b.release("t9", 10), Some(1));
    let win: i64 = 1538 * 2_200 - 46_187;
    let expect_cc: i64 = 200_000_000 + 9 * win - 1_976_024;
    assert_eq!(b.current().number, 2);
    assert_eq!(b.reference_equity().cents(), expect_cc.div_euclid(100));
    assert_eq!(b.batches()[0].completions.len(), 10);
}

#[test]
fn internal_transfers_do_not_create_pnl_or_double_count_the_reserve() {
    let mut b = EquityLedger::default();
    for (kind, cents) in [
        (CapitalFlowKind::ReserveToExchange, 1_000_000),
        (CapitalFlowKind::IntraAccountTransfer, 300_000),
        (CapitalFlowKind::ExchangeToReserve, 200_000),
    ] {
        b.record_flow(CapitalFlow {
            at: 1,
            kind,
            amount: Money::from_cents(cents),
            note: "internal".into(),
        });
    }
    assert_eq!(b.equity_centicents(), 200_000_000);
    assert_eq!(b.external_reserve_outstanding_cents(), 700_000);
    b.record_flow(CapitalFlow {
        at: 2,
        kind: CapitalFlowKind::OwnerContribution,
        amount: Money::from_cents(100_000),
        note: "new capital".into(),
    });
    b.record_flow(CapitalFlow {
        at: 3,
        kind: CapitalFlowKind::OwnerDistribution,
        amount: Money::from_cents(40_000),
        note: "withdrawn from strategy".into(),
    });
    assert_eq!(b.capital_base_cents(), 2_060_000);
}

// ---------- mode ----------

fn mode_in(config: ConfigMode) -> ModeInputs {
    ModeInputs {
        config,
        live_gates_set: true,
        reconciliation_healthy: true,
        hard_blockers: vec![],
        funds_sufficient: true,
        eligible_market_listed: true,
    }
}

#[test]
fn mode_is_derived_and_fails_closed() {
    assert_eq!(
        derive_mode(&mode_in(ConfigMode::LiveDataOnly)),
        Mode::LiveDataOnly
    );
    assert_eq!(derive_mode(&mode_in(ConfigMode::Shadow)), Mode::Shadow);
    assert_eq!(derive_mode(&mode_in(ConfigMode::Live)), Mode::LiveExecuting);
    let mut i = mode_in(ConfigMode::Live);
    i.live_gates_set = false;
    assert_eq!(derive_mode(&i), Mode::Shadow);
    let mut i = mode_in(ConfigMode::Live);
    i.hard_blockers = vec!["EXIT_CAPACITY_UNBOUNDED".into()];
    assert_eq!(derive_mode(&i), Mode::Shadow);
    let mut i = mode_in(ConfigMode::Live);
    i.funds_sufficient = false;
    assert_eq!(derive_mode(&i), Mode::ArmedWaitingFunds);
    let mut i = mode_in(ConfigMode::Live);
    i.eligible_market_listed = false;
    assert_eq!(derive_mode(&i), Mode::ArmedWaitingDate);
    let mut i = mode_in(ConfigMode::Live);
    i.reconciliation_healthy = false;
    assert_eq!(derive_mode(&i), Mode::ReconciliationHold);
}

// ---------- execution contract ----------

fn contract_json() -> Value {
    let path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../research/vital/bots/nba-001/strategy/execution_contract.json"
    );
    serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap()
}

#[test]
fn shipped_contract_parses_with_six_unresolved_fields() {
    let c = ContractStatus::parse(&contract_json().to_string()).unwrap();
    assert_eq!(c.contract_id, "nba-001-first78_67-v1");
    assert_eq!(
        c.unresolved,
        vec![
            "hedge_ladder_advancement",
            "hedge_initial_limit_gap_policy",
            "emergency_action",
            "data_outage_policy",
            "entry_order",
            "slot_and_batch_release",
        ]
    );
    // Behaviour change (2026-09-27): account fills verified the fee rule for
    // quadratic_with_maker_fees at multiplier 1 (FEES.md §5), so the shipped
    // contract marks fees VERIFIED. The worker still reports FEE_UNVERIFIED
    // for any other series fee type or multiplier (engine::fees_verified).
    assert!(c.fees_verified);
    assert_eq!(c.emergency, ExitBound::Unbounded);
    assert!(!c.entry_post_only);
    assert!(!c.hedge_pre_trigger_orders);
    assert!(!c.production_submission_enabled);
    assert!(!c.batch_resize_approved);
}

#[test]
fn contract_mismatch_or_pre_trigger_orders_fail_closed() {
    let mut j = contract_json();
    j["fields"]["entry"]["entry_cents"] = 80.into();
    assert!(matches!(
        ContractStatus::parse(&j.to_string()),
        Err(ContractError::Mismatch(_))
    ));
    let mut j = contract_json();
    j["fields"]["hedge_pre_trigger_orders"]["value"] = true.into();
    assert!(ContractStatus::parse(&j.to_string()).is_err());
    let mut j = contract_json();
    j["schema_version"] = "other".into();
    assert!(matches!(
        ContractStatus::parse(&j.to_string()),
        Err(ContractError::Schema(_))
    ));
    assert!(matches!(
        ContractStatus::parse("{"),
        Err(ContractError::Json(_))
    ));
}

#[test]
fn resolved_emergency_with_bound_makes_exit_bounded() {
    let mut j = contract_json();
    j["fields"]["emergency_action"]["status"] = "RESOLVED".into();
    j["fields"]["emergency_action"]["worst_price_bound_cents"] = 50.into();
    let c = ContractStatus::parse(&j.to_string()).unwrap();
    assert_eq!(
        c.emergency,
        ExitBound::Bounded {
            worst_price_cents: 50
        }
    );
    assert_eq!(c.unresolved.len(), 5);
    j["fields"]["emergency_action"]["worst_price_bound_cents"] = 100.into();
    assert_eq!(
        ContractStatus::parse(&j.to_string()).unwrap().emergency,
        ExitBound::Unbounded
    );
}

#[test]
fn resolved_sell_original_emergency_and_post_only_entry() {
    let mut j = contract_json();
    j["fields"]["emergency_action"]["status"] = "RESOLVED".into();
    j["fields"]["emergency_action"]["action"] = "SELL_ORIGINAL_REDUCE_ONLY_IOC".into();
    j["fields"]["emergency_action"]["floor_cents"] = 1.into();
    j["fields"]["entry_order"]["status"] = "RESOLVED".into();
    j["fields"]["entry_order"]["post_only"] = true.into();
    let c = ContractStatus::parse(&j.to_string()).unwrap();
    assert_eq!(c.emergency, ExitBound::SellOriginal { floor_cents: 1 });
    assert!(c.entry_post_only);
    j["fields"]["emergency_action"]["action"] = "HOLD_TO_SETTLEMENT".into();
    assert_eq!(
        ContractStatus::parse(&j.to_string()).unwrap().emergency,
        ExitBound::Unbounded
    );
    j["fields"]["emergency_action"]["action"] = "SELL_ORIGINAL_REDUCE_ONLY_IOC".into();
    j["fields"]["emergency_action"]["floor_cents"] = serde_json::Value::Null;
    assert_eq!(
        ContractStatus::parse(&j.to_string()).unwrap().emergency,
        ExitBound::Unbounded
    );
}
