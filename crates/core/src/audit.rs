//! Append-only audit events. Do not overwrite.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::approval::{ApprovedTradeIntent, RiskRejectReason};
use crate::ids::{
    ClientOrderId, EventId, FillId, GameId, MarketId, PositionId, RiskDecisionId, SnapshotId,
    VenueOrderId,
};
use crate::money::{Money, Price};
use crate::order::OrderState;
use crate::reconciliation::{ReconcileOutcome, ReconciliationResult};
use crate::snapshot::WeeklyBankrollSnapshot;
use crate::time::{ExchangeTimestamp, ReceivedAt, utc_now};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct AuditMeta {
    pub event_id: EventId,
    pub recorded_at: DateTime<Utc>,
}

impl AuditMeta {
    pub fn now() -> Self {
        Self {
            event_id: EventId::generate(),
            recorded_at: utc_now(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum AuditEvent {
    WeeklyBankrollSnapshotCreated {
        meta: AuditMeta,
        snapshot: WeeklyBankrollSnapshot,
    },
    First80Observed {
        meta: AuditMeta,
        game_id: GameId,
        market_id: MarketId,
        exchange_ts: ExchangeTimestamp,
        received_at: ReceivedAt,
        mid: Option<Price>,
        bid: Option<Price>,
        ask: Option<Price>,
    },
    First81Confirmed {
        meta: AuditMeta,
        game_id: GameId,
        market_id: MarketId,
        exchange_ts: ExchangeTimestamp,
        received_at: ReceivedAt,
    },
    First89Observed {
        meta: AuditMeta,
        game_id: GameId,
        market_id: MarketId,
        exchange_ts: ExchangeTimestamp,
        received_at: ReceivedAt,
    },
    GameLocked {
        meta: AuditMeta,
        game_id: GameId,
        position_id: PositionId,
        exchange_ts: ExchangeTimestamp,
        received_at: ReceivedAt,
    },
    RiskApproval {
        meta: AuditMeta,
        intent: ApprovedTradeIntent,
        requested_exposure: Money,
        approved_exposure: Money,
        actual_exposure: Money,
        reserved_exposure: Money,
        remaining_capacity: Money,
        fee_estimate: Money,
        fee_model_id: crate::FeeModelId,
    },
    RiskRejection {
        meta: AuditMeta,
        decision_id: RiskDecisionId,
        snapshot_id: SnapshotId,
        game_id: GameId,
        position_id: Option<PositionId>,
        reason: RiskRejectReason,
        requested_exposure: Money,
        actual_exposure: Money,
        reserved_exposure: Money,
        remaining_capacity: Money,
        fee_estimate: Money,
    },
    OrderSubmitted {
        meta: AuditMeta,
        client_order_id: ClientOrderId,
        position_id: PositionId,
        game_id: GameId,
    },
    OrderAcknowledged {
        meta: AuditMeta,
        client_order_id: ClientOrderId,
    },
    OrderPartiallyFilled {
        meta: AuditMeta,
        fill_id: FillId,
        client_order_id: ClientOrderId,
        position_id: PositionId,
        premium: Money,
    },
    OrderFilled {
        meta: AuditMeta,
        fill_id: FillId,
        client_order_id: ClientOrderId,
        position_id: PositionId,
    },
    OrderCancelled {
        meta: AuditMeta,
        client_order_id: ClientOrderId,
    },
    OrderAmended {
        meta: AuditMeta,
        client_order_id: ClientOrderId,
    },
    OrderWorking {
        meta: AuditMeta,
        client_order_id: ClientOrderId,
    },
    OrderUnknown {
        meta: AuditMeta,
        client_order_id: ClientOrderId,
    },
    OrderRejected {
        meta: AuditMeta,
        client_order_id: ClientOrderId,
    },
    OrderExpired {
        meta: AuditMeta,
        client_order_id: ClientOrderId,
    },
    PositionUpdated {
        meta: AuditMeta,
        position_id: PositionId,
        game_id: GameId,
        actual_exposure: Money,
        filled_quantity: crate::money::Contracts,
        submitted_quantity: crate::money::Contracts,
        working_quantity: crate::money::Contracts,
        remaining_target: Money,
    },
    StopTriggered {
        meta: AuditMeta,
        position_id: PositionId,
        game_id: GameId,
    },
    LiquidationStarted {
        meta: AuditMeta,
        position_id: PositionId,
    },
    LiquidationFilled {
        meta: AuditMeta,
        fill_id: FillId,
        position_id: PositionId,
        fee: Money,
    },
    ReconciliationRequired {
        meta: AuditMeta,
        client_order_id: ClientOrderId,
    },
    ReconciliationRequested {
        meta: AuditMeta,
        client_order_id: ClientOrderId,
        position_id: PositionId,
        game_id: GameId,
    },
    ReconciliationStarted {
        meta: AuditMeta,
        client_order_id: ClientOrderId,
        position_id: PositionId,
    },
    ReconciliationCompleted {
        meta: AuditMeta,
        client_order_id: ClientOrderId,
        outcome: ReconcileOutcome,
    },
    ReconciliationFound {
        meta: AuditMeta,
        result: ReconciliationResult,
    },
    ReconciliationNotFound {
        meta: AuditMeta,
        result: ReconciliationResult,
    },
    ReconciliationAmbiguous {
        meta: AuditMeta,
        result: ReconciliationResult,
    },
    StateCorrection {
        meta: AuditMeta,
        position_id: PositionId,
        client_order_id: Option<ClientOrderId>,
        kind: StateCorrectionKind,
    },
    DuplicateEventIgnored {
        meta: AuditMeta,
        fill_id: Option<FillId>,
        client_order_id: Option<ClientOrderId>,
        venue_order_id: Option<VenueOrderId>,
    },
    ConflictingEventDetected {
        meta: AuditMeta,
        position_id: PositionId,
        client_order_id: ClientOrderId,
        local_status: OrderState,
        venue_status: Option<OrderState>,
    },
    PositionRebuilt {
        meta: AuditMeta,
        position_id: PositionId,
        game_id: GameId,
        filled_quantity: crate::money::Contracts,
    },
    OrderRebuilt {
        meta: AuditMeta,
        client_order_id: ClientOrderId,
        venue_order_id: Option<VenueOrderId>,
        state: OrderState,
    },
    FillRebuilt {
        meta: AuditMeta,
        fill_id: FillId,
        position_id: PositionId,
        client_order_id: ClientOrderId,
    },
    Settlement {
        meta: AuditMeta,
        position_id: PositionId,
        settlement_value: Money,
    },
    PositionClosed {
        meta: AuditMeta,
        position_id: PositionId,
        realized_pnl: Money,
    },
}

pub trait AuditLog {
    fn append(&mut self, event: AuditEvent);
    fn events(&self) -> &[AuditEvent];
}

#[derive(Clone, Debug, Default)]
pub struct InMemoryAuditLog {
    events: Vec<AuditEvent>,
}

impl AuditLog for InMemoryAuditLog {
    fn append(&mut self, event: AuditEvent) {
        self.events.push(event);
    }

    fn events(&self) -> &[AuditEvent] {
        &self.events
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum StateCorrectionKind {
    VenueFillApplied,
    RemainingWorkingReduced,
    OrderMarkedNotFound,
    UnknownPreserved,
}
