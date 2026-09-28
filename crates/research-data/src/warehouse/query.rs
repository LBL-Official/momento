//! Research query API. Callers do not need Kalshi REST details.

use chrono::{DateTime, Utc};

use super::types::{
    CausalCandleFeatures, ComplementarityRow, NbaCandleRow, NbaGameRow, NbaMarketRow, NbaTradeRow,
};

#[derive(Clone, Debug, Default)]
pub struct NbaQuery {
    pub games: Vec<NbaGameRow>,
    pub markets: Vec<NbaMarketRow>,
    pub candles: Vec<NbaCandleRow>,
    pub trades: Vec<NbaTradeRow>,
    pub causal: Vec<CausalCandleFeatures>,
    pub complementarity: Vec<ComplementarityRow>,
}

impl NbaQuery {
    pub fn get_games(&self, season: &str, phase: Option<&str>) -> Vec<NbaGameRow> {
        self.games
            .iter()
            .filter(|g| g.season == season)
            .filter(|g| phase.is_none_or(|p| g.season_phase == p))
            .cloned()
            .collect()
    }

    pub fn get_game(&self, game_id: &str) -> Option<NbaGameRow> {
        self.games
            .iter()
            .find(|g| g.game_id == game_id || g.event_id == game_id || g.event_ticker == game_id)
            .cloned()
    }

    pub fn get_markets(&self, game_id: &str) -> Vec<NbaMarketRow> {
        let event = self
            .get_game(game_id)
            .map(|g| g.event_id)
            .unwrap_or_else(|| game_id.to_string());
        self.markets
            .iter()
            .filter(|m| m.event_id == event || m.game_id == game_id)
            .cloned()
            .collect()
    }

    pub fn get_market(&self, ticker: &str) -> Option<NbaMarketRow> {
        self.markets.iter().find(|m| m.ticker == ticker).cloned()
    }

    pub fn get_candles(
        &self,
        ticker: &str,
        start: Option<DateTime<Utc>>,
        end: Option<DateTime<Utc>>,
    ) -> Vec<NbaCandleRow> {
        self.candles
            .iter()
            .filter(|c| c.ticker == ticker)
            .filter(|c| start.is_none_or(|s| c.end_time >= s))
            .filter(|c| end.is_none_or(|e| c.end_time <= e))
            .cloned()
            .collect()
    }

    pub fn get_trades(
        &self,
        ticker: &str,
        start: Option<DateTime<Utc>>,
        end: Option<DateTime<Utc>>,
    ) -> Vec<NbaTradeRow> {
        self.trades
            .iter()
            .filter(|t| t.ticker == ticker)
            .filter(|t| start.is_none_or(|s| t.timestamp >= s))
            .filter(|t| end.is_none_or(|e| t.timestamp <= e))
            .cloned()
            .collect()
    }

    pub fn get_game_market_data(
        &self,
        game_id: &str,
        start: Option<DateTime<Utc>>,
        end: Option<DateTime<Utc>>,
    ) -> GameMarketData {
        let markets = self.get_markets(game_id);
        let mut sides = Vec::new();
        for m in &markets {
            sides.push(MarketSideSeries {
                ticker: m.ticker.clone(),
                team: m.team.clone(),
                candles: self.get_candles(&m.ticker, start, end),
                trades: self.get_trades(&m.ticker, start, end),
            });
        }
        GameMarketData {
            game: self.get_game(game_id),
            sides,
        }
    }

    pub fn get_season_market_data(&self, season: &str, phase: Option<&str>) -> Vec<GameMarketData> {
        self.get_games(season, phase)
            .into_iter()
            .map(|g| self.get_game_market_data(&g.event_id, None, None))
            .collect()
    }

    pub fn aligned_two_sided(&self, game_id: &str) -> Vec<AlignedQuote> {
        let markets = self.get_markets(game_id);
        if markets.len() != 2 {
            return Vec::new();
        }
        let a = &markets[0];
        let b = &markets[1];
        let mut a_map = std::collections::BTreeMap::new();
        for c in self.get_candles(&a.ticker, None, None) {
            a_map.insert(c.end_period_ts, c);
        }
        let mut out = Vec::new();
        for c in self.get_candles(&b.ticker, None, None) {
            if let Some(ac) = a_map.get(&c.end_period_ts) {
                out.push(AlignedQuote {
                    timestamp: c.end_time,
                    team_a_ticker: a.ticker.clone(),
                    team_b_ticker: b.ticker.clone(),
                    team_a_bid_e4: ac.yes_bid_close_e4,
                    team_a_ask_e4: ac.yes_ask_close_e4,
                    team_a_mid_e4: super::derive::mid_e4(ac.yes_bid_close_e4, ac.yes_ask_close_e4),
                    team_b_bid_e4: c.yes_bid_close_e4,
                    team_b_ask_e4: c.yes_ask_close_e4,
                    team_b_mid_e4: super::derive::mid_e4(c.yes_bid_close_e4, c.yes_ask_close_e4),
                });
            }
        }
        out
    }
}

