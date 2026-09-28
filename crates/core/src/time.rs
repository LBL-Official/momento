use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Current UTC from the OS clock without chrono's `clock` feature
/// (which pulls CoreFoundation on macOS).
pub fn utc_now() -> DateTime<Utc> {
    let dur = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    DateTime::<Utc>::from_timestamp(dur.as_secs() as i64, dur.subsec_nanos())
        .unwrap_or(DateTime::<Utc>::UNIX_EPOCH)
}

/// Exchange-assigned event time. Never silently substitute wall clock.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct ExchangeTimestamp(DateTime<Utc>);

impl ExchangeTimestamp {
    pub const fn from_utc(ts: DateTime<Utc>) -> Self {
        Self(ts)
    }

    pub const fn utc(self) -> DateTime<Utc> {
        self.0
    }
}

/// Local receipt time.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct ReceivedAt(DateTime<Utc>);

impl ReceivedAt {
    pub const fn from_utc(ts: DateTime<Utc>) -> Self {
        Self(ts)
    }

    pub const fn utc(self) -> DateTime<Utc> {
        self.0
    }

    pub fn now() -> Self {
        Self(utc_now())
    }
}

/// Local processing time.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct ProcessedAt(DateTime<Utc>);

impl ProcessedAt {
    pub const fn from_utc(ts: DateTime<Utc>) -> Self {
        Self(ts)
    }

    pub const fn utc(self) -> DateTime<Utc> {
        self.0
    }
}
