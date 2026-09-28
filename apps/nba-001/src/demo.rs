//! `demo-exercise`: the NBA order adapter and executor against the Kalshi demo
//! environment. Demo credentials only: the secret loader and
//! `SandboxHttpTransport::demo` both refuse production. One or two contracts
//! per scenario; every scenario cancels what it rests and sells back what it
//! buys. Output is one JSON report; no secret, key id, or user id is printed.

use std::time::Duration;

use momento_kalshi::{
    KalshiEnvironment, SandboxHttpTransport, credentials_from_secret_file, redact_secrets,
};
use momento_strategy_nba::{
    BalancePrecision, BookSide, FeeModel, FeeType, GameBook, Liquidity, OrderRole, OrderSpec,
    OrderStatus, TimeInForce, multiplier_milli,
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};

use crate::executor::{self, ExecEvent, Sink};
use crate::public::parse_market;
use crate::venue::{AmendOutcome, CancelOutcome, CreateOutcome, NbaVenue};

type Venue = NbaVenue<SandboxHttpTransport>;

const DEFAULT_SERIES: &str = "KXNBAGAME,KXWNBAGAME,KXMLBGAME,KXNFLGAME,KXNHLGAME,KXNCAAFGAME";

struct Run {
    venue: Venue,
    run_id: String,
    seq: u32,
    scenarios: Vec<Value>,
}

struct Target {
    series: String,
    ticker: String,
    event: String,
    bid: u16,
    ask: u16,
    ask_depth: u32,
    fees: Option<FeeModel>,
    book_top: Value,
    fee_type_raw: Value,
    fee_multiplier_raw: Value,
}

fn now_s() -> i64 {
    crate::engine::now_ms() / 1000
}

impl Run {
    fn cid(&mut self, scenario: &str) -> String {
        self.seq += 1;
        let d = Sha256::digest(format!(
            "nba-001-demo|{}|{scenario}|{}",
            self.run_id, self.seq
        ));
        let hex: String = d.iter().take(8).map(|b| format!("{b:02x}")).collect();
        format!("{}{hex}", crate::account::CLIENT_ID_PREFIX)
    }

    fn spec(
        &mut self,
        scenario: &str,
        t: &Target,
        side: BookSide,
        price: u16,
        count: u32,
    ) -> OrderSpec {
        OrderSpec {
            client_order_id: self.cid(scenario),
            role: OrderRole::Entry,
            ticker: t.ticker.clone(),
            side,
            price_cents: price,
            count,
            tif: TimeInForce::GoodTillCanceled,
            post_only: false,
            reduce_only: false,
            expiration_ts: None,
            cancel_order_on_pause: true,
            subaccount: None,
        }
    }

    fn record(&mut self, name: &str, verdict: &str, detail: Value) {
        self.scenarios
            .push(json!({"scenario": name, "verdict": verdict, "detail": detail}));
    }
}

fn sink_into(log: &mut Vec<Value>) -> impl FnMut(&GameBook, ExecEvent) -> Result<(), String> + '_ {
    move |_, ev| {
        log.push(json!(ev));
        Ok(())
    }
}

fn status_name(s: &OrderStatus) -> Value {
    json!(s)
}

/// Top of a demo orderbook from `/markets/{t}/orderbook`. Levels carry
/// fractional contract counts on demo, so depth is kept in hundredths; the
/// usable depth for a whole-contract order is its floor. Unparsed levels are
/// counted, not dropped silently.
struct BookTop {
    best_yes_bid: Option<u16>,
    /// 100 − best NO bid.
    yes_ask: Option<u16>,
    /// Whole contracts available at `yes_ask`.
    ask_depth: u32,
    unparsed_levels: usize,
    top: Value,
}

