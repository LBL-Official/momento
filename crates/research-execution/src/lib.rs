//! Deterministic historical fill simulation for FIRST01 research backtests.
//!
//! Research-only. Does not submit production orders.

#![forbid(unsafe_code)]

pub mod artifacts;
pub mod book_state;
pub mod engine;
pub mod entry_sim;
pub mod exit_sim;
pub mod fill;
pub mod metrics;
pub mod order;
pub mod params;
pub mod pnl;
pub mod position;
pub mod quality;
pub mod trade_ledger;

pub use artifacts::{ExecutionArtifacts, write_execution_artifacts};
pub use engine::{ExecutionBacktestInput, ExecutionBacktestResult, run_execution_backtest};
pub use entry_sim::{queue_ahead_at_submit, should_create_entry_order};
pub use metrics::{DataQualityMetrics, RunMetrics};
pub use order::{FillEvidence, OrderPurpose, OrderStatus, SimulatedOrder};
pub use params::{EXECUTION_MODEL_NAME, EXECUTION_MODEL_VERSION, ExecutionParameters};
pub use pnl::{PortfolioPnl, PositionPnl};
pub use position::ExecutionPosition;
pub use quality::{ExecutionDataQuality, aggregate_execution_quality, classify_orderbook_event};
pub use trade_ledger::write_trade_ledger;
