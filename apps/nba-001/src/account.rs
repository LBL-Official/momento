//! Signed GET-only account observe: balance per shard, positions, resting
//! orders. Unread is `None`, never $0. The credential is never logged.

use std::collections::BTreeMap;
use std::path::Path;

use momento_kalshi::{
    BALANCE_PATH, KalshiEnvironment, KalshiHttpRequest, KalshiTransport, ORDERS_PATH,
    POSITIONS_PATH, ProductionObserveTransport, TransportOutcome, credentials_from_secret_file,
    redact_secrets, signed_count_fp_to_i64,
};
use serde::Serialize;
use serde_json::Value;

/// Shards this worker reads explicitly.
pub const SHARDS: [i64; 2] = [0, 3];
/// Client order ids this bot would use. None exist while submission is unlinked.
pub const CLIENT_ID_PREFIX: &str = "nba001-";

#[derive(Clone, Debug, Default, Serialize)]
pub struct AccountView {
    pub read_at: Option<i64>,
    pub ok: bool,
    pub error: Option<String>,
    pub balance_total_cents: Option<i64>,
    pub portfolio_value_cents: Option<i64>,
    pub balance_breakdown_raw: Option<Value>,
    /// Scoped `GET /portfolio/balance?exchange_index=N` (cents). Authority.
    pub shard_cash_cents: BTreeMap<i64, Option<i64>>,
    pub positions_by_series: BTreeMap<String, u32>,
    pub resting_orders_by_series: BTreeMap<String, u32>,
    pub resting_orders_total: u32,
    pub bot_client_orders_found: u32,
    pub non_get_sent: bool,
    pub gets_sent: usize,
}

fn series_of(ticker: &str) -> String {
    ticker.split('-').next().unwrap_or(ticker).to_string()
}

pub struct Account {
    transport: Option<ProductionObserveTransport>,
    pub load_error: Option<String>,
}

impl Account {
    pub fn from_secret_file(path: Option<&Path>) -> Self {
        let Some(path) = path else {
            return Self {
                transport: None,
                load_error: Some("MOMENTO_KALSHI_SECRET_FILE unset".into()),
            };
        };
        match credentials_from_secret_file(KalshiEnvironment::Production, path)
            .and_then(ProductionObserveTransport::production)
        {
            Ok(t) => Self {
                transport: Some(t),
                load_error: None,
            },
            Err(e) => Self {
                transport: None,
                load_error: Some(redact_secrets(&e.to_string())),
            },
        }
    }

    fn get(t: &mut ProductionObserveTransport, path: &str) -> Result<Value, String> {
        match t.execute(KalshiHttpRequest {
            method: "GET".into(),
            path: path.into(),
            body: None,
        }) {
            TransportOutcome::Http { status: 200, body } => {
                serde_json::from_str(&body).map_err(|e| format!("json: {e}"))
            }
            TransportOutcome::Http { status, body } => Err(format!(
                "HTTP {status} {}: {}",
                path.split('?').next().unwrap_or(path),
                redact_secrets(&body.chars().take(160).collect::<String>())
            )),
            TransportOutcome::Timeout => Err(format!("timeout {path}")),
        }
    }

    fn paged(
        t: &mut ProductionObserveTransport,
        base: &str,
        key: &str,
    ) -> Result<Vec<Value>, String> {
        let mut out = Vec::new();
        let mut cursor: Option<String> = None;
        for _ in 0..20 {
            let path = match &cursor {
                Some(c) => format!("{base}&cursor={c}"),
                None => base.to_string(),
            };
            let v = Self::get(t, &path)?;
            if let Some(arr) = v.get(key).and_then(|a| a.as_array()) {
                out.extend(arr.iter().cloned());
            }
            match v
                .get("cursor")
                .and_then(|c| c.as_str())
                .filter(|c| !c.is_empty())
            {
                Some(next) => cursor = Some(next.to_string()),
                None => return Ok(out),
            }
        }
        Err(format!("{base}: pagination exceeded 20 pages"))
    }

