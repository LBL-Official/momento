//! Entry admission. Every blocker is named. Nothing here shrinks a trade.

use momento_core::Money;
use serde::{Deserialize, Serialize};

use crate::reserve::{EntryReserve, ReserveError};
use crate::routing::Route;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(
    tag = "blocker",
    content = "detail",
    rename_all = "SCREAMING_SNAKE_CASE"
)]
pub enum Blocker {
    ContractUnresolved(String),
    FeeUnverified,
    RoutePairMismatch(String),
    RouteUnread,
    HedgePairInvalid(String),
    ExitCapacityUnbounded,
    SharedCollateralUnaccounted(String),
    FundsUnread,
    BlockedInsufficientCash {
        need_cents: i64,
        available_cents: i64,
    },
    SlotsFull {
        open: u32,
        max: u32,
    },
    LiveGatesUnset,
    /// Production order submission is compiled out or a permit gate failed.
    ProductionSubmissionDisabled(String),
    ReconciliationHold(String),
    ControlPaused,
    /// The tenth completion closed batch 1 and the batch-2 sizing formula is
    /// not approved.
    BatchResizeUnapproved {
        batch: u32,
    },
    StaleData(String),
    SpreadTooWide {
        spread_cents: u16,
    },
    TopOut {
        cents: u16,
    },
    Internal(String),
}

impl Blocker {
    pub fn code(&self) -> &'static str {
        match self {
            Blocker::ContractUnresolved(_) => "CONTRACT_UNRESOLVED",
            Blocker::FeeUnverified => "FEE_UNVERIFIED",
            Blocker::RoutePairMismatch(_) => "ROUTE_PAIR_MISMATCH",
            Blocker::RouteUnread => "ROUTING_UNVERIFIED",
            Blocker::HedgePairInvalid(_) => "HEDGE_PAIR_INVALID",
            Blocker::ExitCapacityUnbounded => "EXIT_CAPACITY_UNBOUNDED",
            Blocker::SharedCollateralUnaccounted(_) => "SHARED_COLLATERAL_UNACCOUNTED",
            Blocker::FundsUnread => "FUNDS_UNREAD",
            Blocker::BlockedInsufficientCash { .. } => "BLOCKED_INSUFFICIENT_CASH",
            Blocker::SlotsFull { .. } => "SLOTS_FULL",
            Blocker::LiveGatesUnset => "LIVE_GATES_UNSET",
            Blocker::ProductionSubmissionDisabled(_) => "PRODUCTION_SUBMISSION_DISABLED",
            Blocker::ReconciliationHold(_) => "RECONCILIATION_HOLD",
            Blocker::ControlPaused => "CONTROL_PAUSED",
            Blocker::BatchResizeUnapproved { .. } => "BATCH_RESIZE_UNAPPROVED",
            Blocker::StaleData(_) => "STALE_DATA",
            Blocker::SpreadTooWide { .. } => "SPREAD_TOO_WIDE",
            Blocker::TopOut { .. } => "TOP_OUT",
            Blocker::Internal(_) => "INTERNAL",
        }
    }
}

/// Who else can spend the same collateral.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "pool", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum CollateralPool {
    /// Separate subaccount or shard with evidence.
    VerifiedIsolation {
        evidence: String,
    },
    /// An account-wide reservation ledger every submitter respects.
    AtomicAccountReservations {
        ledger: String,
    },
    SharedUnaccounted {
        other_submitters: Vec<String>,
    },
    Unknown,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AdmissionInput {
    pub unresolved_fields: Vec<String>,
    pub fees_verified: bool,
    pub route: Route,
    pub pair: Result<(), String>,
    pub reserve: Result<EntryReserve, ReserveError>,
    pub collateral: CollateralPool,
    /// Signed balance on the market's shard. `None` = unread, never $0.
    pub available_cash: Option<Money>,
    /// Reserves already held by this bot's open lifecycles.
    pub outstanding_reserved: Money,
    pub open_slots: u32,
    pub max_slots: u32,
    pub live_gates_set: bool,
    /// `Err(reason)` while production submission is not permitted.
    pub production_permit: Result<(), String>,
    pub reconciliation_healthy: bool,
    pub paused: bool,
    #[serde(default = "one")]
    pub batch_number: u32,
    #[serde(default)]
    pub batch_resize_approved: bool,
}

