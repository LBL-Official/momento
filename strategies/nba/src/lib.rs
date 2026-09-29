//! NBA Bot 001 FIRST78_67. Emits signals, local intents, and blockers only.

#![forbid(unsafe_code)]

pub mod admission;
pub mod bars;
pub mod batch;
pub mod contract;
pub mod exposure;
pub mod fees;
pub mod hedge;
pub mod lifecycle;
pub mod mode;
pub mod orders;
pub mod reserve;
pub mod routing;
pub mod selection;
pub mod signal;
pub mod sizing;
pub mod sizing_epoch;
pub mod slice;

pub use admission::{
    AdmissionDecision, AdmissionInput, Blocker, CollateralPool, capacity_positions,
    evaluate_admission,
};
pub use bars::MinuteBar;
pub use batch::{
    BatchLedger, BatchRecord, CapitalFlow, CapitalFlowKind, EXTERNAL_RESERVE_INITIAL_CENTS,
    EquityLedger, FUNDED_INITIAL_CENTS, REFERENCE_INITIAL_CENTS, Settlement, TradeEconomics,
};
pub use contract::{ContractError, ContractStatus};
pub use exposure::{EmergencyPolicy, Exposure, GameBook, PlanStep, Residual};
pub use fees::{
    BalancePrecision, FeeError, FeeModel, FeeSchedule, FeeType, Liquidity,
    centicents_to_cents_ceil, fee_bound_cents, multiplier_milli,
};
pub use hedge::{
    ComplementPair, EventDescriptor, HedgeAction, HedgePlanner, MarketDescriptor, PathZone,
    complement_settlement_cents, hedge_quantity, opponent_limit_for_path, path_zone,
    verify_complement,
};
pub use lifecycle::{Lifecycle, LifecycleEvent, LifecycleState, Transition, TransitionError};
pub use mode::{ConfigMode, Mode, ModeInputs, derive_mode};
pub use orders::{
    BookSide, Fill, OrderError, OrderEvent, OrderRecord, OrderRole, OrderSpec, OrderStatus,
    SpecError, TimeInForce, UnresolvedAmend, VenueStatus,
};
pub use reserve::{EntryReserve, ExitBound, ReserveError, reserve_for_entry};
pub use routing::{Route, route_for_pair};
pub use selection::{Candidate, select_candidate};
pub use signal::{
    CrossOutcome, CrossTracker, EntrySignal, StopEvent, StopTracker, top_out_at_signal,
    top_out_while_resting,
};
pub use sizing::contracts_for_reference;
pub use slice::{Bucket, ClockHistory, ClockObservation, bucket_for};

pub const STRATEGY_ID: &str = "FIRST78_67";
pub const BOT_ID: &str = "nba-001";
pub const POLICY_VERSION: &str = "nba-001-v1";
pub const ENTRY_CENTS: u16 = 78;
pub const STOP_CENTS: u16 = 67;
pub const PREPARE_CENTS: u16 = 68;
pub const TOP_OUT_CENTS: u16 = 85;
pub const MARKET_DUMP_BELOW_CENTS: u16 = 55;
pub const LADDER_CAP_CENTS: u16 = 45;
pub const MAX_SPREAD_CENTS: u16 = 10;
pub const ALLOCATION_BPS: u32 = 600;
pub const SHARED_SLOTS: u32 = 7;
pub const BATCH_SIZE: u32 = 10;
pub const BATCH_1_REFERENCE_CENTS: i64 = batch::REFERENCE_INITIAL_CENTS;
