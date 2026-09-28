//! Sport-oriented source adapters. MLB is implemented; others are stubs.

use crate::error::IngestError;
use crate::source::{DiscoveredPartition, FetchOutcome, PartitionSource};
use crate::types::DateWindow;

pub const SPORT_MLB: &str = "MLB";
pub const SPORT_NBA: &str = "NBA";
pub const SPORT_WNBA: &str = "WNBA";
pub const SPORT_NCAAB: &str = "NCAAB";

/// Generic ingest contract. Sport-specific PBP/state logic stays outside this plane.
pub trait SportSourceAdapter: PartitionSource {
    fn sport(&self) -> &'static str;
}

pub struct MlbAdapter<S> {
    pub inner: S,
}

impl<S: PartitionSource> PartitionSource for MlbAdapter<S> {
    fn list_partitions(
        &self,
        window: &DateWindow,
    ) -> Result<Vec<DiscoveredPartition>, IngestError> {
        self.inner.list_partitions(window)
    }

    fn fetch(&self, partition: &DiscoveredPartition) -> Result<FetchOutcome, IngestError> {
        self.inner.fetch(partition)
    }
}

impl<S: PartitionSource> SportSourceAdapter for MlbAdapter<S> {
    fn sport(&self) -> &'static str {
        SPORT_MLB
    }
}

/// Future sports. Must not silently fabricate partitions.
pub struct UnimplementedSportAdapter {
    pub sport: &'static str,
}

impl PartitionSource for UnimplementedSportAdapter {
    fn list_partitions(
        &self,
        _window: &DateWindow,
    ) -> Result<Vec<DiscoveredPartition>, IngestError> {
        Ok(Vec::new())
    }

    fn fetch(&self, partition: &DiscoveredPartition) -> Result<FetchOutcome, IngestError> {
        Err(IngestError::SportNotImplemented(format!(
            "{} adapter not implemented; refusing {}",
            self.sport, partition.partition_id
        )))
    }
}

impl SportSourceAdapter for UnimplementedSportAdapter {
    fn sport(&self) -> &'static str {
        self.sport
    }
}

pub fn nba_stub() -> UnimplementedSportAdapter {
    UnimplementedSportAdapter { sport: SPORT_NBA }
}

pub fn wnba_stub() -> UnimplementedSportAdapter {
    UnimplementedSportAdapter { sport: SPORT_WNBA }
}

pub fn ncaab_stub() -> UnimplementedSportAdapter {
    UnimplementedSportAdapter { sport: SPORT_NCAAB }
}