    pub fn observe(&mut self, now: i64) -> AccountView {
        let mut view = AccountView {
            read_at: Some(now),
            ..AccountView::default()
        };
        for shard in SHARDS {
            view.shard_cash_cents.insert(shard, None);
        }
        let Some(t) = self.transport.as_mut() else {
            view.error = self.load_error.clone();
            return view;
        };
        let mut errors = Vec::new();
        match Self::get(t, BALANCE_PATH) {
            Ok(v) => {
                view.balance_total_cents = v.get("balance").and_then(|x| x.as_i64());
                view.portfolio_value_cents = v.get("portfolio_value").and_then(|x| x.as_i64());
                view.balance_breakdown_raw = v.get("balance_breakdown").cloned();
            }
            Err(e) => errors.push(e),
        }
        for shard in SHARDS {
            match Self::get(t, &format!("{BALANCE_PATH}?exchange_index={shard}")) {
                Ok(v) => {
                    view.shard_cash_cents
                        .insert(shard, v.get("balance").and_then(|x| x.as_i64()));
                }
                Err(e) => errors.push(e),
            }
        }
        match Self::paged(
            t,
            &format!("{POSITIONS_PATH}?limit=200"),
            "market_positions",
        ) {
            Ok(rows) => {
                for row in rows {
                    let held = row
                        .get("position_fp")
                        .and_then(|x| x.as_str())
                        .and_then(|s| signed_count_fp_to_i64(s).ok())
                        .or_else(|| row.get("position").and_then(|x| x.as_i64()))
                        .is_some_and(|p| p != 0);
                    if held && let Some(tk) = row.get("ticker").and_then(|x| x.as_str()) {
                        *view.positions_by_series.entry(series_of(tk)).or_default() += 1;
                    }
                }
            }
            Err(e) => errors.push(e),
        }
        match Self::paged(
            t,
            &format!("{ORDERS_PATH}?status=resting&limit=200"),
            "orders",
        ) {
            Ok(rows) => {
                for row in rows {
                    view.resting_orders_total += 1;
                    if let Some(tk) = row.get("ticker").and_then(|x| x.as_str()) {
                        *view
                            .resting_orders_by_series
                            .entry(series_of(tk))
                            .or_default() += 1;
                    }
                    if row
                        .get("client_order_id")
                        .and_then(|x| x.as_str())
                        .is_some_and(|c| c.starts_with(CLIENT_ID_PREFIX))
                    {
                        view.bot_client_orders_found += 1;
                    }
                }
            }
            Err(e) => errors.push(e),
        }
        view.non_get_sent = t.non_get_was_sent();
        view.gets_sent = t.sent_count();
        view.ok = errors.is_empty();
        view.error = if errors.is_empty() {
            None
        } else {
            Some(errors.join("; "))
        };
        view
    }