fn book_top(venue: &mut Venue, ticker: &str) -> Option<BookTop> {
    let book = venue
        .get_json(format!("/trade-api/v2/markets/{ticker}/orderbook"))
        .ok()?;
    let mut unparsed = 0;
    let mut levels = |side: &str| -> Vec<(u16, i64)> {
        let raw = book
            .get("orderbook_fp")
            .and_then(|ob| ob.get(side)?.as_array().cloned())
            .unwrap_or_default();
        let mut out = Vec::new();
        for lvl in &raw {
            let parsed = (|| {
                let p = crate::venue::dollars_to_micros(lvl.get(0)?.as_str()?)?;
                let c = momento_kalshi::count_fp_to_hundredths(lvl.get(1)?.as_str()?).ok()?;
                (p % 10_000 == 0 && (0..=1_000_000).contains(&p))
                    .then_some(((p / 10_000) as u16, c))
            })();
            match parsed {
                Some(x) => out.push(x),
                None => unparsed += 1,
            }
        }
        out
    };
    let yes = levels("yes_dollars");
    let no = levels("no_dollars");
    let best_yes_bid = yes.iter().map(|(p, _)| *p).max();
    let best_no = no.iter().max_by_key(|(p, _)| *p).copied();
    let top = |v: &[(u16, i64)]| {
        let mut v = v.to_vec();
        v.sort_by_key(|x| std::cmp::Reverse(x.0));
        v.into_iter()
            .take(3)
            .map(|(p, h)| json!({"cents": p, "hundredths": h}))
            .collect::<Vec<_>>()
    };
    Some(BookTop {
        best_yes_bid,
        yes_ask: best_no.map(|(p, _)| 100 - p),
        ask_depth: best_no.map_or(0, |(_, h)| u32::try_from(h / 100).unwrap_or(u32::MAX)),
        unparsed_levels: unparsed,
        top: json!({"yes_bids": top(&yes), "no_bids": top(&no)}),
    })
}

fn pick_target(venue: &mut Venue) -> Result<Target, String> {
    let series_list = std::env::var("NBA001_DEMO_SERIES").unwrap_or_else(|_| DEFAULT_SERIES.into());
    let mut tried = Vec::new();
    for series in series_list
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
    {
        let listing = match venue.get_json(format!(
            "/trade-api/v2/markets?series_ticker={series}&status=open&limit=200"
        )) {
            Ok(v) => v,
            Err(e) => {
                tried.push(format!("{series}: {e:?}"));
                continue;
            }
        };
        let mut best: Option<(u16, crate::public::MarketView)> = None;
        for m in listing
            .get("markets")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
        {
            let Some(mv) = parse_market(m) else { continue };
            let (Some(bid), Some(ask)) = (mv.yes_bid_cents, mv.yes_ask_cents) else {
                continue;
            };
            if !(8..=90).contains(&bid) || ask > 95 || ask < bid + 2 {
                continue;
            }
            let spread = ask - bid;
            if best.as_ref().is_none_or(|(s, _)| spread < *s) {
                best = Some((spread, mv));
            }
        }
        let Some((_, mv)) = best else {
            tried.push(format!("{series}: no two-sided market with room to rest"));
            continue;
        };
        let (bid, ask) = (mv.yes_bid_cents.unwrap_or(0), mv.yes_ask_cents.unwrap_or(0));
        let bt = book_top(venue, &mv.desc.ticker);
        let (ask, ask_depth) = match &bt {
            Some(b) if b.yes_ask.is_some() => (b.yes_ask.unwrap_or(ask), b.ask_depth),
            _ => (ask, 0),
        };
        let book_top = json!({
            "book": bt.as_ref().map(|b| &b.top),
            "unparsed_levels": bt.as_ref().map(|b| b.unparsed_levels),
            "listing_yes_bid": mv.yes_bid_cents,
            "listing_yes_ask": mv.yes_ask_cents,
        });
        let sv = venue
            .get_json(format!("/trade-api/v2/series/{series}"))
            .ok()
            .and_then(|v| v.get("series").cloned())
            .unwrap_or(Value::Null);
        let fee_type_raw = sv.get("fee_type").cloned().unwrap_or(Value::Null);
        let fee_multiplier_raw = sv.get("fee_multiplier").cloned().unwrap_or(Value::Null);
        let fees = fee_type_raw
            .as_str()
            .and_then(FeeType::parse)
            .zip(multiplier_milli(&fee_multiplier_raw))
            .map(|(ft, m)| FeeModel::new(ft, m, BalancePrecision::Centicent));
        return Ok(Target {
            series: series.to_string(),
            event: mv.desc.event_ticker.clone(),
            ticker: mv.desc.ticker.clone(),
            bid,
            ask,
            ask_depth,
            fees,
            book_top,
            fee_type_raw,
            fee_multiplier_raw,
        });
    }
    Err(format!("no demo market: {}", tried.join("; ")))
}

