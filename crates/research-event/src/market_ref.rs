//! Identity-only market join keys. W2 does **not** reconstruct Kalshi paths (W3).
//!
//! Team A / Team B YES tickers may be stored as UNMAPPED Kalshi aliases so W3+
//! can attach price paths later. Starting price class is always UNVERIFIED here:
//! a ticker is not a market-open observation.

use serde::{Deserialize, Serialize};

use crate::identity::{CanonicalGameId, MlbMatchStatus, kalshi_alias_from_event_ticker};
use crate::w1_bridge::{RawMarketIdentity, StartingPriceClass};

/// Why a market identity row exists in W2 without a reconstructed price path.
pub const MARKET_REF_SCOPE: &str = "W2_IDENTITY_ONLY";
pub const MARKET_PATH_OWNER: &str = "W3";
pub const STARTING_PRICE_OWNER: &str = "W3_WITH_W1_CLASS";

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MlbMarketReference {
    pub canonical_game_id: CanonicalGameId,
    /// Home (Team A) YES contract identity, if a ticker was observed.
    pub team_a_yes: Option<RawMarketIdentity>,
    /// Away (Team B) YES contract identity, if a ticker was observed.
    pub team_b_yes: Option<RawMarketIdentity>,
    pub match_status: MlbMatchStatus,
    /// Always `StartingPriceUnverified` in W2. Never `MarketOpenPrice`.
    pub starting_price_class: StartingPriceClass,
    /// Explicit: W2 does not own reconstruction.
    pub reconstruction_status: String,
    pub scope: String,
    pub notes: Vec<String>,
}

impl MlbMarketReference {
    pub fn unmapped_from_tickers(
        canonical_game_id: CanonicalGameId,
        event_ticker: &str,
        team_a_yes_ticker: Option<&str>,
        team_b_yes_ticker: Option<&str>,
    ) -> Self {
        let team_a_yes = team_a_yes_ticker.map(|t| kalshi_alias_from_event_ticker(event_ticker, t));
        let team_b_yes = team_b_yes_ticker.map(|t| kalshi_alias_from_event_ticker(event_ticker, t));
        for id in team_a_yes.iter().chain(team_b_yes.iter()) {
            debug_assert_eq!(
                id.starting_price_class,
                StartingPriceClass::StartingPriceUnverified
            );
            debug_assert!(id.mlb_game_pk.is_none());
        }
        Self {
            canonical_game_id,
            team_a_yes,
            team_b_yes,
            match_status: MlbMatchStatus::Unmapped,
            starting_price_class: StartingPriceClass::StartingPriceUnverified,
            reconstruction_status: "UNAVAILABLE".into(),
            scope: MARKET_REF_SCOPE.into(),
            notes: vec![
                "W2 stores contract identity aliases only.".into(),
                "W3 owns Team A/B price paths, trades, candles, settlement.".into(),
                "First locally observed candle is not MARKET_OPEN_PRICE.".into(),
                "starting_price_observed | starting_price_derived | starting_price_unavailable \
                 remain W3/W1 classification work."
                    .into(),
            ],
        }
    }

    pub fn has_reconstructed_path(&self) -> bool {
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::identity::IdentityRegistry;

    #[test]
    fn identity_only_refs_are_unverified_and_unmapped() {
        let ident = IdentityRegistry::kalshi_only_unmapped(
            "KXMLBGAME-26JUN18NYYBOS",
            "KXMLBGAME-26JUN18NYYBOS-NYY",
        );
        let r = MlbMarketReference::unmapped_from_tickers(
            ident.canonical_game_id.clone(),
            "KXMLBGAME-26JUN18NYYBOS",
            Some("KXMLBGAME-26JUN18NYYBOS-NYY"),
            Some("KXMLBGAME-26JUN18NYYBOS-BOS"),
        );
        assert!(!r.has_reconstructed_path());
        assert_eq!(
            r.starting_price_class,
            StartingPriceClass::StartingPriceUnverified
        );
        assert_eq!(r.match_status, MlbMatchStatus::Unmapped);
        assert_eq!(r.reconstruction_status, "UNAVAILABLE");
        let a = r.team_a_yes.expect("team a");
        let b = r.team_b_yes.expect("team b");
        assert!(a.mlb_game_pk.is_none());
        assert!(b.mlb_game_pk.is_none());
        assert_ne!(a.ticker, b.ticker);
    }
}
