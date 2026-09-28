//! Dataset validation rules.

use crate::identity::DiscoveredMarket;
use crate::schema::{MarketMetadata, OrderbookEvent, PublicTrade};

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ValidationReport {
    pub invalid_records: u32,
    pub messages: Vec<String>,
}

impl ValidationReport {
    pub fn ok() -> Self {
        Self::default()
    }

    pub fn is_valid(&self) -> bool {
        self.invalid_records == 0
    }

    fn reject(&mut self, msg: impl Into<String>) {
        self.invalid_records += 1;
        self.messages.push(msg.into());
    }
}

pub fn validate_metadata(rows: &[MarketMetadata]) -> ValidationReport {
    let mut report = ValidationReport::ok();
    let mut seen_market = std::collections::HashSet::new();
    for row in rows {
        if row.ticker.is_empty() {
            report.reject("metadata missing ticker");
        }
        if row.market_id == 0 {
            report.reject(format!("metadata missing market_id for {}", row.ticker));
        }
        if row.game_id == 0 {
            report.reject(format!("metadata missing game_id for {}", row.ticker));
        }
        if !seen_market.insert(row.market_id) {
            report.reject(format!("duplicate market_id {}", row.market_id));
        }
    }
    report
}

pub fn validate_discovered_pairing(markets: &[DiscoveredMarket]) -> ValidationReport {
    let mut report = ValidationReport::ok();
    let mut by_game: std::collections::BTreeMap<u128, Vec<&MarketMetadata>> =
        std::collections::BTreeMap::new();
    for m in markets {
        by_game
            .entry(m.metadata.game_id)
            .or_default()
            .push(&m.metadata);
    }
    for (game, group) in by_game {
        if group.len() >= 2 {
            let ids: Vec<_> = group.iter().map(|m| m.market_id).collect();
            if ids.windows(2).any(|w| w[0] == w[1]) {
                report.reject(format!("game {game} has duplicate market ids"));
            }
        }
    }
    report
}

pub fn validate_trades(rows: &[PublicTrade]) -> ValidationReport {
    let mut report = ValidationReport::ok();
    let mut seen = std::collections::HashSet::new();
    for row in rows {
        if row.yes_price_cents == 0 || row.yes_price_cents > 100 {
            report.reject(format!("trade {} invalid yes price", row.trade_id));
        }
        if row.quantity_hundredths <= 0 {
            report.reject(format!("trade {} non-positive quantity", row.trade_id));
        }
        if !seen.insert(row.trade_id.clone()) {
            report.reject(format!("duplicate trade_id {}", row.trade_id));
        }
    }
    report
}

pub fn validate_orderbook(rows: &[OrderbookEvent]) -> ValidationReport {
    let mut report = ValidationReport::ok();
    for row in rows {
        if row.ticker.is_empty() || row.market_id == 0 || row.game_id == 0 {
            report.reject("orderbook event missing identity");
        }
        for level in &row.levels {
            if level.price_cents == 0 || level.price_cents > 100 {
                report.reject(format!(
                    "orderbook {} invalid price {}",
                    row.ticker, level.price_cents
                ));
            }
            if level.quantity_hundredths < 0 {
                report.reject(format!("orderbook {} negative qty", row.ticker));
            }
        }
        if row.sequence_gap && row.levels.is_empty() && row.yes_bid_cents.is_none() {
            // gap without book is acceptable — marks invalid book state
        }
    }
    report
}

pub fn no_synthetic_rows(rows: &[OrderbookEvent]) -> ValidationReport {
    let mut report = ValidationReport::ok();
    for row in rows {
        if row.source == crate::schema::NormalizedSource::RestCandlestick
            && row.event_type == "l2_snapshot"
        {
            report.reject(format!("candlestick mislabeled as l2 for {}", row.ticker));
        }
    }
    report
}