/// Rest, read back, duplicate id, amend up, amend down, cancel, cancel again.
fn rest_amend_cancel(run: &mut Run, t: &Target) {
    let name = "rest_amend_cancel";
    let mut log = Vec::new();
    let mut book = GameBook::new(&t.event, &t.ticker, &t.ticker);
    let price = t.bid.saturating_sub(3).max(1);
    let mut spec = run.spec(name, t, BookSide::Bid, price, 2);
    spec.post_only = true;
    let cid = spec.client_order_id.clone();
    let mut d = serde_json::Map::new();
    let mut ok = true;
    {
        let mut s = sink_into(&mut log);
        let sink: &mut Sink<'_> = &mut s;
        let r = executor::submit(&mut book, &mut run.venue, spec.clone(), now_s(), sink);
        d.insert(
            "submit".into(),
            json!({"err": r.err(), "status": status_name(&book.order(&cid).unwrap().status)}),
        );
    }
    let Some(vid) = book.order(&cid).and_then(|o| o.venue_order_id.clone()) else {
        run.record(name, "FAIL", json!({"detail": d, "log": log}));
        return;
    };
    ok &= book.order(&cid).unwrap().status == OrderStatus::Resting;
    let mut echoed = None;
    for _ in 0..10 {
        if let Ok(Some(o)) = run.venue.get_order(&vid) {
            echoed = o.client_order_id.clone();
            break;
        }
        std::thread::sleep(Duration::from_millis(500));
    }
    d.insert(
        "client_id_format_accepted_and_echoed".into(),
        json!(echoed.as_deref() == Some(cid.as_str())),
    );
    ok &= echoed.as_deref() == Some(cid.as_str());
    let mut found = false;
    for _ in 0..10 {
        if matches!(run.venue.find_by_client_id(&t.ticker, &cid), Ok(Some(o)) if o.venue_order_id == vid)
        {
            found = true;
            break;
        }
        std::thread::sleep(Duration::from_millis(500));
    }
    d.insert("find_by_client_id".into(), json!(found));
    ok &= found;

    let dup = run.venue.create(&spec);
    let dup_rested =
        matches!(&dup, CreateOutcome::Acked { venue_order_id, .. } if *venue_order_id != vid);
    if let CreateOutcome::Acked { venue_order_id, .. } = &dup
        && dup_rested
    {
        let _ = run.venue.cancel(venue_order_id, &t.ticker);
    }
    d.insert(
        "duplicate_client_id".into(),
        json!({"outcome": dup, "second_order_created": dup_rested}),
    );
    ok &= !dup_rested;

    let up = (price + 1).min(t.ask.saturating_sub(1)).max(price);
    let raw = run.venue.amend(&vid, &spec, up, 2, None);
    let amend_id_stable = match &raw {
        AmendOutcome::Amended { venue_order_id, .. } => Some(*venue_order_id == vid),
        _ => None,
    };
    d.insert(
        "amend_up".into(),
        json!({"outcome": raw, "order_id_stable": amend_id_stable}),
    );
    ok &= amend_id_stable == Some(true);
    if let Ok(Some(after)) = run.venue.get_order(&vid) {
        d.insert("after_amend".into(), json!({"yes_price_dollars": after.yes_price_dollars, "remaining": after.remaining_count, "status": after.status}));
    }
    {
        let mut s = sink_into(&mut log);
        let sink: &mut Sink<'_> = &mut s;
        let _ = executor::reconcile_order(&mut book, &mut run.venue, &cid, now_s(), now_s(), sink);
        let r = executor::amend(&mut book, &mut run.venue, &cid, up, 1, now_s(), sink);
        d.insert("amend_down_total_1".into(), json!({"err": r.err(), "status": status_name(&book.order(&cid).unwrap().status), "max_count": book.order(&cid).unwrap().max_count}));
        let r = executor::cancel(&mut book, &mut run.venue, &cid, now_s(), sink);
        let o = book.order(&cid).unwrap();
        d.insert("cancel".into(), json!({"err": r.err(), "status": status_name(&o.status), "final_count_known": o.final_count_known, "confirmed_filled": o.confirmed_filled(), "max_count_before_cancel": o.max_count}));
        ok &= o.status == OrderStatus::Cancelled || o.status == OrderStatus::Filled;
        let booked = o.confirmed_filled();
        std::thread::sleep(Duration::from_secs(2));
        let venue_fills: Option<u32> = run
            .venue
            .fills_for_order(&vid)
            .ok()
            .map(|f| f.iter().map(|x| x.count).sum());
        let final_read = run.venue.get_order(&vid).ok().flatten();
        d.insert(
            "book_vs_venue".into(),
            json!({
                "booked_fills": booked,
                "venue_fill_records": venue_fills,
                "venue_final_fill_count": final_read.as_ref().map(|v| v.fill_count),
                "venue_final_status": final_read.as_ref().map(|v| v.status),
            }),
        );
        ok &= venue_fills == Some(booked)
            && final_read.as_ref().is_some_and(|v| v.fill_count == booked);
    }
    let again = run.venue.cancel(&vid, &t.ticker);
    d.insert("cancel_again".into(), json!(again));
    ok &= matches!(
        again,
        CancelOutcome::NotFound | CancelOutcome::Rejected { .. }
    );
    run.record(
        name,
        if ok { "PASS" } else { "FAIL" },
        json!({"detail": d, "log": log}),
    );
}

