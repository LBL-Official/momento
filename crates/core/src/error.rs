use thiserror::Error;

use crate::money::Money;

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum MomentoError {
    #[error(transparent)]
    Arithmetic(#[from] ArithmeticError),
    #[error(transparent)]
    Money(#[from] MoneyError),
    #[error(transparent)]
    Price(#[from] PriceError),
    #[error(transparent)]
    Time(#[from] TimeError),
    #[error(transparent)]
    Position(#[from] PositionError),
    #[error(transparent)]
    Order(#[from] OrderError),
    #[error(transparent)]
    Config(#[from] ConfigError),
    #[error(transparent)]
    Snapshot(#[from] SnapshotError),
    #[error(transparent)]
    Venue(#[from] VenueError),
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum ArithmeticError {
    #[error("integer overflow in financial arithmetic")]
    Overflow,
    #[error("division by zero in financial arithmetic")]
    DivisionByZero,
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum MoneyError {
    #[error("cents component must be in 0..100")]
    InvalidCents,
    #[error("money overflow")]
    Overflow,
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum PriceError {
    #[error("price {cents} cents is outside 0..=100")]
    OutOfRange { cents: u16 },
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum TimeError {
    #[error("local time does not exist in America/Los_Angeles")]
    InvalidLocalTime,
    #[error("local time is ambiguous in America/Los_Angeles (DST)")]
    AmbiguousLocalTime,
    #[error("invalid date for weekly boundary")]
    InvalidDate,
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum PositionError {
    #[error("fill would exceed approved fee-inclusive budget {budget} (used {used})")]
    BudgetExceeded { budget: Money, used: Money },
    #[error("entry is not permitted in the current game/position state")]
    EntryNotPermitted,
    #[error("cannot unlock GAME_LOCKED")]
    GameLockPermanent,
    #[error("submitted quantity must not be treated as filled")]
    SubmittedIsNotFilled,
    #[error("liquidation fill exceeds open quantity")]
    LiquidationExceedsOpen,
    #[error("unknown order state requires reconciliation before this action")]
    ReconciliationRequired,
    #[error("a second logical position for the same game is not permitted")]
    SecondPositionForGame,
    #[error("settled position cannot be reopened")]
    SettledCannotReopen,
    #[error("conflicting venue/local event; state is AMBIGUOUS")]
    ConflictingEvent,
    #[error("cannot rebind a filled position to a different MarketId or side")]
    FilledIdentityConflict,
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum OrderError {
    #[error("invalid order state transition from {from} to {to}")]
    InvalidTransition {
        from: &'static str,
        to: &'static str,
    },
    #[error("order is in UNKNOWN state; reconcile before retrying")]
    UnknownRequiresReconciliation,
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum ConfigError {
    #[error("trading mode is missing; refuse to start")]
    MissingMode,
    #[error("live mode is not implemented and cannot be armed")]
    LiveNotImplemented,
    #[error("live mode requires live.enabled = true and an explicit confirmation string")]
    LiveGateIncomplete,
    #[error("failed to parse config: {0}")]
    Parse(String),
    #[error("invalid config value: {0}")]
    Invalid(String),
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum VenueError {
    #[error("live Kalshi transport is disabled")]
    LiveDisabled,
    #[error("Kalshi production hosts are forbidden in this milestone")]
    ProductionForbidden,
    #[error("Kalshi sandbox requires MOMENTO_KALSHI_ENV=demo")]
    SandboxEnvRequired,
    #[error("Kalshi production requires MOMENTO_KALSHI_ENV=production")]
    ProductionEnvRequired,
    #[error("Kalshi credential environment does not match the requested host")]
    EnvironmentMismatch,
    #[error("Kalshi production transport is read-only; mutating request was not sent")]
    ProductionReadOnly,
    #[error("venue request timed out; order state is UNKNOWN")]
    Timeout,
    #[error("venue authentication failed")]
    AuthenticationFailed,
    #[error("malformed venue response: {0}")]
    MalformedResponse(String),
    #[error("unknown venue status {0}; mapped to UNKNOWN")]
    UnknownVenueStatus(String),
    #[error("unsupported or unresolved venue request: {0}")]
    Unsupported(String),
    #[error("ambiguous venue submission; reconcile before retrying")]
    AmbiguousSubmission,
    #[error("venue identity not mapped for ticker {0}")]
    IdentityNotMapped(String),
    #[error("venue value cannot be represented exactly in domain types: {0}")]
    Unrepresentable(String),
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum SnapshotError {
    #[error(transparent)]
    Time(#[from] TimeError),
    #[error(transparent)]
    Arithmetic(#[from] ArithmeticError),
    #[error("max_position_budget must be a positive integer of cents")]
    InvalidBudget,
}
