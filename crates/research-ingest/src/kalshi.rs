//! Kalshi discovery / catalog. Lands source artifacts only — never MarketState.

use std::collections::BTreeMap;
use std::path::PathBuf;

use chrono::{DateTime, NaiveDate, Utc};
use momento_research_data::manifest::{CompletenessStatus, DailyManifest, list_manifest_dates};
use momento_research_data::paths::ResearchPaths;
use momento_research_data::sport::{ResearchSeason, ResearchSport};
use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::error::IngestError;
use crate::land::{LandResult, land_at_dest};
use crate::paths::{IngestPaths, write_json_atomic};
use crate::source::FetchOutcome;
use crate::types::{
    CoverageRow, DateWindow, IdentityMapping, IdentityRow, MarketCompleteness, PartitionStatus,
    SOURCE_KALSHI, SOURCE_KALSHI_DISCOVERY, SOURCE_KALSHI_SETTLEMENT,
};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct DiscoveredMarket {
    pub date: NaiveDate,
    pub ticker: String,
    pub event_ticker: Option<String>,
    pub series: Option<String>,
    pub mapping: IdentityMapping,
    pub observed_game_pk: Option<String>,
    pub completeness: Option<crate::types::MarketCompleteness>,
    pub notes: String,
    #[serde(default)]
    pub open_time: Option<String>,
    #[serde(default)]
    pub close_time: Option<String>,
    #[serde(default)]
    pub result: Option<String>,
    #[serde(default)]
    pub settlement_ts: Option<String>,
    #[serde(default)]
    pub settlement_value_dollars: Option<String>,
    #[serde(default)]
    pub status: Option<String>,
}

pub trait KalshiDiscoverySource {
    fn discover(&self, window: &DateWindow) -> Result<Vec<DiscoveredMarket>, IngestError>;
    fn fetch_artifact(&self, market: &DiscoveredMarket) -> Result<FetchOutcome, IngestError>;
    /// `None` means the source has no dedicated candle fetch; caller may use `fetch_artifact`.
    fn fetch_candlesticks(
        &self,
        market: &DiscoveredMarket,
    ) -> Result<Option<FetchOutcome>, IngestError> {
        let _ = market;
        Ok(None)
    }
}

#[derive(Clone, Debug, Default)]
pub struct FixtureKalshiSource {
    pub markets: Vec<DiscoveredMarket>,
    pub artifacts: BTreeMap<String, FetchOutcome>,
}

impl KalshiDiscoverySource for FixtureKalshiSource {
    fn discover(&self, window: &DateWindow) -> Result<Vec<DiscoveredMarket>, IngestError> {
        Ok(self
            .markets
            .iter()
            .filter(|m| window.contains(m.date))
            .cloned()
            .collect())
    }

    fn fetch_artifact(&self, market: &DiscoveredMarket) -> Result<FetchOutcome, IngestError> {
        self.artifacts.get(&market.ticker).cloned().ok_or_else(|| {
            IngestError::SourceFailure(format!("no kalshi fixture {}", market.ticker))
        })
    }
}

/// Network discovery is not implied by compiling this crate.
#[derive(Clone, Debug, Default)]
pub struct BlockedNetworkKalshiSource;

impl KalshiDiscoverySource for BlockedNetworkKalshiSource {
    fn discover(&self, _window: &DateWindow) -> Result<Vec<DiscoveredMarket>, IngestError> {
        Ok(Vec::new())
    }

    fn fetch_artifact(&self, market: &DiscoveredMarket) -> Result<FetchOutcome, IngestError> {
        Ok(FetchOutcome::Failure(format!(
            "Kalshi network discovery BLOCKED; ticker {} not fetched",
            market.ticker
        )))
    }
}

pub fn catalog_kalshi_manifests(
    lake_root: &std::path::Path,
    season_label: &str,
) -> Result<Vec<CoverageRow>, IngestError> {
    let paths = ResearchPaths {
        root: lake_root.to_path_buf(),
        season: ResearchSeason {
            label: season_label.to_string(),
        },
    };
    let dates = list_manifest_dates(&paths, ResearchSport::Mlb).map_err(IngestError::from)?;
    let mut rows = Vec::new();
    for date in dates {
        rows.push(row_for_date(&paths, date)?);
    }
    Ok(rows)
}

