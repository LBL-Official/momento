//! In-process Kalshi fake for fixture tests. Models the documented V2
//! semantics the adapter depends on; it is not evidence of venue behaviour
//! (the demo exercise is). Faults are injected per HTTP method.

use std::collections::{BTreeMap, VecDeque};

use momento_kalshi::{KalshiHttpRequest, KalshiTransport, TransportOutcome};
use momento_strategy_nba::{BalancePrecision, FeeModel, FeeType, Liquidity};
use serde_json::{Value, json};

#[derive(Clone, Debug)]
pub struct FakeFill {
    pub id: String,
    pub count: u32,
    pub price: u16,
    pub taker: bool,
    pub fee_cc: i64,
}

#[derive(Clone, Debug)]
pub struct FakeOrder {
    pub id: String,
    pub cid: String,
    pub ticker: String,
    pub bid: bool,
    pub price: u16,
    pub total: u32,
    pub filled: u32,
    pub status: &'static str,
    pub fills: Vec<FakeFill>,
}

#[derive(Clone, Copy, Debug, Default)]
pub struct Book {
    pub best_bid: u16,
    pub bid_depth: u32,
    pub best_ask: u16,
    pub ask_depth: u32,
}

#[derive(Clone, Debug)]
pub enum Fault {
    /// Return a timeout. `apply` = the venue processed it anyway.
    Timeout { apply: bool },
    Status {
        code: u16,
        body: String,
        apply: bool,
    },
    /// Before processing a DELETE, a counterparty fills this many.
    FillBeforeCancel { count: u32 },
}

pub struct FakeExchange {
    pub orders: Vec<FakeOrder>,
    pub books: BTreeMap<String, Book>,
    pub positions: BTreeMap<String, i64>,
    pub faults: VecDeque<(&'static str, Fault)>,
    pub log: Vec<KalshiHttpRequest>,
    next: u64,
    fees: FeeModel,
}

fn cnt(n: u32) -> String {
    format!("{n}.00")
}

fn dollars(cents: u16) -> String {
    format!("{}.{:02}00", cents / 100, cents % 100)
}

fn fee_dollars(cc: i64) -> String {
    format!("{}.{:04}", cc / 10_000, cc % 10_000)
}

fn parse_count(v: &Value) -> Option<u32> {
    let s = v.as_str()?;
    let (w, f) = s.split_once('.').unwrap_or((s, ""));
    if f.bytes().any(|b| b != b'0') {
        return None;
    }
    w.parse().ok()
}

fn parse_price(v: &Value) -> Option<u16> {
    let s = v.as_str()?;
    let (w, f) = s.split_once('.')?;
    let f = format!("{f:0<4}");
    if &f[2..] != "00" {
        return None;
    }
    Some(w.parse::<u16>().ok()? * 100 + f[..2].parse::<u16>().ok()?)
}

fn query(path: &str, key: &str) -> Option<String> {
    path.split_once('?')?.1.split('&').find_map(|kv| {
        let (k, v) = kv.split_once('=')?;
        (k == key).then(|| v.to_string())
    })
}

impl Default for FakeExchange {
    fn default() -> Self {
        Self {
            orders: Vec::new(),
            books: BTreeMap::new(),
            positions: BTreeMap::new(),
            faults: VecDeque::new(),
            log: Vec::new(),
            next: 0,
            fees: FeeModel::new(
                FeeType::QuadraticWithMakerFees,
                1000,
                BalancePrecision::Centicent,
            ),
        }
    }
}

impl FakeExchange {
    pub fn book(&mut self, ticker: &str, bid: u16, bid_depth: u32, ask: u16, ask_depth: u32) {
        self.books.insert(
            ticker.into(),
            Book {
                best_bid: bid,
                bid_depth,
                best_ask: ask,
                ask_depth,
            },
        );
    }

    pub fn fault(&mut self, method: &'static str, f: Fault) {
        self.faults.push_back((method, f));
    }

