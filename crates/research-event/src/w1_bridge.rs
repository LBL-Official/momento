//! W1 dependency bridge.
//!
//! W2 **consumes exported W1 types**. It does not fork `RawArtifactRef` /
//! `RawMarketIdentity`. It does not modify W1 files.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use momento_research_data::foundation::{
    IdentityMatchStatus, IdentityStubV1, LakeFileCapture, ProvenanceRecord, SourceTimestampKind,
    TimestampRole,
};

pub use momento_research_data::foundation::{
    IdentityMatchStatus as W1IdentityMatchStatus, RawArtifactRef, RawMarketIdentity,
    StartingPriceClass, W2_HANDOFF_NOTES as W1_CONTRACT_HANDOFF_NOTES,
};

/// Prefix for canonical ids of Kalshi-only (officially unmapped) games.
pub const KALSHI_UNMAPPED_PREFIX: &str = "kalshi:";

pub fn kalshi_unmapped_canonical_id(kalshi_game_id: &str) -> String {
    format!("{KALSHI_UNMAPPED_PREFIX}{kalshi_game_id}")
}

pub fn is_kalshi_unmapped_id(id: &str) -> bool {
    id.starts_with(KALSHI_UNMAPPED_PREFIX)
}

/// Build a W1 Kalshi identity row. Starting price is always UNVERIFIED here:
/// W2 does not reconstruct markets and must not treat a ticker as an open price.
pub fn unmapped_kalshi_identity(
    game_id: impl Into<String>,
    market_id: impl Into<String>,
    ticker: impl Into<String>,
    event_ticker: impl Into<String>,
    series: impl Into<String>,
) -> RawMarketIdentity {
    RawMarketIdentity {
        game_id: game_id.into(),
        market_id: market_id.into(),
        ticker: ticker.into(),
        event_ticker: event_ticker.into(),
        series: series.into(),
        mlb_game_pk: None,
        starting_price_class: StartingPriceClass::StartingPriceUnverified,
    }
}

/// W1 types W2 consumes (no W2 struct fork).
///
/// | W1 type | Fields | W2 use |
/// |---------|--------|--------|
/// | `RawArtifactRef` | sport: String (lake folder), path, sha256, layer, partition_date, observability | Re-export. Sport is **not** a domain enum. |
/// | `RawMarketIdentity` | game_id, market_id, ticker, event_ticker, series, mlb_game_pk, starting_price_class | Re-export. W2 never sets `MarketOpenPrice`. |
/// | `IdentityStubV1` | same ids + mlb_game_pk + match_status (UNMAPPED-only) + open_time | Adapter below. |
/// | `SourceTimestampKind` | TradeCreated, CandleEnd, VenueMetadata, IngestOnly, Unknown | **No PBP variant.** W2 uses local `MlbTimestampKind`; map via `w1_kind_for_mlb` → Unknown (never TradeCreated). |
/// | `StartingPriceClass` | MarketOpenPrice, FirstObservedPrice, FirstObservedTime, StartingPriceUnverified | W2 always Unverified on Kalshi aliases. |
///
/// Not a W1 incompatibility requiring a W1 patch: PBP clock is a W2 domain clock.
pub const W1_CONTRACT_FIELD_MAP: &str = "\
RawArtifactRef.sport = lake folder string (MLB), not SportCode.
RawMarketIdentity.starting_price_class is required; W2 sets STARTING_PRICE_UNVERIFIED.
IdentityStubV1.open_time is venue metadata, not MARKET_OPEN_PRICE, and is not a RawMarketIdentity field.
IdentityStubV1.match_status is UNMAPPED-only; W2 MlbMatchStatus is the richer local graph.";

/// Convert a W1 identity stub into W1 `RawMarketIdentity`.
///
/// Copied: game_id, market_id, ticker, event_ticker, series, mlb_game_pk.
/// Dropped: `match_status` (not on RawMarketIdentity; W1 stub is always UNMAPPED),
/// `open_time` (not on RawMarketIdentity; must not become MarketOpenPrice).
/// Set: `starting_price_class = StartingPriceUnverified`.
pub fn identity_from_w1_stub(stub: &IdentityStubV1) -> RawMarketIdentity {
    let _open_time_is_not_a_starting_price = &stub.open_time;
    RawMarketIdentity {
        game_id: stub.game_id.clone(),
        market_id: stub.market_id.clone(),
        ticker: stub.ticker.clone(),
        event_ticker: stub.event_ticker.clone(),
        series: stub.series.clone(),
        mlb_game_pk: stub.mlb_game_pk.clone(),
        starting_price_class: StartingPriceClass::StartingPriceUnverified,
    }
}

/// Inverse adapter. Loses `starting_price_class` (stub has no such field).
/// `open_time` is always `None` — W2 must not invent venue open times.
pub fn identity_to_w1_stub(id: &RawMarketIdentity) -> IdentityStubV1 {
    IdentityStubV1::unmapped(
        id.game_id.clone(),
        id.market_id.clone(),
        id.ticker.clone(),
        id.event_ticker.clone(),
        id.series.clone(),
    )
}

