//! Orchestra authority and account-derived performance; no transport or order I/O.
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, Eq, PartialEq, Ord, PartialOrd, Serialize, Deserialize)]
pub enum PortfolioState {
    Normal,
    Caution,
    NoNewEntries,
    ExecutionLocked,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub enum Priority {
    P0,
    P1,
    P2,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Incident {
    pub id: String,
    pub priority: Priority,
    pub state: PortfolioState,
    pub evidence_id: String,
    pub first_seen_ms: i64,
}
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Authority {
    pub incidents: BTreeMap<String, Incident>,
}
impl Authority {
    pub fn state(&self) -> PortfolioState {
        self.incidents
            .values()
            .map(|i| i.state)
            .max()
            .unwrap_or(PortfolioState::Normal)
    }
    pub fn entries_allowed(&self) -> bool {
        self.state() < PortfolioState::NoNewEntries
    }
    pub fn raise(&mut self, incident: Incident) -> Result<(), String> {
        if incident.id.trim().is_empty()
            || incident.evidence_id.trim().is_empty()
            || (incident.priority == Priority::P0 && incident.state < PortfolioState::NoNewEntries)
        {
            return Err("INVALID_INCIDENT".into());
        }
        // Repeat delivery must not silently downgrade an active incident.
        if self
            .incidents
            .get(&incident.id)
            .is_none_or(|old| old.state < incident.state)
        {
            self.incidents.insert(incident.id.clone(), incident);
        }
        Ok(())
    }
    /// Caller journals resolution evidence before publishing the cleared state.
    pub fn resolve(&mut self, id: &str, evidence_id: &str) -> Result<(), String> {
        if evidence_id.trim().is_empty() {
            return Err("RESOLUTION_EVIDENCE_REQUIRED".into());
        }
        if self.incidents.remove(id).is_none() {
            return Err("UNKNOWN_INCIDENT".into());
        }
        Ok(())
    }
}

/// All monetary values are centicents ($0.0001). Cash is not equity.
/// Position value must use the same authoritative valuation convention as the baseline.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AccountSnapshot {
    pub id: String,
    pub observed_ms: i64,
    pub cash: i64,
    pub position_value: i64,
    pub reconciled: bool,
    /// Cumulative external deposits minus withdrawals, independently reconciled.
    pub net_external_flows: i64,
    /// Actual acquisition cash still reserved for orders, not an equity deduction.
    pub reserved_cash: i64,
}
impl AccountSnapshot {
    pub fn equity(&self) -> Result<i64, String> {
        self.cash
            .checked_add(self.position_value)
            .ok_or_else(|| "EQUITY_OVERFLOW".into())
    }
    pub fn available_cash(&self) -> Result<i64, String> {
        self.cash
            .checked_sub(self.reserved_cash)
            .filter(|v| *v >= 0)
            .ok_or_else(|| "CASH_OVERCOMMITTED".into())
    }
}
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Performance {
    pub baseline: Option<AccountSnapshot>,
    pub latest: Option<AccountSnapshot>,
    pub peak_flow_adjusted_equity: Option<i64>,
    pub max_drawdown: i64,
}
impl Performance {
    pub fn observe(&mut self, s: AccountSnapshot, now: i64, max_age_ms: i64) -> Result<(), String> {
        if !s.reconciled
            || s.id.trim().is_empty()
            || s.cash < 0
            || s.position_value < 0
            || s.reserved_cash < 0
            || max_age_ms < 0
            || s.observed_ms > now
            || now - s.observed_ms > max_age_ms
        {
            return Err("ACCOUNT_RECONCILIATION_REQUIRED".into());
        }
        s.available_cash()?;
        let equity = s.equity()?;
        if let Some(prev) = &self.latest {
            if s.observed_ms < prev.observed_ms {
                return Err("ACCOUNT_TIME_REGRESSION".into());
            }
            if s.id == prev.id {
                if serde_json::to_value(&s).unwrap() != serde_json::to_value(prev).unwrap() {
                    return Err("SNAPSHOT_ID_COLLISION".into());
                }
                return Ok(());
            }
        }
        let baseline = self.baseline.as_ref().unwrap_or(&s);
        let flows = s
            .net_external_flows
            .checked_sub(baseline.net_external_flows)
            .ok_or("FLOW_OVERFLOW")?;
        let adjusted = equity.checked_sub(flows).ok_or("EQUITY_OVERFLOW")?;
        let peak = self
            .peak_flow_adjusted_equity
            .unwrap_or(adjusted)
            .max(adjusted);
        let drawdown = peak.checked_sub(adjusted).ok_or("DRAWDOWN_OVERFLOW")?;
        if self.baseline.is_none() {
            self.baseline = Some(s.clone());
        }
        self.peak_flow_adjusted_equity = Some(peak);
        self.max_drawdown = self.max_drawdown.max(drawdown);
        self.latest = Some(s);
        Ok(())
    }
    /// Net total P&L includes realized and mark-to-market changes, already net of fees.
    /// Never add separately reported fees or trade P&L to this value again.
    pub fn net_total_pnl(&self) -> Option<i64> {
        let b = self.baseline.as_ref()?;
        let s = self.latest.as_ref()?;
        s.equity()
            .ok()?
            .checked_sub(b.equity().ok()?)?
            .checked_sub(s.net_external_flows.checked_sub(b.net_external_flows)?)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn snapshot(id: &str, cash: i64, flow: i64) -> AccountSnapshot {
        AccountSnapshot {
            id: id.into(),
            observed_ms: 100,
            cash,
            position_value: 0,
            reconciled: true,
            net_external_flows: flow,
            reserved_cash: 0,
        }
    }
    #[test]
    fn deposit_is_not_profit_and_withdrawal_is_not_loss() {
        let mut p = Performance::default();
        p.observe(snapshot("1", 200_000, 200_000), 100, 10).unwrap(); // $20
        p.observe(snapshot("2", 200_000_000, 200_000_000), 100, 10)
            .unwrap(); // $20,000
        assert_eq!(p.net_total_pnl(), Some(0));
        p.observe(snapshot("3", 200_010_000, 200_000_000), 100, 10)
            .unwrap();
        assert_eq!(p.net_total_pnl(), Some(10_000));
        p.observe(snapshot("4", 110_000, 100_000), 100, 10).unwrap();
        assert_eq!(p.net_total_pnl(), Some(10_000));
        assert_eq!(p.max_drawdown, 0);
    }
    #[test]
    fn snapshot_collision_and_staleness_fail_without_changing_baseline() {
        let mut p = Performance::default();
        assert!(p.observe(snapshot("1", 200_000, 0), 200, 10).is_err());
        assert!(p.baseline.is_none());
        p.observe(snapshot("1", 200_000, 0), 100, 10).unwrap();
        assert!(p.observe(snapshot("1", 300_000, 0), 100, 10).is_err());
        assert_eq!(p.net_total_pnl(), Some(0));
    }
    #[test]
    fn all_incidents_must_clear_and_redelivery_cannot_unlock() {
        let mut a = Authority::default();
        for (id, state) in [
            ("recon", PortfolioState::ExecutionLocked),
            ("feed", PortfolioState::NoNewEntries),
        ] {
            a.raise(Incident {
                id: id.into(),
                priority: Priority::P0,
                state,
                evidence_id: "ev".into(),
                first_seen_ms: 1,
            })
            .unwrap();
        }
        a.resolve("recon", "reconciled").unwrap();
        assert!(!a.entries_allowed());
        a.resolve("feed", "fresh").unwrap();
        assert!(a.entries_allowed());
    }
}
