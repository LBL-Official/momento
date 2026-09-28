//! Fail-closed identity join. Uses W2 matching; never invents gamePk or tickers.

use std::collections::{BTreeMap, BTreeSet};

use chrono::{Datelike, NaiveDate};
use momento_research_event::identity::{
    DataYear, MlbMatchStatus, OfficialMlbGameRef, SourceRef, match_official_to_kalshi_tickers,
};

use crate::kalshi::DiscoveredMarket;
use crate::source::DiscoveredPartition;
use crate::types::{GameMarketPair, IdentityMapping, MarketCompleteness};

#[derive(Clone, Debug)]
pub struct ObservedMlbGame {
    pub game_pk: String,
    pub date: NaiveDate,
    pub home_abbreviation: String,
    pub away_abbreviation: String,
    pub game_number: u8,
}

impl ObservedMlbGame {
    pub fn from_partition(part: &DiscoveredPartition) -> Self {
        Self {
            game_pk: part.partition_id.clone(),
            date: part.date,
            home_abbreviation: part.home_abbreviation.clone(),
            away_abbreviation: part.away_abbreviation.clone(),
            game_number: part.game_number,
        }
    }

    pub fn from_official(official: &OfficialMlbGameRef) -> Self {
        Self {
            game_pk: official.game_pk.clone(),
            date: official.official_date,
            home_abbreviation: official.home_abbreviation.clone(),
            away_abbreviation: official.away_abbreviation.clone(),
            game_number: if official.game_number == 0 {
                1
            } else {
                official.game_number
            },
        }
    }
}

pub fn join_game_market_pairs(
    games: &[ObservedMlbGame],
    markets: &[DiscoveredMarket],
) -> Vec<GameMarketPair> {
    let mut event_tickers_by_date: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    let mut markets_by_date: BTreeMap<String, Vec<&DiscoveredMarket>> = BTreeMap::new();
    for m in markets {
        let date = m.date.to_string();
        if let Some(et) = m.event_ticker.as_ref().filter(|s| !s.is_empty()) {
            event_tickers_by_date
                .entry(date.clone())
                .or_default()
                .insert(et.clone());
        }
        markets_by_date.entry(date).or_default().push(m);
    }

    let mut mapped_events: BTreeSet<String> = BTreeSet::new();
    let mut ambiguous_events: BTreeSet<String> = BTreeSet::new();
    let mut pairs = Vec::new();

    for game in games {
        let date = game.date.to_string();
        let day_tickers: Vec<String> = event_tickers_by_date
            .get(&date)
            .map(|s| s.iter().cloned().collect())
            .unwrap_or_default();
        let official = official_ref(game);
        let (status, hits) = match_official_to_kalshi_tickers(&official, &day_tickers);
        match status {
            MlbMatchStatus::Mapped => {
                for et in &hits {
                    mapped_events.insert(et.clone());
                }
                let day_markets = markets_by_date.get(&date).cloned().unwrap_or_default();
                for market in day_markets {
                    if market
                        .event_ticker
                        .as_ref()
                        .is_some_and(|et| hits.contains(et))
                    {
                        pairs.push(GameMarketPair {
                            game_pk: Some(game.game_pk.clone()),
                            official_date: date.clone(),
                            event_ticker: market.event_ticker.clone(),
                            ticker: market.ticker.clone(),
                            mapping: IdentityMapping::Mapped,
                            completeness: market.completeness,
                            notes: "MAPPED via unique observed abbr suffix; gamePk OBSERVED from StatsAPI".into(),
                        });
                    }
                }
            }
            MlbMatchStatus::Ambiguous => {
                for et in &hits {
                    ambiguous_events.insert(et.clone());
                }
                pairs.push(GameMarketPair {
                    game_pk: Some(game.game_pk.clone()),
                    official_date: date,
                    event_ticker: hits.first().cloned(),
                    ticker: String::new(),
                    mapping: IdentityMapping::Ambiguous,
                    completeness: None,
                    notes: "AMBIGUOUS retained; not resolved by guesswork".into(),
                });
            }
            MlbMatchStatus::Unmatched => {
                pairs.push(GameMarketPair {
                    game_pk: Some(game.game_pk.clone()),
                    official_date: date,
                    event_ticker: None,
                    ticker: String::new(),
                    mapping: IdentityMapping::Unmatched,
                    completeness: None,
                    notes: "PBP game has no unique Kalshi event_ticker on this date".into(),
                });
            }
            _ => {}
        }
    }

    // A unique suffix match that hits two official games is still AMBIGUOUS.
    let mut event_to_games: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for p in &pairs {
        if p.mapping == IdentityMapping::Mapped {
            if let (Some(et), Some(pk)) = (&p.event_ticker, &p.game_pk) {
                event_to_games
                    .entry(et.clone())
                    .or_default()
                    .insert(pk.clone());
            }
        }
    }
    let collided: BTreeSet<String> = event_to_games
        .into_iter()
        .filter(|(_, games)| games.len() > 1)
        .map(|(et, _)| et)
        .collect();
    for p in &mut pairs {
        if p.mapping == IdentityMapping::Mapped
            && p.event_ticker
                .as_ref()
                .is_some_and(|et| collided.contains(et))
        {
            p.mapping = IdentityMapping::Ambiguous;
            p.notes =
                "AMBIGUOUS: same event_ticker uniquely suffix-matched more than one gamePk".into();
        }
    }

    for market in markets {
        let et = market.event_ticker.clone().unwrap_or_default();
        if mapped_events.contains(&et) || ambiguous_events.contains(&et) {
            continue;
        }
        if pairs
            .iter()
            .any(|p| p.ticker == market.ticker && p.mapping == IdentityMapping::Mapped)
        {
            continue;
        }
        pairs.push(GameMarketPair {
            game_pk: None,
            official_date: market.date.to_string(),
            event_ticker: market.event_ticker.clone(),
            ticker: market.ticker.clone(),
            mapping: IdentityMapping::Unmatched,
            completeness: market.completeness,
            notes: "Kalshi ticker retained UNMATCHED; gamePk not inferred from ticker text".into(),
        });
    }

    pairs
}