/// W1 `SourceTimestampKind` has no PBP variant. W2 does **not** patch W1.
/// Official PBP time is classified locally as [`MlbTimestampKind::PbpOfficial`].
/// Extending the W1 enum is a **W1 follow-up** (not required for W2 closeout).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MlbTimestampKind {
    /// Official PBP / StatsAPI play timestamp when present in source.
    PbpOfficial,
    /// Source-declared received time (if any).
    SourceReceived,
    /// Collector / ingest wall clock.
    Collector,
    /// Baseball clock (inning / half / outs) — not a wall timestamp.
    GameClock,
    /// Canonical event order: sequence number (and source time when present).
    CanonicalOrder,
}

pub const W1_TIMESTAMP_GAP: &str = "\
W1 SourceTimestampKind = TradeCreated | CandleEnd | VenueMetadata | IngestOnly | Unknown. \
W2 MlbTimestampKind::PbpOfficial is the PBP clock. Do not copy collector time into source_event_ts. \
Do not treat Kalshi trade created_time as PBP time (CTO-W4 sync). \
W1 follow-up (optional): add SourceTimestampKind::PbpOfficial in a new W1 schema version.";

pub fn w1_stub_is_unmapped(stub: &IdentityStubV1) -> bool {
    stub.mlb_game_pk.is_none() && stub.match_status == IdentityMatchStatus::Unmapped
}

/// Attach W1 provenance to a PBP raw file without using ingest time as play time.
pub fn pbp_file_provenance(
    source: impl Into<String>,
    path: impl Into<String>,
    checksum: Option<String>,
    retrieval: Option<DateTime<Utc>>,
    coverage_status: impl Into<String>,
) -> ProvenanceRecord {
    ProvenanceRecord::for_lake_file(
        source,
        path,
        checksum,
        LakeFileCapture {
            collector_version: Some(crate::versions::PARSER_VERSION.to_string()),
            schema_version: Some(crate::versions::SCHEMA_VERSION.to_string()),
            retrieval_timestamp: retrieval,
        },
        coverage_status,
        TimestampRole::Unknown,
        vec![
            "PBP source_timestamp is MlbTimestampKind::PbpOfficial, not W1 ingestion.".into(),
            W1_TIMESTAMP_GAP.into(),
        ],
    )
}

/// Map W2 PBP clock onto the closest W1 kind without claiming they are equal.
pub fn w1_kind_for_mlb(kind: MlbTimestampKind) -> SourceTimestampKind {
    match kind {
        MlbTimestampKind::Collector => SourceTimestampKind::IngestOnly,
        MlbTimestampKind::PbpOfficial
        | MlbTimestampKind::SourceReceived
        | MlbTimestampKind::GameClock
        | MlbTimestampKind::CanonicalOrder => SourceTimestampKind::Unknown,
    }
}

pub fn assert_not_market_open_price(id: &RawMarketIdentity) {
    debug_assert_ne!(
        id.starting_price_class,
        StartingPriceClass::MarketOpenPrice,
        "W2 must not claim MARKET_OPEN_PRICE"
    );
}

#[cfg(test)]
mod tests {
    use super::*;
    use momento_research_data::foundation::ObservabilityKind;

    #[test]
    fn consumes_exported_w1_identity_without_inventing_pk() {
        let s = IdentityStubV1::unmapped("g", "m", "t", "e", "KXMLBGAME");
        assert!(w1_stub_is_unmapped(&s));
        let raw = identity_from_w1_stub(&s);
        assert!(raw.mlb_game_pk.is_none());
        assert_eq!(
            raw.starting_price_class,
            StartingPriceClass::StartingPriceUnverified
        );
    }

    #[test]
    fn stub_open_time_does_not_become_market_open_price() {
        let mut s = IdentityStubV1::unmapped("g", "m", "t", "e", "KXMLBGAME");
        s.open_time = Some("2026-06-18T17:00:00Z".into());
        let raw = identity_from_w1_stub(&s);
        assert_eq!(
            raw.starting_price_class,
            StartingPriceClass::StartingPriceUnverified
        );
        assert_ne!(
            raw.starting_price_class,
            StartingPriceClass::MarketOpenPrice
        );
    }

    #[test]
    fn pbp_clock_is_not_silently_trade_created() {
        assert_eq!(
            w1_kind_for_mlb(MlbTimestampKind::PbpOfficial),
            SourceTimestampKind::Unknown
        );
    }

    #[test]
    fn w1_raw_artifact_sport_is_lake_folder_string() {
        let r = RawArtifactRef {
            sport: "MLB".into(),
            path: "orderbook/date=2026-06-18/orderbook.parquet".into(),
            sha256: None,
            layer: "orderbook".into(),
            partition_date: Some("2026-06-18".into()),
            observability: ObservabilityKind::Observed,
        };
        assert_eq!(r.sport, "MLB");
    }
}