    /// One-shot GET-only evidence for fees, routing, and subaccount isolation.
    /// Order ids are hashed; no user id, key id, or secret is emitted.
    pub fn evidence(&mut self, now: i64, nba_series: &str) -> Value {
        let Some(t) = self.transport.as_mut() else {
            return serde_json::json!({"ok": false, "error": self.load_error});
        };
        let mut out = serde_json::Map::new();
        out.insert("read_at".into(), now.into());
        let mut record = |key: &str, r: Result<Value, String>| {
            out.insert(
                key.into(),
                r.unwrap_or_else(|e| serde_json::json!({"UNAVAILABLE": e})),
            );
        };
        record("api_limits", Self::get(t, "/trade-api/v2/account/limits"));
        record(
            "subaccount_balances",
            Self::get(t, "/trade-api/v2/portfolio/subaccounts/balances"),
        );
        record(
            "subaccount_netting",
            Self::get(t, "/trade-api/v2/portfolio/subaccounts/netting"),
        );
        record(
            "target_balance_allocation",
            Self::get(t, "/trade-api/v2/portfolio/target_balance_allocation"),
        );
        let mut shard_cash = serde_json::Map::new();
        for shard in SHARDS {
            let v = Self::get(t, &format!("{BALANCE_PATH}?exchange_index={shard}"))
                .map(|v| v.get("balance").cloned().unwrap_or(Value::Null));
            shard_cash.insert(
                shard.to_string(),
                v.unwrap_or_else(|e| serde_json::json!({"UNAVAILABLE": e})),
            );
        }
        record("shard_cash_cents", Ok(Value::Object(shard_cash)));

        record("routing", routing_evidence(t, nba_series));

        let fills = Self::paged(t, "/trade-api/v2/portfolio/fills?limit=200", "fills");
        let mut series_fee: BTreeMap<String, Result<(String, Value), String>> = BTreeMap::new();
        let fee_evidence = fills.map(|rows| {
            for row in &rows {
                if let Some(tk) = row.get("ticker").and_then(|x| x.as_str()) {
                    let s = series_of(tk);
                    if let std::collections::btree_map::Entry::Vacant(slot) = series_fee.entry(s) {
                        let r = Self::get(t, &format!("/trade-api/v2/series/{}", slot.key())).map(
                            |v| {
                                let sv = v.get("series").cloned().unwrap_or(v);
                                (
                                    sv.get("fee_type")
                                        .and_then(|x| x.as_str())
                                        .unwrap_or("")
                                        .to_string(),
                                    sv.get("fee_multiplier").cloned().unwrap_or(Value::Null),
                                )
                            },
                        );
                        slot.insert(r);
                    }
                }
            }
            let mut schedules: BTreeMap<String, Result<Schedule, String>> = BTreeMap::new();
            let mut changes = Vec::new();
            for s in series_fee
                .keys()
                .cloned()
                .chain(std::iter::once(nba_series.to_string()))
                .collect::<std::collections::BTreeSet<_>>()
            {
                let r = Self::get(
                    t,
                    &format!("/trade-api/v2/series/fee_changes?series_ticker={s}&show_historical=true"),
                );
                schedules.insert(s.clone(), r.as_ref().map(schedule_from).map_err(Clone::clone));
                changes.push(serde_json::json!({"series": s, "schedule": r.as_ref().map(schedule_from).ok()}));
            }
            (fee_comparison(&rows, &series_fee, &schedules), changes)
        });
        match fee_evidence {
            Ok((cmp, changes)) => {
                out.insert("fees".into(), cmp);
                out.insert("fee_changes".into(), Value::Array(changes));
            }
            Err(e) => {
                out.insert("fees".into(), serde_json::json!({"UNAVAILABLE": e}));
            }
        }
        out.insert("non_get_sent".into(), t.non_get_was_sent().into());
        out.insert("gets_sent".into(), t.sent_count().into());
        Value::Object(out)
    }
}

/// Series `exchange_index` versus each open event/market `exchange_index`.
fn routing_evidence(t: &mut ProductionObserveTransport, series: &str) -> Result<Value, String> {
    let sv = Account::get(t, &format!("/trade-api/v2/series/{series}"))?;
    let series_index = sv
        .get("series")
        .and_then(|s| s.get("exchange_index"))
        .cloned()
        .unwrap_or(Value::Null);
    let events = Account::get(
        t,
        &format!(
            "/trade-api/v2/events?series_ticker={series}&status=open&with_nested_markets=true&limit=200"
        ),
    )?;
    let mut rows = Vec::new();
    for ev in events
        .get("events")
        .and_then(|e| e.as_array())
        .into_iter()
        .flatten()
    {
        let markets: Vec<Value> = ev
            .get("markets")
            .and_then(|m| m.as_array())
            .into_iter()
            .flatten()
            .map(|m| {
                serde_json::json!({
                    "ticker": m.get("ticker"),
                    "exchange_index": m.get("exchange_index"),
                })
            })
            .collect();
        rows.push(serde_json::json!({
            "event_ticker": ev.get("event_ticker"),
            "event_exchange_index": ev.get("exchange_index"),
            "markets": markets,
        }));
    }
    Ok(serde_json::json!({
        "series": series,
        "series_exchange_index": series_index,
        "open_events": rows,
    }))
}

