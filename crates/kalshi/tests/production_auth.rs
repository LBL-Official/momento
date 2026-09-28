//! M9 production credential safety. No live sockets. No real keys.

use std::sync::OnceLock;

use chrono::{TimeZone, Utc};
use momento_core::error::VenueError;
use momento_core::{
    ClientOrderId, Contracts, GameId, MarketId, Order, PositionId, Price, ReceivedAt,
    RiskDecisionId, TradingConfig,
};
use momento_kalshi::{
    CREATE_ORDER_PATH, DisabledLiveTransport, EXCHANGE_STATUS_PATH, FILLS_PATH, KalshiCredentials,
    KalshiEnvironment, KalshiHttpRequest, KalshiTransport, KalshiVenue, MARKETS_PATH,
    MarketBinding, POSITIONS_PATH, ProductionObserveTransport, ProductionReadOnlyTransport,
    ProductionTradingTransport, REST_DEMO_ORIGIN, REST_DEMO_SHARED, REST_PRODUCTION,
    SandboxHttpTransport, ScriptedTransport, StaticIdentity, TransportOutcome,
    UnimplementedLiveKalshi, create_order_is_blocked, credentials_from_secret_json,
    is_mutating_kalshi_request, production_observe_allows, production_read_only_allows,
    production_trading_allows, redact_secrets, refuse_if_demo, refuse_if_production,
    require_host_matches_credentials,
};
use rand::rngs::OsRng;
use rsa::RsaPrivateKey;
use rsa::pkcs1::{EncodeRsaPrivateKey, LineEnding};

fn recv() -> ReceivedAt {
    ReceivedAt::from_utc(
        Utc.with_ymd_and_hms(2026, 8, 24, 18, 0, 0)
            .single()
            .unwrap(),
    )
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

fn entry_order() -> Order {
    Order::new_entry(
        ClientOrderId::from_raw(1),
        PositionId::from_raw(7),
        GameId::from_raw(10),
        RiskDecisionId::from_raw(1),
        Price::from_cents(80).unwrap(),
        Contracts::from_u32(1),
    )
}

fn test_pem() -> &'static str {
    static PEM: OnceLock<String> = OnceLock::new();
    PEM.get_or_init(|| {
        let key = RsaPrivateKey::new(&mut OsRng, 2048).expect("test rsa key");
        key.to_pkcs1_pem(LineEnding::LF)
            .expect("test pem")
            .to_string()
    })
}

fn demo_creds() -> KalshiCredentials {
    KalshiCredentials::from_pem(
        KalshiEnvironment::Demo,
        "00000000-0000-0000-0000-000000000001",
        test_pem(),
    )
    .unwrap()
}

fn prod_creds() -> KalshiCredentials {
    KalshiCredentials::from_pem(
        KalshiEnvironment::Production,
        "00000000-0000-0000-0000-000000000002",
        test_pem(),
    )
    .unwrap()
}

#[test]
fn credentials_are_never_logged() {
    let creds = prod_creds();
    let debug = format!("{creds:?}");
    assert!(!debug.contains(test_pem()));
    assert!(!debug.contains("00000000-0000-0000-0000-000000000002"));
    assert!(debug.contains("[REDACTED]"));
    let signed = creds.sign("GET", EXCHANGE_STATUS_PATH).unwrap();
    let signed_debug = format!("{signed:?}");
    assert!(!signed_debug.contains(&signed.signature));
    assert!(!signed_debug.contains(&signed.key_id));
    let leaked = format!(
        "KALSHI-ACCESS-SIGNATURE: {}\napi_key_id={}\n{}",
        signed.signature,
        signed.key_id,
        test_pem()
    );
    let redacted = redact_secrets(&leaked);
    assert!(!redacted.contains(&signed.signature));
    assert!(!redacted.contains(&signed.key_id));
    assert!(!redacted.contains("BEGIN RSA PRIVATE KEY"));
}

#[test]
fn demo_credentials_cannot_select_production() {
    assert!(SandboxHttpTransport::demo(prod_creds()).is_err());
    assert!(require_host_matches_credentials(KalshiEnvironment::Demo, REST_PRODUCTION).is_err());
    assert!(refuse_if_production(REST_PRODUCTION).is_err());
}

#[test]
fn demo_http_uses_official_demo_origin() {
    let transport = SandboxHttpTransport::demo(demo_creds()).unwrap();
    assert_eq!(transport.origin(), REST_DEMO_ORIGIN);
}

