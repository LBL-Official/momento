//! Read-only Kalshi fill / public candle CLI for Jump.
//!
//! Prints JSON. Never POSTs orders. Never logs the secret file contents.

use std::env;
use std::path::PathBuf;
use std::process;

use chrono::{TimeZone, Utc};
use momento_kalshi::{
    BALANCE_PATH, CREATE_ORDER_PATH, FILLS_PATH, GetBalanceResponse, GetMarketCandlesticksResponse,
    INTRA_TRANSFER_PATH, KalshiEnvironment, KalshiHttpRequest, KalshiTransport, POSITIONS_PATH,
    ProductionReadOnlyTransport, PublicMarketClient, REST_DEMO_ORIGIN, REST_PRODUCTION_ORIGIN,
    SandboxHttpTransport, TransportOutcome, count_fp_to_contracts, count_fp_to_hundredths,
    create_order_is_blocked, credentials_from_secret_file, dollars_to_money_cents,
    dollars_to_price_cents, is_mutating_kalshi_request, production_read_only_allows,
    redact_secrets, refuse_if_production, require_host_matches_credentials,
};
use serde::{Deserialize, Serialize};

const MAX_FILL_PAGES: usize = 50;
const PAGE_LIMIT: u32 = 200;

#[derive(Deserialize)]
struct FillsPage {
    #[serde(default)]
    fills: Vec<FillIn>,
    #[serde(default)]
    cursor: Option<String>,
}

#[derive(Deserialize)]
struct FillIn {
    #[serde(default)]
    trade_id: Option<String>,
    #[serde(default)]
    fill_id: Option<String>,
    order_id: String,
    #[serde(default)]
    ticker: Option<String>,
    #[serde(default)]
    market_ticker: Option<String>,
    count_fp: String,
    #[serde(default)]
    yes_price_dollars: Option<String>,
    #[serde(default)]
    ts_ms: Option<i64>,
    #[serde(default)]
    ts: Option<i64>,
    #[serde(default)]
    created_time: Option<String>,
    #[serde(default)]
    exchange_index: Option<i64>,
}

#[derive(Serialize)]
struct FillOut {
    trade_id: Option<String>,
    fill_id: Option<String>,
    order_id: String,
    ticker: String,
    qty: Option<u32>,
    yes_price_cents: Option<u16>,
    exchange_ts: Option<String>,
    ts_ms: Option<i64>,
    created_time: Option<String>,
    exchange_index: Option<i64>,
}

#[derive(Serialize)]
struct CandleOut {
    end_period_ts: i64,
    open_cents: Option<u16>,
    high_cents: Option<u16>,
    low_cents: Option<u16>,
    close_cents: Option<u16>,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{}", redact_secrets(&err));
        process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!(
            "momento-jump-fills-read fills --environment demo|production --secret-file PATH\n\
             momento-jump-fills-read balance --environment demo|production --secret-file PATH\n\
             momento-jump-fills-read book --environment demo|production --secret-file PATH\n\
             momento-jump-fills-read candles --ticker TICKER --start-ts UNIX --end-ts UNIX [--period 1] [--environment production|demo]\n\
             momento-jump-fills-read demo-intra-transfer --environment demo --secret-file PATH --source-shard N --destination-shard N --amount-centicents N"
        );
        return Ok(());
    }
    let mode = args
        .first()
        .map(String::as_str)
        .filter(|a| !a.starts_with('-'))
        .unwrap_or("fills");
    match mode {
        "candles" => run_candles(&args),
        "fills" => run_fills(&args),
        "balance" => run_balance(&args),
        "book" => run_book(&args),
        "demo-intra-transfer" => run_demo_intra_transfer(&args),
        other => Err(format!(
            "unknown mode {other}; expected fills, balance, book, candles, or demo-intra-transfer"
        )),
    }
}

fn flag<'a>(args: &'a [String], name: &str) -> Option<&'a str> {
    let mut i = 0;
    while i + 1 < args.len() {
        if args[i] == name {
            return Some(args[i + 1].as_str());
        }
        i += 1;
    }
    None
}

fn parse_env(raw: &str) -> Result<KalshiEnvironment, String> {
    match raw.trim().to_ascii_lowercase().as_str() {
        "demo" | "sandbox" => Ok(KalshiEnvironment::Demo),
        "production" | "prod" => Ok(KalshiEnvironment::Production),
        _ => Err("environment must be demo or production".into()),
    }
}

