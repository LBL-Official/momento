//! Reconstruct a MarketPath from a discovery envelope plus optional lake rows.

use std::collections::{HashMap, HashSet};

use chrono::{DateTime, Datelike, Utc};
use chrono_tz::America::Los_Angeles;
use momento_research_data::foundation::{
    ObservabilityKind, StartingPriceClass, StartingPriceEvidence,
};
use momento_research_data::schema::RawMarketEvent;
use momento_research_ingest::types::IdentityMapping;
use serde_json::Value;
use sha2::{Digest, Sha256};

use crate::capability::{MarketCapabilityCard, Presence};
use crate::cents::{dollars_to_cents, fp_to_hundredths, optional_dollars_to_cents};
use crate::completeness::{ObservationFlags, classify};
use crate::error::W4Error;
use crate::reader::{DiscoveryEnvelope, IdentityIndex, attach_identity};
use crate::types::{
    CandleOhlcCents, LifetimeCoverage, MarketObservationKind, MarketPath, MarketPoint,
    ReconstructionAnomaly, assert_event_type_legal,
};
use crate::versions::{
    RECONSTRUCTION_VERSION, SERIES_MLB, SOURCE_KALSHI_CANDLE, SOURCE_KALSHI_HISTORICAL_TRADE,
    SOURCE_KALSHI_TRADE, SOURCE_LAKE_CANDLE, SOURCE_LAKE_TRADE,
};

pub fn market_id_hex(ticker: &str) -> String {
    format!(
        "{:x}",
        Sha256::digest(format!("market\0{ticker}").as_bytes())
    )
}

