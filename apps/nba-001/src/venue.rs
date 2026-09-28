//! NBA-only Kalshi order adapter (Create/Amend/Cancel V2 + reconciliation
//! reads). Isolated from MLB's `KalshiVenue`. Production mutations are
//! refused here while `PRODUCTION_ORDERS_COMPILED` is false, before any
//! request is built, so a refusal is provably `NotSent`.
//!
//! HTTP mapping (docs create-order-v2, cancel-order-v2, amend-order-v2):
//! 201/200 → Acked; 400/401/403/404 → Rejected (no retry); 409 → Ambiguous
//! (duplicate client id or conflict: reconcile); 429, 5xx, timeout, and
//! transport status 0 → Ambiguous. An ambiguous create is never retried
//! blind; the executor reconciles by client order id first.

use momento_kalshi::{
    CREATE_ORDER_PATH, FILLS_PATH, KalshiHttpRequest, KalshiTransport, ORDERS_PATH, POSITIONS_PATH,
    TransportOutcome, count_fp_to_contracts, redact_secrets,
};
use momento_strategy_nba::{BookSide, Fill, OrderSpec, TimeInForce, VenueStatus};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

/// Production order submission is compiled out of this build.
pub const PRODUCTION_ORDERS_COMPILED: bool = false;
const _: () = assert!(!PRODUCTION_ORDERS_COMPILED);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum VenueEnv {
    Fixture,
    Demo,
    Production,
}

/// Proof that every production gate passed. Unconstructable in this build.
pub struct ProductionPermit {
    _private: (),
}

/// Every reason production submission is not permitted. Always non-empty
/// while `PRODUCTION_ORDERS_COMPILED` is false.
/// Production fills on whole-contract orders can be fractional (host evidence
/// 2026-09-27: 19 MLB 7-lots). Counts here are whole contracts, so a
/// fractional count fails closed as a read error and the lane holds.
pub const FRACTIONAL_FILLS_SUPPORTED: bool = false;

