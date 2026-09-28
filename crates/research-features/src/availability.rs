//! Typed feature availability. TRADE never becomes bid/ask/L2.

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum FeatureAvailability {
    Available,
    UnavailableSource,
    InsufficientHistory,
    NotApplicable,
    Invalidated,
}

impl FeatureAvailability {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Available => "AVAILABLE",
            Self::UnavailableSource => "UNAVAILABLE_SOURCE",
            Self::InsufficientHistory => "INSUFFICIENT_HISTORY",
            Self::NotApplicable => "NOT_APPLICABLE",
            Self::Invalidated => "INVALIDATED",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum FeatureLayer {
    Baseball,
    StartingMarket,
    CurrentMarket,
    MarketHistory,
    PriceDynamics,
    EventResponse,
    Microstructure,
    FairValue,
    A1Targets,
    Outcome,
}

impl FeatureLayer {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Baseball => "BASEBALL",
            Self::StartingMarket => "STARTING_MARKET",
            Self::CurrentMarket => "CURRENT_MARKET",
            Self::MarketHistory => "MARKET_HISTORY",
            Self::PriceDynamics => "PRICE_DYNAMICS",
            Self::EventResponse => "EVENT_RESPONSE",
            Self::Microstructure => "MICROSTRUCTURE",
            Self::FairValue => "FAIR_VALUE",
            Self::A1Targets => "A1_TARGETS",
            Self::Outcome => "OUTCOME",
        }
    }
}