const DIAG_FIELDS: [&str; 9] = [
    "order_id",
    "client_order_id",
    "ticker",
    "status",
    "yes_price_dollars",
    "fill_count_fp",
    "remaining_count_fp",
    "created_time",
    "last_update_time",
];

fn diag_view(v: &Value) -> Value {
    let o = v.get("order").unwrap_or(v);
    let mut m = serde_json::Map::new();
    for k in DIAG_FIELDS {
        m.insert(k.into(), o.get(k).cloned().unwrap_or(Value::Null));
    }
    let mut keys: Vec<&str> = o
        .as_object()
        .map(|x| {
            x.keys()
                .map(String::as_str)
                .filter(|k| *k != "user_id")
                .collect()
        })
        .unwrap_or_default();
    keys.sort_unstable();
    m.insert("keys".into(), json!(keys));
    Value::Object(m)
}

/// Venue read-after-write behaviour: single-order GET fields, list
/// visibility latency by client id, and when a price-only amend shows.
fn read_after_write(run: &mut Run, t: &Target) {
    let name = "read_after_write_diagnostics";
    let mut spec = run.spec(name, t, BookSide::Bid, t.bid.saturating_sub(4).max(1), 1);
    spec.post_only = true;
    let cid = spec.client_order_id.clone();
    let sent = std::time::Instant::now();
    let out = run.venue.create(&spec);
    let CreateOutcome::Acked { venue_order_id, .. } = &out else {
        run.record(name, "FAIL", json!({"create": out}));
        return;
    };
    let vid = venue_order_id.clone();
    let get_now = run
        .venue
        .get_json(format!("{}/{vid}", momento_kalshi::ORDERS_PATH))
        .map(|v| diag_view(&v));
    let mut seen_by_client_id_search: Option<u128> = None;
    let mut seen_in_ticker_list: Option<u128> = None;
    for _ in 0..40 {
        if seen_by_client_id_search.is_none()
            && matches!(run.venue.find_by_client_id(&t.ticker, &cid), Ok(Some(_)))
        {
            seen_by_client_id_search = Some(sent.elapsed().as_millis());
        }
        if seen_in_ticker_list.is_none()
            && run
                .venue
                .get_json(format!(
                    "{}?ticker={}&limit=200",
                    momento_kalshi::ORDERS_PATH,
                    t.ticker
                ))
                .ok()
                .and_then(|v| v.get("orders").and_then(Value::as_array).cloned())
                .is_some_and(|os| {
                    os.iter().any(|o| {
                        o.get("client_order_id").and_then(Value::as_str) == Some(cid.as_str())
                    })
                })
        {
            seen_in_ticker_list = Some(sent.elapsed().as_millis());
        }
        if seen_by_client_id_search.is_some() && seen_in_ticker_list.is_some() {
            break;
        }
        std::thread::sleep(Duration::from_millis(500));
    }
    let up = (spec.price_cents + 1)
        .min(t.ask.saturating_sub(1))
        .max(spec.price_cents);
    let amend = run.venue.amend(&vid, &spec, up, 1, None);
    let amended_at = std::time::Instant::now();
    let mut price_seen = Vec::new();
    for wait_ms in [0u64, 1000, 3000] {
        std::thread::sleep(Duration::from_millis(wait_ms));
        let p = run
            .venue
            .get_json(format!("{}/{vid}", momento_kalshi::ORDERS_PATH))
            .ok()
            .and_then(|v| {
                v.get("order")
                    .and_then(|o| o.get("yes_price_dollars"))
                    .cloned()
            });
        price_seen
            .push(json!({"after_ms": amended_at.elapsed().as_millis(), "yes_price_dollars": p}));
    }
    let cancel = run.venue.cancel(&vid, &t.ticker);
    let echoed = get_now.as_ref().ok().and_then(|v| {
        v.get("client_order_id")
            .and_then(Value::as_str)
            .map(|s| s == cid)
    });
    run.record(
        name,
        "OBSERVED",
        json!({
            "client_order_id_sent": cid,
            "get_immediately": get_now.as_ref().ok(),
            "get_error": get_now.as_ref().err(),
            "get_echoes_client_order_id": echoed,
            "client_id_search_visible_after_ms": seen_by_client_id_search,
            "ticker_list_visible_after_ms": seen_in_ticker_list,
            "price_only_amend": amend,
            "amend_target_price_cents": up,
            "price_after_amend": price_seen,
            "cancel": cancel,
        }),
    );
}