pub fn reconstruct_path(
    env: &DiscoveryEnvelope,
    identity: &IdentityIndex,
    lake_rows: &[RawMarketEvent],
) -> Result<(MarketPath, Vec<ReconstructionAnomaly>), W4Error> {
    let mut anomalies = Vec::new();
    if env.ticker.trim().is_empty() {
        return Err(W4Error::Reconstruction("empty ticker".into()));
    }
    if !env.ticker.starts_with(SERIES_MLB) {
        return Err(W4Error::Reconstruction(format!(
            "non-MLB ticker {}",
            env.ticker
        )));
    }
    let event_ticker = env
        .event_ticker
        .clone()
        .filter(|s| !s.is_empty())
        .or_else(|| {
            env.payload
                .get("event_ticker")
                .and_then(|v| v.as_str())
                .map(str::to_string)
        })
        .unwrap_or_default();
    let market_id = market_id_hex(&env.ticker);
    let (identity_mapping, game_pk) = attach_identity(env, identity);
    let open_time = str_field(&env.payload, "open_time");
    let close_time = str_field(&env.payload, "close_time");
    let settlement =
        str_field(&env.payload, "settlement_ts").or_else(|| str_field(&env.payload, "settlement"));

    let mut points: Vec<MarketPoint> = Vec::new();
    let mut seen_trades: HashMap<String, i32> = HashMap::new();
    let mut ingest_only_pit_count = 0usize;
    let retrieval = env
        .retrieved_at
        .as_deref()
        .and_then(|s| parse_rfc3339(s).ok());

    append_envelope_trades(
        env,
        &event_ticker,
        &market_id,
        retrieval,
        &mut points,
        &mut seen_trades,
        &mut anomalies,
    )?;
    append_envelope_candles(
        env,
        &event_ticker,
        &market_id,
        retrieval,
        &mut points,
        &mut anomalies,
    )?;

    for row in lake_rows {
        match row.endpoint.as_str() {
            "markets/orderbook" => {
                ingest_only_pit_count += 1;
            }
            "markets/trades" | "matched_historical_trades" => {
                let source = if row.endpoint == "matched_historical_trades" {
                    SOURCE_KALSHI_HISTORICAL_TRADE
                } else {
                    SOURCE_LAKE_TRADE
                };
                append_raw_trade(
                    row,
                    PointCtx {
                        ticker: &env.ticker,
                        event_ticker: &event_ticker,
                        market_id: &market_id,
                        source,
                        retrieval: None,
                    },
                    &mut TradeSink {
                        points: &mut points,
                        seen: &mut seen_trades,
                        anomalies: &mut anomalies,
                    },
                )?;
            }
            "candlesticks" => {
                append_raw_candles(
                    row,
                    &env.ticker,
                    &event_ticker,
                    &market_id,
                    &mut points,
                    &mut anomalies,
                )?;
            }
            other => {
                assert_event_type_legal(other)?;
            }
        }
    }

    let unsorted = !is_sorted(&points);
    if unsorted {
        anomalies.push(ReconstructionAnomaly {
            ticker: env.ticker.clone(),
            code: "UNSORTED_TRADES".into(),
            message: "t_game points were not venue-time ordered; sorted".into(),
        });
        points.sort_by(|a, b| {
            a.exchange_timestamp
                .cmp(&b.exchange_timestamp)
                .then_with(|| a.trade_id.cmp(&b.trade_id))
                .then_with(|| a.kind.as_str().cmp(b.kind.as_str()))
        });
    }

    for p in &points {
        if let (Some(bid), Some(ask)) = (p.yes_bid_cents, p.yes_ask_cents) {
            if ask < bid {
                anomalies.push(ReconstructionAnomaly {
                    ticker: env.ticker.clone(),
                    code: "CROSSED_BOOK".into(),
                    message: format!("ask {ask} < bid {bid} at {}", p.exchange_timestamp),
                });
            }
        }
    }

    let has_metadata = !env.ticker.is_empty();
    let mut flags = ObservationFlags::from_points(&points, has_metadata);
    flags.l2_delta_ungapped = false;
    let completeness = classify(&flags);
    let blocked = matches!(
        completeness,
        crate::types::MarketCompleteness::MarketMetadataOnly
            | crate::types::MarketCompleteness::Unobserved
    ) && identity_mapping == IdentityMapping::Mapped;

    let starting_price = StartingPriceEvidence::unverified_from_metadata(
        env.ticker.clone(),
        event_ticker.clone(),
        market_id.clone(),
        open_time.clone(),
    );
    let lifetime_coverage = classify_lifetime(&open_time, &settlement, &points);
    let anomalies = compact_anomalies(anomalies);
    let trade_capability = if flags.has_trade {
        Presence::Observed
    } else {
        Presence::from_status_label(str_field(&env.payload, "trades_status").as_deref())
    };
    let candle_capability = if flags.has_candle {
        Presence::Observed
    } else if env
        .payload
        .get("candlesticks")
        .and_then(|v| v.get("error"))
        .is_some()
    {
        Presence::Malformed
    } else {
        Presence::from_status_label(str_field(&env.payload, "candles_status").as_deref())
    };
    let settlement_capability = if settlement.is_some() {
        Presence::Observed
    } else {
        Presence::Unavailable
    };
    let capability = MarketCapabilityCard::build(
        completeness,
        identity_mapping,
        game_pk.as_deref(),
        trade_capability,
        candle_capability,
        settlement_capability,
        lifetime_coverage,
    );

    let path = MarketPath {
        ticker: env.ticker.clone(),
        event_ticker,
        market_id,
        identity: identity_mapping,
        game_pk,
        completeness,
        open_time,
        close_time,
        settlement,
        points,
        starting_price_class: StartingPriceClass::StartingPriceUnverified,
        starting_price,
        lifetime_coverage,
        ingest_only_pit_count,
        blocked_on_ingest_observations: blocked,
        capability,
        observed_start: None,
        observed_end: None,
        reconstruction_version: RECONSTRUCTION_VERSION.into(),
    }
    .with_observed_bounds();
    Ok((path, anomalies))
}

fn str_field(payload: &Value, key: &str) -> Option<String> {
    payload
        .get(key)
        .and_then(|v| v.as_str())
        .filter(|s| !s.is_empty())
        .map(str::to_string)
}

fn is_sorted(points: &[MarketPoint]) -> bool {
    points
        .windows(2)
        .all(|w| w[0].exchange_timestamp <= w[1].exchange_timestamp)
}

