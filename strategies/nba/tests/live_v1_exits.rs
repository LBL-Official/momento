use momento_strategy_nba::{
    BalancePrecision, FeeModel, FeeType, Fill, OrderEvent, OrderRole, OrderStatus, Residual,
    live_v1::*,
};

fn policy(floor: Option<u16>) -> Policy {
    Policy {
        quote_max_age_ms: 5000,
        sports_max_age_ms: 5000,
        entry_reprice_ms: 1000,
        emergency_floor_cents: floor,
        fee_model: FeeModel::new(
            FeeType::QuadraticWithMakerFees,
            1000,
            BalancePrecision::Cent,
        ),
        fee_version: "TEST_ONLY".into(),
    }
}

fn mapping() -> Mapping {
    Mapping {
        event_id: "game".into(),
        sport: Sport::NBA,
        tickers: ["A".into(), "B".into()],
        espn_event_id: "1".into(),
        espn_team_ids: ["1".into(), "2".into()],
        season: "2026-27".into(),
        membership_evidence: None,
        both_p5: false,
        complement_evidence: "fixture".into(),
    }
}

fn quote(side: usize, bid: u16, ask: u16, at: i64) -> Input {
    Input::Quote {
        event_id: "game".into(),
        quote: Quote {
            side,
            bid,
            ask,
            receive_ms: at,
            exchange_ms: Some(at),
        },
    }
}

/// Settle hedge/emergency intents only after `emergency` is already set.
/// Settling earlier re-queues a replacement hedge.
fn settle_open_intents(e: &mut Engine, at: i64) {
    for _ in 0..8 {
        let open: Vec<(String, OrderStatus, u32, OrderRole)> = e
            .games
            .get("game")
            .and_then(|g| g.trade.as_ref())
            .map(|t| {
                t.book
                    .orders
                    .iter()
                    .filter(|o| !o.is_settled())
                    .map(|o| {
                        (
                            o.spec.client_order_id.clone(),
                            o.status.clone(),
                            o.potential_additional().max(o.spec.count),
                            o.spec.role,
                        )
                    })
                    .collect()
            })
            .unwrap_or_default();
        if open.is_empty() {
            return;
        }
        for (id, status, remaining, role) in open {
            if role == OrderRole::Entry && matches!(status, OrderStatus::Filled) {
                continue;
            }
            match status {
                OrderStatus::Staged | OrderStatus::Sending => {
                    let _ = e.apply(
                        at,
                        Input::Order {
                            event_id: "game".into(),
                            client_order_id: id,
                            evidence: OrderEvent::LocalRefusal {
                                reason: "fixture_not_sent".into(),
                            },
                        },
                    );
                }
                OrderStatus::Resting => {
                    let _ = e.apply(
                        at,
                        Input::Order {
                            event_id: "game".into(),
                            client_order_id: id.clone(),
                            evidence: OrderEvent::CancelSent,
                        },
                    );
                    let _ = e.apply(
                        at,
                        Input::Order {
                            event_id: "game".into(),
                            client_order_id: id,
                            evidence: OrderEvent::CancelAcked {
                                reduced_by: remaining,
                            },
                        },
                    );
                }
                _ => {}
            }
        }
    }
}

fn fill_entry(e: &mut Engine, equity_cents: u64, at: i64) -> u32 {
    e.apply(at, Input::Register { mapping: mapping() }).unwrap();
    e.apply(
        at,
        Input::Account {
            clean: true,
            cash_centicents: equity_cents as i64 * 100,
            equity_cents,
            snapshot_id: "s".into(),
            observed_ms: at,
        },
    )
    .unwrap();
    e.apply(
        at,
        Input::Sports {
            state: SportsState {
                event_id: "game".into(),
                status: "pre".into(),
                period: 0,
                clock_seconds: 0,
                scores: [0, 0],
                received_ms: at,
                provider_ms: Some(at),
            },
        },
    )
    .unwrap();
    e.apply(at, quote(0, 50, 52, at)).unwrap();
    e.apply(at, quote(1, 48, 50, at)).unwrap();
    e.apply(
        at,
        Input::Sports {
            state: SportsState {
                event_id: "game".into(),
                status: "pre".into(),
                period: 0,
                clock_seconds: 0,
                scores: [0, 0],
                received_ms: at,
                provider_ms: Some(at),
            },
        },
    )
    .unwrap();
    e.apply(
        at,
        Input::Sports {
            state: SportsState {
                event_id: "game".into(),
                status: "in".into(),
                period: 3,
                clock_seconds: 700,
                scores: [0, 0],
                received_ms: at,
                provider_ms: Some(at),
            },
        },
    )
    .unwrap();
    // Keep opponent mid below 36 so fill does not immediately arm the hedge.
    e.apply(at, quote(1, 20, 22, at)).unwrap();
    let actions = e.apply(at, quote(0, 77, 79, at)).unwrap();
    let Action::Submit { order, .. } = &actions[0] else {
        panic!("{actions:?}");
    };
    let id = order.client_order_id.clone();
    let count = order.count;
    e.apply(
        at,
        Input::Order {
            event_id: "game".into(),
            client_order_id: id.clone(),
            evidence: OrderEvent::Sending,
        },
    )
    .unwrap();
    e.apply(
        at,
        Input::Order {
            event_id: "game".into(),
            client_order_id: id.clone(),
            evidence: OrderEvent::Acked {
                venue_order_id: "v".into(),
                fill_count: 0,
                remaining_count: count,
            },
        },
    )
    .unwrap();
    e.apply(
        at,
        Input::Order {
            event_id: "game".into(),
            client_order_id: id,
            evidence: OrderEvent::Fill(Fill {
                fill_id: "f1".into(),
                count,
                yes_price_centicents: 7800,
                is_taker: Some(false),
                fee_centicents: Some(0),
                ts: at,
            }),
        },
    )
    .unwrap();
    count
}