    fn id(&mut self, prefix: &str) -> String {
        self.next += 1;
        format!("{prefix}-{}", self.next)
    }

    fn fill(&mut self, idx: usize, n: u32, price: u16, taker: bool) {
        if n == 0 {
            return;
        }
        let liq = if taker {
            Liquidity::Taker
        } else {
            Liquidity::Maker
        };
        let fee_cc = self.fees.order_fee_centicents(liq, n, price).unwrap_or(0);
        let fid = self.id("fill");
        let o = &mut self.orders[idx];
        o.filled += n;
        o.fills.push(FakeFill {
            id: fid,
            count: n,
            price,
            taker,
            fee_cc,
        });
        let signed = if o.bid { i64::from(n) } else { -i64::from(n) };
        *self.positions.entry(o.ticker.clone()).or_default() += signed;
        if o.filled == o.total {
            o.status = "executed";
        }
    }

    /// A counterparty trades against a resting order (maker fill), capped at
    /// what remains.
    pub fn trade_against(&mut self, order_id: &str, n: u32) -> u32 {
        let Some(idx) = self.orders.iter().position(|o| o.id == order_id) else {
            return 0;
        };
        if self.orders[idx].status != "resting" {
            return 0;
        }
        let n = n.min(self.orders[idx].total - self.orders[idx].filled);
        let price = self.orders[idx].price;
        self.fill(idx, n, price, false);
        n
    }

    pub fn order_by_cid(&self, cid: &str) -> Option<&FakeOrder> {
        self.orders.iter().find(|o| o.cid == cid)
    }

    fn order_json(o: &FakeOrder) -> Value {
        json!({
            "order_id": o.id,
            "client_order_id": o.cid,
            "ticker": o.ticker,
            "status": o.status,
            "book_side": if o.bid { "bid" } else { "ask" },
            "yes_price_dollars": dollars(o.price),
            "fill_count_fp": cnt(o.filled),
            "remaining_count_fp": cnt(if o.status == "resting" { o.total - o.filled } else { 0 }),
            "initial_count_fp": cnt(o.total),
        })
    }

    fn http(code: u16, body: Value) -> TransportOutcome {
        TransportOutcome::Http {
            status: code,
            body: body.to_string(),
        }
    }

    fn err(code: u16, c: &str) -> TransportOutcome {
        Self::http(code, json!({"error": {"code": c, "message": c}}))
    }

    /// Crossing fill for an incoming order against the synthetic book.
    fn match_incoming(&mut self, idx: usize) {
        let (ticker, bid, price, want) = {
            let o = &self.orders[idx];
            (o.ticker.clone(), o.bid, o.price, o.total - o.filled)
        };
        let Some(mut b) = self.books.get(&ticker).copied() else {
            return;
        };
        if bid && b.ask_depth > 0 && price >= b.best_ask {
            let n = want.min(b.ask_depth);
            b.ask_depth -= n;
            self.fill(idx, n, b.best_ask, true);
        } else if !bid && b.bid_depth > 0 && price <= b.best_bid {
            let n = want.min(b.bid_depth);
            b.bid_depth -= n;
            self.fill(idx, n, b.best_bid, true);
        }
        self.books.insert(ticker, b);
    }