fn short_hash(raw: &str) -> String {
    use sha2::{Digest, Sha256};
    let d = Sha256::digest(raw.as_bytes());
    d.iter().take(6).map(|b| format!("{b:02x}")).collect()
}

fn price_cents_exact(raw: &str) -> Option<i64> {
    let micros = crate::venue::dollars_to_micros(raw)?;
    (micros % 10_000 == 0).then_some(micros / 10_000)
}

/// Per-order model versus observed `fee_cost`. Trade fee per fill rounds up
/// to $0.000001; the order total rounds up to $0.0001.
/// Fee schedule entries for one series: (scheduled_ts RFC 3339 UTC, fee_type,
/// fee_multiplier), sorted by time.
type Schedule = Vec<(String, String, Value)>;

fn schedule_from(changes: &Value) -> Schedule {
    let mut v: Schedule = changes
        .get("series_fee_change_arr")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|c| {
            Some((
                c.get("scheduled_ts")?.as_str()?.to_string(),
                c.get("fee_type")?.as_str()?.to_string(),
                c.get("fee_multiplier")?.clone(),
            ))
        })
        .collect();
    v.sort_by(|a, b| a.0.cmp(&b.0));
    v
}

/// micros for one fill: coef × M × C × P × (1 − P) × 1e6 rounded up to a
/// micro-dollar, coef 0.07 taker, 0.0175 maker (maker-fee types only).
/// `hundredths` is the fill count in hundredths of a contract.
fn fill_fee_micros(
    ft: &str,
    mult: &Value,
    hundredths: i64,
    p: i64,
    taker: bool,
) -> Result<i64, String> {
    let m = momento_strategy_nba::multiplier_milli(mult).ok_or("fee_multiplier unread")?;
    let raw = 7 * m * hundredths * p * (100 - p);
    match (ft, taker) {
        ("quadratic" | "quadratic_with_maker_fees", true) => Ok((raw + 99_999) / 100_000),
        ("quadratic_with_maker_fees", false) => Ok((raw + 399_999) / 400_000),
        ("quadratic", false) => Ok(0),
        _ => Err(format!("fee_type {ft} not modeled")),
    }
}