fn refuse_if_create_allowed() -> Result<(), String> {
    if production_read_only_allows("POST", CREATE_ORDER_PATH)
        || !is_mutating_kalshi_request("POST", CREATE_ORDER_PATH)
    {
        return Err("Create V2 must stay refused".into());
    }
    Ok(())
}

fn load_book_creds(
    args: &[String],
) -> Result<
    (
        momento_kalshi::KalshiEnvironment,
        momento_kalshi::KalshiCredentials,
    ),
    String,
> {
    let env_raw = flag(args, "--environment")
        .map(str::to_string)
        .or_else(|| env::var("JUMP_KALSHI_ENV").ok())
        .ok_or("missing --environment or JUMP_KALSHI_ENV")?;
    let expected = parse_env(&env_raw)?;
    let secret = flag(args, "--secret-file")
        .map(PathBuf::from)
        .or_else(|| {
            env::var(momento_kalshi::ENV_KALSHI_SECRET_FILE)
                .ok()
                .map(PathBuf::from)
        })
        .ok_or("missing --secret-file or MOMENTO_KALSHI_SECRET_FILE")?;
    let creds = credentials_from_secret_file(expected, &secret).map_err(|e| e.to_string())?;
    if creds.environment() != expected {
        return Err("credential environment does not match requested book".into());
    }
    Ok((expected, creds))
}

fn run_fills(args: &[String]) -> Result<(), String> {
    if !create_order_is_blocked() || !production_read_only_allows("GET", FILLS_PATH) {
        return Err("read-only allowlist is not fills-only GET".into());
    }
    refuse_if_create_allowed()?;
    let (expected, creds) = load_book_creds(args)?;

    let (sent, body) = match expected {
        KalshiEnvironment::Production => {
            require_host_matches_credentials(expected, REST_PRODUCTION_ORIGIN)
                .map_err(|e| e.to_string())?;
            let mut transport =
                ProductionReadOnlyTransport::production(creds).map_err(|e| e.to_string())?;
            let pages = pull_fills(&mut transport, None)?;
            if transport.mutating_request_was_sent() {
                return Err("mutating Kalshi request was sent; aborting".into());
            }
            (transport.sent_paths().to_vec(), pages)
        }
        KalshiEnvironment::Demo => {
            require_host_matches_credentials(expected, REST_DEMO_ORIGIN)
                .map_err(|e| e.to_string())?;
            let mut transport = SandboxHttpTransport::demo(creds).map_err(|e| e.to_string())?;
            let pages = pull_fills(&mut transport, None)?;
            (Vec::new(), pages)
        }
    };

    let env_label = match expected {
        KalshiEnvironment::Demo => "DEMO",
        KalshiEnvironment::Production => "PRODUCTION",
    };
    let payload = serde_json::json!({
        "ok": true,
        "environment": env_label,
        "fills": body.0,
        "cursor": body.1,
        "mutating_sent": false,
        "read_only": true,
        "sent_n": sent.len(),
    });
    println!("{payload}");
    Ok(())
}

fn pull_fills<T: KalshiTransport>(
    transport: &mut T,
    exchange_index: Option<i64>,
) -> Result<(Vec<FillOut>, Option<String>), String> {
    let mut fills = Vec::new();
    let mut cursor: Option<String> = None;
    let mut last_cursor = None;
    for _ in 0..MAX_FILL_PAGES {
        let mut path = format!("{FILLS_PATH}?limit={PAGE_LIMIT}");
        if let Some(idx) = exchange_index {
            path.push_str(&format!("&exchange_index={idx}"));
        }
        if let Some(c) = &cursor {
            path.push_str("&cursor=");
            path.push_str(c);
        }
        if is_mutating_kalshi_request("GET", &path) {
            return Err("fills path classified as mutating; refusing".into());
        }
        match transport.execute(KalshiHttpRequest {
            method: "GET".into(),
            path,
            body: None,
        }) {
            TransportOutcome::Timeout => return Err("fills GET timed out".into()),
            TransportOutcome::Http { status: 401, .. } => {
                return Err("fills GET authentication failed".into());
            }
            TransportOutcome::Http { status: 0, body } => {
                return Err(format!(
                    "fills GET refused locally: {}",
                    redact_secrets(&body)
                ));
            }
            TransportOutcome::Http { status: 200, body } => {
                let parsed: FillsPage = serde_json::from_str(&body)
                    .map_err(|e| format!("fills JSON: {}", redact_secrets(&e.to_string())))?;
                for fill in parsed.fills {
                    fills.push(map_fill(&fill));
                }
                last_cursor = parsed.cursor.clone();
                match parsed.cursor.filter(|c| !c.is_empty()) {
                    Some(next) => cursor = Some(next),
                    None => break,
                }
            }
            TransportOutcome::Http { status, body } => {
                return Err(format!(
                    "fills GET HTTP {status}: {}",
                    redact_secrets(&body)
                ));
            }
        }
    }
    Ok((fills, last_cursor))
}

