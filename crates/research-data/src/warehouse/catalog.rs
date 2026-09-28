//! Build event/market/game rows from raw Kalshi JSON.

use std::collections::{BTreeMap, BTreeSet};

use chrono::Utc;
use momento_kalshi::{game_id_for_event_ticker, market_id_for_ticker};
use serde_json::Value;

use super::config::WarehouseConfig;
use super::identity::{
    TENNIS_COMPETITION_UNAVAILABLE, TennisCompetition, VenueSides, classify_phase_for_sport,
    classify_tennis_phase_for_event, hex_u128, market_no_team, market_tennis_competitor,
    market_yes_team, parse_event_date_token, parse_venue_sides, season_for_date_for_sport,
    tennis_competition_resolved, tennis_player_sides, ticker_yes_code,
};
use super::types::{
    NbaEventRow, NbaGameRow, NbaMarketRow, count_fp_to_hundredths, dollars_to_e4, json_bool,
    json_str,
};

#[derive(Clone, Debug)]
pub struct DiscoveredUniverse {
    pub cutoff: Value,
    pub events: Vec<Value>,
    pub markets: Vec<Value>,
    pub event_pages: u32,
    pub market_pages: u32,
}

pub fn event_row(
    event: &Value,
    now: chrono::DateTime<Utc>,
    config: &WarehouseConfig,
) -> Option<NbaEventRow> {
    let event_ticker = json_str(event, "event_ticker")?;
    let date = parse_event_date_token(&event_ticker);
    let title = json_str(event, "title");
    let subtitle = json_str(event, "sub_title");
    let sport = config.research_sport();
    let (phase, venue) = if sport.is_tennis() {
        // Tennis phase lives in `product_metadata.competition`, not the title,
        // and a tennis match has no home/away. The subtitle "A vs B (Mon D)"
        // carries display names only; the two side codes are filled in from the
        // event's two market tickers by `assign_tennis_sides`.
        (
            classify_tennis_phase_for_event(event),
            VenueSides {
                away_code: None,
                home_code: None,
                relation: "PLAYER_SIDES".into(),
            },
        )
    } else {
        (
            classify_phase_for_sport(sport, title.as_deref(), subtitle.as_deref(), date),
            parse_venue_sides(subtitle.as_deref(), title.as_deref()),
        )
    };
    let season = date
        .map(|d| season_for_date_for_sport(sport, d))
        .unwrap_or_else(|| "UNKNOWN".into());
    Some(NbaEventRow {
        event_id: event_ticker.clone(),
        event_ticker,
        series_ticker: json_str(event, "series_ticker").unwrap_or_else(|| config.series.clone()),
        event_title: title,
        event_subtitle: subtitle,
        event_category: json_str(event, "category"),
        mutually_exclusive: json_bool(event, "mutually_exclusive"),
        last_updated_ts: json_str(event, "last_updated_ts"),
        sport: config.sport.clone(),
        league: config.league().into(),
        season,
        season_phase: phase.phase.as_str().into(),
        phase_method: phase.method,
        home_team_code: venue.home_code,
        away_team_code: venue.away_code,
        game_date: date.map(|d| d.to_string()),
        source: "kalshi_rest".into(),
        ingested_at: now,
        schema_version: config.schema_version().into(),
    })
}