#[test]
fn production_credentials_cannot_select_demo() {
    assert!(ProductionReadOnlyTransport::production(demo_creds()).is_err());
    assert!(
        require_host_matches_credentials(KalshiEnvironment::Production, REST_DEMO_SHARED).is_err()
    );
    assert!(refuse_if_demo(REST_DEMO_SHARED).is_err());
    assert!(ProductionReadOnlyTransport::with_origin(prod_creds(), REST_DEMO_SHARED).is_err());
}

#[test]
fn secret_json_environment_must_match() {
    let json = format!(
        r#"{{"environment":"demo","api_key_id":"00000000-0000-0000-0000-000000000001","private_key_pem":{}}}"#,
        serde_json::json!(test_pem())
    );
    assert!(matches!(
        credentials_from_secret_json(KalshiEnvironment::Production, &json),
        Err(VenueError::EnvironmentMismatch)
    ));
    let prod_json = format!(
        r#"{{"environment":"production","api_key_id":"00000000-0000-0000-0000-000000000002","private_key_pem":{}}}"#,
        serde_json::json!(test_pem())
    );
    assert!(matches!(
        credentials_from_secret_json(KalshiEnvironment::Demo, &prod_json),
        Err(VenueError::EnvironmentMismatch)
    ));
    assert!(credentials_from_secret_json(KalshiEnvironment::Production, &prod_json).is_ok());
}

#[test]
fn production_read_only_refuses_orders_without_sending() {
    assert!(create_order_is_blocked());
    assert!(is_mutating_kalshi_request("POST", CREATE_ORDER_PATH));
    assert!(is_mutating_kalshi_request(
        "DELETE",
        "/trade-api/v2/portfolio/events/orders/abc"
    ));
    assert!(production_read_only_allows("GET", EXCHANGE_STATUS_PATH));
    assert!(!production_read_only_allows("POST", CREATE_ORDER_PATH));
    let mut transport = ProductionReadOnlyTransport::production(prod_creds()).unwrap();
    let outcome = transport.execute(KalshiHttpRequest {
        method: "POST".into(),
        path: CREATE_ORDER_PATH.into(),
        body: Some("{}".into()),
    });
    assert!(matches!(outcome, TransportOutcome::Http { status: 0, .. }));
    assert!(!transport.mutating_request_was_sent());
    assert_eq!(transport.sent_paths().len(), 0);
    assert_eq!(transport.refused_requests().len(), 1);
}

#[test]
fn live_enabled_false_prevents_order_submission_with_production_credentials() {
    let cfg = TradingConfig::from_toml_str(include_str!("../../../config/paper.toml")).unwrap();
    cfg.validate().unwrap();
    assert!(!cfg.live.enabled);
    assert!(UnimplementedLiveKalshi::connect_live().is_err());

    let mut disabled = KalshiVenue::disabled(DisabledLiveTransport, identity(), recv());
    let err = disabled
        .submit_post_only(&entry_order(), "KXNBA-TEST")
        .unwrap_err();
    assert!(matches!(
        err,
        momento_core::MomentoError::Venue(VenueError::LiveDisabled)
    ));

    // Even if a sandbox venue is mistakenly wrapped around production read-only,
    // the POST is refused locally and never sent.
    let transport = ProductionReadOnlyTransport::production(prod_creds()).unwrap();
    let mut venue = KalshiVenue::sandbox(transport, identity(), recv());
    let err = venue
        .submit_post_only(&entry_order(), "KXNBA-TEST")
        .unwrap_err();
    assert!(matches!(
        err,
        momento_core::MomentoError::Venue(VenueError::Unsupported(_))
            | momento_core::MomentoError::Venue(VenueError::ProductionReadOnly)
            | momento_core::MomentoError::Venue(VenueError::LiveDisabled)
            | momento_core::MomentoError::Venue(VenueError::MalformedResponse(_))
    ));
}

#[test]
fn scripted_success_cannot_bypass_disabled_access() {
    let transport = ScriptedTransport::new([TransportOutcome::Http {
        status: 201,
        body: r#"{"order_id":"00000000-0000-0000-0000-000000000099","fill_count":"0.00","remaining_count":"1.00","ts_ms":1}"#.into(),
    }]);
    let mut venue = KalshiVenue::disabled(transport, identity(), recv());
    assert!(
        venue
            .submit_post_only(&entry_order(), "KXNBA-TEST")
            .is_err()
    );
}

#[test]
fn production_trading_transport_rejects_demo_credentials() {
    assert!(ProductionTradingTransport::production(demo_creds()).is_err());
    assert!(ProductionTradingTransport::production(prod_creds()).is_ok());
}

