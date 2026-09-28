use chrono::{TimeZone, Utc};
use momento_core::error::VenueError;
use momento_core::{
    ClientOrderId, Contracts, GameId, MarketId, MomentoError, Order, OrderState, PositionId, Price,
    ReceivedAt, ReconcileOutcome, RiskDecisionId, Side, UnknownOrder, VenueAccount, VenueFills,
    VenueMarketDiscovery, VenueOrderId, VenueOrderStatus, VenueOrders, VenueSettlement,
};
use momento_kalshi::{
    DisabledLiveTransport, KalshiTransport, KalshiVenue, MarketBinding, ScriptedTransport,
    StaticIdentity, TransportOutcome, UnimplementedLiveKalshi, WsDedupe, count_fp_to_contracts,
    decode_client_order_id, dollars_to_price_cents, encode_client_order_id, encode_venue_order_id,
    map_order_state, parse_fill_msg, parse_ws_frame, signature_payload,
};

fn recv() -> ReceivedAt {
    let t = Utc
        .with_ymd_and_hms(2026, 8, 24, 18, 0, 0)
        .single()
        .unwrap();
    ReceivedAt::from_utc(t)
}

fn identity() -> StaticIdentity {
    let mut id = StaticIdentity::new();
    id.bind(
        "KXNBA-TEST",
        MarketBinding {
            market_id: MarketId::from_raw(2),
            game_id: GameId::from_raw(10),
            position_id: Some(PositionId::from_raw(7)),
        },
    );
    id
}

fn entry_order(client: u128) -> Order {
    Order::new_entry(
        ClientOrderId::from_raw(client),
        PositionId::from_raw(7),
        GameId::from_raw(10),
        RiskDecisionId::from_raw(1),
        Price::from_cents(80).unwrap(),
        Contracts::from_u32(3),
    )
}

fn created(order_id: u128, client: u128) -> String {
    format!(
        r#"{{"order_id":"{}","client_order_id":"{}","fill_count":"0.00","remaining_count":"3.00","ts_ms":1715793600123}}"#,
        encode_venue_order_id(VenueOrderId::from_raw(order_id)),
        encode_client_order_id(ClientOrderId::from_raw(client))
    )
}

fn kalshi_order_json(status: &str, fill: &str, remaining: &str, initial: &str) -> String {
    format!(
        r#"{{"order":{{"order_id":"{}","client_order_id":"{}","ticker":"KXNBA-TEST","status":"{status}","type":"limit","fill_count_fp":"{fill}","remaining_count_fp":"{remaining}","initial_count_fp":"{initial}","yes_price_dollars":"0.8000"}}}}"#,
        encode_venue_order_id(VenueOrderId::from_raw(9)),
        encode_client_order_id(ClientOrderId::from_raw(1))
    )
}

fn market_json() -> String {
    r#"{"market":{"ticker":"KXNBA-TEST","event_ticker":"KXNBA-GAME","yes_bid_dollars":"0.8000","yes_ask_dollars":"0.8300","last_price_dollars":"0.8100","yes_bid_size_fp":"10.00","yes_ask_size_fp":"4.00","updated_time":"2026-08-24T18:00:00Z","result":"","price_level_structure":"linear_cent"}}"#.into()
}

fn fill_json(trade: u128, order: u128, client: u128, count: &str) -> String {
    format!(
        r#"{{"trade_id":"{}","order_id":"{}","client_order_id":"{}","ticker":"KXNBA-TEST","count_fp":"{count}","yes_price_dollars":"0.8000","ts_ms":1715793600123}}"#,
        encode_venue_order_id(VenueOrderId::from_raw(trade)),
        encode_venue_order_id(VenueOrderId::from_raw(order)),
        encode_client_order_id(ClientOrderId::from_raw(client))
    )
}

