//! MOMENTO_FIRST78_LIVE_V1 sizing policy. No I/O or submission.
//!
//! Completion requests a resize; only the LA overnight window permits it.
//! The caller must serialize admissions, completion and resize under one
//! writer/transaction, persist the proposed state before publishing it, and
//! supply an authoritative reconciled equity snapshot (never estimated P&L).
//! This deliberately does not migrate the legacy FIRST78_67 EquityLedger.

use std::collections::BTreeSet;

use chrono::{DateTime, Timelike, Utc};
use chrono_tz::America::Los_Angeles;
use serde::{Deserialize, Serialize};

pub const POLICY_ID: &str = "MOMENTO_FIRST78_LIVE_V1";
pub const MIN_COMPLETIONS: usize = 10;
pub const ALLOCATION_BPS: u64 = 600;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Epoch {
    pub number: u64,
    pub starting_equity_cents: u64,
    pub trade_budget_cents: u64,
    pub effective_at: DateTime<Utc>,
    pub reconciliation_snapshot_id: String,
    pub completions: BTreeSet<String>,
}

/// Store this value on each admitted trade; never look up its budget again
/// from the active epoch while replacing or partially filling its entry.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct AdmissionBudget {
    pub epoch: u64,
    pub acquisition_budget_cents: u64,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ResizeRecord {
    pub old_epoch: u64,
    pub old_equity_cents: u64,
    pub old_budget_cents: u64,
    pub new_epoch: u64,
    pub new_equity_cents: u64,
    pub new_budget_cents: u64,
    pub calculation_timestamp: DateTime<Utc>,
    pub effective_timestamp: DateTime<Utc>,
    pub reconciliation_snapshot_id: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SizingEpochs {
    epochs: Vec<Epoch>,
    resizes: Vec<ResizeRecord>,
}

#[derive(Clone, Debug)]
pub struct ReconciledEquity {
    pub snapshot_id: String,
    pub equity_cents: u64,
    pub observed_at: DateTime<Utc>,
    pub reconciliation_clean: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ResizeError {
    InvalidEvidence,
    NotPending,
    OutsideWindow,
    ReconciliationRequired,
    EntryConstructionInFlight,
    Overflow,
}

fn budget(equity: u64) -> Result<u64, ResizeError> {
    // Multiply wide, then floor to cents. No float and no overflow at u64 max.
    u64::try_from(u128::from(equity) * u128::from(ALLOCATION_BPS) / 10_000)
        .map_err(|_| ResizeError::Overflow)
}

impl SizingEpochs {
    pub fn new(
        equity_cents: u64,
        at: DateTime<Utc>,
        snapshot_id: String,
    ) -> Result<Self, ResizeError> {
        if snapshot_id.trim().is_empty() {
            return Err(ResizeError::InvalidEvidence);
        }
        Ok(Self {
            epochs: vec![Epoch {
                number: 1,
                starting_equity_cents: equity_cents,
                trade_budget_cents: budget(equity_cents)?,
                effective_at: at,
                reconciliation_snapshot_id: snapshot_id,
                completions: BTreeSet::new(),
            }],
            resizes: Vec::new(),
        })
    }

    pub fn active(&self) -> &Epoch {
        self.epochs
            .last()
            .expect("validated nonempty sizing epochs")
    }

    /// Must be called after decoding persisted state before any admission.
    pub fn validate(&self) -> Result<(), ResizeError> {
        if self.epochs.is_empty() || self.resizes.len() + 1 != self.epochs.len() {
            return Err(ResizeError::InvalidEvidence);
        }
        let mut seen = BTreeSet::new();
        for (i, e) in self.epochs.iter().enumerate() {
            if e.number != i as u64 + 1
                || e.trade_budget_cents != budget(e.starting_equity_cents)?
                || e.reconciliation_snapshot_id.trim().is_empty()
                || e.completions
                    .iter()
                    .any(|id| id.trim().is_empty() || !seen.insert(id))
            {
                return Err(ResizeError::InvalidEvidence);
            }
            if i > 0 {
                let prior = &self.epochs[i - 1];
                let record = &self.resizes[i - 1];
                if prior.completions.len() < MIN_COMPLETIONS
                    || e.effective_at < prior.effective_at
                    || !Self::in_resize_window(e.effective_at)
                    || record.old_epoch != prior.number
                    || record.old_equity_cents != prior.starting_equity_cents
                    || record.old_budget_cents != prior.trade_budget_cents
                    || record.new_epoch != e.number
                    || record.new_equity_cents != e.starting_equity_cents
                    || record.new_budget_cents != e.trade_budget_cents
                    || record.effective_timestamp != e.effective_at
                    || record.calculation_timestamp != e.effective_at
                    || record.reconciliation_snapshot_id != e.reconciliation_snapshot_id
                {
                    return Err(ResizeError::InvalidEvidence);
                }
            }
        }
        Ok(())
    }

    pub fn admission_budget(&self) -> AdmissionBudget {
        AdmissionBudget {
            epoch: self.active().number,
            acquisition_budget_cents: self.active().trade_budget_cents,
        }
    }

    /// Only call for a fully closed/settled trade with final fills and fees
    /// reconciled. The boolean is supplied by the reconciler, not the UI.
    /// Duplicate deliveries never count twice, including across epochs.
    pub fn record_completion(
        &mut self,
        trade_id: &str,
        fully_reconciled: bool,
    ) -> Result<bool, ResizeError> {
        self.validate()?;
        if trade_id.trim().is_empty() || !fully_reconciled {
            return Err(ResizeError::InvalidEvidence);
        }
        if self.epochs.iter().any(|e| e.completions.contains(trade_id)) {
            return Ok(false);
        }
        self.epochs
            .last_mut()
            .expect("validated")
            .completions
            .insert(trade_id.into());
        Ok(true)
    }

    pub fn resize_pending(&self) -> bool {
        self.active().completions.len() >= MIN_COMPLETIONS
    }

    pub fn in_resize_window(at: DateTime<Utc>) -> bool {
        (1..3).contains(&at.with_timezone(&Los_Angeles).hour())
    }

    /// Produce the entire candidate state without mutating the active state.
    /// Commit it durably under the admission lock before replacing active state.
    /// Snapshot maximum age is a required operational setting, not a guessed default.
    pub fn propose_resize(
        &self,
        now: DateTime<Utc>,
        snapshot: &ReconciledEquity,
        max_snapshot_age_ms: i64,
        entry_construction_in_flight: bool,
    ) -> Result<Self, ResizeError> {
        self.validate()?;
        if !self.resize_pending() {
            return Err(ResizeError::NotPending);
        }
        if !Self::in_resize_window(now) {
            return Err(ResizeError::OutsideWindow);
        }
        let age = now
            .signed_duration_since(snapshot.observed_at)
            .num_milliseconds();
        if !snapshot.reconciliation_clean
            || snapshot.snapshot_id.trim().is_empty()
            || max_snapshot_age_ms < 0
            || age < 0
            || age > max_snapshot_age_ms
            || now < self.active().effective_at
        {
            return Err(ResizeError::ReconciliationRequired);
        }
        if entry_construction_in_flight {
            return Err(ResizeError::EntryConstructionInFlight);
        }
        let old = self.active();
        let next = old.number.checked_add(1).ok_or(ResizeError::Overflow)?;
        let new_budget = budget(snapshot.equity_cents)?;
        let mut proposed = self.clone();
        proposed.resizes.push(ResizeRecord {
            old_epoch: old.number,
            old_equity_cents: old.starting_equity_cents,
            old_budget_cents: old.trade_budget_cents,
            new_epoch: next,
            new_equity_cents: snapshot.equity_cents,
            new_budget_cents: new_budget,
            calculation_timestamp: now,
            effective_timestamp: now,
            reconciliation_snapshot_id: snapshot.snapshot_id.clone(),
        });
        proposed.epochs.push(Epoch {
            number: next,
            starting_equity_cents: snapshot.equity_cents,
            trade_budget_cents: new_budget,
            effective_at: now,
            reconciliation_snapshot_id: snapshot.snapshot_id.clone(),
            completions: BTreeSet::new(),
        });
        Ok(proposed)
    }
}
