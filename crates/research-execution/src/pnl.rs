//! P&L calculations (integer cents, fees explicit).

use serde::{Deserialize, Serialize};

use crate::params::FeesModel;
use crate::position::{ExecutionPosition, PositionStatus};

#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct FeesStatus {
    pub status: String,
    pub fees_cents: i64,
}

impl FeesStatus {
    pub fn not_modeled() -> Self {
        Self {
            status: "NOT_MODELED".into(),
            fees_cents: 0,
        }
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct PositionPnl {
    pub position_id: u128,
    pub gross_entry_cost_cents: i64,
    pub gross_exit_proceeds_cents: i64,
    pub gross_realized_pnl_cents: i64,
    pub fees_cents: i64,
    pub net_realized_pnl_cents: i64,
    pub unrealized_pnl_cents: Option<i64>,
    pub mark_price_cents: Option<u16>,
    pub status: String,
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct PortfolioPnl {
    pub gross_entry_cost_cents: i64,
    pub gross_exit_proceeds_cents: i64,
    pub gross_realized_pnl_cents: i64,
    pub fees: FeesStatus,
    pub net_realized_pnl_cents: i64,
    pub unrealized_pnl_cents: i64,
    pub net_pnl_cents: i64,
    pub return_on_capital_bps: Option<i32>,
}

pub fn compute_position_pnl(
    position: &ExecutionPosition,
    mark_bid_cents: Option<u16>,
    fees_model: FeesModel,
) -> PositionPnl {
    let gross_entry_cost_cents: i64 = position
        .entry_fills
        .iter()
        .map(|f| i64::from(f.quantity_contracts) * i64::from(f.price_cents))
        .sum();
    let gross_exit_proceeds_cents: i64 = position
        .exit_fills
        .iter()
        .map(|f| i64::from(f.quantity_contracts) * i64::from(f.price_cents))
        .sum();
    let gross_realized_pnl_cents =
        gross_exit_proceeds_cents - gross_entry_cost_for_exited(position);
    let fees = match fees_model {
        FeesModel::NotModeled => 0,
    };
    let net_realized = gross_realized_pnl_cents - fees;

    let net_contracts = position.net_contracts();
    let unrealized = if net_contracts > 0 {
        mark_bid_cents.map(|mark| {
            let entry_cost_remaining = remaining_entry_cost(position);
            i64::from(net_contracts) * i64::from(mark) - entry_cost_remaining
        })
    } else {
        None
    };

    let status = match position.status {
        PositionStatus::Flat => "REALIZED".into(),
        PositionStatus::OpenAtEnd => "OPEN_AT_END".into(),
        PositionStatus::LiquidationActive => "LIQUIDATION_ACTIVE".into(),
        PositionStatus::Open => {
            if net_contracts == 0 {
                "REALIZED".into()
            } else {
                "OPEN".into()
            }
        }
    };

    PositionPnl {
        position_id: position.position_id,
        gross_entry_cost_cents,
        gross_exit_proceeds_cents,
        gross_realized_pnl_cents,
        fees_cents: fees,
        net_realized_pnl_cents: net_realized,
        unrealized_pnl_cents: unrealized,
        mark_price_cents: mark_bid_cents,
        status,
    }
}

fn gross_entry_cost_for_exited(position: &ExecutionPosition) -> i64 {
    let exited: u32 = position
        .exit_fills
        .iter()
        .map(|f| f.quantity_contracts)
        .sum();
    if exited == 0 || position.filled_quantity == 0 {
        return 0;
    }
    let total_entry: i64 = position
        .entry_fills
        .iter()
        .map(|f| i64::from(f.quantity_contracts) * i64::from(f.price_cents))
        .sum();
    total_entry * i64::from(exited) / i64::from(position.filled_quantity)
}

fn remaining_entry_cost(position: &ExecutionPosition) -> i64 {
    let net = position.net_contracts();
    if net == 0 {
        return 0;
    }
    let vwap = position.entry_vwap_cents().unwrap_or(0);
    i64::from(net) * i64::from(vwap)
}

pub fn compute_portfolio_pnl(
    positions: &[ExecutionPosition],
    marks: &[(u128, u16)],
    fees_model: FeesModel,
) -> PortfolioPnl {
    let mut portfolio = PortfolioPnl {
        fees: FeesStatus::not_modeled(),
        ..PortfolioPnl::default()
    };
    for pos in positions {
        let mark = marks
            .iter()
            .find(|(m, _)| *m == pos.market_id)
            .map(|(_, p)| *p);
        let pnl = compute_position_pnl(pos, mark, fees_model);
        portfolio.gross_entry_cost_cents += pnl.gross_entry_cost_cents;
        portfolio.gross_exit_proceeds_cents += pnl.gross_exit_proceeds_cents;
        portfolio.gross_realized_pnl_cents += pnl.gross_realized_pnl_cents;
        portfolio.net_realized_pnl_cents += pnl.net_realized_pnl_cents;
        portfolio.unrealized_pnl_cents += pnl.unrealized_pnl_cents.unwrap_or(0);
    }
    portfolio.net_pnl_cents = portfolio.net_realized_pnl_cents + portfolio.unrealized_pnl_cents;
    portfolio
}