fn official_ref(game: &ObservedMlbGame) -> OfficialMlbGameRef {
    OfficialMlbGameRef {
        source: "mlb_statsapi".into(),
        game_pk: game.game_pk.clone(),
        season: DataYear(game.date.year()),
        official_date: game.date,
        home_team: SourceRef {
            source: "mlb_statsapi".into(),
            source_id: game.home_abbreviation.clone(),
        },
        away_team: SourceRef {
            source: "mlb_statsapi".into(),
            source_id: game.away_abbreviation.clone(),
        },
        venue: None,
        game_number: if game.game_number == 0 {
            1
        } else {
            game.game_number
        },
        competition: "MLB".into(),
        home_abbreviation: game.home_abbreviation.clone(),
        away_abbreviation: game.away_abbreviation.clone(),
    }
}

pub fn completeness_label(c: Option<MarketCompleteness>) -> &'static str {
    match c {
        Some(MarketCompleteness::L2Complete) => "L2_COMPLETE",
        Some(MarketCompleteness::L2Partial) => "L2_PARTIAL",
        Some(MarketCompleteness::TradesOnly) => "TRADES_ONLY",
        Some(MarketCompleteness::CandlesOnly) => "CANDLES_ONLY",
        Some(MarketCompleteness::MarketMetadataOnly) => "MARKET_METADATA_ONLY",
        None => "UNKNOWN",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::IdentityMapping;

    fn game(pk: &str, away: &str, home: &str) -> ObservedMlbGame {
        game_n(pk, away, home, 1)
    }

    fn game_n(pk: &str, away: &str, home: &str, game_number: u8) -> ObservedMlbGame {
        ObservedMlbGame {
            game_pk: pk.into(),
            date: NaiveDate::from_ymd_opt(2026, 6, 18).unwrap(),
            home_abbreviation: home.into(),
            away_abbreviation: away.into(),
            game_number,
        }
    }

    fn market(ticker: &str, event: &str) -> DiscoveredMarket {
        DiscoveredMarket {
            date: NaiveDate::from_ymd_opt(2026, 6, 18).unwrap(),
            ticker: ticker.into(),
            event_ticker: Some(event.into()),
            series: Some("KXMLBGAME".into()),
            mapping: IdentityMapping::Unmatched,
            observed_game_pk: None,
            completeness: Some(MarketCompleteness::TradesOnly),
            notes: String::new(),
            open_time: None,
            close_time: None,
            result: None,
            settlement_ts: None,
            settlement_value_dollars: None,
            status: None,
        }
    }

    #[test]
    fn unique_suffix_maps_without_inventing_pk() {
        let games = vec![game("747001", "NYY", "BOS")];
        let markets = vec![
            market("KXMLBGAME-26JUN18NYYBOS-NYY", "KXMLBGAME-26JUN18NYYBOS"),
            market("KXMLBGAME-26JUN18NYYBOS-BOS", "KXMLBGAME-26JUN18NYYBOS"),
        ];
        let pairs = join_game_market_pairs(&games, &markets);
        let mapped: Vec<_> = pairs
            .iter()
            .filter(|p| p.mapping == IdentityMapping::Mapped)
            .collect();
        assert_eq!(mapped.len(), 2);
        assert_eq!(mapped[0].game_pk.as_deref(), Some("747001"));
    }

    #[test]
    fn doubleheader_stays_ambiguous() {
        let games = vec![game("1", "NYY", "BOS"), game("2", "NYY", "BOS")];
        let markets = vec![
            market("KXMLBGAME-26JUN18NYYBOS-NYY", "KXMLBGAME-26JUN18NYYBOS"),
            market(
                "KXMLBGAME-26JUN181200NYYBOS-NYY",
                "KXMLBGAME-26JUN181200NYYBOS",
            ),
        ];
        let pairs = join_game_market_pairs(&games, &markets);
        // Two games same abbrs + two event tickers with same team suffix → each game Ambiguous
        assert!(
            pairs
                .iter()
                .filter(|p| p.game_pk.is_some())
                .all(|p| p.mapping == IdentityMapping::Ambiguous)
        );
    }

    #[test]
    fn numbered_doubleheader_maps_each_game_without_inventing_pk() {
        let games = vec![
            game_n("746001", "ATH", "MIL", 1),
            game_n("746002", "ATH", "MIL", 2),
        ];
        let markets = vec![
            market("KXMLBGAME-25APR18ATHMIL-ATH", "KXMLBGAME-25APR18ATHMIL"),
            market("KXMLBGAME-25APR18ATHMIL-MIL", "KXMLBGAME-25APR18ATHMIL"),
            market("KXMLBGAME-25APR18ATHMIL2-ATH", "KXMLBGAME-25APR18ATHMIL2"),
            market("KXMLBGAME-25APR18ATHMIL2-MIL", "KXMLBGAME-25APR18ATHMIL2"),
        ];
        let pairs = join_game_market_pairs(&games, &markets);
        let mapped: Vec<_> = pairs
            .iter()
            .filter(|p| p.mapping == IdentityMapping::Mapped)
            .collect();
        assert_eq!(mapped.len(), 4);
        assert!(mapped.iter().all(|p| p.mapping == IdentityMapping::Mapped));
        let g1: Vec<_> = mapped
            .iter()
            .filter(|p| p.game_pk.as_deref() == Some("746001"))
            .map(|p| p.event_ticker.as_deref())
            .collect();
        let g2: Vec<_> = mapped
            .iter()
            .filter(|p| p.game_pk.as_deref() == Some("746002"))
            .map(|p| p.event_ticker.as_deref())
            .collect();
        assert!(g1.iter().all(|et| *et == Some("KXMLBGAME-25APR18ATHMIL")));
        assert!(g2.iter().all(|et| *et == Some("KXMLBGAME-25APR18ATHMIL2")));
    }

    #[test]
    fn g1_g2_doubleheader_maps_each_game_without_inventing_pk() {
        let games = vec![
            game_n("824766", "TB", "BOS", 1),
            game_n("824737", "TB", "BOS", 2),
        ];
        let markets = vec![
            market(
                "KXMLBGAME-26JUL171335TBBOSG1-TB",
                "KXMLBGAME-26JUL171335TBBOSG1",
            ),
            market(
                "KXMLBGAME-26JUL171335TBBOSG1-BOS",
                "KXMLBGAME-26JUL171335TBBOSG1",
            ),
            market(
                "KXMLBGAME-26JUL171910TBBOSG2-TB",
                "KXMLBGAME-26JUL171910TBBOSG2",
            ),
            market(
                "KXMLBGAME-26JUL171910TBBOSG2-BOS",
                "KXMLBGAME-26JUL171910TBBOSG2",
            ),
        ];
        let pairs = join_game_market_pairs(&games, &markets);
        let mapped: Vec<_> = pairs
            .iter()
            .filter(|p| p.mapping == IdentityMapping::Mapped)
            .collect();
        assert_eq!(mapped.len(), 4);
        assert!(
            mapped
                .iter()
                .filter(|p| p.game_pk.as_deref() == Some("824766"))
                .all(|p| p.event_ticker.as_deref() == Some("KXMLBGAME-26JUL171335TBBOSG1"))
        );
        assert!(
            mapped
                .iter()
                .filter(|p| p.game_pk.as_deref() == Some("824737"))
                .all(|p| p.event_ticker.as_deref() == Some("KXMLBGAME-26JUL171910TBBOSG2"))
        );
    }

    #[test]
    fn unmatched_kalshi_retained() {
        let games = vec![game("9", "AAA", "BBB")];
        let markets = vec![market(
            "KXMLBGAME-26JUN18NYYBOS-NYY",
            "KXMLBGAME-26JUN18NYYBOS",
        )];
        let pairs = join_game_market_pairs(&games, &markets);
        assert!(
            pairs
                .iter()
                .any(|p| p.mapping == IdentityMapping::Unmatched && p.ticker.contains("NYYBOS"))
        );
        assert!(pairs.iter().all(|p| p.game_pk != Some("invented".into())));
    }
}
