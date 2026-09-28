//! M8 sandbox validation: demo/sandbox Kalshi only. Does not arm live trading.

use std::time::Instant;

use momento_core::{
    ClientOrderId, Contracts, GameId, MarketId, Order, OrderPresence, OrderState, PositionId,
    Price, ReceivedAt, RiskDecisionId, StrategyId, TradingConfig, VenueAccount, VenueOrderSnapshot,
    VenueOrderStatus, VenueOrders, utc_now,
};
use momento_kalshi::{
    GetBalanceResponse, GetFillsResponse, GetMarketsResponse, KalshiHttpRequest, KalshiMarket,
    KalshiTransport, KalshiVenue, MarketBinding, REST_PRODUCTION, SandboxCredentials,
    SandboxHttpTransport, SandboxWs, StaticIdentity, WS_PRODUCTION, dollars_to_price_cents,
    encode_client_order_id, encode_venue_order_id, map_fill, mapped_order_to_snapshot,
    redact_secrets, refuse_if_production,
};
use momento_pnl::PnlBreakdown;
use momento_positions::{InMemoryPositionTracker, PositionEvent, PositionTracker};
use momento_strategy_mlb::{MlbGamePhase, MlbGameSnapshot, MlbStrategy, MlbStrategySnapshot};

fn main() {
    if let Err(err) = run() {
        eprintln!("sandbox-validate fatal: {}", redact_secrets(&err));
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    assert_live_stays_disarmed()?;
    if refuse_if_production(REST_PRODUCTION).is_ok() {
        return Err("production REST URL must be refused".into());
    }
    if refuse_if_production(WS_PRODUCTION).is_ok() {
        return Err("production websocket URL must be refused".into());
    }

    let creds = SandboxCredentials::from_env().map_err(|e| e.to_string())?;
    let transport = SandboxHttpTransport::demo(creds.clone()).map_err(|e| e.to_string())?;
    println!("host={}", transport.origin());
    println!("environment=demo");
    println!("live.enabled=false");
    println!("live_implemented=false");

    let rest = rest_probe(&creds)?;
    println!(
        "rest_status={} rest_http={} rest_latency_ms={}",
        rest.ok, rest.status, rest.latency_ms
    );

    let public = public_demo_status()?;
    println!(
        "demo_exchange_status_http={} demo_exchange_status_latency_ms={}",
        public.status, public.latency_ms
    );

    let snapshot_ok = snapshot_survives_disconnect();
    println!("m6_snapshot_consistent_across_disconnect={snapshot_ok}");

    let ws = if rest.ok {
        match ws_probe(&creds) {
            Ok(ws) => ws,
            Err(err) => {
                println!("ws_status=false ws_error={}", redact_secrets(&err));
                WsProbe {
                    connected: false,
                    reconnect: false,
                    frames: 0,
                }
            }
        }
    } else {
        println!("ws_status=skipped (demo auth failed; production was not contacted)");
        WsProbe {
            connected: false,
            reconnect: false,
            frames: 0,
        }
    };
    if rest.ok {
        println!(
            "ws_status={} ws_reconnect={} ws_frames={}",
            ws.connected, ws.reconnect, ws.frames
        );
    }

    let orders = if rest.ok {
        match order_lifecycle(&creds) {
            Ok(orders) => orders,
            Err(err) => {
                println!("order_place=false order_error={}", redact_secrets(&err));
                OrderProbe {
                    placed: false,
                    polled: false,
                    cancelled: false,
                    fills: 0,
                    client: None,
                    ticker: None,
                }
            }
        }
    } else {
        println!("order_place=skipped (demo auth failed; production was not contacted)");
        OrderProbe {
            placed: false,
            polled: false,
            cancelled: false,
            fills: 0,
            client: None,
            ticker: None,
        }
    };
    if rest.ok {
        println!(
            "order_place={} order_poll={} order_cancel={} fills_ingested={}",
            orders.placed, orders.polled, orders.cancelled, orders.fills
        );
        if let Some(ticker) = &orders.ticker {
            println!("order_ticker={ticker}");
        }
    }

    let recon = recon_and_pnl(&orders)?;
    println!(
        "recon_outcome={} recon_state={} pnl_realized_is_none={}",
        recon.outcome, recon.state, recon.realized_none
    );

    let redaction_ok = redaction_audit();
    println!("log_redaction_ok={redaction_ok}");
    Ok(())
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

struct RestProbe {
    ok: bool,
    status: u16,
    latency_ms: u128,
}

fn rest_probe(creds: &SandboxCredentials) -> Result<RestProbe, String> {
    let mut transport = SandboxHttpTransport::demo(creds.clone()).map_err(|e| e.to_string())?;
    let started = Instant::now();
    let outcome = transport.execute(KalshiHttpRequest {
        method: "GET".into(),
        path: "/trade-api/v2/portfolio/balance".into(),
        body: None,
    });
    let latency_ms = started.elapsed().as_millis();
    match outcome {
        momento_kalshi::TransportOutcome::Http { status, body } if status == 200 => {
            let parsed: Result<GetBalanceResponse, _> = serde_json::from_str(&body);
            if let Ok(bal) = parsed {
                println!(
                    "demo_balance_cents={} demo_balance_dollars={}",
                    bal.balance,
                    bal.balance_dollars.as_deref().unwrap_or("none")
                );
            } else {
                let v: serde_json::Value =
                    serde_json::from_str(&body).map_err(|e| redact_secrets(&e.to_string()))?;
                v.get("balance")
                    .and_then(|b| b.as_i64())
                    .ok_or_else(|| "balance missing".to_string())?;
            }
            Ok(RestProbe {
                ok: true,
                status,
                latency_ms,
            })
        }
        momento_kalshi::TransportOutcome::Http { status, body } => {
            println!(
                "rest_auth_error status={status} body={}",
                redact_secrets(&body)
            );
            Ok(RestProbe {
                ok: false,
                status,
                latency_ms,
            })
        }
        momento_kalshi::TransportOutcome::Timeout => Err("demo REST timed out".into()),
    }
}

fn public_demo_status() -> Result<RestProbe, String> {
    let started = Instant::now();
    let resp = ureq::get("https://demo-api.kalshi.co/trade-api/v2/exchange/status")
        .timeout(std::time::Duration::from_secs(15))
        .call();
    let latency_ms = started.elapsed().as_millis();
    match resp {
        Ok(r) => Ok(RestProbe {
            ok: r.status() == 200,
            status: r.status(),
            latency_ms,
        }),
        Err(ureq::Error::Status(status, _)) => Ok(RestProbe {
            ok: false,
            status,
            latency_ms,
        }),
        Err(_) => Err("demo exchange status request failed".into()),
    }
}

struct WsProbe {
    connected: bool,
    reconnect: bool,
    frames: usize,
}

fn ws_probe(creds: &SandboxCredentials) -> Result<WsProbe, String> {
    let mut frames = 0;
    let mut first = SandboxWs::connect(creds).map_err(|e| e.to_string())?;
    first.subscribe_ticker().map_err(|e| e.to_string())?;
    for _ in 0..5 {
        match first.read_text() {
            Ok(Some(_)) => frames += 1,
            Ok(None) => {}
            Err(_) => break,
        }
    }
    first.close();
    let mut second = SandboxWs::connect(creds).map_err(|e| e.to_string())?;
    second.subscribe_ticker().map_err(|e| e.to_string())?;
    let _ = second.read_text();
    second.close();
    Ok(WsProbe {
        connected: true,
        reconnect: true,
        frames,
    })
}

fn snapshot_survives_disconnect() -> bool {
    let mut snap = MlbGameSnapshot::new(GameId::from_raw(10));
    snap.phase = MlbGamePhase::GameLocked;
    let before = MlbStrategy::restore(MlbStrategySnapshot {
        games: vec![snap.clone()],
    })
    .snapshot();
    // Simulated WS disconnect: strategy state is file/memory, not the socket.
    let after = MlbStrategy::restore(before.clone()).snapshot();
    after.games.len() == 1 && after.games[0].phase == MlbGamePhase::GameLocked
}

struct OrderProbe {
    placed: bool,
    polled: bool,
    cancelled: bool,
    fills: usize,
    client: Option<ClientOrderId>,
    ticker: Option<String>,
}

fn order_lifecycle(creds: &SandboxCredentials) -> Result<OrderProbe, String> {
    let mut transport = SandboxHttpTransport::demo(creds.clone()).map_err(|e| e.to_string())?;
    let markets_out = transport.execute(KalshiHttpRequest {
        method: "GET".into(),
        path: "/trade-api/v2/markets?limit=200&status=open".into(),
        body: None,
    });
    let markets = match markets_out {
        momento_kalshi::TransportOutcome::Http { status: 200, body } => {
            serde_json::from_str::<GetMarketsResponse>(&body).map_err(|e| e.to_string())?
        }
        momento_kalshi::TransportOutcome::Http { status, body } => {
            return Err(format!("markets HTTP {status}: {}", redact_secrets(&body)));
        }
        momento_kalshi::TransportOutcome::Timeout => return Err("markets timeout".into()),
    };
    let ticker = pick_resting_ticker(&markets.markets).ok_or("no open demo market")?;
    let mut identity = StaticIdentity::new();
    identity.bind(
        ticker.clone(),
        MarketBinding {
            market_id: MarketId::from_raw(2),
            game_id: GameId::from_raw(10),
            position_id: Some(PositionId::from_raw(7)),
        },
    );
    let recv = ReceivedAt::from_utc(utc_now());
    let mut venue = KalshiVenue::sandbox(transport, identity, recv);
    let client = ClientOrderId::from_raw(unix_client_id());
    let order = Order::new_entry(
        client,
        PositionId::from_raw(7),
        GameId::from_raw(10),
        RiskDecisionId::from_raw(1),
        Price::from_cents(1).map_err(|e| e.to_string())?,
        Contracts::from_u32(1),
    );
    venue
        .submit_post_only(&order, &ticker)
        .map_err(|e| redact_secrets(&e.to_string()))?;
    let venue_id = venue
        .venue_order_id(client)
        .ok()
        .flatten()
        .ok_or("missing venue order id")?;
    let view = venue
        .get_order(venue_id)
        .map_err(|e| redact_secrets(&e.to_string()))?;
    let polled = matches!(
        view.state,
        OrderState::Working | OrderState::PartiallyFilled | OrderState::Filled
    );
    VenueOrders::cancel(&mut venue, client).map_err(|e| redact_secrets(&e.to_string()))?;

    let mut fills = 0;
    let fills_out = {
        // Re-bind transport by reconstructing is not possible; GET fills via a fresh transport.
        let mut t = SandboxHttpTransport::demo(creds.clone()).map_err(|e| e.to_string())?;
        t.execute(KalshiHttpRequest {
            method: "GET".into(),
            path: format!(
                "/trade-api/v2/portfolio/fills?limit=10&order_id={}",
                encode_venue_order_id(venue_id)
            ),
            body: None,
        })
    };
    if let momento_kalshi::TransportOutcome::Http { status: 200, body } = fills_out {
        if let Ok(parsed) = serde_json::from_str::<GetFillsResponse>(&body) {
            for mut fill in parsed.fills {
                if fill.client_order_id.is_empty() {
                    fill.client_order_id = encode_client_order_id(client);
                }
                if map_fill(&fill, PositionId::from_raw(7), recv).is_ok() {
                    fills += 1;
                }
            }
        }
    }

    Ok(OrderProbe {
        placed: true,
        polled,
        cancelled: true,
        fills,
        client: Some(client),
        ticker: Some(ticker),
    })
}

fn pick_resting_ticker(markets: &[KalshiMarket]) -> Option<String> {
    // A 1-cent post-only bid can rest only when the YES ask is strictly above 1 cent.
    // This is adapter validation, not the MLB 80–83 entry band.
    markets.iter().find_map(|m| {
        if m.ticker.is_empty() {
            return None;
        }
        let ask = m.yes_ask_dollars.as_deref()?;
        let ask_cents = dollars_to_price_cents(ask).ok()?.cents();
        if ask_cents > 1 {
            Some(m.ticker.clone())
        } else {
            None
        }
    })
}

fn unix_client_id() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(1)
}

struct ReconProbe {
    outcome: String,
    state: String,
    realized_none: bool,
}

fn recon_and_pnl(orders: &OrderProbe) -> Result<ReconProbe, String> {
    let mut tracker = InMemoryPositionTracker::new();
    let now = utc_now();
    let snap = momento_core::WeeklyBankrollSnapshot::capture(
        momento_core::Money::from_usd(50, 0).unwrap(),
        momento_core::Bps::PCT_12_5,
        now,
        momento_core::SnapshotSource::Test,
    )
    .map_err(|e| e.to_string())?;
    let pid = tracker
        .get_or_create(
            StrategyId::from_raw(1),
            GameId::from_raw(10),
            &snap,
            Some(MarketId::from_raw(2)),
            Some(momento_core::Side::Yes),
        )
        .id();
    let client = orders.client.unwrap_or(ClientOrderId::from_raw(1));
    let order = Order::new_entry(
        client,
        pid,
        GameId::from_raw(10),
        RiskDecisionId::from_raw(1),
        Price::from_cents(1).map_err(|e| e.to_string())?,
        Contracts::from_u32(1),
    );
    tracker
        .apply_event(PositionEvent::OrderSubmitted { order })
        .map_err(|e| format!("{e:?}"))?;
    tracker
        .apply_event(PositionEvent::Unknown {
            client_order_id: client,
        })
        .map_err(|e| format!("{e:?}"))?;

    let mut venue_snap = if orders.placed {
        VenueOrderSnapshot {
            presence: OrderPresence::Found,
            venue_order_id: None,
            venue_status: Some(OrderState::Cancelled),
            venue_filled: Some(Contracts::ZERO),
            venue_remaining: Some(Contracts::ZERO),
            venue_fill_prices: Vec::new(),
            venue_fees: None,
            fills: Vec::new(),
            exchange_ts: None,
            contradictory: false,
            insufficient: false,
            authoritative: true,
        }
    } else {
        mapped_order_to_snapshot(&momento_core::MappedOrderView {
            client_order_id: client,
            venue_order_id: momento_core::VenueOrderId::from_raw(1),
            ticker: orders.ticker.clone().unwrap_or_else(|| "DEMO".into()),
            state: OrderState::Working,
            requested: Contracts::from_u32(1),
            filled: Contracts::ZERO,
            remaining: Contracts::from_u32(1),
        })
    };
    venue_snap.authoritative = true;
    let recv = ReceivedAt::from_utc(utc_now());
    let result = tracker
        .reconcile(client, venue_snap, recv)
        .map_err(|e| format!("{e:?}"))?;
    let pnl = tracker
        .get(pid)
        .map(PnlBreakdown::from_position)
        .unwrap_or_default();
    Ok(ReconProbe {
        outcome: result.outcome.as_str().to_string(),
        state: format!("{:?}", tracker.reconciliation_state()),
        realized_none: pnl.realized_pnl.is_none(),
    })
}

fn redaction_audit() -> bool {
    let raw = "KALSHI-ACCESS-SIGNATURE: supersecret\nAuthorization: Bearer abc\n";
    let out = redact_secrets(raw);
    !out.contains("supersecret") && !out.contains("abc") && out.contains("[REDACTED]")
}