fn map_fill(fill: &FillIn) -> FillOut {
    let qty = count_fp_to_contracts(&fill.count_fp).ok().map(|c| c.get());
    let yes_price_cents = fill
        .yes_price_dollars
        .as_deref()
        .and_then(|raw| dollars_to_price_cents(raw).ok())
        .map(|p| p.cents());
    let ts_ms = fill
        .ts_ms
        .or_else(|| fill.ts.map(|s| s.saturating_mul(1000)));
    let exchange_ts = ts_ms
        .and_then(|ms| Utc.timestamp_millis_opt(ms).single())
        .map(|t| t.to_rfc3339_opts(chrono::SecondsFormat::Secs, true))
        .or_else(|| fill.created_time.clone());
    let ticker = fill
        .ticker
        .clone()
        .filter(|t| !t.is_empty())
        .or_else(|| fill.market_ticker.clone())
        .unwrap_or_default();
    FillOut {
        trade_id: fill.trade_id.clone(),
        fill_id: fill.fill_id.clone(),
        order_id: fill.order_id.clone(),
        ticker,
        qty,
        yes_price_cents,
        exchange_ts,
        ts_ms,
        created_time: fill.created_time.clone(),
        exchange_index: fill.exchange_index,
    }
}

fn run_balance(args: &[String]) -> Result<(), String> {
    if !create_order_is_blocked() || !production_read_only_allows("GET", BALANCE_PATH) {
        return Err("read-only allowlist is not balance GET".into());
    }
    refuse_if_create_allowed()?;
    let (expected, creds) = load_book_creds(args)?;
    let scoped = match flag(args, "--exchange-index") {
        Some(raw) => Some(
            raw.parse::<i64>()
                .map_err(|_| "exchange-index must be an integer".to_string())?,
        ),
        None => None,
    };

    let (sent, body) = match expected {
        KalshiEnvironment::Production => {
            require_host_matches_credentials(expected, REST_PRODUCTION_ORIGIN)
                .map_err(|e| e.to_string())?;
            let mut transport =
                ProductionReadOnlyTransport::production(creds).map_err(|e| e.to_string())?;
            let page = match scoped {
                Some(idx) => pull_balance_path(
                    &mut transport,
                    &format!("{BALANCE_PATH}?exchange_index={idx}"),
                )?,
                None => pull_balance(&mut transport)?,
            };
            if transport.mutating_request_was_sent() {
                return Err("mutating Kalshi request was sent; aborting".into());
            }
            (transport.sent_paths().to_vec(), page)
        }
        KalshiEnvironment::Demo => {
            require_host_matches_credentials(expected, REST_DEMO_ORIGIN)
                .map_err(|e| e.to_string())?;
            let mut transport = SandboxHttpTransport::demo(creds).map_err(|e| e.to_string())?;
            let page = match scoped {
                Some(idx) => pull_balance_path(
                    &mut transport,
                    &format!("{BALANCE_PATH}?exchange_index={idx}"),
                )?,
                None => pull_balance(&mut transport)?,
            };
            (Vec::new(), page)
        }
    };

    let env_label = match expected {
        KalshiEnvironment::Demo => "DEMO",
        KalshiEnvironment::Production => "PRODUCTION",
    };
    let payload = serde_json::json!({
        "ok": true,
        "environment": env_label,
        "balance_cents": body.0,
        "balance_dollars": body.1,
        "portfolio_value_cents": body.2,
        "balance_breakdown": body.3,
        "exchange_index": scoped,
        "mutating_sent": false,
        "read_only": true,
        "sent_n": sent.len(),
    });
    println!("{payload}");
    Ok(())
}