fn post_only_cross(run: &mut Run, t: &Target) {
    let name = "post_only_cross";
    let mut spec = run.spec(name, t, BookSide::Bid, t.ask, 1);
    spec.post_only = true;
    let out = run.venue.create(&spec);
    if let CreateOutcome::Acked { venue_order_id, .. } = &out {
        let _ = run.venue.cancel(venue_order_id, &t.ticker);
    }
    let verdict = if matches!(out, CreateOutcome::Rejected { .. }) {
        "PASS"
    } else {
        "FAIL"
    };
    run.record(name, verdict, json!({"price": t.ask, "outcome": out}));
}

fn expiring_gtc(run: &mut Run, t: &Target) {
    let name = "expiring_gtc";
    let mut spec = run.spec(name, t, BookSide::Bid, t.bid.saturating_sub(3).max(1), 1);
    spec.expiration_ts = Some(now_s() + 10);
    let out = run.venue.create(&spec);
    let CreateOutcome::Acked { venue_order_id, .. } = &out else {
        run.record(name, "FAIL", json!({"outcome": out}));
        return;
    };
    std::thread::sleep(Duration::from_secs(16));
    let after = run.venue.get_order(venue_order_id);
    let expired =
        matches!(&after, Ok(Some(o)) if o.status == momento_strategy_nba::VenueStatus::Canceled);
    if !expired {
        let _ = run.venue.cancel(venue_order_id, &t.ticker);
    }
    run.record(
        name,
        if expired { "PASS" } else { "FAIL" },
        json!({"outcome": out, "status_after_expiry": after.ok().flatten().map(|o| o.status)}),
    );
}

fn reduce_only_without_position(run: &mut Run, t: &Target) {
    let name = "reduce_only_without_position";
    let mut spec = run.spec(name, t, BookSide::Ask, t.bid, 1);
    spec.tif = TimeInForce::ImmediateOrCancel;
    spec.reduce_only = true;
    spec.cancel_order_on_pause = false;
    let out = run.venue.create(&spec);
    let filled = matches!(&out, CreateOutcome::Acked { fill_count, .. } if *fill_count > 0);
    run.record(
        name,
        if filled { "FAIL" } else { "PASS" },
        json!({"outcome": out}),
    );
}

fn fee_check(t: &Target, liq: Liquidity, fills: &[momento_strategy_nba::Fill]) -> Value {
    let observed: Option<i64> = fills.iter().map(|f| f.fee_centicents).sum();
    let total: u32 = fills.iter().map(|f| f.count).sum();
    let price = fills
        .first()
        .filter(|f| f.yes_price_centicents % 100 == 0)
        .map(|f| (f.yes_price_centicents / 100) as u16);
    let model = match (t.fees, price) {
        (Some(m), Some(p)) => {
            let yes_side_price = p;
            m.order_fee_centicents(liq, total, yes_side_price).ok()
        }
        _ => None,
    };
    json!({
        "series_fee_type": t.fee_type_raw,
        "series_fee_multiplier": t.fee_multiplier_raw,
        "liquidity": liq,
        "is_taker": fills.iter().map(|f| f.is_taker).collect::<Vec<_>>(),
        "observed_fee_centicents": observed,
        "model_fee_centicents": model,
        "match": observed.is_some() && observed == model,
    })
}

