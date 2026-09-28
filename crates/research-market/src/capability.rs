//! Downstream capability gates. TRADES_ONLY is usable; missing L2 is not invented.

use momento_research_ingest::types::IdentityMapping;
use serde::{Deserialize, Serialize};

use crate::types::{LifetimeCoverage, MarketCompleteness};

/// Identity for GameId-linked research. Ingest `MAPPED` with an observed
/// `game_pk` is [`MarketIdentityStatus::Matched`]. Never guessed from clocks.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MarketIdentityStatus {
    Matched,
    Ambiguous,
    Unmatched,
}

impl MarketIdentityStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Matched => "MATCHED",
            Self::Ambiguous => "AMBIGUOUS",
            Self::Unmatched => "UNMATCHED",
        }
    }

    pub fn from_ingest(mapping: IdentityMapping, game_pk: Option<&str>) -> Self {
        match mapping {
            IdentityMapping::Mapped if game_pk.is_some_and(|s| !s.is_empty()) => Self::Matched,
            IdentityMapping::Ambiguous => Self::Ambiguous,
            _ => Self::Unmatched,
        }
    }

    pub fn permits_game_id_research(self) -> bool {
        self == Self::Matched
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Presence {
    Observed,
    NotRequested,
    Unavailable,
    Malformed,
}

impl Presence {
    pub fn from_status_label(raw: Option<&str>) -> Self {
        match raw.map(|s| s.trim().to_ascii_uppercase()).as_deref() {
            Some("OBSERVED") | Some("OBSERVED_HISTORICAL") => Self::Observed,
            Some("NOT_REQUESTED") => Self::NotRequested,
            Some("MALFORMED") => Self::Malformed,
            Some(s) if s.contains("MALFORMED") => Self::Malformed,
            Some("UNAVAILABLE") | Some("") | None => Self::Unavailable,
            _ => Self::Unavailable,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Observed => "OBSERVED",
            Self::NotRequested => "NOT_REQUESTED",
            Self::Unavailable => "UNAVAILABLE",
            Self::Malformed => "MALFORMED",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum OrderbookCapability {
    L2Complete,
    L2Partial,
    L2HistoricalUnavailable,
    Unavailable,
}

impl OrderbookCapability {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::L2Complete => "L2_COMPLETE",
            Self::L2Partial => "L2_PARTIAL",
            Self::L2HistoricalUnavailable => "L2_HISTORICAL_UNAVAILABLE",
            Self::Unavailable => "UNAVAILABLE",
        }
    }

    pub fn from_completeness(c: MarketCompleteness) -> Self {
        match c {
            MarketCompleteness::L2Complete => Self::L2Complete,
            MarketCompleteness::L2Partial => Self::L2Partial,
            _ => Self::L2HistoricalUnavailable,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ResearchCapability {
    PricePathResearch,
    OrderbookMicrostructure,
    MakerFillSimulation,
    GameIdLinkedResearch,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum GateDecision {
    Allowed,
    Conditional,
    Blocked,
}

impl GateDecision {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Allowed => "ALLOWED",
            Self::Conditional => "CONDITIONAL",
            Self::Blocked => "BLOCKED",
        }
    }

    pub fn is_allowed(self) -> bool {
        self == Self::Allowed
    }

    pub fn is_blocked(self) -> bool {
        self == Self::Blocked
    }

    /// PRICE_PATH_RESEARCH CONDITIONAL (candles) is usable; BLOCKED is not.
    pub fn permits_price_path(self) -> bool {
        !self.is_blocked()
    }
}

/// W12/W13 (and later) must read this matrix. Do not infer L2 from trades/candles.
pub fn research_gate(
    cap: ResearchCapability,
    completeness: MarketCompleteness,
    identity: MarketIdentityStatus,
) -> GateDecision {
    match cap {
        ResearchCapability::PricePathResearch => match completeness {
            MarketCompleteness::L2Complete
            | MarketCompleteness::L2Partial
            | MarketCompleteness::TradesOnly => GateDecision::Allowed,
            MarketCompleteness::CandlesOnly => GateDecision::Conditional,
            MarketCompleteness::MarketMetadataOnly | MarketCompleteness::Unobserved => {
                GateDecision::Blocked
            }
        },
        ResearchCapability::OrderbookMicrostructure => match completeness {
            MarketCompleteness::L2Complete => GateDecision::Allowed,
            MarketCompleteness::L2Partial => GateDecision::Conditional,
            _ => GateDecision::Blocked,
        },
        ResearchCapability::MakerFillSimulation => match completeness {
            MarketCompleteness::L2Complete => GateDecision::Allowed,
            _ => GateDecision::Blocked,
        },
        ResearchCapability::GameIdLinkedResearch => {
            if identity.permits_game_id_research() {
                GateDecision::Allowed
            } else {
                GateDecision::Blocked
            }
        }
    }
}

/// Explicit missingness / capability card carried on every [`crate::types::MarketPath`].
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MarketCapabilityCard {
    pub market_identity_status: MarketIdentityStatus,
    pub price_observation_capability: MarketCompleteness,
    pub orderbook_capability: OrderbookCapability,
    pub trade_capability: Presence,
    pub candle_capability: Presence,
    pub settlement_capability: Presence,
    pub time_coverage: LifetimeCoverage,
    pub source_completeness: MarketCompleteness,
    pub price_path_research: GateDecision,
    pub orderbook_microstructure: GateDecision,
    pub maker_fill_simulation: GateDecision,
    pub game_id_linked_research: GateDecision,
}

impl MarketCapabilityCard {
    pub fn build(
        completeness: MarketCompleteness,
        identity_mapping: IdentityMapping,
        game_pk: Option<&str>,
        trade_capability: Presence,
        candle_capability: Presence,
        settlement_capability: Presence,
        time_coverage: LifetimeCoverage,
    ) -> Self {
        let market_identity_status = MarketIdentityStatus::from_ingest(identity_mapping, game_pk);
        Self {
            market_identity_status,
            price_observation_capability: completeness,
            orderbook_capability: OrderbookCapability::from_completeness(completeness),
            trade_capability,
            candle_capability,
            settlement_capability,
            time_coverage,
            source_completeness: completeness,
            price_path_research: research_gate(
                ResearchCapability::PricePathResearch,
                completeness,
                market_identity_status,
            ),
            orderbook_microstructure: research_gate(
                ResearchCapability::OrderbookMicrostructure,
                completeness,
                market_identity_status,
            ),
            maker_fill_simulation: research_gate(
                ResearchCapability::MakerFillSimulation,
                completeness,
                market_identity_status,
            ),
            game_id_linked_research: research_gate(
                ResearchCapability::GameIdLinkedResearch,
                completeness,
                market_identity_status,
            ),
        }
    }
}

impl Default for MarketCapabilityCard {
    fn default() -> Self {
        Self::build(
            MarketCompleteness::Unobserved,
            IdentityMapping::Unmatched,
            None,
            Presence::Unavailable,
            Presence::Unavailable,
            Presence::Unavailable,
            LifetimeCoverage::Unknown,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn trades_only_is_price_path_allowed_and_l2_blocked() {
        let id = MarketIdentityStatus::Unmatched;
        let c = MarketCompleteness::TradesOnly;
        assert_eq!(
            research_gate(ResearchCapability::PricePathResearch, c, id),
            GateDecision::Allowed
        );
        assert_eq!(
            research_gate(ResearchCapability::OrderbookMicrostructure, c, id),
            GateDecision::Blocked
        );
        assert_eq!(
            research_gate(ResearchCapability::MakerFillSimulation, c, id),
            GateDecision::Blocked
        );
    }

    #[test]
    fn unmatched_blocks_game_id_research() {
        assert!(!MarketIdentityStatus::Unmatched.permits_game_id_research());
        assert_eq!(
            research_gate(
                ResearchCapability::GameIdLinkedResearch,
                MarketCompleteness::TradesOnly,
                MarketIdentityStatus::Unmatched
            ),
            GateDecision::Blocked
        );
    }

    #[test]
    fn matched_permits_game_id_research() {
        assert!(MarketIdentityStatus::Matched.permits_game_id_research());
        assert_eq!(
            research_gate(
                ResearchCapability::GameIdLinkedResearch,
                MarketCompleteness::MarketMetadataOnly,
                MarketIdentityStatus::Matched
            ),
            GateDecision::Allowed
        );
    }

    #[test]
    fn l2_complete_and_partial_gates() {
        assert_eq!(
            research_gate(
                ResearchCapability::MakerFillSimulation,
                MarketCompleteness::L2Partial,
                MarketIdentityStatus::Matched
            ),
            GateDecision::Blocked
        );
        assert_eq!(
            research_gate(
                ResearchCapability::OrderbookMicrostructure,
                MarketCompleteness::L2Partial,
                MarketIdentityStatus::Matched
            ),
            GateDecision::Conditional
        );
        assert_eq!(
            research_gate(
                ResearchCapability::OrderbookMicrostructure,
                MarketCompleteness::L2Complete,
                MarketIdentityStatus::Matched
            ),
            GateDecision::Allowed
        );
        assert_eq!(
            research_gate(
                ResearchCapability::MakerFillSimulation,
                MarketCompleteness::L2Complete,
                MarketIdentityStatus::Matched
            ),
            GateDecision::Allowed
        );
    }
}
