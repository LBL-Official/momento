use momento_strategy_nba::{
    BalancePrecision, FeeModel, FeeType, OrderEvent, OrderRole, live_v1::*,
};
fn policy() -> Policy {
    Policy {
        quote_max_age_ms: 5000,
        sports_max_age_ms: 5000,
        entry_reprice_ms: 1000,
        emergency_floor_cents: Some(1),
        fee_model: FeeModel::new(
            FeeType::QuadraticWithMakerFees,
            1000,
            BalancePrecision::Cent,
        ),
        fee_version: "TEST_ONLY".into(),
    }
}
fn mapping(sport: Sport, p5: bool) -> Mapping {
    Mapping {
        event_id: "game".into(),
        sport,
        tickers: ["A".into(), "B".into()],
        espn_event_id: "1".into(),
        espn_team_ids: ["1".into(), "2".into()],
        season: "2026-27".into(),
        membership_evidence: if p5 { Some("fixture".into()) } else { None },
        both_p5: p5,
        complement_evidence: "fixture".into(),
    }
}
fn sports(status: &str, period: u8, clock: u16, at: i64) -> Input {
    Input::Sports {
        state: SportsState {
            event_id: "game".into(),
            status: status.into(),
            period,
            clock_seconds: clock,
            scores: [0, 0],
            received_ms: at,
            provider_ms: None,
        },
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
fn account(equity: u64, at: i64) -> Input {
    Input::Account {
        clean: true,
        cash_centicents: equity as i64 * 100,
        equity_cents: equity,
        snapshot_id: format!("account-{at}"),
        observed_ms: at,
    }
}
fn ready(equity: u64, sport: Sport, p5: bool) -> Engine {
    let mut e = Engine::new(policy(), 0).unwrap();
    e.apply(1000, account(equity, 1000)).unwrap();
    e.apply(
        1000,
        Input::Register {
            mapping: mapping(sport, p5),
        },
    )
    .unwrap();
    e.apply(1000, sports("pre", 0, 0, 1000)).unwrap();
    e.apply(1000, quote(0, 50, 52, 1000)).unwrap();
    e.apply(1000, quote(1, 48, 50, 1000)).unwrap();
    e.apply(1000, sports("pre", 0, 0, 1000)).unwrap();
    e
}
#[test]
fn same_policy_and_lifecycle_at_twenty_and_twenty_thousand() {
    let mut counts = Vec::new();
    for equity in [2000, 2_000_000] {
        let mut e = ready(equity, Sport::NBA, false);
        e.apply(1000, sports("in", 3, 700, 1000)).unwrap();
        let a = e.apply(1000, quote(0, 77, 79, 1000)).unwrap();
        let order = match &a[0] {
            Action::Submit { order, .. } => order.clone(),
            _ => panic!("no order"),
        };
        assert_eq!(order.role, OrderRole::Entry);
        assert_eq!(order.price_cents, 78);
        assert!(order.post_only);
        let budget = e.epochs.as_ref().unwrap().active().trade_budget_cents;
        let fees = e
            .policy
            .fee_model
            .order_fee_centicents(momento_strategy_nba::Liquidity::Maker, order.count, 78)
            .unwrap();
        assert!(i64::from(order.count) * 7800 + fees <= budget as i64 * 100);
        counts.push(order.count);
        e.apply(
            1000,
            Input::Order {
                event_id: "game".into(),
                client_order_id: order.client_order_id.clone(),
                evidence: OrderEvent::Sending,
            },
        )
        .unwrap();
        e.apply(
            1000,
            Input::Order {
                event_id: "game".into(),
                client_order_id: order.client_order_id.clone(),
                evidence: OrderEvent::Acked {
                    venue_order_id: "v".into(),
                    fill_count: 0,
                    remaining_count: order.count,
                },
            },
        )
        .unwrap();
        let actions = e.apply(1001, quote(0, 85, 87, 1001)).unwrap();
        assert!(matches!(&actions[0], Action::Cancel { .. }));
        // It must not place a replacement while cancellation is unconfirmed.
        assert!(
            !e.apply(1002, Input::Tick)
                .unwrap()
                .iter()
                .any(|a| matches!(a, Action::Submit { .. }))
        );
    }
    assert_eq!(counts[0], 1);
    assert!(counts[1] > 1000);
}
#[test]
fn no_reference_bankroll_and_stale_account_cannot_bootstrap() {
    let mut e = Engine::new(policy(), 0).unwrap();
    assert!(e.epochs.is_none());
    e.apply(10_000, account(2000, 0)).unwrap();
    assert!(e.epochs.is_none());
    assert!(!e.account_clean);
    e.apply(10_000, account(2000, 10_000)).unwrap();
    assert_eq!(e.epochs.as_ref().unwrap().active().trade_budget_cents, 120);
    e.apply(10_001, account(2_000_000, 10_001)).unwrap();
    assert_eq!(e.epochs.as_ref().unwrap().active().trade_budget_cents, 120); // deposits do not bypass frozen epoch
}
#[test]
fn ncaab_requires_both_p5_and_never_retries_a_prior_touch() {
    for p5 in [false, true] {
        let mut e = ready(2000, Sport::NCAAB, p5);
        e.apply(1000, sports("in", 2, 1000, 1000)).unwrap();
        let actions = e.apply(1000, quote(0, 77, 79, 1000)).unwrap();
        assert_eq!(
            actions.iter().any(|a| matches!(a, Action::Submit { .. })),
            p5
        );
    }
    let mut e = ready(2000, Sport::NBA, false);
    e.apply(1000, sports("in", 1, 700, 1000)).unwrap();
    e.apply(1000, quote(0, 77, 79, 1000)).unwrap();
    e.apply(1000, sports("in", 3, 700, 1000)).unwrap();
    assert!(
        !e.apply(1000, quote(0, 78, 80, 1000))
            .unwrap()
            .iter()
            .any(|a| matches!(a, Action::Submit { .. }))
    );
}
#[test]
fn gap_and_stale_pregame_cannot_create_a_second_chance() {
    let mut e = ready(2000, Sport::NBA, false);
    e.apply(
        1000,
        Input::Gap {
            reason: "disconnect".into(),
        },
    )
    .unwrap();
    e.apply(1000, sports("in", 3, 700, 1000)).unwrap();
    assert!(matches!(
        &e.apply(1000, quote(0, 77, 79, 1000)).unwrap()[0],
        Action::Block { .. }
    ));
    let mut e = ready(2000, Sport::NBA, false);
    e.apply(7000, quote(0, 77, 79, 7000)).unwrap();
    assert!(e.games["game"].first_touch.is_some());
    assert!(e.games["game"].trade.is_none());
}
