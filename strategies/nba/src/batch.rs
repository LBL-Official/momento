//! Strategy reference equity and batches of ten completions.
//!
//! Batch 1 reference `R0` = $20,000 = $5,000 funded + $15,000 disclosed
//! external reserve. Sizing equity at a batch boundary:
//!
//! ```text
//! E = R0 + Σ owner contributions − Σ owner distributions
//!        + Σ settled trades: net P&L
//!        + Σ open trades:    open contribution
//! ```
//!
//! Net P&L = settlement payout + original sale proceeds − original cost −
//! opponent cost − every trade fee (incl. rounding) − settlement fee.
//! Open contribution = locked pairs × 100¢ + unpaired contracts at average
//! cost − costs + proceeds − fees paid. An unhedged open trade therefore
//! counts as −(fees paid); a hedge-complete trade counts its locked result.
//! A trade contributes one term or the other, never both.
//!
//! Reserve deposits, withdrawals back to the reserve, and shard/subaccount
//! transfers are internal: they change neither the reference nor P&L.
//! Exchange cash is tracked by the worker from the API, for affordability
//! only; it is not the sizing base.

use std::collections::BTreeMap;

use momento_core::Money;
use serde::{Deserialize, Serialize};

use crate::BATCH_SIZE;

pub const REFERENCE_INITIAL_CENTS: i64 = 2_000_000;
pub const FUNDED_INITIAL_CENTS: i64 = 500_000;
pub const EXTERNAL_RESERVE_INITIAL_CENTS: i64 = 1_500_000;
const CC_PER_CONTRACT_PAYOUT: i64 = 10_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum CapitalFlowKind {
    /// Disclosed external reserve deposited to Kalshi. Internal.
    ReserveToExchange,
    /// Exchange cash returned to the external reserve. Internal.
    ExchangeToReserve,
    /// Shard or subaccount transfer inside the Kalshi account. Internal.
    IntraAccountTransfer,
    /// New owner capital beyond the disclosed $20,000. Raises the reference.
    OwnerContribution,
    /// Capital removed from the strategy. Lowers the reference.
    OwnerDistribution,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct CapitalFlow {
    pub at: i64,
    pub kind: CapitalFlowKind,
    /// Positive cents.
    pub amount: Money,
    pub note: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Settlement {
    pub payout_centicents: i64,
    pub fee_centicents: i64,
}

/// Confirmed economics of one trade (both legs), from fills only.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct TradeEconomics {
    pub trade_id: String,
    pub original_bought: u32,
    pub original_cost_centicents: i64,
    pub original_sold: u32,
    pub original_proceeds_centicents: i64,
    pub opponent_bought: u32,
    pub opponent_cost_centicents: i64,
    pub fees_centicents: i64,
    pub settlement: Option<Settlement>,
    pub released_at: Option<i64>,
}

impl TradeEconomics {
    pub fn original_held(&self) -> i64 {
        i64::from(self.original_bought) - i64::from(self.original_sold)
    }

    pub fn locked_pairs(&self) -> i64 {
        self.original_held()
            .min(i64::from(self.opponent_bought))
            .max(0)
    }

    pub fn realized_centicents(&self) -> Option<i64> {
        let s = self.settlement.as_ref()?;
        Some(
            s.payout_centicents + self.original_proceeds_centicents
                - self.original_cost_centicents
                - self.opponent_cost_centicents
                - self.fees_centicents
                - s.fee_centicents,
        )
    }

    /// Conservative value of an unsettled trade (floors fractional cost).
    pub fn open_contribution_centicents(&self) -> i64 {
        let pairs = self.locked_pairs();
        let orig_left = self.original_held() - pairs;
        let opp_left = i64::from(self.opponent_bought) - pairs;
        let at_cost = |left: i64, cost: i64, bought: u32| {
            if bought == 0 || left <= 0 {
                0
            } else {
                left * cost / i64::from(bought)
            }
        };
        pairs * CC_PER_CONTRACT_PAYOUT
            + at_cost(
                orig_left,
                self.original_cost_centicents,
                self.original_bought,
            )
            + at_cost(
                opp_left,
                self.opponent_cost_centicents,
                self.opponent_bought,
            )
            + self.original_proceeds_centicents
            - self.original_cost_centicents
            - self.opponent_cost_centicents
            - self.fees_centicents
    }

    pub fn contribution_centicents(&self) -> i64 {
        self.realized_centicents()
            .unwrap_or_else(|| self.open_contribution_centicents())
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct BatchRecord {
    pub number: u32,
    pub reference_equity: Money,
    pub opened_at: Option<i64>,
    pub completed_at: Option<i64>,
    pub completions: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EquityLedger {
    pub reference_initial: Money,
    batches: Vec<BatchRecord>,
    trades: BTreeMap<String, TradeEconomics>,
    flows: Vec<CapitalFlow>,
}

impl Default for EquityLedger {
    fn default() -> Self {
        Self::new(Money::from_cents(REFERENCE_INITIAL_CENTS))
    }
}

/// Kept for callers of the v1 name.
pub type BatchLedger = EquityLedger;

impl EquityLedger {
    pub fn new(batch_1_reference: Money) -> Self {
        Self {
            reference_initial: batch_1_reference,
            batches: vec![BatchRecord {
                number: 1,
                reference_equity: batch_1_reference,
                opened_at: None,
                completed_at: None,
                completions: Vec::new(),
            }],
            trades: BTreeMap::new(),
            flows: Vec::new(),
        }
    }

    pub fn current(&self) -> &BatchRecord {
        // Never empty: `new` seeds batch 1 and `release` only appends.
        &self.batches[self.batches.len() - 1]
    }

    pub fn batches(&self) -> &[BatchRecord] {
        &self.batches
    }

    /// Sizing reference for the current batch.
    pub fn reference_equity(&self) -> Money {
        self.current().reference_equity
    }

    pub fn flows(&self) -> &[CapitalFlow] {
        &self.flows
    }

    pub fn trades(&self) -> &BTreeMap<String, TradeEconomics> {
        &self.trades
    }

    pub fn record_flow(&mut self, flow: CapitalFlow) {
        self.flows.push(flow);
    }

    pub fn upsert_trade(&mut self, t: TradeEconomics) {
        self.trades.insert(t.trade_id.clone(), t);
    }

    fn flow_sum(&self, kind: CapitalFlowKind) -> i64 {
        self.flows
            .iter()
            .filter(|f| f.kind == kind)
            .map(|f| f.amount.cents())
            .sum()
    }

    /// Owner capital base: R0 + contributions − distributions (cents).
    pub fn capital_base_cents(&self) -> i64 {
        self.reference_initial.cents() + self.flow_sum(CapitalFlowKind::OwnerContribution)
            - self.flow_sum(CapitalFlowKind::OwnerDistribution)
    }

    /// Disclosed reserve not yet deposited (cents). Informational.
    pub fn external_reserve_outstanding_cents(&self) -> i64 {
        EXTERNAL_RESERVE_INITIAL_CENTS - self.flow_sum(CapitalFlowKind::ReserveToExchange)
            + self.flow_sum(CapitalFlowKind::ExchangeToReserve)
    }

    /// Sizing equity now, in centicents.
    pub fn equity_centicents(&self) -> i64 {
        self.capital_base_cents() * 100
            + self
                .trades
                .values()
                .map(TradeEconomics::contribution_centicents)
                .sum::<i64>()
    }

    /// Records a slot release (a completion). On the tenth, closes the batch
    /// and opens the next at the sizing equity, floored to whole cents.
    /// Returns the closed batch number.
    pub fn release(&mut self, trade_id: &str, at: i64) -> Option<u32> {
        if let Some(t) = self.trades.get_mut(trade_id) {
            t.released_at.get_or_insert(at);
        }
        if self
            .batches
            .iter()
            .any(|b| b.completions.iter().any(|c| c == trade_id))
        {
            return None;
        }
        let equity_cc = self.equity_centicents();
        let last = self.batches.len() - 1;
        let batch = &mut self.batches[last];
        batch.opened_at.get_or_insert(at);
        batch.completions.push(trade_id.into());
        if u32::try_from(batch.completions.len()).unwrap_or(u32::MAX) < BATCH_SIZE {
            return None;
        }
        batch.completed_at = Some(at);
        let closed = batch.number;
        self.batches.push(BatchRecord {
            number: closed + 1,
            reference_equity: Money::from_cents(equity_cc.div_euclid(100)),
            opened_at: None,
            completed_at: None,
            completions: Vec::new(),
        });
        Some(closed)
    }
}