#[test]
fn market_mapping() {
    let transport = ScriptedTransport::new([TransportOutcome::Http {
        status: 200,
        body: market_json(),
    }]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let snap = venue.get_market("KXNBA-TEST").unwrap();
    assert_eq!(snap.ticker, "KXNBA-TEST");
    assert_eq!(snap.event_ticker, "KXNBA-GAME");
    assert_eq!(snap.market_id, Some(MarketId::from_raw(2)));
    assert_eq!(snap.game_id, Some(GameId::from_raw(10)));
    assert_eq!(snap.bid, Some(Price::from_cents(80).unwrap()));
    assert_eq!(snap.ask, Some(Price::from_cents(83).unwrap()));
    assert_eq!(snap.mid, None);
    assert_eq!(snap.bid_depth, Some(10));
}

#[test]
fn last_bid_and_ask_are_not_promoted_to_mlb_mid() {
    let received = recv();
    let market: momento_kalshi::KalshiMarket = serde_json::from_str(
        r#"{"ticker":"KXMLBGAME-TEST","event_ticker":"KXMLBGAME-EVT","yes_bid_dollars":"0.8000","yes_ask_dollars":"0.8300","last_price_dollars":"0.8100","yes_bid_size_fp":"10.00","yes_ask_size_fp":"4.00","updated_time":"2026-08-24T18:00:00Z","result":"","price_level_structure":"linear_cent"}"#,
    )
    .unwrap();
    let snap = momento_kalshi::map_market(
        &market,
        received,
        Some(MarketId::from_raw(2)),
        Some(GameId::from_raw(10)),
    )
    .unwrap();
    assert_eq!(snap.last, Some(Price::from_cents(81).unwrap()));
    assert_eq!(snap.bid, Some(Price::from_cents(80).unwrap()));
    assert_eq!(snap.ask, Some(Price::from_cents(83).unwrap()));
    assert_eq!(snap.mid, None);
}

#[test]
fn subcent_yes_bid_and_subcent_tick_fail_closed() {
    let received = recv();
    let subcent_bid: momento_kalshi::KalshiMarket = serde_json::from_str(
        r#"{"ticker":"KXMLBGAME-TEST","event_ticker":"KXMLBGAME-EVT","yes_bid_dollars":"0.8050","yes_ask_dollars":"0.8300","last_price_dollars":"0.8100","updated_time":"2026-08-24T18:00:00Z","result":"","price_level_structure":"linear_cent"}"#,
    )
    .unwrap();
    assert!(
        momento_kalshi::map_market(
            &subcent_bid,
            received,
            Some(MarketId::from_raw(2)),
            Some(GameId::from_raw(10)),
        )
        .is_err()
    );

    let subcent_step: momento_kalshi::KalshiMarket = serde_json::from_str(
        r#"{"ticker":"KXMLBGAME-TEST","event_ticker":"KXMLBGAME-EVT","yes_bid_dollars":"0.8000","yes_ask_dollars":"0.8300","last_price_dollars":"0.8100","updated_time":"2026-08-24T18:00:00Z","result":"","price_level_structure":"linear_cent","price_ranges":[{"start":"0.0000","end":"1.0000","step":"0.0010"}]}"#,
    )
    .unwrap();
    assert!(
        momento_kalshi::map_market(
            &subcent_step,
            received,
            Some(MarketId::from_raw(2)),
            Some(GameId::from_raw(10)),
        )
        .is_err()
    );
}

#[test]
fn linear_cent_price_range_maps_yes_bid_exactly() {
    let received = recv();
    let market: momento_kalshi::KalshiMarket = serde_json::from_str(
        r#"{"ticker":"KXMLBGAME-TEST","event_ticker":"KXMLBGAME-EVT","yes_bid_dollars":"0.8000","yes_ask_dollars":"0.8300","last_price_dollars":"0.9900","updated_time":"2026-08-24T18:00:00Z","result":"","price_level_structure":"linear_cent","price_ranges":[{"start":"0.0000","end":"1.0000","step":"0.0100"}]}"#,
    )
    .unwrap();
    let snap = momento_kalshi::map_market(
        &market,
        received,
        Some(MarketId::from_raw(2)),
        Some(GameId::from_raw(10)),
    )
    .unwrap();
    assert_eq!(snap.bid, Some(Price::from_cents(80).unwrap()));
    assert_eq!(snap.ask, Some(Price::from_cents(83).unwrap()));
    assert_eq!(snap.last, Some(Price::from_cents(99).unwrap()));
    assert_eq!(snap.mid, None);
}

#[test]
fn order_mapping_working_partial_filled_cancelled_rejected() {
    assert_eq!(
        map_order_state("resting", Contracts::ZERO, Contracts::from_u32(3)).unwrap(),
        OrderState::Working
    );
    assert_eq!(
        map_order_state("resting", Contracts::from_u32(1), Contracts::from_u32(2)).unwrap(),
        OrderState::PartiallyFilled
    );
    assert_eq!(
        map_order_state("executed", Contracts::from_u32(3), Contracts::ZERO).unwrap(),
        OrderState::Filled
    );
    assert_eq!(
        map_order_state("canceled", Contracts::from_u32(1), Contracts::ZERO).unwrap(),
        OrderState::Cancelled
    );
}

#[test]
fn fill_json_without_client_order_id_deserializes_empty() {
    let raw = r#"{"trade_id":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa","order_id":"bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb","ticker":"KXMLBGAME-TEST","count_fp":"7.00","yes_price_dollars":"0.8100","ts_ms":1715793600123}"#;
    let parsed: momento_kalshi::KalshiFill = serde_json::from_str(raw).unwrap();
    assert!(parsed.client_order_id.is_empty());
    assert_eq!(parsed.order_id, "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");
}

#[test]
fn fill_json_with_ticker_and_market_ticker_deserializes() {
    let raw = r#"{"trade_id":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa","order_id":"bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb","ticker":"KXMLBGAME-26SEP13CINMIL-MIL","market_ticker":"KXMLBGAME-26SEP13CINMIL-MIL","count_fp":"7.00","yes_price_dollars":"0.8200","created_time":"2026-09-13T20:52:38Z"}"#;
    let parsed: momento_kalshi::KalshiFill = serde_json::from_str(raw).unwrap();
    assert!(parsed.client_order_id.is_empty());
    assert_eq!(parsed.ticker(), "KXMLBGAME-26SEP13CINMIL-MIL");
    assert_eq!(parsed.created_time.as_deref(), Some("2026-09-13T20:52:38Z"));
}

#[test]
fn fill_json_null_client_order_id_deserializes_empty() {
    let raw = r#"{"trade_id":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa","order_id":"bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb","client_order_id":null,"ticker":"KXMLBGAME-TEST","count_fp":"7.00","yes_price_dollars":"0.8100","ts_ms":1715793600123}"#;
    let parsed: momento_kalshi::KalshiFill = serde_json::from_str(raw).unwrap();
    assert!(parsed.client_order_id.is_empty());
}

#[test]
fn client_order_id_is_preserved() {
    let id = ClientOrderId::from_raw(0xaabb_ccdd_ee00_1122_3344_5566_7788_99aa);
    let encoded = encode_client_order_id(id);
    assert_eq!(decode_client_order_id(&encoded).unwrap(), id);
}

#[test]
fn venue_order_id_is_preserved() {
    let transport = ScriptedTransport::new([TransportOutcome::Http {
        status: 201,
        body: created(42, 7),
    }]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let venue_id = venue
        .submit_post_only(&entry_order(7), "KXNBA-TEST")
        .unwrap();
    assert_eq!(venue_id, VenueOrderId::from_raw(42));
}

#[test]
fn working_order_mapping_from_get_order() {
    let transport = ScriptedTransport::new([TransportOutcome::Http {
        status: 200,
        body: kalshi_order_json("resting", "0.00", "3.00", "3.00"),
    }]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let view = venue.get_order(VenueOrderId::from_raw(9)).unwrap();
    assert_eq!(view.state, OrderState::Working);
    assert_eq!(view.filled, Contracts::ZERO);
}

#[test]
fn partial_fill_mapping() {
    let pos = PositionId::from_raw(7);
    let view = KalshiVenue::scripted(ScriptedTransport::new([]), identity(), recv())
        .map_fill(&fill_json(11, 9, 1, "3.00"), pos, recv())
        .unwrap();
    assert_eq!(view.fill.position_id(), pos);
    assert_eq!(view.fill.quantity(), Contracts::from_u32(3));
    assert_eq!(view.fill.price(), Price::from_cents(80).unwrap());
    assert_eq!(view.fill.client_order_id(), ClientOrderId::from_raw(1));
    assert_eq!(view.fill.venue_order_id(), Some(VenueOrderId::from_raw(9)));
}

#[test]
fn complete_fill_mapping() {
    let transport = ScriptedTransport::new([TransportOutcome::Http {
        status: 200,
        body: kalshi_order_json("executed", "3.00", "0.00", "3.00"),
    }]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let view = venue.get_order(VenueOrderId::from_raw(9)).unwrap();
    assert_eq!(view.state, OrderState::Filled);
    assert_eq!(view.filled, Contracts::from_u32(3));
    assert_eq!(view.remaining, Contracts::ZERO);
}

#[test]
fn cancellation_mapping() {
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: created(9, 1),
        },
        TransportOutcome::Http {
            status: 200,
            body: r#"{"order_id":"x","reduced_by":"3.00","ts_ms":1}"#.into(),
        },
    ]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    venue
        .submit_post_only(&entry_order(1), "KXNBA-TEST")
        .unwrap();
    VenueOrders::cancel(&mut venue, ClientOrderId::from_raw(1)).unwrap();
}

#[test]
fn cancel_http_404_is_idempotent_success() {
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: created(9, 1),
        },
        TransportOutcome::Http {
            status: 404,
            body: r#"{"error":{"code":"not_found","message":"order not found"}}"#.into(),
        },
    ]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    venue
        .submit_post_only(&entry_order(1), "KXNBA-TEST")
        .unwrap();
    VenueOrders::cancel(&mut venue, ClientOrderId::from_raw(1)).unwrap();
}