fn trigger_hedge(e: &mut Engine, at: i64) {
    e.apply(at, quote(1, 36, 38, at)).unwrap();
    assert!(
        e.games["game"]
            .trade
            .as_ref()
            .unwrap()
            .hedge_trigger_mid2
            .is_some()
    );
}

#[test]
fn deterioration_does_not_become_floor25_because_residual_remains() {
    for equity in [2000u64, 2_000_000] {
        let mut e = Engine::new(policy(None), 0).unwrap();
        let qty = fill_entry(&mut e, equity, 1000);
        assert!(qty >= 1);
        trigger_hedge(&mut e, 1000);
        assert_eq!(
            e.games["game"].trade.as_ref().unwrap().exit_kind,
            ExitKind::None
        );
        e.apply(1001, quote(1, 37, 39, 1001)).unwrap();
        let t = e.games["game"].trade.as_ref().unwrap();
        assert_eq!(t.exit_kind, ExitKind::Deterioration);
        assert!(t.emergency);
        settle_open_intents(&mut e, 1001);
        e.apply(1002, quote(1, 24, 26, 1002)).unwrap();
        let t = e.games["game"].trade.as_ref().unwrap();
        assert_eq!(t.exit_kind, ExitKind::Deterioration);
        let actions = e.apply(1003, Input::Tick).unwrap();
        assert!(
            actions.iter().any(|a| matches!(
                a,
                Action::Block { reason, .. } if reason ==
                    "EMERGENCY_PRICE_POLICY_UNRESOLVED"
            )),
            "{actions:?}"
        );
    }
}

#[test]
fn floor25_triggers_from_recovery_path_only() {
    for equity in [2000u64, 2_000_000] {
        let mut e = Engine::new(policy(None), 0).unwrap();
        fill_entry(&mut e, equity, 1000);
        trigger_hedge(&mut e, 1000);
        e.apply(1001, quote(1, 34, 36, 1001)).unwrap();
        assert_eq!(
            e.games["game"].trade.as_ref().unwrap().exit_kind,
            ExitKind::None
        );
        e.apply(1002, quote(1, 33, 35, 1002)).unwrap();
        assert_eq!(
            e.games["game"].trade.as_ref().unwrap().exit_kind,
            ExitKind::None
        );
        e.apply(1003, quote(1, 24, 26, 1003)).unwrap();
        assert_eq!(
            e.games["game"].trade.as_ref().unwrap().exit_kind,
            ExitKind::Floor25
        );
    }
}

#[test]
fn unresolved_floor_blocks_one_and_thousands() {
    for equity in [2000u64, 2_000_000] {
        let mut e = Engine::new(policy(None), 0).unwrap();
        let qty = fill_entry(&mut e, equity, 1000);
        assert!(qty >= 1);
        trigger_hedge(&mut e, 1000);
        e.apply(1001, quote(1, 24, 26, 1001)).unwrap();
        settle_open_intents(&mut e, 1001);
        let actions = e.apply(1002, Input::Tick).unwrap();
        assert!(
            actions.iter().any(|a| matches!(
                a,
                Action::Block { reason, .. } if reason ==
                    "EMERGENCY_PRICE_POLICY_UNRESOLVED"
            )),
            "{actions:?}"
        );
    }
}

#[test]
fn recovery_ratchet_36_35_34_then_25() {
    let mut e = Engine::new(policy(None), 0).unwrap();
    fill_entry(&mut e, 2000, 1000);
    trigger_hedge(&mut e, 1000);
    assert_eq!(e.games["game"].trade.as_ref().unwrap().hedge_limit, 35);
    e.apply(1001, quote(1, 34, 36, 1001)).unwrap();
    let t = e.games["game"].trade.as_ref().unwrap();
    assert_eq!(t.exit_kind, ExitKind::None);
    assert!(t.hedge_limit <= 35);
    e.apply(1002, quote(1, 33, 35, 1002)).unwrap();
    let t = e.games["game"].trade.as_ref().unwrap();
    assert_eq!(t.exit_kind, ExitKind::None);
    assert!(t.hedge_limit <= 34);
    e.apply(1003, quote(1, 24, 26, 1003)).unwrap();
    assert_eq!(
        e.games["game"].trade.as_ref().unwrap().exit_kind,
        ExitKind::Floor25
    );
}

