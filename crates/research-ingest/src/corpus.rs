//! Research corpus coverage vs measured targets. Never fabricate counts.

use crate::types::{
    CompletenessCounts, CorpusCoverage, GameMarketPair, IdentityMapping, MarketCompleteness,
    TARGET_MIN_MAPPED_PAIRS, TARGET_MIN_PBP_GAMES, TARGET_PREFERRED_MAPPED_PAIRS,
    TARGET_PREFERRED_PBP_GAMES,
};

pub fn corpus_from_pairs(
    mlb_games_discovered: usize,
    pbp_games_committed: usize,
    kalshi_markets_discovered: usize,
    kalshi_artifacts_committed: usize,
    pairs: &[GameMarketPair],
) -> CorpusCoverage {
    let pairs_mapped = pairs
        .iter()
        .filter(|p| p.mapping == IdentityMapping::Mapped && !p.ticker.is_empty())
        .count();
    let pairs_unmatched = pairs
        .iter()
        .filter(|p| p.mapping == IdentityMapping::Unmatched)
        .count();
    let pairs_ambiguous = pairs
        .iter()
        .filter(|p| p.mapping == IdentityMapping::Ambiguous)
        .count();
    let games_mapped = unique_pks(pairs, IdentityMapping::Mapped);
    let games_unmatched = unique_pks(pairs, IdentityMapping::Unmatched);
    let games_ambiguous = unique_pks(pairs, IdentityMapping::Ambiguous);
    let mut completeness = CompletenessCounts::default();
    for p in pairs
        .iter()
        .filter(|p| p.mapping == IdentityMapping::Mapped)
    {
        match p.completeness {
            Some(MarketCompleteness::L2Complete) => completeness.l2_complete += 1,
            Some(MarketCompleteness::L2Partial) => completeness.l2_partial += 1,
            Some(MarketCompleteness::TradesOnly) => completeness.trades_only += 1,
            Some(MarketCompleteness::CandlesOnly) => completeness.candles_only += 1,
            Some(MarketCompleteness::MarketMetadataOnly) => completeness.market_metadata_only += 1,
            None => {}
        }
    }
    let pbp_target_met = pbp_games_committed >= TARGET_MIN_PBP_GAMES;
    let pair_target_met = pairs_mapped >= TARGET_MIN_MAPPED_PAIRS;
    CorpusCoverage {
        mlb_games_discovered,
        pbp_games_committed,
        kalshi_markets_discovered,
        kalshi_artifacts_committed,
        pairs_mapped,
        pairs_unmatched,
        pairs_ambiguous,
        games_mapped,
        games_unmatched,
        games_ambiguous,
        completeness,
        target_min_pbp_games: TARGET_MIN_PBP_GAMES,
        target_min_mapped_pairs: TARGET_MIN_MAPPED_PAIRS,
        pbp_target_met,
        pair_target_met,
        notes: format!(
            "measured not manufactured; preferred PBP {} mapped-pairs {}; L2 never inferred from candles",
            TARGET_PREFERRED_PBP_GAMES, TARGET_PREFERRED_MAPPED_PAIRS
        ),
    }
}

fn unique_pks(pairs: &[GameMarketPair], mapping: IdentityMapping) -> usize {
    let mut s = std::collections::BTreeSet::new();
    for p in pairs.iter().filter(|p| p.mapping == mapping) {
        if let Some(pk) = &p.game_pk {
            s.insert(pk.clone());
        }
    }
    s.len()
}