fn row_for_date(paths: &ResearchPaths, date: NaiveDate) -> Result<CoverageRow, IngestError> {
    let Some(m) =
        DailyManifest::read(paths, ResearchSport::Mlb, date).map_err(IngestError::from)?
    else {
        return Ok(CoverageRow {
            date: date.to_string(),
            source: SOURCE_KALSHI.into(),
            partition_id: date.to_string(),
            status: PartitionStatus::Unavailable,
            sha256: None,
            path: None,
            notes: "manifest listed but unreadable as missing".into(),
        });
    };
    let (status, notes) = match m.completeness_status {
        CompletenessStatus::Complete => (
            PartitionStatus::Complete,
            format!("COMPLETE_V1_OBSERVED markets={}", m.markets_collected),
        ),
        CompletenessStatus::Missing => (
            PartitionStatus::Unavailable,
            "MISSING_V1_OBSERVED (not fabricated COMPLETE)".into(),
        ),
        CompletenessStatus::Partial => (
            PartitionStatus::Failed,
            "PARTIAL_V1_OBSERVED (not upgraded to COMPLETE)".into(),
        ),
        CompletenessStatus::Invalid => (PartitionStatus::Failed, "INVALID_V1_OBSERVED".into()),
    };
    Ok(CoverageRow {
        date: date.to_string(),
        source: SOURCE_KALSHI.into(),
        partition_id: date.to_string(),
        status,
        sha256: m.checksums.values().next().cloned(),
        path: Some(
            paths
                .manifest_path(ResearchSport::Mlb, date)
                .display()
                .to_string(),
        ),
        notes,
    })
}

pub fn wrap_kalshi_discovery_envelope(
    market: &DiscoveredMarket,
    payload: serde_json::Value,
    retrieved_at: DateTime<Utc>,
) -> Result<Vec<u8>, IngestError> {
    if market.ticker.trim().is_empty() {
        return Err(IngestError::SourceFailure(
            "refusing empty Kalshi ticker (never fabricate)".into(),
        ));
    }
    let envelope = json!({
        "envelope_version": "INGEST.KALSHI.DISCOVERY.1.0.0",
        "fixture_kind": "HISTORICAL_SOURCE",
        "source": SOURCE_KALSHI_DISCOVERY,
        "ticker": market.ticker,
        "event_ticker": market.event_ticker,
        "series": market.series,
        "identity_mapping": market.mapping,
        "observed_game_pk": market.observed_game_pk,
        "retrieved_at": retrieved_at.to_rfc3339(),
        "payload": payload,
    });
    Ok(serde_json::to_vec(&envelope)?)
}

pub fn land_kalshi_discovery(
    paths: &IngestPaths,
    market: &DiscoveredMarket,
    bytes: &[u8],
) -> Result<LandResult, IngestError> {
    let dest = paths.landing_kalshi_discovery(market.date, &market.ticker);
    land_at_dest(dest, bytes, &market.ticker)
}

/// Venue catalog fields only. Missing result stays missing. Never box-score fill.
pub fn land_market_settlement(
    paths: &IngestPaths,
    market: &DiscoveredMarket,
) -> Result<PathBuf, IngestError> {
    let dest = paths.landing_kalshi_settlement(market.date, &market.ticker);
    write_json_atomic(
        &dest,
        &json!({
            "envelope_version": "INGEST.KALSHI.SETTLEMENT.1.0.0",
            "fixture_kind": "HISTORICAL_SOURCE",
            "source": SOURCE_KALSHI_SETTLEMENT,
            "ticker": market.ticker,
            "event_ticker": market.event_ticker,
            "date": market.date.to_string(),
            "result": market.result,
            "settlement_ts": market.settlement_ts,
            "settlement_value_dollars": market.settlement_value_dollars,
            "open_time": market.open_time,
            "close_time": market.close_time,
            "status": market.status,
        }),
    )?;
    Ok(dest)
}

pub fn completeness_from_payload(payload: &serde_json::Value) -> Option<MarketCompleteness> {
    serde_json::from_value(payload.get("completeness")?.clone()).ok()
}

pub fn completeness_from_landed_bytes(bytes: &[u8]) -> Option<MarketCompleteness> {
    let v: serde_json::Value = serde_json::from_slice(bytes).ok()?;
    completeness_from_payload(v.get("payload").unwrap_or(&v))
}

pub const HISTORICAL_CANDLES_ENVELOPE: &str = "INGEST.KALSHI.HISTORICAL_CANDLES.1.0.0";

pub fn status_is_observed(status: Option<&str>) -> bool {
    status.is_some_and(|s| s.starts_with("OBSERVED"))
}

fn payload_of(root: &serde_json::Value) -> &serde_json::Value {
    root.get("payload").unwrap_or(root)
}