fn cents_to_dollars_string(cents: i64) -> String {
    let sign = if cents < 0 { "-" } else { "" };
    let abs = cents.unsigned_abs();
    format!("{sign}{}.{:02}", abs / 100, abs % 100)
}

fn breakdown_is_present(raw: &Option<serde_json::Value>) -> bool {
    matches!(raw, Some(serde_json::Value::Array(rows)) if !rows.is_empty())
}

fn pull_balance_path<T: KalshiTransport>(
    transport: &mut T,
    path: &str,
) -> Result<(i64, Option<String>, Option<i64>, Option<serde_json::Value>), String> {
    if is_mutating_kalshi_request("GET", path) {
        return Err("balance path classified as mutating; refusing".into());
    }
    if !production_read_only_allows("GET", path) {
        return Err("balance path is not read-only allowlisted".into());
    }
    match transport.execute(KalshiHttpRequest {
        method: "GET".into(),
        path: path.into(),
        body: None,
    }) {
        TransportOutcome::Timeout => Err("balance GET timed out".into()),
        TransportOutcome::Http { status: 401, .. } => {
            Err("balance GET authentication failed".into())
        }
        TransportOutcome::Http { status: 0, body } => Err(format!(
            "balance GET refused locally: {}",
            redact_secrets(&body)
        )),
        TransportOutcome::Http { status: 200, body } => {
            let parsed: GetBalanceResponse = serde_json::from_str(&body)
                .map_err(|e| format!("balance JSON: {}", redact_secrets(&e.to_string())))?;
            let cents = resolve_balance_cents(&parsed)?;
            let raw: serde_json::Value = serde_json::from_str(&body)
                .map_err(|e| format!("balance JSON: {}", redact_secrets(&e.to_string())))?;
            Ok((
                cents,
                parsed.balance_dollars,
                parsed.portfolio_value,
                raw.get("balance_breakdown").cloned(),
            ))
        }
        TransportOutcome::Http { status, body } => Err(format!(
            "balance GET HTTP {status}: {}",
            redact_secrets(&body)
        )),
    }
}

fn pull_balance<T: KalshiTransport>(
    transport: &mut T,
) -> Result<(i64, Option<String>, Option<i64>, Option<serde_json::Value>), String> {
    let all = pull_balance_path(transport, BALANCE_PATH)?;
    if breakdown_is_present(&all.3) {
        return Ok(all);
    }
    // Official Get Balance: omit exchange_index = all indexes + optional
    // breakdown. When Demo omits the array, scoped GETs are the authority.
    // A missing index is unread, not $0.
    let mut rows = Vec::new();
    for idx in [0_i64, 3] {
        let scoped = format!("{BALANCE_PATH}?exchange_index={idx}");
        match pull_balance_path(transport, &scoped) {
            Ok((cents, dollars, _, _)) => rows.push(serde_json::json!({
                "exchange_index": idx,
                "balance": dollars.clone().unwrap_or_else(|| cents_to_dollars_string(cents)),
                "balance_cents": cents,
            })),
            Err(_) => {}
        }
    }
    let breakdown = if rows.is_empty() {
        all.3
    } else {
        Some(serde_json::Value::Array(rows))
    };
    Ok((all.0, all.1, all.2, breakdown))
}

fn required_i64(args: &[String], name: &str) -> Result<i64, String> {
    let raw = flag(args, name).ok_or_else(|| format!("missing {name}"))?;
    raw.parse::<i64>()
        .map_err(|_| format!("{name} must be an integer"))
}