/// Order-level comparison of observed `fee_cost` with the documented rule,
/// under the schedule in effect at each fill (from fee-change history) and,
/// for reference, under today's series values.
fn fee_comparison(
    rows: &[Value],
    series_fee: &BTreeMap<String, Result<(String, Value), String>>,
    schedules: &BTreeMap<String, Result<Schedule, String>>,
) -> Value {
    #[derive(Default)]
    struct Agg {
        ticker: String,
        fills: u32,
        contracts: i64,
        taker: Option<bool>,
        mixed_liquidity: bool,
        first_fill: Option<String>,
        observed: i64,
        at_fill: Option<i64>,
        now: Option<i64>,
        schedule_ts: Option<String>,
        unmodeled_at_fill: Option<String>,
        unmodeled_now: Option<String>,
        observed_unreadable: bool,
        m1: Option<i64>,
        m1_unmodeled: Option<String>,
        fractional_fills: u32,
    }
    let mut fills_total = 0u32;
    let mut fills_fractional = 0u32;
    let mut fills_count_unreadable = 0u32;
    let mut orders: BTreeMap<String, Agg> = BTreeMap::new();
    for row in rows {
        let oid = row.get("order_id").and_then(|x| x.as_str()).unwrap_or("");
        let tk = row.get("ticker").and_then(|x| x.as_str()).unwrap_or("");
        let ts = row
            .get("created_time")
            .and_then(|x| x.as_str())
            .map(str::to_string);
        let a = orders.entry(short_hash(oid)).or_default();
        a.ticker = tk.to_string();
        a.fills += 1;
        if let Some(t) = &ts
            && a.first_fill.as_ref().is_none_or(|f| t < f)
        {
            a.first_fill = Some(t.clone());
        }
        fills_total += 1;
        let hundredths = row
            .get("count_fp")
            .and_then(|x| x.as_str())
            .and_then(|s| momento_kalshi::count_fp_to_hundredths(s.trim_start_matches('+')).ok());
        match hundredths {
            Some(h) if h % 100 != 0 => {
                fills_fractional += 1;
                a.fractional_fills += 1;
            }
            Some(_) => {}
            None => fills_count_unreadable += 1,
        }
        a.contracts += hundredths.unwrap_or(0);
        let taker = row.get("is_taker").and_then(|x| x.as_bool());
        if a.taker.is_some() && a.taker != taker {
            a.mixed_liquidity = true;
        }
        a.taker = taker;
        match row
            .get("fee_cost")
            .and_then(|x| x.as_str())
            .and_then(crate::venue::dollars_to_micros)
        {
            Some(m) => a.observed += m,
            None => a.observed_unreadable = true,
        }
        let price = row
            .get("yes_price_dollars")
            .and_then(|x| x.as_str())
            .and_then(price_cents_exact);
        let series = series_of(tk);
        let now_fee: Result<(String, Value), String> = match series_fee.get(&series) {
            Some(Ok(v)) => Ok(v.clone()),
            _ => Err("series fee unread".into()),
        };
        let at_fill: Result<(String, Value, Option<String>), String> =
            match (schedules.get(&series), &ts) {
                (Some(Ok(sch)), Some(t)) if !sch.is_empty() => sch
                    .iter()
                    .rev()
                    .find(|(at, _, _)| at.as_str() <= t.as_str())
                    .map(|(at, ft, m)| (ft.clone(), m.clone(), Some(at.clone())))
                    .ok_or_else(|| "fill predates fee-change history".to_string()),
                (Some(Ok(_)), Some(_)) => now_fee.clone().map(|(ft, m)| (ft, m, None)),
                (_, None) => Err("fill time unread".into()),
                _ => Err("fee history unread".into()),
            };
        let model = |f: Result<(String, Value), String>| -> Result<i64, String> {
            let (ft, m) = f?;
            let p = price.ok_or("sub-cent or unreadable price")?;
            let tk = taker.ok_or("is_taker unread")?;
            let h = hundredths.ok_or("count unreadable")?;
            fill_fee_micros(&ft, &m, h, p, tk)
        };
        let m1 = now_fee
            .as_ref()
            .map_err(Clone::clone)
            .and_then(|(ft, _)| model(Ok((ft.clone(), Value::from(1)))));
        match m1 {
            Ok(v) => *a.m1.get_or_insert(0) += v,
            Err(e) => a.m1_unmodeled = Some(e),
        }
        match model(now_fee) {
            Ok(m) => *a.now.get_or_insert(0) += m,
            Err(e) => a.unmodeled_now = Some(e),
        }
        match at_fill {
            Ok((ft, m, at)) => {
                if at.is_some() {
                    a.schedule_ts = at;
                }
                match model(Ok((ft, m))) {
                    Ok(v) => *a.at_fill.get_or_insert(0) += v,
                    Err(e) => a.unmodeled_at_fill = Some(e),
                }
            }
            Err(e) => a.unmodeled_at_fill = Some(e),
        }
    }
    let order_round = |m: i64| (m + 99) / 100 * 100;
    let verdict = |model: Option<i64>, why: &Option<String>, obs: i64, unreadable: bool| match (
        model, why, unreadable,
    ) {
        (_, _, true) | (None, _, _) | (_, Some(_), _) => "UNMODELED",
        (Some(m), None, false) if order_round(m) == obs => "MATCH",
        _ => "MISMATCH",
    };
    let mut groups: BTreeMap<String, (u32, u32, Vec<Value>)> = BTreeMap::new();
    let mut totals: BTreeMap<&'static str, u32> = BTreeMap::new();
    let mut first_by_series: BTreeMap<String, (String, String)> = BTreeMap::new();
    let mut fractional: BTreeMap<String, BTreeMap<&'static str, u32>> = BTreeMap::new();
    for (h, a) in &orders {
        let series = series_of(&a.ticker);
        if a.fractional_fills > 0 {
            let shape = if a.contracts % 100 == 0 {
                "orders_with_fractional_fills_whole_total"
            } else {
                "orders_with_fractional_total"
            };
            *fractional
                .entry(series.clone())
                .or_default()
                .entry(shape)
                .or_default() += 1;
        }
        let v_fill = verdict(
            a.at_fill,
            &a.unmodeled_at_fill,
            a.observed,
            a.observed_unreadable,
        );
        let v_now = verdict(a.now, &a.unmodeled_now, a.observed, a.observed_unreadable);
        *totals.entry(v_fill).or_default() += 1;
        if let Some(f) = &a.first_fill {
            let e = first_by_series
                .entry(series.clone())
                .or_insert_with(|| (f.clone(), f.clone()));
            if *f < e.0 {
                e.0 = f.clone();
            }
            if *f > e.1 {
                e.1 = f.clone();
            }
        }
        let liq = match (a.mixed_liquidity, a.taker) {
            (true, _) => "MIXED",
            (false, Some(true)) => "TAKER",
            (false, Some(false)) => "MAKER",
            (false, None) => "UNREAD",
        };
        let v_m1 = verdict(a.m1, &a.m1_unmodeled, a.observed, a.observed_unreadable);
        let g = groups
            .entry(format!("{series}|{liq}|{v_fill}"))
            .or_insert_with(|| (0, 0, Vec::new()));
        g.0 += 1;
        if v_m1 == "MATCH" {
            g.1 += 1;
        }
        if g.2.len() < 3 {
            g.2.push(serde_json::json!({
                "order": h,
                "first_fill": a.first_fill,
                "fills": a.fills,
                "contracts_hundredths": a.contracts,
                "observed_micros": a.observed,
                "model_multiplier_1_order_micros": a.m1.map(order_round),
                "model_at_fill_order_micros": a.at_fill.map(order_round),
                "schedule_ts": a.schedule_ts,
                "unmodeled_at_fill": a.unmodeled_at_fill,
                "model_now_order_micros": a.now.map(order_round),
                "verdict_now": v_now,
            }));
        }
    }
    let series: BTreeMap<&String, Value> = series_fee
        .iter()
        .map(|(k, v)| {
            (
                k,
                match v {
                    Ok((ft, m)) => serde_json::json!({"fee_type": ft, "fee_multiplier": m}),
                    Err(e) => serde_json::json!({"UNAVAILABLE": e}),
                },
            )
        })
        .collect();
    serde_json::json!({
        "orders": orders.len(),
        "verdict_at_fill": totals,
        "series_fee_now": series,
        "fill_time_range_by_series": first_by_series,
        "fills": {"total": fills_total, "fractional": fills_fractional, "count_unreadable": fills_count_unreadable, "fractional_by_series": fractional},
        "groups": groups.into_iter().map(|(k, (n, m1, ex))| serde_json::json!({"group": k, "orders": n, "orders_matching_if_multiplier_1": m1, "examples": ex})).collect::<Vec<_>>(),
        "rule": "per fill ceil to $0.000001; per order ceil to $0.0001; schedule = latest fee change at or before the fill",
    })
}