pub fn status_from_json(root: &serde_json::Value, key: &str) -> Option<String> {
    let payload = payload_of(root);
    payload
        .get(key)
        .and_then(|v| v.as_str())
        .or_else(|| root.get(key).and_then(|v| v.as_str()))
        .map(str::to_string)
}

pub fn file_status_observed(path: &std::path::Path, key: &str) -> bool {
    let Ok(bytes) = std::fs::read(path) else {
        return false;
    };
    let Ok(v) = serde_json::from_slice::<serde_json::Value>(&bytes) else {
        return false;
    };
    status_is_observed(status_from_json(&v, key).as_deref())
}

pub fn landed_trades_observed(paths: &IngestPaths, market: &DiscoveredMarket) -> bool {
    let dest = paths.landing_kalshi_discovery(market.date, &market.ticker);
    if dest.exists()
        && let Ok(bytes) = std::fs::read(&dest)
        && let Ok(v) = serde_json::from_slice::<serde_json::Value>(&bytes)
        && status_is_observed(status_from_json(&v, "trades_status").as_deref())
    {
        return true;
    }
    file_status_observed(
        &paths.landing_kalshi_matched_trades(market.date, &market.ticker),
        "trades_status",
    )
}

pub fn landed_candles_observed(paths: &IngestPaths, market: &DiscoveredMarket) -> bool {
    let dest = paths.landing_kalshi_discovery(market.date, &market.ticker);
    if dest.exists()
        && let Ok(bytes) = std::fs::read(&dest)
        && let Ok(v) = serde_json::from_slice::<serde_json::Value>(&bytes)
        && status_is_observed(status_from_json(&v, "candles_status").as_deref())
    {
        return true;
    }
    file_status_observed(
        &paths.landing_kalshi_candles(market.date, &market.ticker),
        "candles_status",
    )
}

pub fn candlesticks_array(value: &serde_json::Value) -> Vec<serde_json::Value> {
    if let Some(arr) = value.as_array() {
        return arr.clone();
    }
    value
        .get("candlesticks")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
}

pub fn wrap_historical_candles(
    market: &DiscoveredMarket,
    candlesticks: Vec<serde_json::Value>,
    status: &str,
    start_ts: i64,
    end_ts: i64,
    retrieved_at: DateTime<Utc>,
) -> Result<Vec<u8>, IngestError> {
    let envelope = json!({
        "envelope_version": HISTORICAL_CANDLES_ENVELOPE,
        "fixture_kind": "HISTORICAL_SOURCE",
        "source": crate::types::SOURCE_KALSHI_HISTORICAL_CANDLES,
        "ticker": market.ticker,
        "event_ticker": market.event_ticker,
        "official_date": market.date.to_string(),
        "retrieved_at": retrieved_at.to_rfc3339(),
        "period_interval": 1,
        "window_start_ts": start_ts,
        "window_end_ts": end_ts,
        "candles_status": status,
        "candle_count": candlesticks.len(),
        "l2": "HISTORICAL_L2_UNAVAILABLE",
        "candlesticks": candlesticks,
    });
    Ok(serde_json::to_vec(&envelope)?)
}

pub fn land_historical_candles(
    paths: &IngestPaths,
    market: &DiscoveredMarket,
    bytes: &[u8],
) -> Result<LandResult, IngestError> {
    let dest = paths.landing_kalshi_candles(market.date, &market.ticker);
    land_at_dest(dest, bytes, &IngestPaths::ticker_file_stem(&market.ticker))
}

pub fn wrap_historical_trades_sidecar(
    market: &DiscoveredMarket,
    trades: Vec<serde_json::Value>,
    status: &str,
    retrieved_at: DateTime<Utc>,
) -> Result<Vec<u8>, IngestError> {
    let envelope = json!({
        "envelope_version": "INGEST.KALSHI.HISTORICAL_TRADES.1.0.0",
        "fixture_kind": "HISTORICAL_SOURCE",
        "source": crate::types::SOURCE_KALSHI_MATCHED_TRADES,
        "ticker": market.ticker,
        "event_ticker": market.event_ticker,
        "game_pk": market.observed_game_pk,
        "identity_mapping": market.mapping,
        "official_date": market.date.to_string(),
        "retrieved_at": retrieved_at.to_rfc3339(),
        "trades_status": status,
        "canonical_trade_count": trades.len(),
        "l2": "HISTORICAL_L2_UNAVAILABLE",
        "trades": trades,
    });
    Ok(serde_json::to_vec(&envelope)?)
}

pub fn land_historical_trades(
    paths: &IngestPaths,
    market: &DiscoveredMarket,
    bytes: &[u8],
) -> Result<LandResult, IngestError> {
    let dest = paths.landing_kalshi_matched_trades(market.date, &market.ticker);
    land_at_dest(dest, bytes, &IngestPaths::ticker_file_stem(&market.ticker))
}