#[test]
fn rejection_mapping() {
    let transport = ScriptedTransport::new([TransportOutcome::Http {
        status: 400,
        body: r#"{"code":"bad_request","message":"invalid"}"#.into(),
    }]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let err = venue
        .submit_post_only(&entry_order(1), "KXNBA-TEST")
        .unwrap_err();
    assert!(matches!(
        err,
        MomentoError::Venue(VenueError::Unsupported(_))
    ));
}

#[test]
fn timeout_maps_to_unknown_and_retains_reservation_semantics() {
    let transport = ScriptedTransport::new([TransportOutcome::Timeout]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let err = venue
        .submit_post_only(&entry_order(1), "KXNBA-TEST")
        .unwrap_err();
    assert!(matches!(err, MomentoError::Venue(VenueError::Timeout)));
    assert!(venue.is_unknown(ClientOrderId::from_raw(1)));
}

#[test]
fn unknown_venue_status_fails_closed() {
    assert!(matches!(
        map_order_state("pending", Contracts::ZERO, Contracts::from_u32(1)),
        Err(VenueError::UnknownVenueStatus(_))
    ));
    assert!(matches!(
        map_order_state("failed", Contracts::ZERO, Contracts::ZERO),
        Err(VenueError::UnknownVenueStatus(_))
    ));
    let transport = ScriptedTransport::new([TransportOutcome::Http {
        status: 200,
        body: kalshi_order_json("pending", "0.00", "3.00", "3.00"),
    }]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let err = venue.get_order(VenueOrderId::from_raw(9)).unwrap_err();
    assert!(matches!(
        err,
        MomentoError::Venue(VenueError::UnknownVenueStatus(_))
    ));
}

#[test]
fn duplicate_fill_events_are_ignored() {
    let mut venue = KalshiVenue::scripted(ScriptedTransport::new([]), identity(), recv());
    let json = fill_json(11, 9, 1, "3.00");
    let first = venue
        .ingest_fill_json(&json, PositionId::from_raw(7))
        .unwrap();
    let second = venue
        .ingest_fill_json(&json, PositionId::from_raw(7))
        .unwrap();
    assert!(first.is_some());
    assert!(second.is_none());
}

#[test]
fn timestamp_preservation() {
    let view = KalshiVenue::scripted(ScriptedTransport::new([]), identity(), recv())
        .map_fill(
            &fill_json(11, 9, 1, "3.00"),
            PositionId::from_raw(7),
            recv(),
        )
        .unwrap();
    assert_eq!(view.fill.client_order_id(), ClientOrderId::from_raw(1));
}

#[test]
fn malformed_response_fails_closed() {
    let transport = ScriptedTransport::new([TransportOutcome::Http {
        status: 201,
        body: "not-json".into(),
    }]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let err = venue
        .submit_post_only(&entry_order(1), "KXNBA-TEST")
        .unwrap_err();
    assert!(matches!(
        err,
        MomentoError::Venue(VenueError::MalformedResponse(_))
    ));
}

#[test]
fn authentication_failure_handling() {
    let transport = ScriptedTransport::new([TransportOutcome::Http {
        status: 401,
        body: r#"{"code":"unauthorized"}"#.into(),
    }]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let err = venue
        .submit_post_only(&entry_order(1), "KXNBA-TEST")
        .unwrap_err();
    assert!(matches!(
        err,
        MomentoError::Venue(VenueError::AuthenticationFailed)
    ));
    assert!(!venue.is_unknown(ClientOrderId::from_raw(1)));
}

#[test]
fn network_timeout_does_not_retry() {
    let transport = ScriptedTransport::new([
        TransportOutcome::Timeout,
        TransportOutcome::Http {
            status: 201,
            body: created(9, 1),
        },
    ]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    assert!(
        venue
            .submit_post_only(&entry_order(1), "KXNBA-TEST")
            .is_err()
    );
    let retry = venue
        .submit_post_only(&entry_order(1), "KXNBA-TEST")
        .unwrap_err();
    assert!(matches!(
        retry,
        MomentoError::Venue(VenueError::AmbiguousSubmission)
    ));
}

#[test]
fn adapter_does_not_create_position_ids() {
    let pos = PositionId::from_raw(7);
    let json = fill_json(11, 9, 1, "3.00");
    let view = KalshiVenue::scripted(ScriptedTransport::new([]), identity(), recv())
        .map_fill(&json, pos, recv())
        .unwrap();
    assert_eq!(view.fill.position_id(), pos);
}

#[test]
fn live_connection_remains_disabled() {
    assert!(UnimplementedLiveKalshi::connect_live().is_err());
    let mut venue = KalshiVenue::disabled(DisabledLiveTransport, identity(), recv());
    let err = venue
        .submit_post_only(&entry_order(1), "KXNBA-TEST")
        .unwrap_err();
    assert!(matches!(err, MomentoError::Venue(VenueError::LiveDisabled)));
}

#[test]
fn signature_payload_strips_query_and_matches_official_form() {
    let payload = signature_payload(
        "1703123456789",
        "GET",
        "/trade-api/v2/portfolio/orders?limit=5",
    );
    assert_eq!(payload, "1703123456789GET/trade-api/v2/portfolio/orders");
}

#[test]
fn subcent_price_and_fractional_count_fail_closed() {
    assert!(dollars_to_price_cents("0.8050").is_err());
    assert!(count_fp_to_contracts("2.50").is_err());
}

#[test]
fn liquidation_reduce_only_ioc_ask_is_submitted() {
    let captured = std::sync::Arc::new(std::sync::Mutex::new(None::<String>));
    struct Capture {
        inner: ScriptedTransport,
        captured: std::sync::Arc<std::sync::Mutex<Option<String>>>,
    }
    impl KalshiTransport for Capture {
        fn execute(&mut self, request: momento_kalshi::KalshiHttpRequest) -> TransportOutcome {
            *self.captured.lock().expect("lock") = request.body.clone();
            self.inner.execute(request)
        }
    }
    let mut venue = KalshiVenue::scripted(
        Capture {
            inner: ScriptedTransport::new([TransportOutcome::Http {
                status: 201,
                body: created(42, 2),
            }]),
            captured: std::sync::Arc::clone(&captured),
        },
        identity(),
        recv(),
    );
    let liq = Order::new_liquidation(
        ClientOrderId::from_raw(2),
        PositionId::from_raw(7),
        GameId::from_raw(10),
        RiskDecisionId::from_raw(1),
        Price::from_cents(40).unwrap(),
        Contracts::from_u32(3),
        MarketId::from_raw(2),
        Side::Yes,
    );
    VenueOrders::submit_reduce_only_liquidation(&mut venue, &liq).unwrap();
    let body = captured.lock().expect("lock").clone().unwrap();
    assert!(body.contains("\"side\":\"ask\""));
    assert!(body.contains("\"reduce_only\":true"));
    assert!(body.contains("\"post_only\":false"));
    assert!(body.contains("\"time_in_force\":\"immediate_or_cancel\""));
    assert!(body.contains("\"price\":\"0.4000\""));
}

#[test]
fn liquidation_uses_market_ticker_not_game_ticker() {
    let captured = std::sync::Arc::new(std::sync::Mutex::new(None::<String>));
    struct Capture {
        inner: ScriptedTransport,
        captured: std::sync::Arc<std::sync::Mutex<Option<String>>>,
    }
    impl KalshiTransport for Capture {
        fn execute(&mut self, request: momento_kalshi::KalshiHttpRequest) -> TransportOutcome {
            *self.captured.lock().expect("lock") = request.body.clone();
            self.inner.execute(request)
        }
    }
    let mut identity = StaticIdentity::new();
    let game = GameId::from_raw(10);
    let wsh_market = MarketId::from_raw(200);
    let col_market = MarketId::from_raw(201);
    identity.bind(
        "KXMLBGAME-COL",
        MarketBinding {
            market_id: col_market,
            game_id: game,
            position_id: None,
        },
    );
    identity.bind(
        "KXMLBGAME-WSH",
        MarketBinding {
            market_id: wsh_market,
            game_id: game,
            position_id: Some(PositionId::from_raw(7)),
        },
    );
    let mut venue = KalshiVenue::scripted(
        Capture {
            inner: ScriptedTransport::new([TransportOutcome::Http {
                status: 201,
                body: created(42, 2),
            }]),
            captured: std::sync::Arc::clone(&captured),
        },
        identity,
        recv(),
    );
    let liq = Order::new_liquidation(
        ClientOrderId::from_raw(2),
        PositionId::from_raw(7),
        game,
        RiskDecisionId::from_raw(1),
        Price::from_cents(40).unwrap(),
        Contracts::from_u32(7),
        wsh_market,
        Side::Yes,
    );
    VenueOrders::submit_reduce_only_liquidation(&mut venue, &liq).unwrap();
    let body = captured.lock().expect("lock").clone().unwrap();
    assert!(body.contains("KXMLBGAME-WSH"));
    assert!(!body.contains("KXMLBGAME-COL"));
}

#[test]
fn liquidation_rejects_ticker_that_does_not_match_market_id() {
    let mut identity = StaticIdentity::new();
    let game = GameId::from_raw(10);
    identity.bind(
        "KXMLBGAME-COL",
        MarketBinding {
            market_id: MarketId::from_raw(201),
            game_id: game,
            position_id: None,
        },
    );
    identity.bind(
        "KXMLBGAME-WSH",
        MarketBinding {
            market_id: MarketId::from_raw(200),
            game_id: game,
            position_id: None,
        },
    );
    let mut venue = KalshiVenue::scripted(ScriptedTransport::new([]), identity, recv());
    let liq = Order::new_liquidation(
        ClientOrderId::from_raw(2),
        PositionId::from_raw(7),
        game,
        RiskDecisionId::from_raw(1),
        Price::from_cents(8).unwrap(),
        Contracts::from_u32(7),
        MarketId::from_raw(200),
        Side::Yes,
    );
    let err = venue
        .submit_reduce_only_liquidation_on(&liq, "KXMLBGAME-COL")
        .unwrap_err();
    assert!(
        err.to_string().contains("does not match position MarketId")
            || matches!(err, MomentoError::Venue(VenueError::Unsupported(_)))
    );
}

#[test]
fn ioc_liquidation_ack_exposes_remaining_zero_after_unfilled_cancel() {
    let mut identity = StaticIdentity::new();
    identity.bind(
        "KXMLBGAME-WSH",
        MarketBinding {
            market_id: MarketId::from_raw(200),
            game_id: GameId::from_raw(10),
            position_id: Some(PositionId::from_raw(7)),
        },
    );
    let mut venue = KalshiVenue::scripted(
        ScriptedTransport::new([TransportOutcome::Http {
            status: 201,
            body: format!(
                r#"{{"order_id":"{}","fill_count":"0.00","remaining_count":"0.00","ts_ms":1715793600123}}"#,
                encode_venue_order_id(VenueOrderId::from_raw(42))
            ),
        }]),
        identity,
        recv(),
    );
    let liq = Order::new_liquidation(
        ClientOrderId::from_raw(2),
        PositionId::from_raw(7),
        GameId::from_raw(10),
        RiskDecisionId::from_raw(1),
        Price::from_cents(40).unwrap(),
        Contracts::from_u32(7),
        MarketId::from_raw(200),
        Side::Yes,
    );
    let ack = venue
        .submit_reduce_only_liquidation_on(&liq, "KXMLBGAME-WSH")
        .unwrap();
    assert_eq!(ack.fill_count, Contracts::from_u32(0));
    assert_eq!(ack.remaining_count, Contracts::from_u32(0));
    assert_eq!(ack.venue_order_id, VenueOrderId::from_raw(42));
}

#[test]
fn best_yes_bid_is_last_yes_dollars_level() {
    let book: momento_kalshi::GetOrderbookResponse = serde_json::from_str(
        r#"{"orderbook_fp":{"yes_dollars":[["0.3900","1.00"],["0.4000","5.00"]],"no_dollars":[]}}"#,
    )
    .unwrap();
    assert_eq!(
        momento_kalshi::best_yes_bid_from_orderbook(&book).unwrap(),
        Some(Price::from_cents(40).unwrap())
    );
}

#[test]
fn websocket_duplicate_seq_is_ignored() {
    let mut d = WsDedupe::new();
    assert!(d.accept_seq(1, 3));
    assert!(!d.accept_seq(1, 3));
    assert!(!d.accept_seq(1, 2));
    assert!(d.accept_seq(1, 4));
    let env = parse_ws_frame(
        r#"{"type":"orderbook_delta","sid":1,"seq":4,"msg":{"market_ticker":"KXNBA-TEST","price_dollars":"0.8000","side":"yes","ts_ms":1}}"#,
    )
    .unwrap();
    assert_eq!(env.msg_type, "orderbook_delta");
}

#[test]
fn websocket_fill_market_ticker_maps_to_ticker() {
    let env = parse_ws_frame(
        r#"{"type":"fill","sid":13,"msg":{"trade_id":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa","order_id":"bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb","market_ticker":"KXMLBGAME-TEST","exchange_index":1,"is_taker":false,"side":"yes","yes_price_dollars":"0.8100","count_fp":"3.00","fee_cost":"0.0000","action":"buy","ts":1715793600,"ts_ms":1715793600123,"client_order_id":"00000000-0000-0000-0000-00000000000b","post_position_fp":"3.00","purchased_side":"yes","outcome_side":"yes","book_side":"bid"}}"#,
    )
    .unwrap();
    let fill = parse_fill_msg(&env).unwrap();
    assert_eq!(fill.ticker(), "KXMLBGAME-TEST");
    assert_eq!(fill.yes_price_dollars.as_deref(), Some("0.8100"));
    assert_eq!(fill.client_order_id, "00000000-0000-0000-0000-00000000000b");
}

#[test]
fn settlement_yes_maps_without_inventing_scalar() {
    let body = r#"{"market":{"ticker":"KXNBA-TEST","event_ticker":"KXNBA-GAME","result":"yes","settlement_value_dollars":"1.0000","settlement_ts":"2026-08-24T19:00:00Z"}}"#;
    let transport = ScriptedTransport::new([TransportOutcome::Http {
        status: 200,
        body: body.into(),
    }]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let s = venue.get_settlement("KXNBA-TEST").unwrap();
    assert_eq!(s.result, Some(Side::Yes));
}

#[test]
fn two_fills_same_position_id() {
    let pos = PositionId::from_raw(7);
    let v = KalshiVenue::scripted(ScriptedTransport::new([]), identity(), recv());
    let a = v
        .map_fill(&fill_json(11, 9, 1, "3.00"), pos, recv())
        .unwrap()
        .fill;
    let b = v
        .map_fill(&fill_json(12, 10, 2, "1.00"), pos, recv())
        .unwrap()
        .fill;
    assert_eq!(a.position_id(), b.position_id());
    assert_ne!(a.client_order_id(), b.client_order_id());
}

fn cutoff_json(orders_updated_ts: i64) -> String {
    format!(r#"{{"orders_updated_ts":{orders_updated_ts}}}"#)
}

fn cutoff_rfc3339(ts: &str) -> String {
    format!(r#"{{"orders_updated_ts":"{ts}"}}"#)
}

fn empty_orders_page() -> String {
    r#"{"orders":[],"cursor":null}"#.into()
}

fn listed_order(status: &str, client: u128) -> String {
    format!(
        r#"{{"orders":[{{"order_id":"{}","client_order_id":"{}","ticker":"KXNBA-TEST","status":"{status}","type":"limit","fill_count_fp":"0.00","remaining_count_fp":"3.00","initial_count_fp":"3.00","yes_price_dollars":"0.8000"}}],"cursor":null}}"#,
        encode_venue_order_id(VenueOrderId::from_raw(9)),
        encode_client_order_id(ClientOrderId::from_raw(client))
    )
}

/// Nanos-based client id after the fixture cutoff (1700000000).
const RECONCILE_CLIENT: u128 = 1_700_000_001_000_000_000;

#[test]
fn create_http_404_user_not_found_is_reject_not_unknown() {
    let transport = ScriptedTransport::new([TransportOutcome::Http {
        status: 404,
        body: r#"{"error":{"code":"user_not_found","message":"user not found"}}"#.into(),
    }]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let err = venue
        .submit_post_only(&entry_order(1), "KXNBA-TEST")
        .unwrap_err();
    assert!(matches!(
        err,
        MomentoError::Venue(VenueError::Unsupported(_))
    ));
    assert!(!venue.is_unknown(ClientOrderId::from_raw(1)));
}

#[test]
fn reconcile_without_venue_id_not_found_after_status_search() {
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 200,
            body: cutoff_json(1_700_000_000),
        },
        TransportOutcome::Http {
            status: 200,
            body: empty_orders_page(),
        },
        TransportOutcome::Http {
            status: 200,
            body: empty_orders_page(),
        },
        TransportOutcome::Http {
            status: 200,
            body: empty_orders_page(),
        },
    ]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let outcome = venue
        .reconcile_unknown(&UnknownOrder {
            client_order_id: ClientOrderId::from_raw(RECONCILE_CLIENT),
        })
        .unwrap();
    assert_eq!(outcome, ReconcileOutcome::NotFound);
}

/// Production unknown order `1787852602753489627` is after the observed
/// `2026-06-28T00:00:00Z` cutoff, so live status search may conclude NotFound.
#[test]
fn reconcile_production_rfc3339_cutoff_not_found() {
    const LIVE_UNKNOWN: u128 = 1_787_852_602_753_489_627;
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 200,
            body: cutoff_rfc3339("2026-06-28T00:00:00Z"),
        },
        TransportOutcome::Http {
            status: 200,
            body: empty_orders_page(),
        },
        TransportOutcome::Http {
            status: 200,
            body: empty_orders_page(),
        },
        TransportOutcome::Http {
            status: 200,
            body: empty_orders_page(),
        },
    ]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let outcome = venue
        .reconcile_unknown(&UnknownOrder {
            client_order_id: ClientOrderId::from_raw(LIVE_UNKNOWN),
        })
        .unwrap();
    assert_eq!(outcome, ReconcileOutcome::NotFound);
}

#[test]
fn reconcile_without_venue_id_found_in_canceled() {
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 200,
            body: cutoff_json(1_700_000_000),
        },
        TransportOutcome::Http {
            status: 200,
            body: empty_orders_page(),
        },
        TransportOutcome::Http {
            status: 200,
            body: listed_order("canceled", RECONCILE_CLIENT),
        },
    ]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let outcome = venue
        .reconcile_unknown(&UnknownOrder {
            client_order_id: ClientOrderId::from_raw(RECONCILE_CLIENT),
        })
        .unwrap();
    assert_eq!(outcome, ReconcileOutcome::Found);
    assert_eq!(
        venue
            .venue_order_id(ClientOrderId::from_raw(RECONCILE_CLIENT))
            .unwrap(),
        Some(VenueOrderId::from_raw(9))
    );
}

#[test]
fn reconcile_stays_ambiguous_when_historical_cutoff_hides_order() {
    let transport = ScriptedTransport::new([TransportOutcome::Http {
        status: 200,
        body: cutoff_json(1_800_000_000),
    }]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let outcome = venue
        .reconcile_unknown(&UnknownOrder {
            client_order_id: ClientOrderId::from_raw(RECONCILE_CLIENT),
        })
        .unwrap();
    assert_eq!(outcome, ReconcileOutcome::Ambiguous);
}

#[test]
fn reconcile_status_search_timeout_is_ambiguous() {
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 200,
            body: cutoff_json(1_700_000_000),
        },
        TransportOutcome::Timeout,
    ]);
    let mut venue = KalshiVenue::scripted(transport, identity(), recv());
    let outcome = venue
        .reconcile_unknown(&UnknownOrder {
            client_order_id: ClientOrderId::from_raw(RECONCILE_CLIENT),
        })
        .unwrap();
    assert_eq!(outcome, ReconcileOutcome::Ambiguous);
}
