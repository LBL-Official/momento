use momento_core::{
    ClientOrderId, GameId, PositionId, ReconciliationState,
    error::{OrderError, PositionError},
};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TrackerError {
    Position(PositionError),
    Order(OrderError),
    MissingPosition(PositionId),
    MissingOrder(ClientOrderId),
    SecondPositionForGame {
        game: GameId,
        existing: PositionId,
        attempted: PositionId,
    },
    NewExposureBlocked(ReconciliationState),
    ConflictingEvent,
    SettledCannotReopen,
}

impl From<PositionError> for TrackerError {
    fn from(value: PositionError) -> Self {
        match value {
            PositionError::SettledCannotReopen => Self::SettledCannotReopen,
            PositionError::ConflictingEvent => Self::ConflictingEvent,
            other => Self::Position(other),
        }
    }
}

impl From<OrderError> for TrackerError {
    fn from(value: OrderError) -> Self {
        Self::Order(value)
    }
}