pub fn production_permit(
    contract_unresolved: &[String],
    contract_enabled: bool,
    fees_verified: bool,
    live_gates_set: bool,
    collateral_accounted: bool,
) -> Result<ProductionPermit, Vec<String>> {
    let mut why = Vec::new();
    if !PRODUCTION_ORDERS_COMPILED {
        why.push("PRODUCTION_ORDERS_NOT_COMPILED".to_string());
    }
    if !FRACTIONAL_FILLS_SUPPORTED {
        why.push("FRACTIONAL_FILLS_UNSUPPORTED".to_string());
    }
    if !contract_enabled {
        why.push("CONTRACT_PRODUCTION_SUBMISSION_DISABLED".into());
    }
    for f in contract_unresolved {
        why.push(format!("CONTRACT_UNRESOLVED:{f}"));
    }
    if !fees_verified {
        why.push("FEE_UNVERIFIED".into());
    }
    if !live_gates_set {
        why.push("LIVE_GATES_UNSET".into());
    }
    if !collateral_accounted {
        why.push("SHARED_COLLATERAL_UNACCOUNTED".into());
    }
    if why.is_empty() {
        Ok(ProductionPermit { _private: () })
    } else {
        Err(why)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "outcome", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum CreateOutcome {
    Acked {
        venue_order_id: String,
        fill_count: u32,
        remaining_count: u32,
    },
    Rejected {
        http_status: u16,
        code: String,
    },
    Ambiguous {
        reason: String,
    },
    NotSent {
        reason: String,
    },
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "outcome", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum CancelOutcome {
    Cancelled { reduced_by: u32 },
    NotFound,
    Rejected { http_status: u16, code: String },
    Ambiguous { reason: String },
    NotSent { reason: String },
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "outcome", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum AmendOutcome {
    /// `amend_fill_count` counts fills caused by the amend only; both counts
    /// are omitted by the venue when the resting size did not change.
    Amended {
        venue_order_id: String,
        amend_fill_count: Option<u32>,
        remaining_count: Option<u32>,
    },
    Rejected {
        http_status: u16,
        code: String,
    },
    Ambiguous {
        reason: String,
    },
    NotSent {
        reason: String,
    },
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct VenueOrder {
    pub venue_order_id: String,
    pub client_order_id: Option<String>,
    pub ticker: String,
    pub status: VenueStatus,
    pub fill_count: u32,
    pub remaining_count: u32,
    pub initial_count: Option<u32>,
    pub yes_price_dollars: Option<String>,
    pub taker_fees_dollars: Option<String>,
    pub maker_fees_dollars: Option<String>,
    pub exchange_index: Option<i64>,
    pub subaccount_number: Option<i64>,
    pub created_time: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ReadError {
    Http { status: u16, body: String },
    Timeout,
    Malformed(String),
}

pub struct NbaVenue<T: KalshiTransport> {
    transport: T,
    env: VenueEnv,
    pub subaccount: Option<u8>,
    pub requests_sent: usize,
    pub mutations_sent: usize,
}

fn status_of(o: &Value) -> Option<VenueStatus> {
    match o.get("status")?.as_str()? {
        "resting" => Some(VenueStatus::Resting),
        "canceled" | "cancelled" => Some(VenueStatus::Canceled),
        "executed" => Some(VenueStatus::Executed),
        _ => None,
    }
}

/// First present key wins. A present count that is not a whole number of
/// contracts (fractional, malformed) is `None`, never a fall-through to an
/// older field.
fn count_field(o: &Value, keys: &[&str]) -> Option<u32> {
    let v = keys.iter().find_map(|k| o.get(*k))?;
    match v {
        Value::String(s) => count_fp_to_contracts(s).ok().map(|c| c.get()),
        Value::Number(n) => n.as_u64().and_then(|n| u32::try_from(n).ok()),
        _ => None,
    }
}

fn str_field(o: &Value, key: &str) -> Option<String> {
    o.get(key).and_then(|v| v.as_str()).map(str::to_string)
}

/// Exact fixed-point dollars → micro-dollars (10⁻⁶). No floats.
pub fn dollars_to_micros(raw: &str) -> Option<i64> {
    let (neg, s) = raw.strip_prefix('-').map_or((false, raw), |r| (true, r));
    let (w, f) = s.split_once('.').unwrap_or((s, ""));
    if w.is_empty() || !w.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    if f.len() > 6 || !f.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let mut frac = f.to_string();
    while frac.len() < 6 {
        frac.push('0');
    }
    let v = w.parse::<i64>().ok()?.checked_mul(1_000_000)? + frac.parse::<i64>().ok()?;
    Some(if neg { -v } else { v })
}

pub fn parse_order(o: &Value) -> Result<VenueOrder, ReadError> {
    let m = |what: &str| ReadError::Malformed(format!("order {what}"));
    Ok(VenueOrder {
        venue_order_id: str_field(o, "order_id").ok_or_else(|| m("order_id"))?,
        client_order_id: str_field(o, "client_order_id").filter(|s| !s.is_empty()),
        ticker: str_field(o, "ticker").ok_or_else(|| m("ticker"))?,
        status: status_of(o).ok_or_else(|| m("status"))?,
        fill_count: count_field(o, &["fill_count_fp", "fill_count"])
            .ok_or_else(|| m("fill_count"))?,
        remaining_count: count_field(o, &["remaining_count_fp", "remaining_count"])
            .ok_or_else(|| m("remaining_count"))?,
        initial_count: count_field(o, &["initial_count_fp", "initial_count"]),
        yes_price_dollars: str_field(o, "yes_price_dollars"),
        taker_fees_dollars: str_field(o, "taker_fees_dollars"),
        maker_fees_dollars: str_field(o, "maker_fees_dollars"),
        exchange_index: o.get("exchange_index").and_then(Value::as_i64),
        subaccount_number: o.get("subaccount_number").and_then(Value::as_i64),
        created_time: str_field(o, "created_time"),
    })
}

pub fn parse_fill(f: &Value) -> Result<(String, Fill), ReadError> {
    let m = |what: &str| ReadError::Malformed(format!("fill {what}"));
    let fill_id = str_field(f, "fill_id")
        .or_else(|| str_field(f, "trade_id"))
        .ok_or_else(|| m("fill_id"))?;
    let order_id = str_field(f, "order_id").ok_or_else(|| m("order_id"))?;
    let count = count_field(f, &["count_fp", "count"]).ok_or_else(|| m("count"))?;
    let price_micros = str_field(f, "yes_price_dollars")
        .and_then(|s| dollars_to_micros(&s))
        .ok_or_else(|| m("yes_price_dollars"))?;
    if price_micros % 100 != 0 || !(0..=1_000_000).contains(&price_micros) {
        return Err(m("sub-centicent price"));
    }
    let fee_centicents = match f.get("fee_cost") {
        Some(Value::String(s)) => {
            let micros = dollars_to_micros(s).ok_or_else(|| m("fee_cost"))?;
            // Ceil: a fee is never understated.
            Some((micros + 99).div_euclid(100))
        }
        _ => None,
    };
    let ts = f.get("ts").and_then(Value::as_i64).unwrap_or_default();
    Ok((
        order_id,
        Fill {
            fill_id,
            count,
            yes_price_centicents: u32::try_from(price_micros / 100).map_err(|_| m("price"))?,
            is_taker: f.get("is_taker").and_then(Value::as_bool),
            fee_centicents,
            ts,
        },
    ))
}

fn error_code(body: &str) -> String {
    serde_json::from_str::<Value>(body)
        .ok()
        .and_then(|v| {
            v.get("error")
                .and_then(|e| e.get("code").or_else(|| e.get("message")))
                .or_else(|| v.get("code"))
                .and_then(|c| c.as_str().map(str::to_string))
        })
        .unwrap_or_else(|| redact_secrets(&body.chars().take(160).collect::<String>()))
}

fn tif_str(t: TimeInForce) -> &'static str {
    match t {
        TimeInForce::GoodTillCanceled => "good_till_canceled",
        TimeInForce::ImmediateOrCancel => "immediate_or_cancel",
        TimeInForce::FillOrKill => "fill_or_kill",
    }
}

fn side_str(s: BookSide) -> &'static str {
    match s {
        BookSide::Bid => "bid",
        BookSide::Ask => "ask",
    }
}

pub fn price_str(cents: u16) -> String {
    format!("{}.{:02}00", cents / 100, cents % 100)
}

pub fn count_str(n: u32) -> String {
    format!("{n}.00")
}

/// Create Order V2 body. `exchange_index` is omitted: auto-route by ticker.
pub fn create_body(spec: &OrderSpec) -> Value {
    let mut b = json!({
        "ticker": spec.ticker,
        "client_order_id": spec.client_order_id,
        "side": side_str(spec.side),
        "count": count_str(spec.count),
        "price": price_str(spec.price_cents),
        "time_in_force": tif_str(spec.tif),
        "self_trade_prevention_type": "taker_at_cross",
        "post_only": spec.post_only,
        "reduce_only": spec.reduce_only,
        "cancel_order_on_pause": spec.cancel_order_on_pause,
    });
    if let Some(e) = spec.expiration_ts {
        b["expiration_time"] = json!(e);
    }
    if let Some(s) = spec.subaccount {
        b["subaccount"] = json!(s);
    }
    b
}

impl<T: KalshiTransport> NbaVenue<T> {
    #[cfg_attr(not(test), allow(dead_code))]
    pub fn fixture(transport: T) -> Self {
        Self::with_env(transport, VenueEnv::Fixture)
    }

    pub fn demo(transport: T) -> Self {
        Self::with_env(transport, VenueEnv::Demo)
    }

    /// Requires a permit; `production_permit` cannot issue one in this build.
    #[allow(dead_code)]
    pub fn production(transport: T, _permit: ProductionPermit) -> Self {
        Self::with_env(transport, VenueEnv::Production)
    }

    fn with_env(transport: T, env: VenueEnv) -> Self {
        Self {
            transport,
            env,
            subaccount: None,
            requests_sent: 0,
            mutations_sent: 0,
        }
    }

    pub fn env(&self) -> VenueEnv {
        self.env
    }

    pub fn transport(&self) -> &T {
        &self.transport
    }

    #[cfg_attr(not(test), allow(dead_code))]
    pub fn transport_mut(&mut self) -> &mut T {
        &mut self.transport
    }

    pub fn can_mutate(&self) -> bool {
        self.mutation_refused().is_none()
    }

    fn mutation_refused(&self) -> Option<String> {
        (self.env == VenueEnv::Production && !PRODUCTION_ORDERS_COMPILED)
            .then(|| "PRODUCTION_ORDERS_NOT_COMPILED".to_string())
    }

    fn send(&mut self, method: &str, path: String, body: Option<Value>) -> TransportOutcome {
        self.requests_sent += 1;
        if method != "GET" {
            self.mutations_sent += 1;
        }
        self.transport.execute(KalshiHttpRequest {
            method: method.into(),
            path,
            body: body.map(|b| b.to_string()),
        })
    }

    fn sub_q(&self, sep: char) -> String {
        self.subaccount
            .map(|s| format!("{sep}subaccount={s}"))
            .unwrap_or_default()
    }

    pub fn create(&mut self, spec: &OrderSpec) -> CreateOutcome {
        if let Some(reason) = self.mutation_refused() {
            return CreateOutcome::NotSent { reason };
        }
        if let Err(e) = spec.validate() {
            return CreateOutcome::NotSent {
                reason: format!("{e:?}"),
            };
        }
        let mut body = create_body(spec);
        if spec.subaccount.is_none()
            && let Some(s) = self.subaccount
        {
            body["subaccount"] = json!(s);
        }
        match self.send("POST", CREATE_ORDER_PATH.into(), Some(body)) {
            TransportOutcome::Timeout => CreateOutcome::Ambiguous {
                reason: "timeout".into(),
            },
            TransportOutcome::Http { status, body } => match status {
                200 | 201 => {
                    let v: Value = match serde_json::from_str(&body) {
                        Ok(v) => v,
                        Err(_) => {
                            return CreateOutcome::Ambiguous {
                                reason: "2xx with unparseable body".into(),
                            };
                        }
                    };
                    let o = v.get("order").unwrap_or(&v);
                    match (
                        str_field(o, "order_id"),
                        count_field(o, &["fill_count", "fill_count_fp"]),
                        count_field(o, &["remaining_count", "remaining_count_fp"]),
                    ) {
                        (Some(id), Some(f), Some(r)) => CreateOutcome::Acked {
                            venue_order_id: id,
                            fill_count: f,
                            remaining_count: r,
                        },
                        _ => CreateOutcome::Ambiguous {
                            reason: "2xx missing order_id or counts".into(),
                        },
                    }
                }
                400 | 401 | 403 | 404 => CreateOutcome::Rejected {
                    http_status: status,
                    code: error_code(&body),
                },
                0 => CreateOutcome::Ambiguous {
                    reason: format!("transport: {}", error_code(&body)),
                },
                s => CreateOutcome::Ambiguous {
                    reason: format!("http {s}: {}", error_code(&body)),
                },
            },
        }
    }

    pub fn cancel(&mut self, venue_order_id: &str, ticker: &str) -> CancelOutcome {
        if let Some(reason) = self.mutation_refused() {
            return CancelOutcome::NotSent { reason };
        }
        let path = format!(
            "{CREATE_ORDER_PATH}/{venue_order_id}?market_ticker={ticker}{}",
            self.sub_q('&')
        );
        match self.send("DELETE", path, None) {
            TransportOutcome::Timeout => CancelOutcome::Ambiguous {
                reason: "timeout".into(),
            },
            TransportOutcome::Http { status, body } => match status {
                200 | 201 => {
                    let v: Value = serde_json::from_str(&body).unwrap_or(Value::Null);
                    match count_field(&v, &["reduced_by", "reduced_by_fp"]) {
                        Some(n) => CancelOutcome::Cancelled { reduced_by: n },
                        None => CancelOutcome::Ambiguous {
                            reason: "cancel 2xx without reduced_by".into(),
                        },
                    }
                }
                404 => CancelOutcome::NotFound,
                400 | 401 | 403 => CancelOutcome::Rejected {
                    http_status: status,
                    code: error_code(&body),
                },
                s => CancelOutcome::Ambiguous {
                    reason: format!("http {s}: {}", error_code(&body)),
                },
            },
        }
    }

    /// Amend V2. `total_count` = already filled + desired resting.
    pub fn amend(
        &mut self,
        venue_order_id: &str,
        spec: &OrderSpec,
        price_cents: u16,
        total_count: u32,
        updated_client_order_id: Option<&str>,
    ) -> AmendOutcome {
        if let Some(reason) = self.mutation_refused() {
            return AmendOutcome::NotSent { reason };
        }
        if !(1..=99).contains(&price_cents) || total_count == 0 {
            return AmendOutcome::NotSent {
                reason: "invalid amend".into(),
            };
        }
        let mut body = json!({
            "ticker": spec.ticker,
            "side": side_str(spec.side),
            "price": price_str(price_cents),
            "count": count_str(total_count),
            "client_order_id": spec.client_order_id,
        });
        if let Some(u) = updated_client_order_id {
            body["updated_client_order_id"] = json!(u);
        }
        let path = format!(
            "{CREATE_ORDER_PATH}/{venue_order_id}/amend{}",
            self.sub_q('?')
        );
        match self.send("POST", path, Some(body)) {
            TransportOutcome::Timeout => AmendOutcome::Ambiguous {
                reason: "timeout".into(),
            },
            TransportOutcome::Http { status, body } => match status {
                200 | 201 => {
                    let v: Value = serde_json::from_str(&body).unwrap_or(Value::Null);
                    match str_field(&v, "order_id") {
                        Some(id) => AmendOutcome::Amended {
                            venue_order_id: id,
                            amend_fill_count: count_field(&v, &["fill_count", "fill_count_fp"]),
                            remaining_count: count_field(
                                &v,
                                &["remaining_count", "remaining_count_fp"],
                            ),
                        },
                        None => AmendOutcome::Ambiguous {
                            reason: "amend 2xx without order_id".into(),
                        },
                    }
                }
                400 | 401 | 403 | 404 => AmendOutcome::Rejected {
                    http_status: status,
                    code: error_code(&body),
                },
                s => AmendOutcome::Ambiguous {
                    reason: format!("http {s}: {}", error_code(&body)),
                },
            },
        }
    }

    pub fn get_json(&mut self, path: String) -> Result<Value, ReadError> {
        match self.send("GET", path, None) {
            TransportOutcome::Timeout => Err(ReadError::Timeout),
            TransportOutcome::Http { status: 200, body } => {
                serde_json::from_str(&body).map_err(|e| ReadError::Malformed(e.to_string()))
            }
            TransportOutcome::Http { status, body } => Err(ReadError::Http {
                status,
                body: redact_secrets(&body.chars().take(200).collect::<String>()),
            }),
        }
    }

    /// `Ok(None)` only on an explicit 404.
    pub fn get_order(&mut self, venue_order_id: &str) -> Result<Option<VenueOrder>, ReadError> {
        match self.get_json(format!("{ORDERS_PATH}/{venue_order_id}")) {
            Ok(v) => parse_order(v.get("order").unwrap_or(&v)).map(Some),
            Err(ReadError::Http { status: 404, .. }) => Ok(None),
            Err(e) => Err(e),
        }
    }

    /// Every order on `ticker` since `min_ts` (all statuses, paged).
    pub fn list_orders(
        &mut self,
        ticker: &str,
        min_ts: Option<i64>,
    ) -> Result<Vec<VenueOrder>, ReadError> {
        let mut out = Vec::new();
        let mut cursor = String::new();
        for _ in 0..20 {
            let mut path = format!("{ORDERS_PATH}?ticker={ticker}&limit=200{}", self.sub_q('&'));
            if let Some(ts) = min_ts {
                path.push_str(&format!("&min_ts={ts}"));
            }
            if !cursor.is_empty() {
                path.push_str(&format!("&cursor={cursor}"));
            }
            let v = self.get_json(path)?;
            for o in v
                .get("orders")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
            {
                out.push(parse_order(o)?);
            }
            cursor = str_field(&v, "cursor").unwrap_or_default();
            if cursor.is_empty() {
                return Ok(out);
            }
        }
        Err(ReadError::Malformed(
            "orders pagination did not terminate".into(),
        ))
    }

    /// Searches every order on the ticker: client ids stay reserved after an
    /// order is cancelled (demo: 409 `order_already_exists`), so a time
    /// window could miss the order a retry collided with.
    pub fn find_by_client_id(
        &mut self,
        ticker: &str,
        client_order_id: &str,
    ) -> Result<Option<VenueOrder>, ReadError> {
        let hits: Vec<VenueOrder> = self
            .list_orders(ticker, None)?
            .into_iter()
            .filter(|o| o.client_order_id.as_deref() == Some(client_order_id))
            .collect();
        match hits.len() {
            0 => Ok(None),
            1 => Ok(hits.into_iter().next()),
            n => Err(ReadError::Malformed(format!(
                "{n} orders share client id {client_order_id}"
            ))),
        }
    }

    pub fn fills_for_order(&mut self, venue_order_id: &str) -> Result<Vec<Fill>, ReadError> {
        let mut out = Vec::new();
        let mut cursor = String::new();
        for _ in 0..50 {
            let mut path = format!("{FILLS_PATH}?order_id={venue_order_id}&limit=200");
            if !cursor.is_empty() {
                path.push_str(&format!("&cursor={cursor}"));
            }
            let v = self.get_json(path)?;
            for f in v
                .get("fills")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
            {
                let (oid, fill) = parse_fill(f)?;
                if oid != venue_order_id {
                    return Err(ReadError::Malformed("fill for another order".into()));
                }
                out.push(fill);
            }
            cursor = str_field(&v, "cursor").unwrap_or_default();
            if cursor.is_empty() {
                return Ok(out);
            }
        }
        Err(ReadError::Malformed(
            "fills pagination did not terminate".into(),
        ))
    }

    /// Signed YES position on `ticker` (positive = long YES).
    pub fn position(&mut self, ticker: &str) -> Result<i64, ReadError> {
        let v = self.get_json(format!(
            "{POSITIONS_PATH}?ticker={ticker}&count_filter=position{}",
            self.sub_q('&')
        ))?;
        let rows = v
            .get("market_positions")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let mut total = 0i64;
        for r in rows
            .iter()
            .filter(|r| str_field(r, "ticker").as_deref() == Some(ticker))
        {
            let raw = str_field(r, "position_fp")
                .ok_or_else(|| ReadError::Malformed("position_fp".into()))?;
            total += momento_kalshi::signed_count_fp_to_i64(&raw)
                .map_err(|e| ReadError::Malformed(e.to_string()))?;
        }
        Ok(total)
    }

    pub fn balance_cents(&mut self, exchange_index: Option<i64>) -> Result<Value, ReadError> {
        let mut path = momento_kalshi::BALANCE_PATH.to_string();
        let mut q = Vec::new();
        if let Some(i) = exchange_index {
            q.push(format!("exchange_index={i}"));
        }
        if let Some(s) = self.subaccount {
            q.push(format!("subaccount={s}"));
        }
        if !q.is_empty() {
            path.push('?');
            path.push_str(&q.join("&"));
        }
        self.get_json(path)
    }
}

#[cfg(test)]
mod count_tests {
    use super::count_field;
    use serde_json::json;

    #[test]
    fn whole_counts_parse() {
        assert_eq!(
            count_field(&json!({"fill_count_fp": "12.00"}), &["fill_count_fp"]),
            Some(12)
        );
        assert_eq!(
            count_field(&json!({"fill_count": 3}), &["fill_count_fp", "fill_count"]),
            Some(3)
        );
    }

    // Demo books carry fractional counts ("7309.75"). An order count that is
    // not whole must fail closed, not fall through to an older field.
    #[test]
    fn fractional_count_is_none_without_fall_through() {
        let v = json!({"fill_count_fp": "0.50", "fill_count": 0});
        assert_eq!(count_field(&v, &["fill_count_fp", "fill_count"]), None);
        assert_eq!(
            count_field(&json!({"count_fp": "abc"}), &["count_fp"]),
            None
        );
        assert_eq!(count_field(&json!({}), &["count_fp"]), None);
    }
}