#[derive(Clone, Debug)]
pub struct MarketSideSeries {
    pub ticker: String,
    pub team: Option<String>,
    pub candles: Vec<NbaCandleRow>,
    pub trades: Vec<NbaTradeRow>,
}

#[derive(Clone, Debug)]
pub struct GameMarketData {
    pub game: Option<NbaGameRow>,
    pub sides: Vec<MarketSideSeries>,
}

#[derive(Clone, Debug)]
pub struct AlignedQuote {
    pub timestamp: DateTime<Utc>,
    pub team_a_ticker: String,
    pub team_b_ticker: String,
    pub team_a_bid_e4: Option<i64>,
    pub team_a_ask_e4: Option<i64>,
    pub team_a_mid_e4: Option<i64>,
    pub team_b_bid_e4: Option<i64>,
    pub team_b_ask_e4: Option<i64>,
    pub team_b_mid_e4: Option<i64>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::warehouse::types::{
        MARKET_DATA_TYPE_CANDLE_TOB, NbaCandleRow, NbaGameRow, NbaMarketRow, SCHEMA_VERSION,
    };
    use chrono::{TimeZone, Utc};

    fn market(ticker: &str, team: &str) -> NbaMarketRow {
        NbaMarketRow {
            market_id: ticker.into(),
            ticker: ticker.into(),
            event_id: "KXNBAGAME-26JUN13NYKSAS".into(),
            game_id: "g1".into(),
            series_ticker: "KXNBAGAME".into(),
            market_title: None,
            yes_subtitle: Some(team.into()),
            no_subtitle: None,
            team: Some(team.into()),
            opponent: None,
            market_status: Some("finalized".into()),
            result: None,
            settlement_value_e4: None,
            volume_hundredths: None,
            open_interest_hundredths: None,
            last_price_e4: None,
            yes_bid_e4: None,
            yes_ask_e4: None,
            open_time: None,
            close_time: None,
            expiration_time: None,
            settlement_time: None,
            created_time: None,
            updated_time: None,
            occurrence_datetime: None,
            sport: "nba".into(),
            league: "NBA".into(),
            season: "2025-2026".into(),
            season_phase: "FINALS".into(),
            source: "test".into(),
            ingested_at: Utc::now(),
            schema_version: SCHEMA_VERSION.into(),
        }
    }

    fn candle(ticker: &str, bid: i64, ask: i64) -> NbaCandleRow {
        let ts = 1_700_000_060;
        NbaCandleRow {
            ticker: ticker.into(),
            event_id: "KXNBAGAME-26JUN13NYKSAS".into(),
            market_id: ticker.into(),
            game_id: "g1".into(),
            end_period_ts: ts,
            start_time: Utc.timestamp_opt(ts - 60, 0).unwrap(),
            end_time: Utc.timestamp_opt(ts, 0).unwrap(),
            yes_bid_open_e4: Some(bid),
            yes_bid_high_e4: Some(bid),
            yes_bid_low_e4: Some(bid),
            yes_bid_close_e4: Some(bid),
            yes_ask_open_e4: Some(ask),
            yes_ask_high_e4: Some(ask),
            yes_ask_low_e4: Some(ask),
            yes_ask_close_e4: Some(ask),
            price_open_e4: None,
            price_high_e4: None,
            price_low_e4: None,
            price_close_e4: None,
            price_mean_e4: None,
            price_previous_e4: None,
            volume_hundredths: None,
            open_interest_hundredths: None,
            market_data_type: MARKET_DATA_TYPE_CANDLE_TOB.into(),
            orderbook_depth_available: false,
            is_valid: true,
            is_duplicate: false,
            is_pre_market: false,
            is_post_market: false,
            source: "test".into(),
            ingested_at: Utc::now(),
            schema_version: SCHEMA_VERSION.into(),
        }
    }