#[cfg(test)]
mod fee_tests {
    use super::*;
    use serde_json::json;

    fn fill(order: &str, ts: &str, fee: &str) -> Value {
        json!({"order_id": order, "ticker": "KXMLBGAME-26SEP01AAABBB-AAA", "created_time": ts,
               "count_fp": "7.00", "is_taker": false, "yes_price_dollars": "0.8300", "fee_cost": fee})
    }

    // Host evidence 2026-09-27: 7 maker contracts at 83 charged $0.0173, which
    // is multiplier 1 (17,288 micros rounded up). Today's multiplier is 0.5.
    #[test]
    fn maker_fee_is_modelled_under_the_schedule_at_fill_time() {
        let rows = vec![
            fill("o1", "2026-08-01T12:00:00Z", "0.0173"),
            fill("o2", "2026-09-01T12:00:00Z", "0.0087"),
        ];
        let mut now = BTreeMap::new();
        now.insert(
            "KXMLBGAME".to_string(),
            Ok(("quadratic_with_maker_fees".to_string(), json!(0.5))),
        );
        let sched = schedule_from(&json!({"series_fee_change_arr": [
            {"scheduled_ts": "2026-08-07T04:59:45.131Z", "fee_type": "quadratic_with_maker_fees", "fee_multiplier": 0.5},
            {"scheduled_ts": "2025-10-04T07:00:00Z", "fee_type": "quadratic_with_maker_fees", "fee_multiplier": 1}
        ]}));
        let mut schedules = BTreeMap::new();
        schedules.insert("KXMLBGAME".to_string(), Ok(sched));
        let v = fee_comparison(&rows, &now, &schedules);
        assert_eq!(v["verdict_at_fill"]["MATCH"], 2, "{v}");
        let groups = v["groups"].as_array().unwrap();
        let ex: Vec<&Value> = groups
            .iter()
            .flat_map(|g| g["examples"].as_array().unwrap())
            .collect();
        let before = ex
            .iter()
            .find(|e| e["first_fill"] == "2026-08-01T12:00:00Z")
            .unwrap();
        assert_eq!(before["model_at_fill_order_micros"], 17_300);
        assert_eq!(before["verdict_now"], "MISMATCH");
    }

