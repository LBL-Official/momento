//! M9 production read-only authentication. Does not place or cancel orders.

use momento_core::{
    ClientOrderId, Contracts, GameId, MarketId, Order, PositionId, Price, ReceivedAt,
    RiskDecisionId, TradingConfig, utc_now,
};
use momento_kalshi::{
    BALANCE_PATH, CREATE_ORDER_PATH, DisabledLiveTransport, EXCHANGE_STATUS_PATH,
    GetBalanceResponse, KalshiCredentials, KalshiEnvironment, KalshiHttpRequest, KalshiTransport,
    KalshiVenue, MarketBinding, ProductionReadOnlyTransport, REST_PRODUCTION, StaticIdentity,
    UnimplementedLiveKalshi, credentials_from_secret_file, redact_secrets, refuse_if_demo,
};

fn main() {
    if let Err(err) = run() {
        eprintln!("prod-auth-validate fatal: {}", redact_secrets(&err));
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    assert_live_stays_disarmed()?;
    refuse_if_demo(REST_PRODUCTION).map_err(|e| e.to_string())?;
    if UnimplementedLiveKalshi::connect_live().is_ok() {
        return Err("live Kalshi connect must remain unimplemented".into());
    }

    let creds = load_production_creds()?;
    if creds.environment() != KalshiEnvironment::Production {
        return Err("credentials are not tagged production".into());
    }

    let mut transport =
        ProductionReadOnlyTransport::production(creds).map_err(|e| e.to_string())?;
    println!("host={}", transport.origin());
    println!("environment=production");
    println!("live.enabled=false");
    println!("live_implemented=false");
    println!("mode=paper");

    let public = public_exchange_status()?;
    println!(
        "exchange_status_http={} exchange_status_ok={}",
        public.status, public.ok
    );

    let status = transport.execute(KalshiHttpRequest {
        method: "GET".into(),
        path: EXCHANGE_STATUS_PATH.into(),
        body: None,
    });
    match status {
        momento_kalshi::TransportOutcome::Http { status, .. } => {
            println!("signed_exchange_status_http={status}");
        }
        momento_kalshi::TransportOutcome::Timeout => {
            return Err("signed production exchange status timed out".into());
        }
    }

    let balance = transport.execute(KalshiHttpRequest {
        method: "GET".into(),
        path: BALANCE_PATH.into(),
        body: None,
    });
    match balance {
        momento_kalshi::TransportOutcome::Http { status: 200, body } => {
            let parsed: Result<GetBalanceResponse, _> = serde_json::from_str(&body);
            let present = parsed
                .ok()
                .map(|b| b.balance_dollars.is_some() || b.balance >= 0)
                .unwrap_or_else(|| body.contains("balance"));
            println!("production_auth=true balance_http=200 balance_field_present={present}");
        }
        momento_kalshi::TransportOutcome::Http { status, body } => {
            println!(
                "production_auth=false balance_http={status} body={}",
                redact_secrets(&body)
            );
            return Err(format!("production balance read failed HTTP {status}"));
        }
        momento_kalshi::TransportOutcome::Timeout => {
            return Err("production balance read timed out".into());
        }
    }

    let create = transport.execute(KalshiHttpRequest {
        method: "POST".into(),
        path: CREATE_ORDER_PATH.into(),
        body: Some("{}".into()),
    });
    let cancel = transport.execute(KalshiHttpRequest {
        method: "DELETE".into(),
        path: format!("{CREATE_ORDER_PATH}/00000000-0000-0000-0000-000000000000"),
        body: None,
    });
    let orders_sent = transport.mutating_request_was_sent();
    println!(
        "order_submit_sent={} order_cancel_sent={} create_refused={} cancel_refused={}",
        orders_sent,
        orders_sent,
        matches!(
            create,
            momento_kalshi::TransportOutcome::Http { status: 0, .. }
        ),
        matches!(
            cancel,
            momento_kalshi::TransportOutcome::Http { status: 0, .. }
        )
    );
    if orders_sent {
        return Err("mutating Kalshi request was sent; aborting".into());
    }

    let mut disabled = KalshiVenue::disabled(
        DisabledLiveTransport,
        {
            let mut identity = StaticIdentity::new();
            identity.bind(
                "KXNBA-TEST",
                MarketBinding {
                    market_id: MarketId::from_raw(2),
                    game_id: GameId::from_raw(10),
                    position_id: Some(PositionId::from_raw(7)),
                },
            );
            identity
        },
        ReceivedAt::from_utc(utc_now()),
    );
    let order = Order::new_entry(
        ClientOrderId::from_raw(1),
        PositionId::from_raw(7),
        GameId::from_raw(10),
        RiskDecisionId::from_raw(1),
        Price::from_cents(80).map_err(|e| e.to_string())?,
        Contracts::from_u32(1),
    );
    if disabled.submit_post_only(&order, "KXNBA-TEST").is_ok() {
        return Err("disabled venue must not submit orders".into());
    }
    println!("disabled_venue_submit=false");
    println!("read_only_sent={}", transport.sent_paths().join(","));
    Ok(())
}

fn load_production_creds() -> Result<KalshiCredentials, String> {
    if let Ok(path) = std::env::var(momento_kalshi::ENV_KALSHI_SECRET_FILE) {
        return credentials_from_secret_file(KalshiEnvironment::Production, path.as_ref())
            .map_err(|e| e.to_string());
    }
    KalshiCredentials::from_production_env().map_err(|e| e.to_string())
}

fn assert_live_stays_disarmed() -> Result<(), String> {
    let paper = include_str!("../../../config/paper.toml");
    let cfg = TradingConfig::from_toml_str(paper).map_err(|e| e.to_string())?;
    cfg.validate().map_err(|e| e.to_string())?;
    if cfg.live.enabled {
        return Err("paper live.enabled must remain false".into());
    }
    Ok(())
}

struct PublicStatus {
    ok: bool,
    status: u16,
}

fn public_exchange_status() -> Result<PublicStatus, String> {
    let url = format!(
        "{}{EXCHANGE_STATUS_PATH}",
        "https://external-api.kalshi.com"
    );
    match ureq::get(&url)
        .timeout(std::time::Duration::from_secs(15))
        .call()
    {
        Ok(r) => Ok(PublicStatus {
            ok: r.status() == 200,
            status: r.status(),
        }),
        Err(ureq::Error::Status(status, _)) => Ok(PublicStatus { ok: false, status }),
        Err(_) => Err("production exchange status request failed".into()),
    }
}