/// Buy 1 at the ask (taker IOC), then sell it back reduce-only.
fn taker_round_trip(run: &mut Run, t: &Target, funded: bool) {
    let name = "taker_round_trip";
    if !funded || t.ask_depth < 1 {
        run.record(
            name,
            "SKIPPED",
            json!({"funded": funded, "ask_depth": t.ask_depth}),
        );
        return;
    }
    let mut log = Vec::new();
    let mut book = GameBook::new(&t.event, &t.ticker, &t.ticker);
    let mut buy = run.spec(name, t, BookSide::Bid, t.ask, 1);
    buy.tif = TimeInForce::ImmediateOrCancel;
    buy.cancel_order_on_pause = false;
    let bcid = buy.client_order_id.clone();
    let mut d = serde_json::Map::new();
    let mut ok = true;
    let no_fill = {
        let mut s = sink_into(&mut log);
        let sink: &mut Sink<'_> = &mut s;
        let r = executor::submit(&mut book, &mut run.venue, buy, now_s(), sink);
        for _ in 0..10 {
            let _ =
                executor::reconcile_order(&mut book, &mut run.venue, &bcid, now_s(), now_s(), sink);
            if book.order(&bcid).is_some_and(|o| o.is_settled()) {
                break;
            }
            std::thread::sleep(Duration::from_millis(500));
        }
        let o = book.order(&bcid).unwrap();
        d.insert("buy".into(), json!({"price": t.ask, "err": r.err(), "status": status_name(&o.status), "filled": o.confirmed_filled(), "settled": o.is_settled()}));
        d.insert("buy_fee".into(), fee_check(t, Liquidity::Taker, &o.fills));
        ok &= o.confirmed_filled() == 1 && o.is_settled();
        o.is_settled() && o.confirmed_filled() == 0
    };
    if no_fill {
        run.record(name, "OBSERVED_NO_FILL", json!({"detail": d, "log": log}));
        return;
    }
    let pos = run.venue.position(&t.ticker);
    d.insert("position_after_buy".into(), json!(pos));
    let held = pos.as_ref().copied().unwrap_or(0);
    if held > 0 {
        let fresh = run
            .venue
            .get_json(format!("/trade-api/v2/markets/{}", t.ticker))
            .ok()
            .and_then(|v| v.get("market").and_then(parse_market));
        let bid = fresh.and_then(|m| m.yes_bid_cents).unwrap_or(1).max(1);
        let mut sell = run.spec(name, t, BookSide::Ask, bid, held as u32);
        sell.role = OrderRole::Emergency;
        sell.tif = TimeInForce::ImmediateOrCancel;
        sell.reduce_only = true;
        sell.cancel_order_on_pause = false;
        let scid = sell.client_order_id.clone();
        let mut s = sink_into(&mut log);
        let sink: &mut Sink<'_> = &mut s;
        let r = executor::submit(&mut book, &mut run.venue, sell, now_s(), sink);
        for _ in 0..10 {
            let _ =
                executor::reconcile_order(&mut book, &mut run.venue, &scid, now_s(), now_s(), sink);
            if book.order(&scid).is_some_and(|o| o.is_settled()) {
                break;
            }
            std::thread::sleep(Duration::from_millis(500));
        }
        let o = book.order(&scid).unwrap();
        d.insert("sell_reduce_only".into(), json!({"price": bid, "err": r.err(), "status": status_name(&o.status), "filled": o.confirmed_filled()}));
        d.insert("sell_fee".into(), fee_check(t, Liquidity::Taker, &o.fills));
        let after = run.venue.position(&t.ticker);
        d.insert("position_after_sell".into(), json!(after));
        ok &= matches!(after, Ok(0));
    }
    run.record(
        name,
        if ok { "PASS" } else { "FAIL" },
        json!({"detail": d, "log": log}),
    );
}

/// Crash after send, before the ack is persisted: a fresh book loaded from
/// the persisted SENDING snapshot must find the order by client id.
fn restart_reconcile(run: &mut Run, t: &Target) {
    let name = "restart_reconcile";
    let mut persisted: Option<String> = None;
    let mut book = GameBook::new(&t.event, &t.ticker, &t.ticker);
    let mut spec = run.spec(name, t, BookSide::Bid, t.bid.saturating_sub(4).max(1), 1);
    spec.post_only = true;
    let cid = spec.client_order_id.clone();
    let sent_at = now_s();
    {
        let mut s = |b: &GameBook, ev: ExecEvent| -> Result<(), String> {
            if matches!(ev, ExecEvent::BeforeSend { .. }) {
                persisted = Some(serde_json::to_string(b).map_err(|e| e.to_string())?);
            }
            Ok(())
        };
        let sink: &mut Sink<'_> = &mut s;
        let _ = executor::submit(&mut book, &mut run.venue, spec, sent_at, sink);
    }
    let live_vid = book.order(&cid).and_then(|o| o.venue_order_id.clone());
    let Some(snapshot) = persisted else {
        run.record(name, "FAIL", json!({"reason": "nothing persisted"}));
        return;
    };
    let mut restored: GameBook = match serde_json::from_str(&snapshot) {
        Ok(b) => b,
        Err(e) => {
            run.record(name, "FAIL", json!({"reason": e.to_string()}));
            return;
        }
    };
    let before = restored.order(&cid).map(|o| status_name(&o.status));
    let mut log = Vec::new();
    let started = std::time::Instant::now();
    let mut passes = 0u32;
    let mut errors = Vec::new();
    while started.elapsed() < Duration::from_secs(25) {
        passes += 1;
        errors = {
            let mut s = sink_into(&mut log);
            let sink: &mut Sink<'_> = &mut s;
            executor::reconcile_book(&mut restored, &mut run.venue, now_s(), sink)
        };
        if restored
            .order(&cid)
            .is_some_and(|o| o.venue_order_id.is_some() || o.status.is_terminal())
        {
            break;
        }
        std::thread::sleep(Duration::from_secs(1));
    }
    let recovered_after_ms = started.elapsed().as_millis();
    let o = restored.order(&cid).cloned();
    let recovered = o.as_ref().and_then(|o| o.venue_order_id.clone());
    let ok = recovered.is_some() && recovered == live_vid;
    {
        let mut s = sink_into(&mut log);
        let sink: &mut Sink<'_> = &mut s;
        if recovered.is_some() {
            let _ = executor::cancel(&mut restored, &mut run.venue, &cid, now_s(), sink);
        } else if let Some(v) = &live_vid {
            let _ = run.venue.cancel(v, &t.ticker);
        }
    }
    run.record(
        name,
        if ok { "PASS" } else { "FAIL" },
        json!({
            "restored_status_before": before,
            "reconcile_passes": passes,
            "recovered_after_ms": recovered_after_ms,
            "reconcile_errors": errors,
            "restored_status_after": o.map(|o| status_name(&o.status)),
            "venue_order_id_recovered": ok,
            "final": restored.order(&cid).map(|o| status_name(&o.status)),
            "log": log,
        }),
    );
}