    fn wnba(count: &str, fee: &str) -> Value {
        json!({"order_id": "w1", "ticker": "KXWNBAGAME-26SEP01AAABBB-AAA", "created_time": "2026-09-01T00:00:00Z",
               "count_fp": count, "is_taker": false, "yes_price_dollars": "0.8300", "fee_cost": fee})
    }

    type SeriesFees = BTreeMap<String, Result<(String, Value), String>>;
    type Schedules = BTreeMap<String, Result<Schedule, String>>;

    fn m1_schedules() -> (SeriesFees, Schedules) {
        let mut now = BTreeMap::new();
        now.insert(
            "KXWNBAGAME".to_string(),
            Ok(("quadratic_with_maker_fees".to_string(), json!(1))),
        );
        let mut sch = BTreeMap::new();
        sch.insert("KXWNBAGAME".to_string(), Ok(Vec::new()));
        (now, sch)
    }

    // 2.5 maker contracts at 83, M = 1: 0.0175 × 2.5 × 0.1411 = $0.00617 →
    // 6,173 micros per fill → $0.0062 per order.
    #[test]
    fn fractional_fill_is_modelled_in_hundredths() {
        let (now, sch) = m1_schedules();
        let v = fee_comparison(&[wnba("2.50", "0.0062")], &now, &sch);
        assert_eq!(v["verdict_at_fill"]["MATCH"], 1, "{v}");
        assert_eq!(v["fills"]["fractional"], 1);
    }

    #[test]
    fn unreadable_count_is_unmodeled_not_zero() {
        let (now, sch) = m1_schedules();
        let v = fee_comparison(&[wnba("x", "0.1027")], &now, &sch);
        assert_eq!(v["verdict_at_fill"]["UNMODELED"], 1, "{v}");
        assert_eq!(v["fills"]["count_unreadable"], 1);
    }

    #[test]
    fn fill_before_any_known_schedule_is_unmodeled_not_guessed() {
        let rows = vec![fill("o1", "2025-01-01T00:00:00Z", "0.0173")];
        let mut now = BTreeMap::new();
        now.insert(
            "KXMLBGAME".to_string(),
            Ok(("quadratic_with_maker_fees".to_string(), json!(0.5))),
        );
        let mut schedules = BTreeMap::new();
        schedules.insert(
            "KXMLBGAME".to_string(),
            Ok(vec![(
                "2025-10-04T07:00:00Z".to_string(),
                "quadratic_with_maker_fees".to_string(),
                json!(1),
            )]),
        );
        let v = fee_comparison(&rows, &now, &schedules);
        assert_eq!(v["verdict_at_fill"]["UNMODELED"], 1, "{v}");
    }
}
