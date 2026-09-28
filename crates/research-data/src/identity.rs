//! Market identity helpers. GameId and MarketId remain independent.

use momento_kalshi::{KalshiMarket, game_id_for_event_ticker, market_id_for_ticker};

use crate::schema::MarketMetadata;
use crate::sport::ResearchSport;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DiscoveredMarket {
    pub metadata: MarketMetadata,
    pub sport: ResearchSport,
}

pub fn metadata_from_kalshi(market: &KalshiMarket, sport: ResearchSport) -> MarketMetadata {
    let game_id = game_id_for_event_ticker(&market.event_ticker).raw();
    let market_id = market_id_for_ticker(&market.ticker).raw();
    MarketMetadata {
        game_id,
        market_id,
        ticker: market.ticker.clone(),
        event_ticker: market.event_ticker.clone(),
        series_ticker: market
            .series_ticker
            .clone()
            .unwrap_or_else(|| sport.series_ticker().to_string()),
        side_label: market.subtitle.clone(),
        status: market.status.clone(),
        open_time: market.open_time.clone(),
        close_time: market.close_time.clone(),
        settlement_ts: market.settlement_ts.clone(),
        result: market.result.clone(),
    }
}

/// Prove two markets share a game but not a market id.
pub fn same_game_different_market(a: &MarketMetadata, b: &MarketMetadata) -> bool {
    a.game_id == b.game_id && a.market_id != b.market_id && a.ticker != b.ticker
}