    #[test]
    fn two_sided_alignment() {
        let q = NbaQuery {
            games: vec![NbaGameRow {
                game_id: "g1".into(),
                event_id: "KXNBAGAME-26JUN13NYKSAS".into(),
                event_ticker: "KXNBAGAME-26JUN13NYKSAS".into(),
                season: "2025-2026".into(),
                season_phase: "FINALS".into(),
                phase_method: "event_title_game_n_plus_june".into(),
                game_date: Some("2026-06-13".into()),
                scheduled_start: None,
                home_team: Some("San Antonio".into()),
                away_team: Some("New York".into()),
                home_team_code: Some("SAS".into()),
                away_team_code: Some("NYK".into()),
                home_market_ticker: Some("KXNBAGAME-26JUN13NYKSAS-SAS".into()),
                away_market_ticker: Some("KXNBAGAME-26JUN13NYKSAS-NYK".into()),
                market_tickers: vec![
                    "KXNBAGAME-26JUN13NYKSAS-NYK".into(),
                    "KXNBAGAME-26JUN13NYKSAS-SAS".into(),
                ],
                market_count: 2,
                event_status: Some("finalized".into()),
                settlement_status: None,
                event_title: Some("Game 5: New York at San Antonio".into()),
                event_subtitle: Some("NYK at SAS (Jun 13)".into()),
                source: "test".into(),
                schema_version: SCHEMA_VERSION.into(),
            }],
            markets: vec![
                market("KXNBAGAME-26JUN13NYKSAS-NYK", "New York"),
                market("KXNBAGAME-26JUN13NYKSAS-SAS", "San Antonio"),
            ],
            candles: vec![
                candle("KXNBAGAME-26JUN13NYKSAS-NYK", 7000, 7200),
                candle("KXNBAGAME-26JUN13NYKSAS-SAS", 2800, 3000),
            ],
            trades: vec![],
            causal: vec![],
            complementarity: vec![],
        };
        assert_eq!(q.get_games("2025-2026", Some("FINALS")).len(), 1);
        assert_eq!(q.get_markets("KXNBAGAME-26JUN13NYKSAS").len(), 2);
        let aligned = q.aligned_two_sided("KXNBAGAME-26JUN13NYKSAS");
        assert_eq!(aligned.len(), 1);
        assert_eq!(aligned[0].team_a_mid_e4, Some(7100));
        assert_eq!(aligned[0].team_b_mid_e4, Some(2900));
    }

    fn ncaab_market(ticker: &str, team: &str) -> NbaMarketRow {
        let mut m = market(ticker, team);
        m.event_id = "KXNCAAMBGAME-26JAN18TLSAUAB".into();
        m.series_ticker = "KXNCAAMBGAME".into();
        m.sport = "ncaab".into();
        m.league = "NCAAB".into();
        m.season_phase = "REGULAR_SEASON".into();
        m.schema_version = crate::warehouse::types::NCAAB_SCHEMA_VERSION.into();
        m
    }

    #[test]
    fn two_sided_ncaab_alignment() {
        let q = NbaQuery {
            games: vec![NbaGameRow {
                game_id: "g1".into(),
                event_id: "KXNCAAMBGAME-26JAN18TLSAUAB".into(),
                event_ticker: "KXNCAAMBGAME-26JAN18TLSAUAB".into(),
                season: "2025-2026".into(),
                season_phase: "REGULAR_SEASON".into(),
                phase_method: "default_unlabeled".into(),
                game_date: Some("2026-01-18".into()),
                scheduled_start: None,
                home_team: Some("UAB".into()),
                away_team: Some("Tulsa".into()),
                home_team_code: Some("UAB".into()),
                away_team_code: Some("TLSA".into()),
                home_market_ticker: Some("KXNCAAMBGAME-26JAN18TLSAUAB-UAB".into()),
                away_market_ticker: Some("KXNCAAMBGAME-26JAN18TLSAUAB-TLSA".into()),
                market_tickers: vec![
                    "KXNCAAMBGAME-26JAN18TLSAUAB-TLSA".into(),
                    "KXNCAAMBGAME-26JAN18TLSAUAB-UAB".into(),
                ],
                market_count: 2,
                event_status: Some("finalized".into()),
                settlement_status: None,
                event_title: Some("Tulsa at UAB".into()),
                event_subtitle: Some("TLSA at UAB (Jan 18)".into()),
                source: "test".into(),
                schema_version: crate::warehouse::types::NCAAB_SCHEMA_VERSION.into(),
            }],
            markets: vec![
                ncaab_market("KXNCAAMBGAME-26JAN18TLSAUAB-TLSA", "Tulsa"),
                ncaab_market("KXNCAAMBGAME-26JAN18TLSAUAB-UAB", "UAB"),
            ],
            candles: vec![
                candle("KXNCAAMBGAME-26JAN18TLSAUAB-TLSA", 4000, 4200),
                candle("KXNCAAMBGAME-26JAN18TLSAUAB-UAB", 5800, 6000),
            ],
            trades: vec![],
            causal: vec![],
            complementarity: vec![],
        };
        assert_eq!(q.get_games("2025-2026", Some("REGULAR_SEASON")).len(), 1);
        assert_eq!(q.get_markets("KXNCAAMBGAME-26JAN18TLSAUAB").len(), 2);
        let aligned = q.aligned_two_sided("KXNCAAMBGAME-26JAN18TLSAUAB");
        assert_eq!(aligned.len(), 1);
        assert_eq!(aligned[0].team_a_mid_e4, Some(4100));
        assert_eq!(aligned[0].team_b_mid_e4, Some(5900));
    }
}