fn run_demo_intra_transfer(args: &[String]) -> Result<(), String> {
    refuse_if_create_allowed()?;
    if !create_order_is_blocked() {
        return Err("Create V2 must stay refused".into());
    }
    if production_read_only_allows("POST", INTRA_TRANSFER_PATH) {
        return Err("production read-only must not allow intra-transfer".into());
    }
    let secret_path = flag(args, "--secret-file").unwrap_or("");
    if secret_path.to_ascii_lowercase().contains("production") {
        return Err("demo-intra-transfer refuses a production secret path".into());
    }
    let (expected, creds) = load_book_creds(args)?;
    if expected != KalshiEnvironment::Demo || creds.environment() != KalshiEnvironment::Demo {
        return Err("demo-intra-transfer refuses production".into());
    }
    require_host_matches_credentials(expected, REST_DEMO_ORIGIN).map_err(|e| e.to_string())?;
    refuse_if_production(REST_DEMO_ORIGIN).map_err(|e| e.to_string())?;
    refuse_if_production(&format!("{REST_DEMO_ORIGIN}{INTRA_TRANSFER_PATH}"))
        .map_err(|e| e.to_string())?;
    let source = required_i64(args, "--source-shard")?;
    let destination = required_i64(args, "--destination-shard")?;
    let amount = required_i64(args, "--amount-centicents")?;
    if source < 0 || destination < 0 || source > 100 || destination > 100 {
        return Err("shard indexes must be 0..=100".into());
    }
    if amount <= 0 {
        return Err("amount-centicents must be a positive integer".into());
    }
    if is_mutating_kalshi_request("POST", CREATE_ORDER_PATH) && !create_order_is_blocked() {
        return Err("Create V2 must stay refused".into());
    }
    let body = serde_json::json!({
        "source": "event_contract",
        "destination": "event_contract",
        "amount": amount,
        "source_exchange_shard": source,
        "destination_exchange_shard": destination,
    });
    let mut transport = SandboxHttpTransport::demo(creds).map_err(|e| e.to_string())?;
    match transport.execute(KalshiHttpRequest {
        method: "POST".into(),
        path: INTRA_TRANSFER_PATH.into(),
        body: Some(body.to_string()),
    }) {
        TransportOutcome::Timeout => Err("demo intra-transfer timed out".into()),
        TransportOutcome::Http { status: 401, .. } => {
            Err("demo intra-transfer authentication failed".into())
        }
        TransportOutcome::Http { status: 200, body } => {
            let raw: serde_json::Value = serde_json::from_str(&body)
                .map_err(|e| format!("transfer JSON: {}", redact_secrets(&e.to_string())))?;
            let payload = serde_json::json!({
                "ok": true,
                "environment": "DEMO",
                "origin": REST_DEMO_ORIGIN,
                "transfer_id": raw.get("transfer_id"),
                "source_exchange_shard": source,
                "destination_exchange_shard": destination,
                "amount_centicents": amount,
                "http_status": 200,
                "submits": false,
                "not_create_v2": true,
                "read_only": false,
            });
            println!("{payload}");
            Ok(())
        }
        TransportOutcome::Http { status, body } => {
            let payload = serde_json::json!({
                "ok": false,
                "environment": "DEMO",
                "http_status": status,
                "detail": redact_secrets(&body),
                "submits": false,
                "not_create_v2": true,
            });
            println!("{payload}");
            Err(format!(
                "demo intra-transfer HTTP {status}: {}",
                redact_secrets(&body)
            ))
        }
    }
}

fn resolve_balance_cents(parsed: &GetBalanceResponse) -> Result<i64, String> {
    let from_int = parsed.balance;
    if let Some(raw) = parsed.balance_dollars.as_deref() {
        match dollars_to_money_cents(raw) {
            Ok(money) if money.cents() != from_int => {
                return Err("balance and balance_dollars disagree".into());
            }
            Ok(_) | Err(_) => {}
        }
    }
    Ok(from_int)
}

#[derive(Deserialize)]
struct PositionsPage {
    #[serde(default)]
    market_positions: Vec<MarketPositionIn>,
    #[serde(default)]
    cursor: Option<String>,
}

#[derive(Deserialize)]
struct MarketPositionIn {
    #[serde(default)]
    ticker: String,
    #[serde(default)]
    exchange_index: Option<i64>,
    #[serde(default)]
    position_fp: Option<String>,
    #[serde(default)]
    market_exposure_dollars: Option<String>,
    #[serde(default)]
    realized_pnl_dollars: Option<String>,
    #[serde(default)]
    fees_paid_dollars: Option<String>,
    #[serde(default)]
    last_updated_ts: Option<String>,
}

#[derive(Serialize)]
struct PositionOut {
    ticker: String,
    exchange_index: Option<i64>,
    position_hundredths: Option<i64>,
    exposure_cents: Option<i64>,
    realized_pnl_cents: Option<i64>,
    fees_cents: Option<i64>,
    last_updated_ts: Option<String>,
    open: bool,
}