pub fn market_row(
    market: &Value,
    event: Option<&NbaEventRow>,
    now: chrono::DateTime<Utc>,
    config: &WarehouseConfig,
) -> Option<NbaMarketRow> {
    let ticker = json_str(market, "ticker")?;
    let event_ticker = json_str(market, "event_ticker").unwrap_or_default();
    let team = market_yes_team(market);
    let opponent = market_no_team(market);
    Some(NbaMarketRow {
        market_id: hex_u128(market_id_for_ticker(&ticker).raw()),
        ticker,
        event_id: event_ticker.clone(),
        game_id: hex_u128(game_id_for_event_ticker(&event_ticker).raw()),
        series_ticker: json_str(market, "series_ticker")
            .or_else(|| event.map(|e| e.series_ticker.clone()))
            .unwrap_or_else(|| config.series.clone()),
        market_title: json_str(market, "title"),
        yes_subtitle: team.clone(),
        no_subtitle: opponent.clone(),
        team,
        opponent,
        market_status: json_str(market, "status"),
        result: json_str(market, "result"),
        settlement_value_e4: json_str(market, "settlement_value_dollars")
            .as_deref()
            .and_then(dollars_to_e4),
        volume_hundredths: json_str(market, "volume_fp")
            .as_deref()
            .and_then(count_fp_to_hundredths),
        open_interest_hundredths: json_str(market, "open_interest_fp")
            .as_deref()
            .and_then(count_fp_to_hundredths),
        last_price_e4: json_str(market, "last_price_dollars")
            .as_deref()
            .and_then(dollars_to_e4),
        yes_bid_e4: json_str(market, "yes_bid_dollars")
            .as_deref()
            .and_then(dollars_to_e4),
        yes_ask_e4: json_str(market, "yes_ask_dollars")
            .as_deref()
            .and_then(dollars_to_e4),
        open_time: json_str(market, "open_time"),
        close_time: json_str(market, "close_time"),
        expiration_time: json_str(market, "expiration_time"),
        settlement_time: json_str(market, "settlement_ts"),
        created_time: json_str(market, "created_time"),
        updated_time: json_str(market, "updated_time"),
        occurrence_datetime: json_str(market, "occurrence_datetime"),
        sport: event
            .map(|e| e.sport.clone())
            .unwrap_or_else(|| config.sport.clone()),
        league: event
            .map(|e| e.league.clone())
            .unwrap_or_else(|| config.league().into()),
        season: event
            .map(|e| e.season.clone())
            .unwrap_or_else(|| "UNKNOWN".into()),
        season_phase: event
            .map(|e| e.season_phase.clone())
            .unwrap_or_else(|| "UNKNOWN".into()),
        source: "kalshi_rest".into(),
        ingested_at: now,
        schema_version: event
            .map(|e| e.schema_version.clone())
            .unwrap_or_else(|| config.schema_version().into()),
    })
}

/// Fill the two tennis player-side slots on each event from its market tickers.
///
/// The shared warehouse schema only has `home_team_code` / `away_team_code`.
/// For tennis those two slots carry ordered player side A and side B; they do
/// **not** mean home and away, because tennis has no venue relation. ROLLER's
/// canonical layer renames them. The shared schema is deliberately unchanged so
/// NBA/NCAAB/MLB/NHL/WNBA reads are unaffected.
///
/// Fails closed: an event that does not resolve to exactly two distinct market
/// suffixes keeps both slots empty and is reported as an anomaly rather than
/// having its sides guessed from the event ticker blob.
pub fn assign_tennis_sides(events: &mut [NbaEventRow], markets: &[NbaMarketRow]) {
    let mut by_event: BTreeMap<&str, Vec<String>> = BTreeMap::new();
    for m in markets {
        by_event
            .entry(m.event_id.as_str())
            .or_default()
            .push(m.ticker.clone());
    }
    for event in events.iter_mut() {
        let mut tickers = by_event
            .get(event.event_id.as_str())
            .cloned()
            .unwrap_or_default();
        tickers.sort();
        match tennis_player_sides(&event.event_ticker, &tickers) {
            Some(sides) => {
                event.home_team_code = Some(sides.side_a_code);
                event.away_team_code = Some(sides.side_b_code);
            }
            None => {
                event.home_team_code = None;
                event.away_team_code = None;
                tracing::warn!(
                    event_ticker = event.event_ticker.as_str(),
                    market_count = tickers.len(),
                    "tennis event did not resolve to two distinct market sides; sides left empty"
                );
            }
        }
    }
}

