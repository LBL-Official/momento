//! Typed errors for the research backtest control plane.

use thiserror::Error;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BacktestErrorCode {
    UnknownStrategy,
    UnsupportedSeries,
    InvalidDateRange,
    InvalidEntryRange,
    UnsupportedExitOverride,
    DatasetMissing,
    DatasetPartial,
    DatasetInvalid,
    ReplayError,
    ResultWriteError,
    GoogleSheetsError,
    InvalidStatus,
    IdempotentHit,
}

impl BacktestErrorCode {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::UnknownStrategy => "UNKNOWN_STRATEGY",
            Self::UnsupportedSeries => "UNSUPPORTED_SERIES",
            Self::InvalidDateRange => "INVALID_DATE_RANGE",
            Self::InvalidEntryRange => "INVALID_ENTRY_RANGE",
            Self::UnsupportedExitOverride => "UNSUPPORTED_EXIT_OVERRIDE",
            Self::DatasetMissing => "DATASET_MISSING",
            Self::DatasetPartial => "DATASET_PARTIAL",
            Self::DatasetInvalid => "DATASET_INVALID",
            Self::ReplayError => "REPLAY_ERROR",
            Self::ResultWriteError => "RESULT_WRITE_ERROR",
            Self::GoogleSheetsError => "GOOGLE_SHEETS_ERROR",
            Self::InvalidStatus => "INVALID_STATUS",
            Self::IdempotentHit => "IDEMPOTENT_HIT",
        }
    }
}

impl std::fmt::Display for BacktestErrorCode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

#[derive(Debug, Error)]
pub enum BacktestError {
    #[error("{code}: {message}")]
    Coded {
        code: BacktestErrorCode,
        message: String,
    },
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
    #[error(transparent)]
    Csv(#[from] csv::Error),
}

impl BacktestError {
    pub fn coded(code: BacktestErrorCode, message: impl Into<String>) -> Self {
        Self::Coded {
            code,
            message: message.into(),
        }
    }

    pub fn code(&self) -> Option<BacktestErrorCode> {
        match self {
            Self::Coded { code, .. } => Some(*code),
            _ => None,
        }
    }

    pub fn code_str(&self) -> &str {
        match self {
            Self::Coded { code, .. } => code.as_str(),
            Self::Io(_) => "RESULT_WRITE_ERROR",
            Self::Json(_) => "RESULT_WRITE_ERROR",
            Self::Csv(_) => "GOOGLE_SHEETS_ERROR",
        }
    }
}
