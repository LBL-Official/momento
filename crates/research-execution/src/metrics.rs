//! Execution quality and portfolio metrics.

use serde::{Deserialize, Serialize};

use crate::fill::SimulatedFill;
use crate::order::{OrderPurpose, OrderStatus, SimulatedOrder};
use crate::pnl::PortfolioPnl;
use crate::position::ExecutionPosition;
use crate::quality::ExecutionDataQuality;

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct DataQualityMetrics {
    pub dates_requested: u32,
    pub dates_used: u32,
    pub complete_dates: u32,
    pub partial_dates: u32,
    pub invalid_dates: u32,
    pub missing_dates: u32,
    pub sequence_gap_count: u64,
    pub execution_data_quality: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct ExecutionQualityMetrics {
    pub signal_to_order_latency_ms: Option<i64>,
    pub order_to_first_fill_time_ms: Option<i64>,
    pub order_to_full_fill_time_ms: Option<i64>,
    pub entry_slippage_vs_signal_cents: Option<i32>,
    pub exit_slippage_vs_stop_cents: Option<i32>,
    pub exit_slippage_vs_trigger_cents: Option<i32>,
    pub maker_fill_rate: f64,
    pub average_fill_fraction: f64,
    pub partial_fill_rate: f64,
    pub unfilled_order_count: u64,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct RunMetrics {
    pub quote_observations: u64,
    pub entry_opportunities: u64,
    pub entry_intents: u64,
    pub entry_signals: u64,
    pub entry_orders: u64,
    pub entry_fills: u64,
    pub entry_fill_rate: f64,
    pub contracts_requested: u64,
    pub contracts_filled: u64,
    pub average_entry_price_cents: Option<u16>,
    pub entry_vwap_cents: Option<u16>,
    pub exit_signals: u64,
    pub exit_orders: u64,
    pub exit_fills: u64,
    pub average_exit_price_cents: Option<u16>,
    pub positions_opened: u64,
    pub positions_closed: u64,
    pub positions_open_at_end: u64,
    pub winning_positions: u64,
    pub losing_positions: u64,
    pub gross_pnl_cents: i64,
    pub fees_status: String,
    pub net_pnl_cents: i64,
    pub unrealized_pnl_cents: i64,
    pub max_drawdown_cents: i64,
    pub average_hold_time_ms: Option<i64>,
    pub median_hold_time_ms: Option<i64>,
    pub stop_trigger_count: u64,
    pub stop_gap_count: u64,
    pub partial_fill_count: u64,
    pub failed_exit_attempts: u64,
    pub execution_quality: ExecutionQualityMetrics,
    pub data_quality: DataQualityMetrics,
}

#[allow(clippy::too_many_arguments)]
pub fn compute_run_metrics(
    quote_observations: u64,
    entry_opportunities: u64,
    entry_intents: u64,
    entry_signals: u64,
    exit_signals: u64,
    orders: &[SimulatedOrder],
    fills: &[SimulatedFill],
    positions: &[ExecutionPosition],
    portfolio: &PortfolioPnl,
    data_quality: DataQualityMetrics,
    sequence_gaps: u64,
    stop_gap_count: u64,
    failed_exit_attempts: u64,
) -> RunMetrics {
    let entry_orders: Vec<_> = orders
        .iter()
        .filter(|o| o.purpose == OrderPurpose::Entry)
        .collect();
    let exit_orders: Vec<_> = orders
        .iter()
        .filter(|o| o.purpose == OrderPurpose::Liquidation)
        .collect();
    let entry_fills: Vec<_> = fills
        .iter()
        .filter(|f| f.purpose == OrderPurpose::Entry)
        .collect();
    let exit_fills: Vec<_> = fills
        .iter()
        .filter(|f| f.purpose == OrderPurpose::Liquidation)
        .collect();

    let contracts_requested: u64 = entry_orders.iter().map(|o| u64::from(o.quantity)).sum();
    let contracts_filled: u64 = entry_fills
        .iter()
        .map(|f| u64::from(f.quantity_contracts))
        .sum();
    let entry_fill_rate = if entry_orders.is_empty() {
        0.0
    } else {
        entry_fills.len() as f64 / entry_orders.len() as f64
    };

    let entry_vwap = weighted_avg_price(&entry_fills);
    let exit_vwap = weighted_avg_price(&exit_fills);

    let positions_opened = positions.iter().filter(|p| p.filled_quantity > 0).count() as u64;
    let positions_closed = positions
        .iter()
        .filter(|p| p.net_contracts() == 0 && p.filled_quantity > 0)
        .count() as u64;
    let positions_open_at_end = positions.iter().filter(|p| p.net_contracts() > 0).count() as u64;

    let mut winning = 0u64;
    let mut losing = 0u64;
    for p in positions {
        if p.net_contracts() > 0 {
            continue;
        }
        let entry_cost: i64 = p
            .entry_fills
            .iter()
            .map(|f| i64::from(f.quantity_contracts) * i64::from(f.price_cents))
            .sum();
        let exit_proceeds: i64 = p
            .exit_fills
            .iter()
            .map(|f| i64::from(f.quantity_contracts) * i64::from(f.price_cents))
            .sum();
        if exit_proceeds > entry_cost {
            winning += 1;
        } else if exit_proceeds < entry_cost {
            losing += 1;
        }
    }

    let hold_times: Vec<i64> = positions
        .iter()
        .filter_map(|p| {
            let opened = p.opened_at_ms?;
            let closed = p.closed_at_ms?;
            Some(closed - opened)
        })
        .collect();
    let avg_hold = if hold_times.is_empty() {
        None
    } else {
        Some(hold_times.iter().sum::<i64>() / hold_times.len() as i64)
    };
    let median_hold = median_i64(&hold_times);

    let partial_fill_count = fills.iter().filter(|f| f.is_partial).count() as u64;
    let _unfilled = entry_orders
        .iter()
        .filter(|o| {
            matches!(
                o.status,
                OrderStatus::Working | OrderStatus::Cancelled | OrderStatus::PartiallyFilled
            ) && o.remaining_quantity > 0
        })
        .count() as u64;

    let execution_quality = compute_execution_quality(orders, fills);

    RunMetrics {
        quote_observations,
        entry_opportunities,
        entry_intents,
        entry_signals,
        entry_orders: entry_orders.len() as u64,
        entry_fills: entry_fills.len() as u64,
        entry_fill_rate,
        contracts_requested,
        contracts_filled,
        average_entry_price_cents: entry_vwap,
        entry_vwap_cents: entry_vwap,
        exit_signals,
        exit_orders: exit_orders.len() as u64,
        exit_fills: exit_fills.len() as u64,
        average_exit_price_cents: exit_vwap,
        positions_opened,
        positions_closed,
        positions_open_at_end,
        winning_positions: winning,
        losing_positions: losing,
        gross_pnl_cents: portfolio.gross_realized_pnl_cents,
        fees_status: portfolio.fees.status.clone(),
        net_pnl_cents: portfolio.net_pnl_cents,
        unrealized_pnl_cents: portfolio.unrealized_pnl_cents,
        max_drawdown_cents: compute_max_drawdown(positions),
        average_hold_time_ms: avg_hold,
        median_hold_time_ms: median_hold,
        stop_trigger_count: exit_signals,
        stop_gap_count,
        partial_fill_count,
        failed_exit_attempts,
        execution_quality,
        data_quality: DataQualityMetrics {
            sequence_gap_count: sequence_gaps,
            execution_data_quality: data_quality.execution_data_quality.clone(),
            ..data_quality
        },
    }
}

fn weighted_avg_price(fills: &[&SimulatedFill]) -> Option<u16> {
    if fills.is_empty() {
        return None;
    }
    let mut qty: u64 = 0;
    let mut premium: u128 = 0;
    for f in fills {
        qty += u64::from(f.quantity_contracts);
        premium += u128::from(f.quantity_contracts) * u128::from(f.price_cents);
    }
    if qty == 0 {
        return None;
    }
    u16::try_from(premium / u128::from(qty)).ok()
}

fn median_i64(values: &[i64]) -> Option<i64> {
    if values.is_empty() {
        return None;
    }
    let mut v = values.to_vec();
    v.sort_unstable();
    Some(v[v.len() / 2])
}

fn compute_max_drawdown(positions: &[ExecutionPosition]) -> i64 {
    let mut peak = 0i64;
    let mut equity = 0i64;
    let mut max_dd = 0i64;
    for p in positions {
        let entry: i64 = p
            .entry_fills
            .iter()
            .map(|f| i64::from(f.quantity_contracts) * i64::from(f.price_cents))
            .sum();
        let exit: i64 = p
            .exit_fills
            .iter()
            .map(|f| i64::from(f.quantity_contracts) * i64::from(f.price_cents))
            .sum();
        equity += exit - entry;
        peak = peak.max(equity);
        max_dd = max_dd.max(peak - equity);
    }
    max_dd
}

fn compute_execution_quality(
    orders: &[SimulatedOrder],
    fills: &[SimulatedFill],
) -> ExecutionQualityMetrics {
    let entry_orders: Vec<_> = orders
        .iter()
        .filter(|o| o.purpose == OrderPurpose::Entry)
        .collect();
    if entry_orders.is_empty() {
        return ExecutionQualityMetrics::default();
    }

    let mut latencies = Vec::new();
    let mut first_fill_times = Vec::new();
    let mut full_fill_times = Vec::new();
    let mut slippages = Vec::new();

    for order in &entry_orders {
        if let (Some(sig_ms), Some(sig_px)) = (order.signal_exchange_ms, order.signal_price_cents) {
            latencies.push(order.submitted_at_ms - sig_ms);
            slippages.push(i32::from(order.limit_price_cents) - i32::from(sig_px));
        }
        let order_fills: Vec<_> = fills
            .iter()
            .filter(|f| f.order_id == order.order_id)
            .collect();
        if let Some(first) = order_fills.first() {
            first_fill_times.push(first.exchange_timestamp_ms - order.submitted_at_ms);
        }
        if order.status == OrderStatus::Filled {
            if let Some(last) = order_fills.last() {
                full_fill_times.push(last.exchange_timestamp_ms - order.submitted_at_ms);
            }
        }
    }

    let partial_rate = if fills.is_empty() {
        0.0
    } else {
        fills.iter().filter(|f| f.is_partial).count() as f64 / fills.len() as f64
    };
    let unfilled = entry_orders
        .iter()
        .filter(|o| o.filled_quantity == 0)
        .count() as u64;

    ExecutionQualityMetrics {
        signal_to_order_latency_ms: avg_i64(&latencies),
        order_to_first_fill_time_ms: avg_i64(&first_fill_times),
        order_to_full_fill_time_ms: avg_i64(&full_fill_times),
        entry_slippage_vs_signal_cents: avg_i32(&slippages),
        maker_fill_rate: if entry_orders.is_empty() {
            0.0
        } else {
            entry_orders
                .iter()
                .filter(|o| o.filled_quantity > 0)
                .count() as f64
                / entry_orders.len() as f64
        },
        average_fill_fraction: if entry_orders.is_empty() {
            0.0
        } else {
            entry_orders
                .iter()
                .map(|o| o.filled_quantity as f64 / o.quantity.max(1) as f64)
                .sum::<f64>()
                / entry_orders.len() as f64
        },
        partial_fill_rate: partial_rate,
        unfilled_order_count: unfilled,
        ..ExecutionQualityMetrics::default()
    }
}

fn avg_i64(values: &[i64]) -> Option<i64> {
    if values.is_empty() {
        None
    } else {
        Some(values.iter().sum::<i64>() / values.len() as i64)
    }
}

fn avg_i32(values: &[i32]) -> Option<i32> {
    if values.is_empty() {
        None
    } else {
        Some(values.iter().sum::<i32>() / values.len() as i32)
    }
}

pub fn empty_data_quality(aggregate: ExecutionDataQuality) -> DataQualityMetrics {
    DataQualityMetrics {
        execution_data_quality: aggregate.as_str().into(),
        ..DataQualityMetrics::default()
    }
}