#[test]
fn cancel_then_late_fill_holds_residual() {
    let mut e = Engine::new(policy(None), 0).unwrap();
    let qty = fill_entry(&mut e, 2000, 1000);
    let actions = e.apply(1000, quote(1, 36, 38, 1000)).unwrap();
    let hedge = actions
        .iter()
        .find_map(|a| match a {
            Action::Submit { order, .. } if order.role == OrderRole::Hedge => Some(order.clone()),
            _ => None,
        })
        .expect("hedge submit");
    e.apply(
        1000,
        Input::Order {
            event_id: "game".into(),
            client_order_id: hedge.client_order_id.clone(),
            evidence: OrderEvent::Sending,
        },
    )
    .unwrap();
    e.apply(
        1000,
        Input::Order {
            event_id: "game".into(),
            client_order_id: hedge.client_order_id.clone(),
            evidence: OrderEvent::Acked {
                venue_order_id: "h".into(),
                fill_count: 0,
                remaining_count: hedge.count,
            },
        },
    )
    .unwrap();
    let actions = e.apply(1001, quote(1, 37, 39, 1001)).unwrap();
    assert!(actions.iter().any(|a| matches!(a, Action::Cancel { .. })));
    e.apply(
        1001,
        Input::Order {
            event_id: "game".into(),
            client_order_id: hedge.client_order_id.clone(),
            evidence: OrderEvent::CancelSent,
        },
    )
    .unwrap();
    e.apply(
        1002,
        Input::Order {
            event_id: "game".into(),
            client_order_id: hedge.client_order_id.clone(),
            evidence: OrderEvent::Fill(Fill {
                fill_id: "late".into(),
                count: 1,
                yes_price_centicents: 3500,
                is_taker: Some(false),
                fee_centicents: Some(0),
                ts: 1002,
            }),
        },
    )
    .unwrap();
    e.apply(
        1003,
        Input::Order {
            event_id: "game".into(),
            client_order_id: hedge.client_order_id,
            evidence: OrderEvent::CancelAcked {
                reduced_by: hedge.count.saturating_sub(1),
            },
        },
    )
    .unwrap();
    let t = e.games["game"].trade.as_ref().unwrap();
    match t.book.reconciled_residual() {
        Residual::Reconciled { unhedged, .. } => {
            assert_eq!(unhedged, qty.saturating_sub(1));
        }
        other => panic!("{other:?}"),
    }
}

#[test]
fn no_bid_and_zero_collateral_block() {
    let mut e = Engine::new(policy(None), 0).unwrap();
    e.apply(0, Input::Register { mapping: mapping() }).unwrap();
    e.apply(
        0,
        Input::Account {
            clean: true,
            cash_centicents: 0,
            equity_cents: 0,
            snapshot_id: "empty".into(),
            observed_ms: 0,
        },
    )
    .unwrap();
    e.apply(
        0,
        Input::Sports {
            state: SportsState {
                event_id: "game".into(),
                status: "pre".into(),
                period: 0,
                clock_seconds: 0,
                scores: [0, 0],
                received_ms: 0,
                provider_ms: Some(0),
            },
        },
    )
    .unwrap();
    e.apply(0, quote(0, 50, 52, 0)).unwrap();
    e.apply(0, quote(1, 48, 50, 0)).unwrap();
    e.apply(
        0,
        Input::Sports {
            state: SportsState {
                event_id: "game".into(),
                status: "pre".into(),
                period: 0,
                clock_seconds: 0,
                scores: [0, 0],
                received_ms: 0,
                provider_ms: Some(0),
            },
        },
    )
    .unwrap();
    e.apply(
        0,
        Input::Sports {
            state: SportsState {
                event_id: "game".into(),
                status: "in".into(),
                period: 3,
                clock_seconds: 700,
                scores: [0, 0],
                received_ms: 0,
                provider_ms: Some(0),
            },
        },
    )
    .unwrap();
    let actions = e.apply(0, quote(0, 77, 79, 0)).unwrap();
    assert!(
        actions.iter().any(|a| match a {
            Action::SizeBelowMinimum {
                remaining_centicents: 0,
                ..
            } => true,
            Action::Block { reason, .. } => {
                reason == "INSUFFICIENT_AVAILABLE_CASH" || reason == "ACCOUNT_UNRECONCILED"
            }
            _ => false,
        }),
        "{actions:?}"
    );
}

#[test]
fn residual_never_negative_and_paired_is_min() {
    let mut e = Engine::new(policy(None), 0).unwrap();
    let qty = fill_entry(&mut e, 2000, 1000);
    let exp = e.games["game"].trade.as_ref().unwrap().book.exposure();
    assert_eq!(exp.original_long as u32, qty);
    assert_eq!(exp.opponent_long, 0);
    assert!(exp.unhedged_original >= 0);
}