#[derive(Clone, Copy)]
struct PointCtx<'a> {
    ticker: &'a str,
    event_ticker: &'a str,
    market_id: &'a str,
    source: &'a str,
    retrieval: Option<DateTime<Utc>>,
}

struct TradeSink<'a> {
    points: &'a mut Vec<MarketPoint>,
    seen: &'a mut HashMap<String, i32>,
    anomalies: &'a mut Vec<ReconstructionAnomaly>,
}

fn append_envelope_trades(
    env: &DiscoveryEnvelope,
    event_ticker: &str,
    market_id: &str,
    retrieval: Option<DateTime<Utc>>,
    points: &mut Vec<MarketPoint>,
    seen: &mut HashMap<String, i32>,
    anomalies: &mut Vec<ReconstructionAnomaly>,
) -> Result<(), W4Error> {
    let Some(trades) = env.payload.get("trades").and_then(|v| v.as_array()) else {
        return Ok(());
    };
    let ctx = PointCtx {
        ticker: &env.ticker,
        event_ticker,
        market_id,
        source: SOURCE_KALSHI_TRADE,
        retrieval,
    };
    let mut sink = TradeSink {
        points,
        seen,
        anomalies,
    };
    for t in trades {
        push_trade_value(t, &ctx, &mut sink)?;
    }
    Ok(())
}

fn append_envelope_candles(
    env: &DiscoveryEnvelope,
    event_ticker: &str,
    market_id: &str,
    retrieval: Option<DateTime<Utc>>,
    points: &mut Vec<MarketPoint>,
    anomalies: &mut Vec<ReconstructionAnomaly>,
) -> Result<(), W4Error> {
    let Some(cs) = env.payload.get("candlesticks") else {
        return Ok(());
    };
    if cs.get("unavailable").is_some() {
        return Ok(());
    }
    let bars = if let Some(arr) = cs.as_array() {
        arr
    } else if let Some(arr) = cs.get("candlesticks").and_then(|v| v.as_array()) {
        arr
    } else {
        return Ok(());
    };
    for bar in bars {
        push_candle_value(
            bar,
            &PointCtx {
                ticker: &env.ticker,
                event_ticker,
                market_id,
                source: SOURCE_KALSHI_CANDLE,
                retrieval,
            },
            points,
            anomalies,
        )?;
    }
    Ok(())
}

fn append_raw_trade(
    row: &RawMarketEvent,
    mut ctx: PointCtx<'_>,
    sink: &mut TradeSink<'_>,
) -> Result<(), W4Error> {
    ctx.retrieval = Some(row.received_at);
    push_trade_value(&row.payload, &ctx, sink)
}

fn append_raw_candles(
    row: &RawMarketEvent,
    ticker: &str,
    event_ticker: &str,
    market_id: &str,
    points: &mut Vec<MarketPoint>,
    anomalies: &mut Vec<ReconstructionAnomaly>,
) -> Result<(), W4Error> {
    assert_event_type_legal(&row.endpoint)?;
    let payload = &row.payload;
    let bars = if let Some(arr) = payload.get("candlesticks").and_then(|v| v.as_array()) {
        arr.clone()
    } else if payload.get("end_period_ts").is_some() {
        vec![payload.clone()]
    } else {
        return Ok(());
    };
    for bar in &bars {
        push_candle_value(
            bar,
            &PointCtx {
                ticker,
                event_ticker,
                market_id,
                source: SOURCE_LAKE_CANDLE,
                retrieval: Some(row.received_at),
            },
            points,
            anomalies,
        )?;
    }
    Ok(())
}