fn one() -> u32 {
    1
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(
    tag = "decision",
    content = "blockers",
    rename_all = "SCREAMING_SNAKE_CASE"
)]
pub enum AdmissionDecision {
    Admit,
    Blocked(Vec<Blocker>),
}

pub fn evaluate_admission(input: &AdmissionInput) -> AdmissionDecision {
    let mut out = Vec::new();
    for field in &input.unresolved_fields {
        out.push(Blocker::ContractUnresolved(field.clone()));
    }
    if !input.fees_verified {
        out.push(Blocker::FeeUnverified);
    }
    match &input.route {
        Route::Verified { .. } => {}
        Route::Unread => out.push(Blocker::RouteUnread),
        other => out.push(Blocker::RoutePairMismatch(
            serde_json::to_string(other).unwrap_or_else(|_| "route".into()),
        )),
    }
    if let Err(reason) = &input.pair {
        out.push(Blocker::HedgePairInvalid(reason.clone()));
    }
    match &input.collateral {
        CollateralPool::VerifiedIsolation { .. }
        | CollateralPool::AtomicAccountReservations { .. } => {}
        CollateralPool::SharedUnaccounted { other_submitters } => out.push(
            Blocker::SharedCollateralUnaccounted(other_submitters.join(",")),
        ),
        CollateralPool::Unknown => out.push(Blocker::SharedCollateralUnaccounted("UNKNOWN".into())),
    }
    match (&input.reserve, input.available_cash) {
        (Err(ReserveError::ExitCapacityUnbounded), _) => out.push(Blocker::ExitCapacityUnbounded),
        (Err(ReserveError::InputUnread), _) => {
            out.push(Blocker::StaleData("sizing or fee multiplier unread".into()))
        }
        (Err(ReserveError::FeeUnsupported), _) => out.push(Blocker::FeeUnverified),
        (Err(other), _) => out.push(Blocker::Internal(format!("reserve {other:?}"))),
        (Ok(_), None) => out.push(Blocker::FundsUnread),
        (Ok(reserve), Some(cash)) => {
            let headroom = cash.cents() - input.outstanding_reserved.cents();
            if headroom < reserve.total.cents() {
                out.push(Blocker::BlockedInsufficientCash {
                    need_cents: reserve.total.cents(),
                    available_cents: headroom,
                });
            }
        }
    }
    if input.open_slots >= input.max_slots {
        out.push(Blocker::SlotsFull {
            open: input.open_slots,
            max: input.max_slots,
        });
    }
    if !input.live_gates_set {
        out.push(Blocker::LiveGatesUnset);
    }
    if let Err(reason) = &input.production_permit {
        out.push(Blocker::ProductionSubmissionDisabled(reason.clone()));
    }
    if !input.reconciliation_healthy {
        out.push(Blocker::ReconciliationHold(
            "reconciliation not healthy".into(),
        ));
    }
    if input.paused {
        out.push(Blocker::ControlPaused);
    }
    if input.batch_number > 1 && !input.batch_resize_approved {
        out.push(Blocker::BatchResizeUnapproved {
            batch: input.batch_number,
        });
    }
    if out.is_empty() {
        AdmissionDecision::Admit
    } else {
        AdmissionDecision::Blocked(out)
    }
}

/// Positions the actual funds could carry now, capped by free slots.
/// `None` when the per-entry reserve is unbounded or funds are unread.
pub fn capacity_positions(
    available_cash: Option<Money>,
    outstanding_reserved: Money,
    per_entry: Result<&EntryReserve, ReserveError>,
    open_slots: u32,
    max_slots: u32,
) -> Option<u32> {
    let cash = available_cash?;
    let reserve = per_entry.ok()?;
    let free_slots = max_slots.saturating_sub(open_slots);
    if reserve.total.cents() <= 0 {
        return None;
    }
    let headroom = (cash.cents() - outstanding_reserved.cents()).max(0);
    let by_cash = u32::try_from(headroom / reserve.total.cents()).unwrap_or(u32::MAX);
    Some(by_cash.min(free_slots))
}