/// The execution lane on demo: the strategy's 78 post-only entry for one
/// contract rests on a market whose ask is above 79, `step` reconciles it,
/// then it is cancelled. Owner decisions stay unresolved in the policy.
fn lane_entry(run: &mut Run, creds_path: &str) {
    let name = "lane_entry_rest_reconcile_cancel";
    let series_list = std::env::var("NBA001_DEMO_SERIES").unwrap_or_else(|_| DEFAULT_SERIES.into());
    let mut pick = None;
    let mut books_read = 0;
    'outer: for series in series_list.split(',').map(str::trim) {
        let Ok(v) = run.venue.get_json(format!(
            "/trade-api/v2/markets?series_ticker={series}&status=open&limit=200"
        )) else {
            continue;
        };
        for m in v
            .get("markets")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
        {
            if books_read >= 30 {
                break 'outer;
            }
            let Some(mv) = parse_market(m) else { continue };
            books_read += 1;
            // A 78 post-only bid rests only if no ask is at or below 78.
            if let Some(b) = book_top(&mut run.venue, &mv.desc.ticker)
                && b.unparsed_levels == 0
                && (b.best_yes_bid.is_some() || b.yes_ask.is_some())
                && b.yes_ask.is_none_or(|a| a >= 80)
                && b.best_yes_bid.is_none_or(|x| x < 77)
            {
                pick = Some((mv, b.best_yes_bid, b.yes_ask));
                break 'outer;
            }
        }
    }
    let Some((mv, book_bid, book_ask)) = pick else {
        run.record(
            name,
            "SKIPPED",
            json!({"reason": "no demo orderbook with ask >= 80 and bid < 77", "books_read": books_read}),
        );
        return;
    };
    let transport =
        credentials_from_secret_file(KalshiEnvironment::Demo, std::path::Path::new(creds_path))
            .and_then(SandboxHttpTransport::demo);
    let Ok(transport) = transport else {
        run.record(name, "FAIL", json!({"reason": "demo transport"}));
        return;
    };
    let mut lane = crate::lane::ExecutionLane::new(
        NbaVenue::demo(transport),
        crate::lane::LanePolicy::unresolved(),
    );
    lane.id_namespace = format!("nba-001-demo-{}", run.run_id);
    let ev = mv.desc.event_ticker.clone();
    let mut log = Vec::new();
    let mut d = serde_json::Map::new();
    {
        let mut s = sink_into(&mut log);
        let sink: &mut Sink<'_> = &mut s;
        let r = lane.enter(&ev, &mv.desc.ticker, &mv.desc.ticker, 1, now_s(), sink);
        d.insert("enter".into(), json!({"err": r.err()}));
        let st = lane.step(&ev, now_s() + 1, sink);
        d.insert(
            "step".into(),
            json!({"plan": st.as_ref().ok(), "err": st.as_ref().err()}),
        );
    }
    let g = &lane.games[&ev];
    let o = g.book.orders[0].clone();
    d.insert("exec".into(), json!(g.exec));
    d.insert("entry".into(), json!({"price": o.spec.price_cents, "post_only": o.spec.post_only, "status": o.status, "venue_order_id_known": o.venue_order_id.is_some()}));
    let rested = o.status == OrderStatus::Resting;
    let cid = o.spec.client_order_id.clone();
    {
        let mut s = sink_into(&mut log);
        let sink: &mut Sink<'_> = &mut s;
        let g = lane.games.get_mut(&ev).unwrap();
        if rested {
            let r = executor::cancel(&mut g.book, &mut lane.venue, &cid, now_s(), sink);
            d.insert(
                "cancel".into(),
                json!({"err": r.err(), "status": g.book.order(&cid).map(|o| &o.status)}),
            );
        }
    }
    let final_ok = lane.games[&ev]
        .book
        .order(&cid)
        .is_some_and(|o| o.status == OrderStatus::Cancelled && o.confirmed_filled() == 0);
    d.insert(
        "market".into(),
        json!({"ticker": mv.desc.ticker, "listing_yes_bid": mv.yes_bid_cents, "listing_yes_ask": mv.yes_ask_cents, "book_yes_bid": book_bid, "book_yes_ask": book_ask}),
    );
    // The book can move between the read and the send; a post-only reject
    // that leaves the lane flat with no order is the correct outcome.
    let post_only_rejected_flat = matches!(
        &o.status,
        OrderStatus::Rejected { code, .. } if code == "invalid_order"
    ) && lane.games[&ev].book.exposure().potential_original_buy == 0
        && lane.games[&ev].book.exposure().original_long == 0;
    run.record(
        name,
        if rested && final_ok {
            "PASS"
        } else if post_only_rejected_flat {
            "OBSERVED_POST_ONLY_REJECTED_FLAT"
        } else {
            "FAIL"
        },
        json!({"detail": d, "log": log}),
    );
}