fn push_trade_value(
    t: &Value,
    ctx: &PointCtx<'_>,
    sink: &mut TradeSink<'_>,
) -> Result<(), W4Error> {
    let trade_id = t
        .get("trade_id")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let Some(ts_raw) = t.get("created_time").and_then(|v| v.as_str()) else {
        sink.anomalies.push(ReconstructionAnomaly {
            ticker: ctx.ticker.into(),
            code: "MISSING_TRADE_TIME".into(),
            message: "created_time missing; retrieved_at not used".into(),
        });
        return Ok(());
    };
    let Ok(ts) = parse_rfc3339(ts_raw) else {
        sink.anomalies.push(ReconstructionAnomaly {
            ticker: ctx.ticker.into(),
            code: "MISSING_TRADE_TIME".into(),
            message: format!("unparseable created_time {ts_raw}"),
        });
        return Ok(());
    };
    if ts.year() < 2024 || ts.year() > 2027 {
        sink.anomalies.push(ReconstructionAnomaly {
            ticker: ctx.ticker.into(),
            code: "IMPOSSIBLE_TIMESTAMP".into(),
            message: format!("created_time {ts_raw} outside 2024–2027"),
        });
        return Ok(());
    }
    let cents = match t
        .get("yes_price_dollars")
        .and_then(|v| v.as_str())
        .map(dollars_to_cents)
    {
        Some(Ok(c)) => c,
        Some(Err(e)) => {
            sink.anomalies.push(ReconstructionAnomaly {
                ticker: ctx.ticker.into(),
                code: "UNPARSEABLE_PRICE".into(),
                message: e.to_string(),
            });
            return Ok(());
        }
        None => {
            sink.anomalies.push(ReconstructionAnomaly {
                ticker: ctx.ticker.into(),
                code: "UNPARSEABLE_PRICE".into(),
                message: "yes_price_dollars missing".into(),
            });
            return Ok(());
        }
    };
    if !trade_id.is_empty() {
        if let Some(prev) = sink.seen.get(&trade_id) {
            if *prev != cents {
                sink.anomalies.push(ReconstructionAnomaly {
                    ticker: ctx.ticker.into(),
                    code: "CONFLICTING_TRADE".into(),
                    message: format!(
                        "trade_id {trade_id} first {prev} cents then {cents}; kept first"
                    ),
                });
            } else {
                sink.anomalies.push(ReconstructionAnomaly {
                    ticker: ctx.ticker.into(),
                    code: "DUPLICATE_TRADE_ID".into(),
                    message: "1".into(),
                });
            }
            return Ok(());
        }
        sink.seen.insert(trade_id.clone(), cents);
    }
    let qty = t
        .get("count_fp")
        .and_then(|v| v.as_str())
        .and_then(|s| fp_to_hundredths(s).ok());
    sink.points.push(MarketPoint {
        ticker: ctx.ticker.into(),
        event_ticker: ctx.event_ticker.into(),
        market_id: ctx.market_id.into(),
        exchange_timestamp: ts,
        yes_bid_cents: None,
        yes_ask_cents: None,
        last_trade_cents: Some(cents),
        quantity_hundredths: qty,
        trade_id: if trade_id.is_empty() {
            None
        } else {
            Some(trade_id.clone())
        },
        candle_ohlc: None,
        kind: MarketObservationKind::Trade,
        observability: ObservabilityKind::Observed,
        source: Some(ctx.source.into()),
        source_record_id: if trade_id.is_empty() {
            None
        } else {
            Some(trade_id)
        },
        retrieval_timestamp: ctx.retrieval,
    });
    Ok(())
}

