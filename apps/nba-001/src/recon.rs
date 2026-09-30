//! Paginated V1 account reconciliation. GET-only. Never invents equity.

use std::path::Path;

use momento_kalshi::{
    BALANCE_PATH, FILLS_PATH, KalshiEnvironment, KalshiHttpRequest, KalshiTransport, ORDERS_PATH,
    POSITIONS_PATH, ProductionObserveTransport, TransportOutcome, credentials_from_secret_file,
    redact_secrets,
};
use momento_strategy_nba::money_v1::{MoneyParseError, reconcile_balance_cents};
use momento_strategy_nba::portfolio_v1::AccountSnapshot;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::account::SHARDS;

const SETTLEMENTS_PATH: &str = "/trade-api/v2/portfolio/settlements";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ShardCash {
    pub exchange_index: i64,
    pub cash_cents: Option<i64>,
    pub error: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReconReport {
    pub observed_ms: i64,
    pub ok: bool,
    pub error: Option<String>,
    pub snapshot: Option<AccountSnapshot>,
    pub cash_cents: Option<i64>,
    pub portfolio_value_cents: Option<i64>,
    pub equity_cents: Option<i64>,
    pub equity_formula: &'static str,
    pub shard_cash: Vec<ShardCash>,
    pub position_rows: usize,
    pub resting_orders: usize,
    pub fills: usize,
    pub settlements: usize,
    pub pages_read: usize,
    pub non_get_sent: bool,
    /// True only when cash and portfolio_value were proven disjoint.
    pub fields_disjoint: bool,
}

pub struct Reconciler {
    transport: Option<ProductionObserveTransport>,
    load_error: Option<String>,
}

impl Reconciler {
    pub fn from_secret_file(path: Option<&Path>) -> Self {
        let Some(path) = path else {
            return Self {
                transport: None,
                load_error: Some("MOMENTO_KALSHI_SECRET_FILE unset".into()),
            };
        };
        match credentials_from_secret_file(KalshiEnvironment::Production, path)
            .and_then(ProductionObserveTransport::production)
        {
            Ok(t) => Self {
                transport: Some(t),
                load_error: None,
            },
            Err(e) => Self {
                transport: None,
                load_error: Some(redact_secrets(&e.to_string())),
            },
        }
    }

    fn get(t: &mut ProductionObserveTransport, path: &str) -> Result<Value, String> {
        match t.execute(KalshiHttpRequest {
            method: "GET".into(),
            path: path.into(),
            body: None,
        }) {
            TransportOutcome::Http { status: 200, body } => {
                serde_json::from_str(&body).map_err(|e| format!("json: {e}"))
            }
            TransportOutcome::Http { status, body } => Err(format!(
                "HTTP {status} {}: {}",
                path.split('?').next().unwrap_or(path),
                redact_secrets(&body.chars().take(120).collect::<String>())
            )),
            TransportOutcome::Timeout => Err(format!("timeout {path}")),
        }
    }

    fn paged(
        t: &mut ProductionObserveTransport,
        base: &str,
        key: &str,
        pages: &mut usize,
    ) -> Result<Vec<Value>, String> {
        let mut out = Vec::new();
        let mut cursor: Option<String> = None;
        for _ in 0..40 {
            *pages += 1;
            let path = match &cursor {
                Some(c) => {
                    if base.contains('?') {
                        format!("{base}&cursor={c}")
                    } else {
                        format!("{base}?cursor={c}")
                    }
                }
                None => base.to_string(),
            };
            let v = Self::get(t, &path)?;
            if let Some(arr) = v.get(key).and_then(|a| a.as_array()) {
                out.extend(arr.iter().cloned());
            }
            match v
                .get("cursor")
                .and_then(|c| c.as_str())
                .filter(|c| !c.is_empty())
            {
                Some(next) => cursor = Some(next.to_string()),
                None => return Ok(out),
            }
        }
        Err(format!("{base}: pagination exceeded 40 pages"))
    }

    pub fn reconcile(&mut self, now_ms: i64, snapshot_id: String) -> ReconReport {
        let mut report = ReconReport {
            observed_ms: now_ms,
            ok: false,
            error: self.load_error.clone(),
            snapshot: None,
            cash_cents: None,
            portfolio_value_cents: None,
            equity_cents: None,
            equity_formula: "UNAVAILABLE_UNTIL_DISJOINT",
            shard_cash: Vec::new(),
            position_rows: 0,
            resting_orders: 0,
            fills: 0,
            settlements: 0,
            pages_read: 0,
            non_get_sent: false,
            fields_disjoint: false,
        };
        let Some(t) = self.transport.as_mut() else {
            return report;
        };
        let mut errors = Vec::new();
        match Self::get(t, BALANCE_PATH) {
            Ok(v) => {
                let dollars = v.get("balance_dollars").and_then(|x| x.as_str());
                match v.get("balance").and_then(|x| x.as_i64()) {
                    Some(cents) => match reconcile_balance_cents(cents, dollars) {
                        Ok(c) => report.cash_cents = Some(c),
                        Err(MoneyParseError::UnitMismatch {
                            cents,
                            dollars_cents,
                        }) => {
                            errors.push(format!(
                                "BALANCE_UNIT_MISMATCH cents={cents} dollars_cents={dollars_cents}"
                            ));
                        }
                        Err(e) => errors.push(format!("BALANCE_PARSE:{e:?}")),
                    },
                    None => errors.push("BALANCE_MISSING".into()),
                }
                report.portfolio_value_cents = v.get("portfolio_value").and_then(|x| x.as_i64());
            }
            Err(e) => errors.push(e),
        }
        for shard in SHARDS {
            match Self::get(t, &format!("{BALANCE_PATH}?exchange_index={shard}")) {
                Ok(v) => {
                    let cents = v.get("balance").and_then(|x| x.as_i64());
                    report.shard_cash.push(ShardCash {
                        exchange_index: shard,
                        cash_cents: cents,
                        error: None,
                    });
                }
                Err(e) => report.shard_cash.push(ShardCash {
                    exchange_index: shard,
                    cash_cents: None,
                    error: Some(e),
                }),
            }
        }
        if report.shard_cash.iter().any(|s| s.cash_cents.is_none()) {
            errors.push("SHARD_CASH_UNREAD".into());
        }
        match Self::paged(
            t,
            &format!("{POSITIONS_PATH}?limit=200"),
            "market_positions",
            &mut report.pages_read,
        ) {
            Ok(rows) => report.position_rows = rows.len(),
            Err(e) => errors.push(e),
        }
        match Self::paged(
            t,
            &format!("{ORDERS_PATH}?status=resting&limit=200"),
            "orders",
            &mut report.pages_read,
        ) {
            Ok(rows) => report.resting_orders = rows.len(),
            Err(e) => errors.push(e),
        }
        match Self::paged(
            t,
            &format!("{FILLS_PATH}?limit=200"),
            "fills",
            &mut report.pages_read,
        ) {
            Ok(rows) => report.fills = rows.len(),
            Err(e) => errors.push(e),
        }
        match Self::paged(
            t,
            &format!("{SETTLEMENTS_PATH}?limit=200"),
            "settlements",
            &mut report.pages_read,
        ) {
            Ok(rows) => report.settlements = rows.len(),
            Err(e) => errors.push(format!("settlements:{e}")),
        }

        // Equity = cash + position value only after those fields are present
        // and not the same integer (which would imply double-counting a total).
        if let (Some(cash), Some(pv)) = (report.cash_cents, report.portfolio_value_cents) {
            if cash == pv && report.position_rows > 0 {
                errors.push("CASH_EQUALS_PORTFOLIO_VALUE_WHILE_POSITIONS_OPEN".into());
            } else {
                report.fields_disjoint = true;
                report.equity_formula = "cash_cents + portfolio_value_cents";
                report.equity_cents = cash.checked_add(pv);
                if report.equity_cents.is_none() {
                    errors.push("EQUITY_OVERFLOW".into());
                }
            }
        } else if let Some(cash) = report.cash_cents {
            if report.position_rows == 0 && report.portfolio_value_cents.unwrap_or(0) == 0 {
                report.fields_disjoint = true;
                report.equity_formula = "cash_cents_no_open_positions";
                report.equity_cents = Some(cash);
            } else {
                errors.push("POSITION_VALUE_UNAVAILABLE".into());
            }
        }

        report.non_get_sent = t.non_get_was_sent();
        if report.non_get_sent {
            errors.push("NON_GET_SENT".into());
        }
        report.ok = errors.is_empty() && report.equity_cents.is_some();
        report.error = if errors.is_empty() {
            None
        } else {
            Some(errors.join("; "))
        };
        if report.ok {
            if let Some(eq) = report.equity_cents {
                // Reservations are not an exchange field. Keep 0 until the
                // local outbox supplies them. Do not invent a reserve.
                report.snapshot = Some(AccountSnapshot {
                    id: snapshot_id,
                    observed_ms: now_ms,
                    cash: report.cash_cents.unwrap_or(0).saturating_mul(100),
                    position_value: report
                        .portfolio_value_cents
                        .unwrap_or(0)
                        .saturating_mul(100),
                    reconciled: true,
                    net_external_flows: 0,
                    reserved_cash: 0,
                });
                let _ = eq;
            }
        }
        report
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use momento_strategy_nba::money_v1::dollar_string_to_centicents;

    #[test]
    fn missing_secret_is_unread_not_zero() {
        let mut r = Reconciler::from_secret_file(None);
        let report = r.reconcile(1, "s".into());
        assert!(!report.ok);
        assert!(report.equity_cents.is_none());
        assert_eq!(report.cash_cents, None);
    }

    #[test]
    fn example_budgets_are_not_defaults() {
        assert_eq!(dollar_string_to_centicents("20.00").unwrap(), 200_000);
        assert_eq!(
            dollar_string_to_centicents("20000.00").unwrap(),
            200_000_000
        );
    }
}
