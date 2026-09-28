//! Canonical FIRST01 trade ledger artifacts.

use std::fs;
use std::path::Path;

use serde::{Deserialize, Serialize};

use momento_research_strategies::{
    ENTRY_REASON_FIRST01, EntryOpportunity, LifecycleAction, QuoteObservation,
};

use crate::engine::ExecutionBacktestResult;
use crate::fill::SimulatedFill;
use crate::order::{OrderPurpose, SimulatedOrder};
use crate::params::FeesModel;
use crate::pnl::compute_position_pnl;
use crate::position::ExecutionPosition;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CanonicalTradeRecord {
    pub trade_id: String,
    pub strategy: String,
    pub strategy_version: u32,
    pub game_id: u128,
    pub market_id: u128,
    pub ticker: String,
    pub side: String,
    pub entry_reason: String,
    pub first_80: PriceStamp,
    pub confirmation_81: PriceStamp,
    pub entry: EntryStamp,
    pub lifecycle_status: String,
    pub order_ids: Vec<u64>,
    pub fills: Vec<FillStamp>,
    pub exit: Option<ExitStamp>,
    pub gross_pnl_cents: Option<i64>,
    pub fees_status: String,
    pub slippage_status: String,
    pub net_pnl_cents: Option<i64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PriceStamp {
    pub timestamp_ms: i64,
    pub price_cents: u16,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EntryStamp {
    pub timestamp_ms: i64,
    pub bid_cents: u16,
    pub ask_cents: u16,
    pub limit_cents: u16,
    pub maker_eligible: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FillStamp {
    pub fill_id: u64,
    pub price_cents: u16,
    pub quantity: u32,
    pub purpose: String,
    pub timestamp_ms: i64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExitStamp {
    pub trigger_bid_cents: u16,
    pub timestamp_ms: i64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LifecycleReportRow {
    pub game_id: u128,
    pub canonical_market_id: u128,
    pub canonical_ticker: String,
    pub opportunity_timestamp_ms: i64,
    pub lifecycle_status: String,
    pub subsequent_qualifying_quotes: u64,
    pub suppressed_quote_count: u64,
    pub order_status: String,
    pub fill_status: String,
    pub exit_status: String,
}

pub fn build_canonical_trades(result: &ExecutionBacktestResult) -> Vec<CanonicalTradeRecord> {
    let mut trades = Vec::new();
    for (i, opp) in result.entry_opportunities.iter().enumerate() {
        let game_orders: Vec<&SimulatedOrder> = result
            .orders
            .iter()
            .filter(|o| o.game_id == opp.game_id && o.purpose == OrderPurpose::Entry)
            .collect();
        let pos: Option<&ExecutionPosition> = result
            .positions
            .iter()
            .find(|p| p.game_id == opp.game_id && p.market_id == opp.market_id);
        let entry_fills: Vec<&SimulatedFill> = result
            .fills
            .iter()
            .filter(|f| {
                f.purpose == OrderPurpose::Entry
                    && pos.map(|p| p.position_id == f.position_id).unwrap_or(false)
            })
            .collect();
        let exit_fills: Vec<&SimulatedFill> = result
            .fills
            .iter()
            .filter(|f| {
                f.purpose == OrderPurpose::Liquidation
                    && pos.map(|p| p.position_id == f.position_id).unwrap_or(false)
            })
            .collect();

        let lifecycle = if entry_fills.is_empty() {
            "UNFILLED"
        } else if pos.map(|p| p.net_contracts() == 0).unwrap_or(false) {
            "CLOSED"
        } else {
            "OPEN"
        };

        let pnl = pos.map(|p| compute_position_pnl(p, None, FeesModel::NotModeled));

        let exit = result
            .exit_signals
            .iter()
            .find(|e| e.scope.game_id == opp.game_id)
            .map(|e| ExitStamp {
                trigger_bid_cents: e.trigger_bid_cents,
                timestamp_ms: e.exchange_timestamp_ms,
            });

        trades.push(CanonicalTradeRecord {
            trade_id: opp.trade_id.0.clone(),
            strategy: "FIRST01".into(),
            strategy_version: 1,
            game_id: opp.game_id,
            market_id: opp.market_id,
            ticker: opp.ticker.clone(),
            side: format!("{:?}", opp.side),
            entry_reason: opp.entry_reason.clone(),
            first_80: PriceStamp {
                timestamp_ms: opp.first_80_timestamp_ms,
                price_cents: opp.first_80_price_cents,
            },
            confirmation_81: PriceStamp {
                timestamp_ms: opp.confirmation_81_timestamp_ms,
                price_cents: opp.confirmation_81_price_cents,
            },
            entry: EntryStamp {
                timestamp_ms: opp.qualifying_timestamp_ms,
                bid_cents: opp.qualifying_bid_cents,
                ask_cents: opp.qualifying_ask_cents,
                limit_cents: opp.maker_limit_cents,
                maker_eligible: true,
            },
            lifecycle_status: lifecycle.into(),
            order_ids: game_orders.iter().map(|o| o.order_id).collect(),
            fills: entry_fills
                .iter()
                .chain(exit_fills.iter())
                .map(|f| FillStamp {
                    fill_id: f.fill_id,
                    price_cents: f.price_cents,
                    quantity: f.quantity_contracts,
                    purpose: format!("{:?}", f.purpose),
                    timestamp_ms: f.exchange_timestamp_ms,
                })
                .collect(),
            exit,
            gross_pnl_cents: pnl.as_ref().map(|p| p.gross_realized_pnl_cents),
            fees_status: "NOT_MODELED".into(),
            slippage_status: "NOT_AVAILABLE".into(),
            net_pnl_cents: pnl.as_ref().map(|p| p.net_realized_pnl_cents),
        });
        let _ = i;
        let _ = ENTRY_REASON_FIRST01;
    }
    trades
}

pub fn build_lifecycle_rows(
    result: &ExecutionBacktestResult,
) -> (Vec<LifecycleReportRow>, Vec<QuoteObservation>) {
    let suppressed: Vec<QuoteObservation> = result
        .quote_observations
        .iter()
        .filter(|q| {
            matches!(
                q.lifecycle_action,
                LifecycleAction::SuppressedByExistingGameTrade
                    | LifecycleAction::SuppressedByOpponentMarket
                    | LifecycleAction::SuppressedByWorkingEntry
                    | LifecycleAction::SuppressedByPosition
                    | LifecycleAction::SuppressedByLiquidation
                    | LifecycleAction::SuppressedByGameLock
                    | LifecycleAction::SuppressedByLifecycleConsumed
            ) && q.qualifies_first01
        })
        .cloned()
        .collect();

    let mut rows = Vec::new();
    for opp in &result.entry_opportunities {
        let subsequent = result
            .quote_observations
            .iter()
            .filter(|q| {
                q.game_id == opp.game_id
                    && q.exchange_timestamp_ms > opp.qualifying_timestamp_ms
                    && q.qualifies_first01
            })
            .count() as u64;
        let suppressed_count = result
            .quote_observations
            .iter()
            .filter(|q| {
                q.game_id == opp.game_id
                    && matches!(
                        q.lifecycle_action,
                        LifecycleAction::SuppressedByExistingGameTrade
                            | LifecycleAction::SuppressedByOpponentMarket
                            | LifecycleAction::SuppressedByWorkingEntry
                            | LifecycleAction::SuppressedByPosition
                            | LifecycleAction::SuppressedByLiquidation
                            | LifecycleAction::SuppressedByLifecycleConsumed
                    )
            })
            .count() as u64;
        let orders: Vec<_> = result
            .orders
            .iter()
            .filter(|o| o.game_id == opp.game_id && o.purpose == OrderPurpose::Entry)
            .collect();
        let fills = result
            .fills
            .iter()
            .filter(|f| {
                f.purpose == OrderPurpose::Entry && orders.iter().any(|o| o.order_id == f.order_id)
            })
            .count();
        let exit = result
            .exit_signals
            .iter()
            .any(|e| e.scope.game_id == opp.game_id);
        rows.push(LifecycleReportRow {
            game_id: opp.game_id,
            canonical_market_id: opp.market_id,
            canonical_ticker: opp.ticker.clone(),
            opportunity_timestamp_ms: opp.qualifying_timestamp_ms,
            lifecycle_status: format!("{:?}", opp.lifecycle),
            subsequent_qualifying_quotes: subsequent,
            suppressed_quote_count: suppressed_count,
            order_status: if orders.is_empty() {
                "NONE".into()
            } else {
                format!("{:?}", orders[0].status)
            },
            fill_status: if fills == 0 {
                "UNFILLED".into()
            } else {
                format!("FILLS={fills}")
            },
            exit_status: if exit {
                "EXIT_SIGNAL".into()
            } else {
                "NONE".into()
            },
        });
    }
    (rows, suppressed)
}

pub fn write_trade_ledger(run_dir: &Path, result: &ExecutionBacktestResult) -> std::io::Result<()> {
    let trades_dir = run_dir.join("trades");
    let diagnostics = run_dir.join("diagnostics");
    fs::create_dir_all(&trades_dir)?;
    fs::create_dir_all(&diagnostics)?;

    let trades = build_canonical_trades(result);
    let (lifecycle, suppressed) = build_lifecycle_rows(result);

    let mut jsonl = String::new();
    for (i, t) in trades.iter().enumerate() {
        write_json(&trades_dir.join(format!("trade_{:06}.json", i + 1)), t)?;
        jsonl.push_str(&serde_json::to_string(t)?);
        jsonl.push('\n');
    }
    fs::write(trades_dir.join("trades.jsonl"), jsonl)?;

    let mut csv = String::from(
        "trade_id,game_id,market_id,ticker,side,entry_limit,lifecycle_status,orders,fills,gross_pnl_cents\n",
    );
    for t in &trades {
        csv.push_str(&format!(
            "{},{},{},{},{},{},{},{},{},{}\n",
            t.trade_id,
            t.game_id,
            t.market_id,
            t.ticker,
            t.side,
            t.entry.limit_cents,
            t.lifecycle_status,
            t.order_ids.len(),
            t.fills.len(),
            t.gross_pnl_cents.map(|c| c.to_string()).unwrap_or_default()
        ));
    }
    fs::write(trades_dir.join("trades.csv"), csv)?;

    let mut life_csv = String::from(
        "game_id,canonical_market_id,canonical_ticker,opportunity_timestamp_ms,lifecycle_status,subsequent_qualifying_quotes,suppressed_quote_count,order_status,fill_status,exit_status\n",
    );
    for r in &lifecycle {
        life_csv.push_str(&format!(
            "{},{},{},{},{},{},{},{},{},{}\n",
            r.game_id,
            r.canonical_market_id,
            r.canonical_ticker,
            r.opportunity_timestamp_ms,
            r.lifecycle_status,
            r.subsequent_qualifying_quotes,
            r.suppressed_quote_count,
            r.order_status,
            r.fill_status,
            r.exit_status
        ));
    }
    fs::write(diagnostics.join("lifecycle_report.csv"), life_csv)?;
    write_json(
        &diagnostics.join("suppressed_opportunities.json"),
        &suppressed,
    )?;
    let mut supp_csv =
        String::from("game_id,market_id,ticker,timestamp_ms,bid,ask,lifecycle_action\n");
    for q in &suppressed {
        supp_csv.push_str(&format!(
            "{},{},{},{},{},{},{:?}\n",
            q.game_id,
            q.market_id,
            q.ticker,
            q.exchange_timestamp_ms,
            q.bid_cents,
            q.ask_cents,
            q.lifecycle_action
        ));
    }
    fs::write(diagnostics.join("suppressed_opportunities.csv"), supp_csv)?;

    // Invariant checks
    let mut games = std::collections::HashSet::new();
    let mut dup_opps = 0u64;
    for opp in &result.entry_opportunities {
        if !games.insert(opp.game_id) {
            dup_opps += 1;
        }
    }
    let invariant = serde_json::json!({
        "one_trade_per_game_invariant": if dup_opps == 0 { "PASS" } else { "FAIL" },
        "canonical_opportunities": result.entry_opportunities.len(),
        "unique_games": games.len(),
        "duplicate_opportunity_count": dup_opps,
        "entry_orders": result.orders.iter().filter(|o| o.purpose == OrderPurpose::Entry).count(),
        "suppressed_qualifying_quotes": suppressed.len(),
        "entry_reason": ENTRY_REASON_FIRST01,
    });
    write_json(&diagnostics.join("lifecycle_invariant.json"), &invariant)?;

    Ok(())
}

fn write_json<T: Serialize>(path: &Path, value: &T) -> std::io::Result<()> {
    let body = serde_json::to_string_pretty(value)?;
    let tmp = path.with_extension("tmp");
    fs::write(&tmp, body)?;
    fs::rename(tmp, path)?;
    Ok(())
}

/// Compile-time silence unused import when building empty ledger.
#[allow(dead_code)]
fn _touch_opp(_: &EntryOpportunity) {}