fn push_candle_value(
    bar: &Value,
    ctx: &PointCtx<'_>,
    points: &mut Vec<MarketPoint>,
    anomalies: &mut Vec<ReconstructionAnomaly>,
) -> Result<(), W4Error> {
    let Some(end) = bar.get("end_period_ts").and_then(|v| v.as_i64()) else {
        anomalies.push(ReconstructionAnomaly {
            ticker: ctx.ticker.into(),
            code: "MISSING_CANDLE_TIME".into(),
            message: "end_period_ts missing".into(),
        });
        return Ok(());
    };
    let Some(ts) = DateTime::<Utc>::from_timestamp(end, 0) else {
        anomalies.push(ReconstructionAnomaly {
            ticker: ctx.ticker.into(),
            code: "MISSING_CANDLE_TIME".into(),
            message: format!("invalid end_period_ts {end}"),
        });
        return Ok(());
    };
    let bid = dist(bar.get("yes_bid"));
    let ask = dist(bar.get("yes_ask"));
    let price = dist(bar.get("price"));
    let ohlc = CandleOhlcCents {
        yes_bid_open: bid.open,
        yes_bid_high: bid.high,
        yes_bid_low: bid.low,
        yes_bid_close: bid.close,
        yes_ask_open: ask.open,
        yes_ask_high: ask.high,
        yes_ask_low: ask.low,
        yes_ask_close: ask.close,
        yes_price_close: price.close,
    };
    points.push(MarketPoint {
        ticker: ctx.ticker.into(),
        event_ticker: ctx.event_ticker.into(),
        market_id: ctx.market_id.into(),
        exchange_timestamp: ts,
        yes_bid_cents: None,
        yes_ask_cents: None,
        last_trade_cents: None,
        quantity_hundredths: None,
        trade_id: None,
        candle_ohlc: Some(ohlc),
        kind: MarketObservationKind::Candle1m,
        observability: ObservabilityKind::Observed,
        source: Some(ctx.source.into()),
        source_record_id: Some(format!("candle:{end}")),
        retrieval_timestamp: ctx.retrieval,
    });
    Ok(())
}
struct DistCents {
    open: Option<i32>,
    high: Option<i32>,
    low: Option<i32>,
    close: Option<i32>,
}

fn dist(v: Option<&Value>) -> DistCents {
    let parse = |key: &str| -> Option<i32> {
        v.and_then(|obj| obj.get(key))
            .and_then(|x| x.as_str())
            .and_then(|s| optional_dollars_to_cents(Some(s)).ok().flatten())
    };
    DistCents {
        open: parse("open_dollars"),
        high: parse("high_dollars"),
        low: parse("low_dollars"),
        close: parse("close_dollars"),
    }
}

fn compact_anomalies(anoms: Vec<ReconstructionAnomaly>) -> Vec<ReconstructionAnomaly> {
    use std::collections::BTreeMap;
    let mut dup: BTreeMap<String, usize> = BTreeMap::new();
    let mut out = Vec::new();
    for a in anoms {
        if a.code == "DUPLICATE_TRADE_ID" {
            *dup.entry(a.ticker).or_insert(0) += 1;
        } else {
            out.push(a);
        }
    }
    for (ticker, n) in dup {
        out.push(ReconstructionAnomaly {
            ticker,
            code: "DUPLICATE_TRADE_ID".into(),
            message: format!("{n} duplicate trade_ids dropped (kept first)"),
        });
    }
    out
}

fn parse_rfc3339(raw: &str) -> Result<DateTime<Utc>, W4Error> {
    DateTime::parse_from_rfc3339(raw)
        .map(|d| d.with_timezone(&Utc))
        .map_err(|e| W4Error::Reconstruction(format!("rfc3339: {e}")))
}

fn classify_lifetime(
    open_time: &Option<String>,
    settlement: &Option<String>,
    points: &[MarketPoint],
) -> LifetimeCoverage {
    if points.is_empty() {
        return LifetimeCoverage::Unknown;
    }
    let Some(settle_raw) = settlement.as_ref() else {
        return LifetimeCoverage::Unknown;
    };
    let Ok(settle) = parse_rfc3339(settle_raw) else {
        return LifetimeCoverage::Unknown;
    };
    let settle_day = settle.with_timezone(&Los_Angeles).date_naive();
    let days: HashSet<_> = points
        .iter()
        .map(|p| {
            p.exchange_timestamp
                .with_timezone(&Los_Angeles)
                .date_naive()
        })
        .collect();
    if days.len() == 1 && days.contains(&settle_day) {
        return LifetimeCoverage::SettlementDayOnly;
    }
    if let Some(open_raw) = open_time {
        if let Ok(open) = parse_rfc3339(open_raw) {
            let open_day = open.with_timezone(&Los_Angeles).date_naive();
            if days.contains(&open_day) && days.contains(&settle_day) {
                return LifetimeCoverage::OpenToSettlement;
            }
        }
    }
    LifetimeCoverage::Unknown
}