pub fn candles_payload_unavailable(value: &serde_json::Value) -> bool {
    if status_from_json(value, "candles_status").as_deref() == Some("UNAVAILABLE") {
        return true;
    }
    let node = value.get("candlesticks").unwrap_or(value);
    node.get("unavailable").and_then(|v| v.as_bool()) == Some(true)
}

pub fn trades_array(value: &serde_json::Value) -> Option<Vec<serde_json::Value>> {
    let payload = payload_of(value);
    let trades = payload.get("trades").unwrap_or(payload);
    trades.as_array().cloned()
}

pub fn identity_row(market: &DiscoveredMarket) -> IdentityRow {
    IdentityRow {
        source: SOURCE_KALSHI_DISCOVERY.into(),
        ticker: market.ticker.clone(),
        partition_id: market.ticker.clone(),
        mapping: market.mapping,
        observed_game_pk: market.observed_game_pk.clone(),
        notes: if market.mapping == IdentityMapping::Unmatched {
            "ticker preserved as observed; gamePk not inferred from ticker text".into()
        } else if market.mapping == IdentityMapping::Ambiguous {
            "AMBIGUOUS retained; not resolved by guesswork".into()
        } else {
            market.notes.clone()
        },
    }
}

#[cfg(test)]
mod landing_status_tests {
    use super::*;
    use chrono::NaiveDate;

    fn market() -> DiscoveredMarket {
        DiscoveredMarket {
            date: NaiveDate::from_ymd_opt(2026, 6, 18).unwrap(),
            ticker: "KXMLBGAME-X-NYY".into(),
            event_ticker: Some("KXMLBGAME-X".into()),
            series: Some("KXMLBGAME".into()),
            mapping: IdentityMapping::Unmatched,
            observed_game_pk: None,
            completeness: Some(MarketCompleteness::MarketMetadataOnly),
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
    fn settlement_sidecar_copies_venue_result_only() {
        let tmp = tempfile::tempdir().unwrap();
        let paths = IngestPaths::new(tmp.path());
        let mut m = market();
        m.result = Some("yes".into());
        m.settlement_ts = Some("2026-06-19T01:57:28Z".into());
        let dest = land_market_settlement(&paths, &m).unwrap();
        let body: serde_json::Value =
            serde_json::from_slice(&std::fs::read(&dest).unwrap()).unwrap();
        assert_eq!(body["result"], "yes");
        assert_eq!(body["source"], SOURCE_KALSHI_SETTLEMENT);
        assert_ne!(body["result"], "no");
    }

    #[test]
    fn sidecar_trades_count_as_observed_without_rewriting_envelope() {
        let tmp = tempfile::tempdir().unwrap();
        let paths = IngestPaths::new(tmp.path());
        let m = market();
        let dest = paths.landing_kalshi_discovery(m.date, &m.ticker);
        std::fs::create_dir_all(dest.parent().unwrap()).unwrap();
        std::fs::write(
            &dest,
            br#"{"payload":{"completeness":"MARKET_METADATA_ONLY","trades_status":"NOT_REQUESTED","candles_status":"NOT_REQUESTED"}}"#,
        )
        .unwrap();
        assert!(!landed_trades_observed(&paths, &m));
        assert!(!landed_candles_observed(&paths, &m));
        let bytes = wrap_historical_trades_sidecar(
            &m,
            vec![json!({"ticker":"KXMLBGAME-X-NYY"})],
            "OBSERVED_HISTORICAL",
            Utc::now(),
        )
        .unwrap();
        land_historical_trades(&paths, &m, &bytes).unwrap();
        assert!(landed_trades_observed(&paths, &m));
        assert!(!landed_candles_observed(&paths, &m));
    }

    #[test]
    fn envelope_unavailable_candles_do_not_count_as_observed() {
        let tmp = tempfile::tempdir().unwrap();
        let paths = IngestPaths::new(tmp.path());
        let m = market();
        let dest = paths.landing_kalshi_discovery(m.date, &m.ticker);
        std::fs::create_dir_all(dest.parent().unwrap()).unwrap();
        std::fs::write(
            &dest,
            br#"{"payload":{"completeness":"TRADES_ONLY","trades_status":"OBSERVED_HISTORICAL","candles_status":"UNAVAILABLE"}}"#,
        )
        .unwrap();
        assert!(landed_trades_observed(&paths, &m));
        assert!(!landed_candles_observed(&paths, &m));
    }
}