    fn create(&mut self, body: &Value) -> TransportOutcome {
        let get = |k: &str| body.get(k).cloned().unwrap_or(Value::Null);
        let cid = get("client_order_id").as_str().unwrap_or("").to_string();
        if !cid.is_empty() && self.orders.iter().any(|o| o.cid == cid) {
            return Self::err(409, "duplicate_client_order_id");
        }
        let (Some(ticker), Some(side), Some(total), Some(price), Some(tif)) = (
            get("ticker").as_str().map(str::to_string),
            get("side").as_str().map(str::to_string),
            parse_count(&get("count")),
            parse_price(&get("price")),
            get("time_in_force").as_str().map(str::to_string),
        ) else {
            return Self::err(400, "invalid_parameters");
        };
        let bid = side == "bid";
        let post_only = get("post_only").as_bool().unwrap_or(false);
        let reduce_only = get("reduce_only").as_bool().unwrap_or(false);
        if reduce_only && tif != "immediate_or_cancel" {
            return Self::err(400, "reduce_only_requires_ioc");
        }
        let b = self.books.get(&ticker).copied().unwrap_or_default();
        let crosses = if bid {
            b.ask_depth > 0 && price >= b.best_ask
        } else {
            b.bid_depth > 0 && price <= b.best_bid
        };
        if post_only && crosses {
            return Self::err(400, "post_only_cross");
        }
        let mut total = total;
        if reduce_only {
            let pos = *self.positions.get(&ticker).unwrap_or(&0);
            let cap = if bid { (-pos).max(0) } else { pos.max(0) };
            total = total.min(u32::try_from(cap).unwrap_or(0));
            if total == 0 {
                return Self::err(400, "reduce_only_no_position");
            }
        }
        let id = self.id("ord");
        self.orders.push(FakeOrder {
            id: id.clone(),
            cid: cid.clone(),
            ticker,
            bid,
            price,
            total,
            filled: 0,
            status: "resting",
            fills: Vec::new(),
        });
        let idx = self.orders.len() - 1;
        self.match_incoming(idx);
        let o = &mut self.orders[idx];
        if o.status == "resting" && tif != "good_till_canceled" {
            o.status = "canceled";
        }
        let remaining = if o.status == "resting" {
            o.total - o.filled
        } else {
            0
        };
        Self::http(
            201,
            json!({
                "order_id": id,
                "client_order_id": cid,
                "fill_count": cnt(o.filled),
                "remaining_count": cnt(remaining),
                "ts_ms": 1,
            }),
        )
    }

    fn cancel(&mut self, id: &str, pre_fill: u32) -> TransportOutcome {
        let Some(idx) = self.orders.iter().position(|o| o.id == id) else {
            return Self::err(404, "not_found");
        };
        if pre_fill > 0 {
            self.trade_against(id, pre_fill);
        }
        let o = &mut self.orders[idx];
        if o.status != "resting" {
            return Self::err(404, "not_found");
        }
        let reduced = o.total - o.filled;
        o.status = "canceled";
        Self::http(
            200,
            json!({"order_id": id, "client_order_id": o.cid, "reduced_by": cnt(reduced), "ts_ms": 2}),
        )
    }

    fn amend(&mut self, id: &str, body: &Value) -> TransportOutcome {
        let Some(idx) = self.orders.iter().position(|o| o.id == id) else {
            return Self::err(404, "not_found");
        };
        let (Some(total), Some(price)) = (
            body.get("count").and_then(parse_count),
            body.get("price").and_then(parse_price),
        ) else {
            return Self::err(400, "invalid_parameters");
        };
        let (filled_before, resting_before) = {
            let o = &mut self.orders[idx];
            if o.status != "resting" || total < o.filled {
                return Self::err(400, "order_not_amendable");
            }
            let before = (o.filled, o.total - o.filled);
            o.total = total;
            o.price = price;
            if o.filled == total {
                o.status = "executed";
            }
            before
        };
        if self.orders[idx].status == "resting" {
            self.match_incoming(idx);
        }
        let o = &self.orders[idx];
        let remaining = if o.status == "resting" {
            o.total - o.filled
        } else {
            0
        };
        // Documented V2 shape: counts only when the amend filled or resized;
        // fill_count is the amend-caused fills, not the order total.
        let mut resp = json!({"order_id": id, "client_order_id": o.cid, "ts_ms": 3});
        let amend_fills = o.filled - filled_before;
        if amend_fills > 0 || remaining != resting_before {
            resp["fill_count"] = json!(cnt(amend_fills));
            resp["remaining_count"] = json!(cnt(remaining));
        }
        Self::http(200, resp)
    }