/// Tennis identity crosswalk, written alongside the normalized tennis tables.
///
/// `product_metadata.competition` and `custom_strike.tennis_competitor` are
/// retained verbatim in the raw JSONL but have no column in the shared parquet
/// schema. This sidecar lifts exactly those two fields (plus the derived side
/// order) into the tennis layer without touching the shared schema.
pub fn build_tennis_crosswalk(universe: &DiscoveredUniverse, events: &[NbaEventRow]) -> Value {
    let kept: BTreeSet<&str> = events.iter().map(|e| e.event_id.as_str()).collect();
    let raw_by_ticker: BTreeMap<String, &Value> = universe
        .events
        .iter()
        .filter_map(|e| json_str(e, "event_ticker").map(|t| (t, e)))
        .collect();
    // Driven by the event rows, so events synthesized from orphan markets are
    // present too (with an unavailable competition rather than a missing row).
    let event_rows: Vec<Value> = events
        .iter()
        .map(|row| {
            let raw = raw_by_ticker.get(&row.event_ticker).copied();
            let competition = raw
                .map(tennis_competition_resolved)
                .unwrap_or(TennisCompetition {
                    name: None,
                    source: TENNIS_COMPETITION_UNAVAILABLE,
                });
            serde_json::json!({
                "event_ticker": row.event_ticker.clone(),
                "competition": competition.name,
                "competition_source": competition.source,
                "competition_scope": raw
                    .and_then(|e| e.get("product_metadata"))
                    .and_then(|m| m.get("competition_scope"))
                    .and_then(|v| v.as_str()),
                "season_phase": row.season_phase.clone(),
                "phase_method": row.phase_method.clone(),
                "side_a_code": row.home_team_code.clone(),
                "side_b_code": row.away_team_code.clone(),
            })
        })
        .collect();
    let market_rows: Vec<Value> = universe
        .markets
        .iter()
        .filter_map(|m| {
            let event_ticker = json_str(m, "event_ticker")?;
            if !kept.contains(event_ticker.as_str()) {
                return None;
            }
            let ticker = json_str(m, "ticker")?;
            Some(serde_json::json!({
                "ticker": ticker.clone(),
                "event_ticker": event_ticker,
                "side_code": ticker_yes_code(&ticker),
                "yes_sub_title": json_str(m, "yes_sub_title"),
                "tennis_competitor": market_tennis_competitor(m),
            }))
        })
        .collect();
    serde_json::json!({
        "note": "Research only. Kalshi tennis_competitor is a stable per-player UUID and is the crosswalk key.",
        "side_slots": "events.home_team_code = side A, events.away_team_code = side B. Tennis has no home/away.",
        "events": event_rows,
        "markets": market_rows,
    })
}

pub fn build_games(events: &[NbaEventRow], markets: &[NbaMarketRow]) -> Vec<NbaGameRow> {
    let mut by_event: BTreeMap<String, Vec<&NbaMarketRow>> = BTreeMap::new();
    for m in markets {
        by_event.entry(m.event_id.clone()).or_default().push(m);
    }
    events
        .iter()
        .map(|event| {
            let ms = by_event.get(&event.event_id).cloned().unwrap_or_default();
            let mut tickers: Vec<String> = ms.iter().map(|m| m.ticker.clone()).collect();
            tickers.sort();
            let (home_mkt, away_mkt) = assign_home_away_markets(event, &ms);
            let statuses: BTreeSet<String> =
                ms.iter().filter_map(|m| m.market_status.clone()).collect();
            let results: BTreeSet<String> = ms.iter().filter_map(|m| m.result.clone()).collect();
            NbaGameRow {
                game_id: hex_u128(game_id_for_event_ticker(&event.event_ticker).raw()),
                event_id: event.event_id.clone(),
                event_ticker: event.event_ticker.clone(),
                season: event.season.clone(),
                season_phase: event.season_phase.clone(),
                phase_method: event.phase_method.clone(),
                game_date: event.game_date.clone(),
                scheduled_start: ms.iter().find_map(|m| m.occurrence_datetime.clone()),
                home_team: home_mkt.as_ref().and_then(|t| {
                    ms.iter()
                        .find(|m| m.ticker == *t)
                        .and_then(|m| m.team.clone())
                }),
                away_team: away_mkt.as_ref().and_then(|t| {
                    ms.iter()
                        .find(|m| m.ticker == *t)
                        .and_then(|m| m.team.clone())
                }),
                home_team_code: event.home_team_code.clone(),
                away_team_code: event.away_team_code.clone(),
                home_market_ticker: home_mkt,
                away_market_ticker: away_mkt,
                market_count: tickers.len() as u32,
                market_tickers: tickers,
                event_status: statuses.iter().next().cloned(),
                settlement_status: if results.is_empty() {
                    None
                } else {
                    Some(results.into_iter().collect::<Vec<_>>().join(","))
                },
                event_title: event.event_title.clone(),
                event_subtitle: event.event_subtitle.clone(),
                source: "kalshi_rest".into(),
                schema_version: event.schema_version.clone(),
            }
        })
        .collect()
}