pub fn exercise() -> Result<(), (i32, String)> {
    let path = std::env::var("MOMENTO_KALSHI_SECRET_FILE").map_err(|_| {
        (
            2,
            "demo-exercise needs MOMENTO_KALSHI_SECRET_FILE (demo secret)".to_string(),
        )
    })?;
    let creds = credentials_from_secret_file(KalshiEnvironment::Demo, std::path::Path::new(&path))
        .map_err(|e| {
            (
                78,
                format!("demo credentials: {}", redact_secrets(&e.to_string())),
            )
        })?;
    let transport =
        SandboxHttpTransport::demo(creds).map_err(|e| (78, format!("demo transport: {e}")))?;
    let mut run = Run {
        venue: NbaVenue::demo(transport),
        run_id: format!("{}", now_s()),
        seq: 0,
        scenarios: Vec::new(),
    };
    let origin = run.venue.transport().origin().to_string();
    let balance = run.venue.balance_cents(None);
    let balance_cents = balance
        .as_ref()
        .ok()
        .and_then(|v| v.get("balance").and_then(Value::as_i64));
    let target = pick_target(&mut run.venue);
    let target_view = target.as_ref().map(|t| {
        json!({
            "series": t.series, "event": t.event, "ticker": t.ticker,
            "yes_bid": t.bid, "yes_ask": t.ask, "ask_depth": t.ask_depth, "book_top": t.book_top,
            "fee_type": t.fee_type_raw, "fee_multiplier": t.fee_multiplier_raw,
        })
    });
    if let Ok(t) = &target {
        rest_amend_cancel(&mut run, t);
        read_after_write(&mut run, t);
        post_only_cross(&mut run, t);
        reduce_only_without_position(&mut run, t);
        restart_reconcile(&mut run, t);
        expiring_gtc(&mut run, t);
        taker_round_trip(&mut run, t, balance_cents.is_some_and(|b| b >= 200));
    }
    lane_entry(&mut run, &path);
    for (name, why) in [
        (
            "create_timeout_reconcile",
            "transport timeout cannot be forced on demo; fixture exec_tests",
        ),
        (
            "late_fill_during_cancel",
            "needs a counterparty at a chosen instant; fixture exec_tests + lane_tests",
        ),
        (
            "partial_hedge_then_emergency",
            "needs controlled partial fills; fixture lane_tests",
        ),
    ] {
        run.record(name, "FIXTURE_ONLY", json!({"reason": why}));
    }
    let pass = run
        .scenarios
        .iter()
        .filter(|s| s["verdict"] == "PASS")
        .count();
    let fail = run
        .scenarios
        .iter()
        .filter(|s| s["verdict"] == "FAIL")
        .count();
    let out = json!({
        "demo_exercise": "nba-001 order adapter against Kalshi demo",
        "origin": origin,
        "environment": format!("{:?}", run.venue.env()),
        "production_orders_compiled": crate::venue::PRODUCTION_ORDERS_COMPILED,
        "balance_cents": balance_cents,
        "target": target_view.as_ref().ok(),
        "target_error": target.as_ref().err(),
        "requests_sent": run.venue.requests_sent,
        "mutations_sent": run.venue.mutations_sent,
        "passed": pass,
        "failed": fail,
        "scenarios": run.scenarios,
    });
    println!("{out}");
    if fail > 0 || target.is_err() {
        return Err((1, format!("demo-exercise: {fail} failed")));
    }
    Ok(())
}
