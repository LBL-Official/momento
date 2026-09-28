//! Completeness is the minimum honest class. Never upgrade candles/PIT to L2.

use crate::types::{MarketCompleteness, MarketObservationKind, MarketPoint};

#[derive(Clone, Copy, Debug, Default)]
pub struct ObservationFlags {
    pub has_metadata: bool,
    pub has_trade: bool,
    pub has_candle: bool,
    pub has_game_time_l2_snapshot: bool,
    pub has_game_time_l2_delta: bool,
    pub l2_delta_ungapped: bool,
}

impl ObservationFlags {
    pub fn from_points(points: &[MarketPoint], has_metadata: bool) -> Self {
        let mut f = Self {
            has_metadata,
            ..Self::default()
        };
        for p in points {
            match p.kind {
                MarketObservationKind::Trade => f.has_trade = true,
                MarketObservationKind::Candle1m => f.has_candle = true,
                MarketObservationKind::L2Snapshot => f.has_game_time_l2_snapshot = true,
                MarketObservationKind::L2Delta => f.has_game_time_l2_delta = true,
                MarketObservationKind::TopOfBook
                | MarketObservationKind::Metadata
                | MarketObservationKind::RestPitSnapshot => {}
            }
        }
        f
    }
}

/// Written L2_COMPLETE definition (SPEC): game-time snapshot AND ungapped delta stream.
/// A single PIT/WS snapshot never satisfies this.
pub fn l2_complete(flags: &ObservationFlags) -> bool {
    flags.has_game_time_l2_snapshot && flags.has_game_time_l2_delta && flags.l2_delta_ungapped
}

pub fn classify(flags: &ObservationFlags) -> MarketCompleteness {
    if l2_complete(flags) {
        return MarketCompleteness::L2Complete;
    }
    if flags.has_game_time_l2_snapshot || flags.has_game_time_l2_delta {
        return MarketCompleteness::L2Partial;
    }
    if flags.has_trade {
        return MarketCompleteness::TradesOnly;
    }
    if flags.has_candle {
        return MarketCompleteness::CandlesOnly;
    }
    if flags.has_metadata {
        return MarketCompleteness::MarketMetadataOnly;
    }
    MarketCompleteness::Unobserved
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use momento_research_data::foundation::ObservabilityKind;

    fn pt(kind: MarketObservationKind) -> MarketPoint {
        MarketPoint {
            ticker: "T".into(),
            event_ticker: "E".into(),
            market_id: "m".into(),
            exchange_timestamp: Utc::now(),
            yes_bid_cents: None,
            yes_ask_cents: None,
            last_trade_cents: None,
            quantity_hundredths: None,
            trade_id: None,
            candle_ohlc: None,
            kind,
            observability: ObservabilityKind::Observed,
            source: None,
            source_record_id: None,
            retrieval_timestamp: None,
        }
    }

    #[test]
    fn trades_win_even_if_candles_exist() {
        let flags = ObservationFlags::from_points(
            &[
                pt(MarketObservationKind::Trade),
                pt(MarketObservationKind::Candle1m),
            ],
            true,
        );
        assert_eq!(classify(&flags), MarketCompleteness::TradesOnly);
    }

    #[test]
    fn candles_only_never_l2() {
        let flags = ObservationFlags::from_points(&[pt(MarketObservationKind::Candle1m)], true);
        assert_eq!(classify(&flags), MarketCompleteness::CandlesOnly);
        assert_ne!(classify(&flags), MarketCompleteness::L2Complete);
        assert_ne!(classify(&flags), MarketCompleteness::L2Partial);
    }

    #[test]
    fn metadata_without_points() {
        let flags = ObservationFlags::from_points(&[], true);
        assert_eq!(classify(&flags), MarketCompleteness::MarketMetadataOnly);
    }

    #[test]
    fn one_snapshot_is_not_l2_complete() {
        let mut flags =
            ObservationFlags::from_points(&[pt(MarketObservationKind::L2Snapshot)], true);
        flags.l2_delta_ungapped = false;
        assert_eq!(classify(&flags), MarketCompleteness::L2Partial);
        assert!(!l2_complete(&flags));
    }

    #[test]
    fn pit_kind_does_not_count_as_l2() {
        let flags =
            ObservationFlags::from_points(&[pt(MarketObservationKind::RestPitSnapshot)], true);
        assert_eq!(classify(&flags), MarketCompleteness::MarketMetadataOnly);
    }
}