    fn get(&mut self, path: &str) -> TransportOutcome {
        let base = path.split('?').next().unwrap_or(path);
        if let Some(id) = base.strip_prefix("/trade-api/v2/portfolio/orders/") {
            return match self.orders.iter().find(|o| o.id == id) {
                Some(o) => Self::http(200, json!({"order": Self::order_json(o)})),
                None => Self::err(404, "not_found"),
            };
        }
        match base {
            "/trade-api/v2/portfolio/orders" => {
                let t = query(path, "ticker");
                let orders: Vec<Value> = self
                    .orders
                    .iter()
                    .filter(|o| t.as_deref().is_none_or(|t| t == o.ticker))
                    .map(Self::order_json)
                    .collect();
                Self::http(200, json!({"orders": orders, "cursor": ""}))
            }
            "/trade-api/v2/portfolio/fills" => {
                let oid = query(path, "order_id");
                let fills: Vec<Value> = self
                    .orders
                    .iter()
                    .filter(|o| oid.as_deref().is_none_or(|x| x == o.id))
                    .flat_map(|o| {
                        o.fills.iter().map(move |f| {
                            json!({
                                "fill_id": f.id,
                                "order_id": o.id,
                                "ticker": o.ticker,
                                "count_fp": cnt(f.count),
                                "yes_price_dollars": dollars(f.price),
                                "is_taker": f.taker,
                                "fee_cost": fee_dollars(f.fee_cc),
                                "ts": 5,
                            })
                        })
                    })
                    .collect();
                Self::http(200, json!({"fills": fills, "cursor": ""}))
            }
            "/trade-api/v2/portfolio/positions" => {
                let t = query(path, "ticker").unwrap_or_default();
                let p = *self.positions.get(&t).unwrap_or(&0);
                let fp = if p < 0 {
                    format!("-{}.00", -p)
                } else {
                    format!("{p}.00")
                };
                Self::http(
                    200,
                    json!({"market_positions": [{"ticker": t, "position_fp": fp}], "cursor": ""}),
                )
            }
            _ => Self::err(404, "no_route"),
        }
    }
}

impl KalshiTransport for FakeExchange {
    fn execute(&mut self, request: KalshiHttpRequest) -> TransportOutcome {
        self.log.push(request.clone());
        let fault = match self.faults.front() {
            Some((m, _)) if *m == request.method => self.faults.pop_front().map(|(_, f)| f),
            _ => None,
        };
        let body: Value = request
            .body
            .as_deref()
            .and_then(|b| serde_json::from_str(b).ok())
            .unwrap_or(Value::Null);
        let base = request
            .path
            .split('?')
            .next()
            .unwrap_or(&request.path)
            .to_string();
        let mut pre_fill = 0;
        let (apply, replace) = match &fault {
            None => (true, None),
            Some(Fault::Timeout { apply }) => (*apply, Some(TransportOutcome::Timeout)),
            Some(Fault::Status { code, body, apply }) => (
                *apply,
                Some(TransportOutcome::Http {
                    status: *code,
                    body: body.clone(),
                }),
            ),
            Some(Fault::FillBeforeCancel { count }) => {
                pre_fill = *count;
                (true, None)
            }
        };
        let real = if !apply {
            TransportOutcome::Timeout
        } else {
            match request.method.as_str() {
                "POST" if base == "/trade-api/v2/portfolio/events/orders" => self.create(&body),
                "POST" if base.ends_with("/amend") => {
                    let id = base
                        .trim_end_matches("/amend")
                        .rsplit('/')
                        .next()
                        .unwrap_or("")
                        .to_string();
                    self.amend(&id, &body)
                }
                "DELETE" => {
                    let id = base.rsplit('/').next().unwrap_or("").to_string();
                    self.cancel(&id, pre_fill)
                }
                "GET" => self.get(&request.path),
                _ => Self::err(405, "method"),
            }
        };
        replace.unwrap_or(real)
    }
}