fn assign_home_away_markets(
    event: &NbaEventRow,
    markets: &[&NbaMarketRow],
) -> (Option<String>, Option<String>) {
    let mut home = None;
    let mut away = None;
    for m in markets {
        let code = ticker_yes_code(&m.ticker);
        if code.as_ref() == event.home_team_code.as_ref() {
            home = Some(m.ticker.clone());
        }
        if code.as_ref() == event.away_team_code.as_ref() {
            away = Some(m.ticker.clone());
        }
    }
    (home, away)
}

pub fn filter_universe(
    config: &WarehouseConfig,
    mut events: Vec<NbaEventRow>,
    markets: Vec<NbaMarketRow>,
) -> (Vec<NbaEventRow>, Vec<NbaMarketRow>, Vec<NbaGameRow>) {
    if config.research_sport().is_tennis() {
        // Run before the market filters so a `--ticker` run cannot strip one of
        // the two sides and silently change the derived side codes.
        assign_tennis_sides(&mut events, &markets);
    }
    let events: Vec<NbaEventRow> = events
        .into_iter()
        .filter(|e| e.season == config.season && config.allows_phase(&e.season_phase))
        .filter(|e| {
            config
                .event_filter
                .as_ref()
                .is_none_or(|f| e.event_ticker == *f)
        })
        .collect();
    let keep: BTreeSet<String> = events.iter().map(|e| e.event_id.clone()).collect();
    let markets: Vec<NbaMarketRow> = markets
        .into_iter()
        .filter(|m| keep.contains(&m.event_id))
        .filter(|m| config.ticker_filter.as_ref().is_none_or(|f| m.ticker == *f))
        .collect();
    let games = build_games(&events, &markets);
    (events, markets, games)
}

pub fn market_window_ts(market: &Value) -> (i64, i64) {
    let open = json_str(market, "open_time")
        .as_deref()
        .and_then(super::types::parse_rfc3339)
        .map(|t| t.timestamp())
        .unwrap_or(0);
    let close = json_str(market, "close_time")
        .as_deref()
        .and_then(super::types::parse_rfc3339)
        .map(|t| t.timestamp());
    let settle = json_str(market, "settlement_ts")
        .as_deref()
        .and_then(super::types::parse_rfc3339)
        .map(|t| t.timestamp());
    let end = close.max(settle).unwrap_or(open + 86_400);
    (open, end.max(open + 60))
}

pub fn cutoff_unix(cutoff: &Value) -> Option<i64> {
    match cutoff.get("market_settled_ts") {
        Some(Value::Number(n)) => n.as_i64(),
        Some(Value::String(s)) => super::types::parse_rfc3339(s).map(|t| t.timestamp()),
        _ => None,
    }
}