fn run_book(args: &[String]) -> Result<(), String> {
    if !create_order_is_blocked()
        || !production_read_only_allows("GET", BALANCE_PATH)
        || !production_read_only_allows("GET", FILLS_PATH)
        || !production_read_only_allows("GET", POSITIONS_PATH)
    {
        return Err("read-only allowlist is not book GET".into());
    }
    refuse_if_create_allowed()?;
    let (expected, creds) = load_book_creds(args)?;

    let (sent, balance, fills, positions) = match expected {
        KalshiEnvironment::Production => {
            require_host_matches_credentials(expected, REST_PRODUCTION_ORIGIN)
                .map_err(|e| e.to_string())?;
            let mut transport =
                ProductionReadOnlyTransport::production(creds).map_err(|e| e.to_string())?;
            let balance = pull_balance(&mut transport)?;
            let fills = pull_fills(&mut transport, Some(3))?;
            let positions = pull_positions(&mut transport, Some(3))?;
            if transport.mutating_request_was_sent() {
                return Err("mutating Kalshi request was sent; aborting".into());
            }
            (transport.sent_paths().to_vec(), balance, fills, positions)
        }
        KalshiEnvironment::Demo => {
            require_host_matches_credentials(expected, REST_DEMO_ORIGIN)
                .map_err(|e| e.to_string())?;
            let mut transport = SandboxHttpTransport::demo(creds).map_err(|e| e.to_string())?;
            let balance = pull_balance(&mut transport)?;
            let fills = pull_fills(&mut transport, None)?;
            let positions = pull_positions(&mut transport, None)?;
            (Vec::new(), balance, fills, positions)
        }
    };

    let env_label = match expected {
        KalshiEnvironment::Demo => "DEMO",
        KalshiEnvironment::Production => "PRODUCTION",
    };
    let payload = serde_json::json!({
        "ok": true,
        "environment": env_label,
        "balance_cents": balance.0,
        "balance_dollars": balance.1,
        "portfolio_value_cents": balance.2,
        "balance_breakdown": balance.3,
        "fills": fills.0,
        "cursor": fills.1,
        "positions": positions,
        "mutating_sent": false,
        "read_only": true,
        "sent_n": sent.len(),
    });
    println!("{payload}");
    Ok(())
}

fn pull_positions<T: KalshiTransport>(
    transport: &mut T,
    exchange_index: Option<i64>,
) -> Result<Vec<PositionOut>, String> {
    let mut out = Vec::new();
    let mut cursor: Option<String> = None;
    for _ in 0..MAX_FILL_PAGES {
        let mut path = format!("{POSITIONS_PATH}?limit={PAGE_LIMIT}&count_filter=position");
        if let Some(idx) = exchange_index {
            path.push_str(&format!("&exchange_index={idx}"));
        }
        if let Some(c) = &cursor {
            path.push_str("&cursor=");
            path.push_str(c);
        }
        if is_mutating_kalshi_request("GET", &path) {
            return Err("positions path classified as mutating; refusing".into());
        }
        match transport.execute(KalshiHttpRequest {
            method: "GET".into(),
            path,
            body: None,
        }) {
            TransportOutcome::Timeout => return Err("positions GET timed out".into()),
            TransportOutcome::Http { status: 401, .. } => {
                return Err("positions GET authentication failed".into());
            }
            TransportOutcome::Http { status: 0, body } => {
                return Err(format!(
                    "positions GET refused locally: {}",
                    redact_secrets(&body)
                ));
            }
            TransportOutcome::Http { status: 200, body } => {
                let parsed: PositionsPage = serde_json::from_str(&body)
                    .map_err(|e| format!("positions JSON: {}", redact_secrets(&e.to_string())))?;
                for row in parsed.market_positions {
                    out.push(map_position(&row));
                }
                match parsed.cursor.filter(|c| !c.is_empty()) {
                    Some(next) => cursor = Some(next),
                    None => break,
                }
            }
            TransportOutcome::Http { status, body } => {
                return Err(format!(
                    "positions GET HTTP {status}: {}",
                    redact_secrets(&body)
                ));
            }
        }
    }
    Ok(out)
}

fn map_position(row: &MarketPositionIn) -> PositionOut {
    let hundredths = row
        .position_fp
        .as_deref()
        .and_then(|raw| count_fp_to_hundredths(raw).ok());
    PositionOut {
        ticker: row.ticker.clone(),
        exchange_index: row.exchange_index,
        position_hundredths: hundredths,
        exposure_cents: dollars_opt_money(row.market_exposure_dollars.as_deref()),
        realized_pnl_cents: dollars_opt_money(row.realized_pnl_dollars.as_deref()),
        fees_cents: dollars_opt_money(row.fees_paid_dollars.as_deref()),
        last_updated_ts: row.last_updated_ts.clone(),
        open: hundredths.unwrap_or(0) != 0,
    }
}