#[test]
fn production_trading_allowlist_is_entry_cancel_and_reads_only() {
    assert!(production_trading_allows("POST", CREATE_ORDER_PATH));
    assert!(production_trading_allows(
        "DELETE",
        "/trade-api/v2/portfolio/events/orders/00000000-0000-0000-0000-000000000001"
    ));
    assert!(production_trading_allows("GET", MARKETS_PATH));
    assert!(production_trading_allows(
        "GET",
        "/trade-api/v2/portfolio/orders"
    ));
    assert!(!production_trading_allows("PATCH", CREATE_ORDER_PATH));
    assert!(!production_trading_allows(
        "POST",
        "/trade-api/v2/portfolio/orders/amend"
    ));
    let mut transport = ProductionTradingTransport::production(prod_creds()).unwrap();
    let refused = transport.execute(KalshiHttpRequest {
        method: "POST".into(),
        path: "/trade-api/v2/portfolio/orders/amend".into(),
        body: Some("{}".into()),
    });
    assert!(matches!(refused, TransportOutcome::Http { status: 0, .. }));
}

#[test]
fn production_read_only_allows_markets_but_not_orders() {
    assert!(production_read_only_allows("GET", MARKETS_PATH));
    assert!(!production_read_only_allows("POST", CREATE_ORDER_PATH));
    assert!(!production_read_only_allows(
        "GET",
        "/trade-api/v2/portfolio/orders"
    ));
}

#[test]
fn production_read_only_allows_get_fills_and_positions() {
    assert!(production_read_only_allows("GET", FILLS_PATH));
    assert!(production_read_only_allows(
        "GET",
        "/trade-api/v2/portfolio/fills?limit=200"
    ));
    assert!(production_read_only_allows("GET", POSITIONS_PATH));
    assert!(!production_read_only_allows("POST", FILLS_PATH));
    assert!(!production_read_only_allows("DELETE", FILLS_PATH));
    assert!(create_order_is_blocked());
}

#[test]
fn production_observe_is_get_only() {
    for path in [
        "/trade-api/v2/portfolio/balance?exchange_index=0",
        "/trade-api/v2/portfolio/orders?status=resting",
        "/trade-api/v2/portfolio/settlements",
        "/trade-api/v2/events?series_ticker=KXNBAGAME",
        "/trade-api/v2/series/KXNBAGAME",
        "/trade-api/v2/milestones?related_event_ticker=X",
        "/trade-api/v2/live_data/basketball_game/milestone/abc",
        "/trade-api/v2/portfolio/subaccounts/balances",
        "/trade-api/v2/portfolio/subaccounts/netting",
        "/trade-api/v2/portfolio/target_balance_allocation",
        "/trade-api/v2/account/limits",
        "/trade-api/v2/historical/cutoff",
        "/trade-api/v2/series/fee_changes?series_ticker=KXNBAGAME",
    ] {
        assert!(production_observe_allows("GET", path), "{path}");
    }
    for path in [
        "/trade-api/v2/portfolio/subaccounts",
        "/trade-api/v2/portfolio/subaccounts/transfer",
        "/trade-api/v2/portfolio/subaccounts/netting",
        "/trade-api/v2/portfolio/target_balance_allocation",
        "/trade-api/v2/portfolio/intra_exchange_instance_transfer",
    ] {
        for method in ["POST", "PUT", "DELETE"] {
            assert!(!production_observe_allows(method, path), "{method} {path}");
        }
    }
    for method in ["POST", "PUT", "PATCH", "DELETE"] {
        assert!(!production_observe_allows(method, CREATE_ORDER_PATH));
        assert!(!production_observe_allows(
            method,
            "/trade-api/v2/portfolio/balance"
        ));
    }
    assert!(!production_observe_allows(
        "GET",
        "/trade-api/v2/portfolio/transfers"
    ));
    assert!(ProductionObserveTransport::production(demo_creds()).is_err());
    let mut transport = ProductionObserveTransport::production(prod_creds()).unwrap();
    for (method, body) in [("POST", Some("{}")), ("DELETE", None), ("GET", Some("{}"))] {
        let outcome = transport.execute(KalshiHttpRequest {
            method: method.into(),
            path: "/trade-api/v2/portfolio/orders".into(),
            body: body.map(str::to_string),
        });
        assert!(matches!(outcome, TransportOutcome::Http { status: 0, .. }));
    }
    assert_eq!(transport.refused_count(), 3);
    assert_eq!(transport.sent_count(), 0);
    assert!(!transport.non_get_was_sent());
}

#[test]
fn live_confirmation_is_mandatory_in_config() {
    let live = TradingConfig::from_toml_str(include_str!("../../../config/live.toml")).unwrap();
    live.validate().unwrap();
    assert!(live.is_live_armed());
    assert_eq!(live.live.confirmation, momento_core::LIVE_CONFIRMATION);
}
