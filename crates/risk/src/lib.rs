//! Risk engine: sole authority for approving entry exposure.
//!
//! Does not submit venue orders. Does not mutate fill-authoritative position state.

#![forbid(unsafe_code)]

mod capacity;
mod config;
mod engine;
mod fees;
mod reservation;

use momento_core::{
    ApprovedTradeIntent, ClientOrderId, KillSwitch, Position, Price, ReconciliationState,
    RiskDecision, RiskDecisionId, RiskGrant, RiskRejectReason, SnapshotId, TradeIntent,
    WeeklyBankrollSnapshot,
};

pub use capacity::{AvailableCapacity, SnapshotPaperBalance};
pub use config::RiskConfig;
pub use engine::{PaperRiskEngine, RiskPersist, SessionLedger};
pub use fees::{FeeEstimateError, FeeModel, ZeroFeeModel, size_entry};
pub use reservation::Reservation;

pub struct RiskLimits {
    pub max_entry_price: Price,
}

pub trait RiskEngine {
    fn evaluate_entry(
        &self,
        intent: &TradeIntent,
        position: &Position,
        snapshot: &WeeklyBankrollSnapshot,
        recon: ReconciliationState,
        kill_switch: KillSwitch,
    ) -> RiskDecision;
}

/// M1 scaffolding retained. Uses [`ZeroFeeModel`] rather than a raw `Money::ZERO`.
pub struct InvariantRisk {
    pub limits: RiskLimits,
    fees: ZeroFeeModel,
}

impl InvariantRisk {
    pub fn new(max_entry_price: Price) -> Self {
        Self {
            limits: RiskLimits { max_entry_price },
            fees: ZeroFeeModel,
        }
    }
}

impl RiskEngine for InvariantRisk {
    fn evaluate_entry(
        &self,
        intent: &TradeIntent,
        position: &Position,
        snapshot: &WeeklyBankrollSnapshot,
        recon: ReconciliationState,
        kill_switch: KillSwitch,
    ) -> RiskDecision {
        let decision_id = RiskDecisionId::generate();
        let snapshot_id = snapshot.snapshot_id();
        let reject = |reason: RiskRejectReason| RiskDecision::Rejected {
            decision_id,
            reason,
            snapshot_id,
        };

        if position.snapshot_id() != snapshot_id {
            return reject(RiskRejectReason::SnapshotMismatch);
        }
        if position.game_id() != intent.build.game_id || position.id() != intent.build.position_id {
            return reject(RiskRejectReason::DuplicateGamePosition);
        }
        if kill_switch.is_tripped() {
            return reject(RiskRejectReason::KillSwitch);
        }
        if recon.blocks_new_exposure() {
            return reject(RiskRejectReason::ReconciliationRequired);
        }
        if position.game_lock().is_locked() {
            return reject(RiskRejectReason::GameLocked);
        }
        if !position.can_attempt_entry() {
            if position.entry_price_gate() == momento_core::EntryPriceGate::PausedAboveMaxPrice {
                return reject(RiskRejectReason::EntryPausedAboveMaxPrice);
            }
            return reject(RiskRejectReason::GameLocked);
        }
        if intent.build.limit_price > self.limits.max_entry_price {
            return reject(RiskRejectReason::InvalidPrice);
        }

        let remaining = match position.actionable_remaining_entry() {
            Ok(m) => m,
            Err(_) => return reject(RiskRejectReason::MaxPositionExceeded),
        };
        if remaining.cents() <= 0 {
            return reject(RiskRejectReason::MaxPositionExceeded);
        }

        let (max_contracts, max_economic, fee) =
            match crate::fees::size_entry(remaining, intent.build.limit_price, &self.fees) {
                Ok(v) => v,
                Err(_) => return reject(RiskRejectReason::InvalidQuantity),
            };
        if max_contracts.get() == 0 {
            return reject(RiskRejectReason::InvalidQuantity);
        }

        let original_budget = snapshot.max_position_budget();
        let approved = ApprovedTradeIntent::from_risk_engine(
            RiskGrant::for_risk_engine(),
            decision_id,
            snapshot_id,
            intent,
            ClientOrderId::generate(),
            max_contracts,
            max_economic,
            max_economic,
            original_budget,
            original_budget.saturating_sub(max_economic),
            fee,
            self.fees.model_id(),
        );
        RiskDecision::Approved(approved)
    }
}

/// True when an incremental order would exceed the original snapshot budget.
pub fn would_exceed_original_budget(
    position: &Position,
    additional_premium: momento_core::Money,
    additional_entry_fee: momento_core::Money,
    original_budget: momento_core::Money,
    snapshot_id: SnapshotId,
) -> bool {
    if position.snapshot_id() != snapshot_id {
        return true;
    }
    let used = position
        .actual_exposure()
        .as_money()
        .checked_add(position.entry_fees())
        .and_then(|u| u.checked_add(additional_premium))
        .and_then(|u| u.checked_add(additional_entry_fee));
    match used {
        Ok(u) => u.cents() > original_budget.cents(),
        Err(_) => true,
    }
}
