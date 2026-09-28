//! Layer 3 — historical L2 is unavailable. TRADE must not become bid/ask/OBI.

use crate::types::MicrostructureFeatures;

/// Current provider. A future HistoricalL2Provider can populate the same fields.
pub trait MarketMicrostructureProvider {
    fn snapshot(&self) -> MicrostructureFeatures;
}

pub struct TradeOnlyProvider;

impl MarketMicrostructureProvider for TradeOnlyProvider {
    fn snapshot(&self) -> MicrostructureFeatures {
        MicrostructureFeatures::trade_only()
    }
}

pub fn current_microstructure() -> MicrostructureFeatures {
    TradeOnlyProvider.snapshot()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::availability::FeatureAvailability;

    #[test]
    fn trade_only_never_invents_l2() {
        let m = current_microstructure();
        assert_eq!(m.bid, FeatureAvailability::UnavailableSource);
        assert_eq!(m.ask, FeatureAvailability::UnavailableSource);
        assert_eq!(m.mid, FeatureAvailability::UnavailableSource);
        assert_eq!(m.spread, FeatureAvailability::UnavailableSource);
        assert_eq!(m.obi_1, FeatureAvailability::UnavailableSource);
        assert_eq!(m.obi_z, FeatureAvailability::UnavailableSource);
        assert_eq!(m.ofi_1m, FeatureAvailability::UnavailableSource);
        assert_eq!(m.microprice, FeatureAvailability::UnavailableSource);
        assert_eq!(m.bid_depth_5, FeatureAvailability::UnavailableSource);
        assert_eq!(m.absorption, FeatureAvailability::UnavailableSource);
        assert_eq!(
            m.microstructure_residual,
            FeatureAvailability::UnavailableSource
        );
        assert_eq!(m.provider, "TRADE_ONLY");
    }
}
