//! Observed / derived / unavailable field wrapper.
//!
//! Never use magic sentinels (-1, 999, "") for unknown baseball state.

use serde::{Deserialize, Serialize};

/// Provenance of a single reconstructed field.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum DataField<T> {
    Observed {
        value: T,
    },
    Derived {
        value: T,
        transform_version: String,
    },
    /// Join/guess. Forbidden as a substitute for official PBP.
    Inferred {
        value: T,
        confidence: String,
    },
    Unavailable {
        reason: String,
    },
}

impl<T> DataField<T> {
    pub fn observed(value: T) -> Self {
        Self::Observed { value }
    }

    pub fn derived(value: T, transform_version: impl Into<String>) -> Self {
        Self::Derived {
            value,
            transform_version: transform_version.into(),
        }
    }

    pub fn unavailable(reason: impl Into<String>) -> Self {
        Self::Unavailable {
            reason: reason.into(),
        }
    }

    pub fn as_value(&self) -> Option<&T> {
        match self {
            Self::Observed { value }
            | Self::Derived { value, .. }
            | Self::Inferred { value, .. } => Some(value),
            Self::Unavailable { .. } => None,
        }
    }

    pub fn into_value(self) -> Option<T> {
        match self {
            Self::Observed { value }
            | Self::Derived { value, .. }
            | Self::Inferred { value, .. } => Some(value),
            Self::Unavailable { .. } => None,
        }
    }

    pub fn is_unavailable(&self) -> bool {
        matches!(self, Self::Unavailable { .. })
    }

    pub fn map<U>(self, f: impl FnOnce(T) -> U) -> DataField<U> {
        match self {
            Self::Observed { value } => DataField::Observed { value: f(value) },
            Self::Derived {
                value,
                transform_version,
            } => DataField::Derived {
                value: f(value),
                transform_version,
            },
            Self::Inferred { value, confidence } => DataField::Inferred {
                value: f(value),
                confidence,
            },
            Self::Unavailable { reason } => DataField::Unavailable { reason },
        }
    }
}

impl<T: Clone> DataField<T> {
    pub fn cloned_value(&self) -> Option<T> {
        self.as_value().cloned()
    }
}
