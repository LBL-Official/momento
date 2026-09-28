//! Couple YES contracts that share event_ticker. Missing side is explicit.

use std::collections::BTreeMap;

use crate::types::{CoupledMarketEpisode, MarketPath, MissingSide, ReconstructionAnomaly};

pub fn couple_paths(
    paths: &[MarketPath],
) -> (Vec<CoupledMarketEpisode>, Vec<ReconstructionAnomaly>) {
    let mut by_event: BTreeMap<String, Vec<MarketPath>> = BTreeMap::new();
    for p in paths {
        if p.event_ticker.is_empty() {
            continue;
        }
        by_event
            .entry(p.event_ticker.clone())
            .or_default()
            .push(p.clone());
    }
    let mut episodes = Vec::new();
    let mut anomalies = Vec::new();
    for (event_ticker, mut group) in by_event {
        group.sort_by(|a, b| a.ticker.cmp(&b.ticker));
        if group.len() > 2 {
            anomalies.push(ReconstructionAnomaly {
                ticker: event_ticker.clone(),
                code: "MORE_THAN_TWO_CONTRACTS".into(),
                message: format!("{} tickers; first two coupled", group.len()),
            });
        }
        let team_a_yes = group.first().cloned();
        let team_b_yes = if group.len() >= 2 {
            Some(group[1].clone())
        } else {
            None
        };
        let missing_side = if team_b_yes.is_none() {
            MissingSide::SecondYesContract
        } else {
            MissingSide::None
        };
        episodes.push(CoupledMarketEpisode {
            event_ticker,
            team_a_yes,
            team_b_yes,
            missing_side,
        });
    }
    (episodes, anomalies)
}