fn dollars_opt_money(raw: Option<&str>) -> Option<i64> {
    raw.and_then(|value| dollars_to_money_cents(value).ok().map(|m| m.cents()))
}

fn run_candles(args: &[String]) -> Result<(), String> {
    let ticker = flag(args, "--ticker")
        .ok_or("missing --ticker")?
        .to_string();
    let start_ts: i64 = flag(args, "--start-ts")
        .ok_or("missing --start-ts")?
        .parse()
        .map_err(|_| "start-ts must be unix seconds")?;
    let end_ts: i64 = flag(args, "--end-ts")
        .ok_or("missing --end-ts")?
        .parse()
        .map_err(|_| "end-ts must be unix seconds")?;
    let period: u32 = flag(args, "--period")
        .unwrap_or("1")
        .parse()
        .map_err(|_| "period must be an integer")?;
    let env_raw = flag(args, "--environment").unwrap_or("production");
    let expected = parse_env(env_raw)?;
    let origin = match expected {
        KalshiEnvironment::Production => REST_PRODUCTION_ORIGIN,
        KalshiEnvironment::Demo => REST_DEMO_ORIGIN,
    };
    require_host_matches_credentials(expected, origin).map_err(|e| e.to_string())?;
    let client = PublicMarketClient::with_base(origin);
    let parsed = fetch_candles(&client, &ticker, start_ts, end_ts, period)?;
    let candles: Vec<CandleOut> = parsed
        .candlesticks
        .iter()
        .map(|c| CandleOut {
            end_period_ts: c.end_period_ts,
            open_cents: dollars_opt(&c.yes_bid.open_dollars),
            high_cents: dollars_opt(&c.yes_bid.high_dollars),
            low_cents: dollars_opt(&c.yes_bid.low_dollars),
            close_cents: dollars_opt(&c.yes_bid.close_dollars),
        })
        .collect();
    let payload = serde_json::json!({
        "ok": true,
        "ticker": parsed.ticker,
        "candles": candles,
        "period_interval": period,
        "honesty": {
            "candle_path_not_fill": true,
            "l2": "DATA_REQUIRED",
            "tick": "DATA_REQUIRED",
        },
    });
    println!("{payload}");
    Ok(())
}

fn fetch_candles(
    client: &PublicMarketClient,
    ticker: &str,
    start_ts: i64,
    end_ts: i64,
    period: u32,
) -> Result<GetMarketCandlesticksResponse, String> {
    match client.get_historical_candlesticks(ticker, start_ts, end_ts, period) {
        Ok(body) if !body.candlesticks.is_empty() => Ok(body),
        Ok(body) => {
            if let Some(series) = series_ticker(ticker) {
                if let Ok(live) = client.get_candlesticks(&series, ticker, start_ts, end_ts, period)
                {
                    if !live.candlesticks.is_empty() {
                        return Ok(live);
                    }
                }
            }
            Ok(body)
        }
        Err(_) => {
            let series = series_ticker(ticker).ok_or("candlesticks DATA_REQUIRED")?;
            client
                .get_candlesticks(&series, ticker, start_ts, end_ts, period)
                .map_err(|_| "candlesticks DATA_REQUIRED".into())
        }
    }
}

fn series_ticker(ticker: &str) -> Option<String> {
    ticker.split_once('-').map(|(s, _)| s.to_string())
}

fn dollars_opt(raw: &str) -> Option<u16> {
    dollars_to_price_cents(raw).ok().map(|p| p.cents())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cents_to_dollars_string_is_integer() {
        assert_eq!(cents_to_dollars_string(2000), "20.00");
        assert_eq!(cents_to_dollars_string(0), "0.00");
        assert_eq!(cents_to_dollars_string(-150), "-1.50");
    }

    #[test]
    fn empty_breakdown_is_absent() {
        assert!(!breakdown_is_present(&None));
        assert!(!breakdown_is_present(&Some(serde_json::json!([]))));
        assert!(breakdown_is_present(&Some(
            serde_json::json!([{"exchange_index": 0}])
        )));
    }
}
