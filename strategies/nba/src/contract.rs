//! Reads `execution_contract.json`. Unknown or unresolved fields block.

use serde::{Deserialize, Serialize};

use crate::reserve::ExitBound;
use crate::{ENTRY_CENTS, LADDER_CAP_CENTS, STOP_CENTS, TOP_OUT_CENTS};

pub const CONTRACT_SCHEMA: &str = "nba_001_execution_contract_v1";

/// Fields whose resolution is required before a new entry can be admitted.
pub const ENTRY_PATH_FIELDS: [&str; 6] = [
    "hedge_ladder_advancement",
    "hedge_initial_limit_gap_policy",
    "emergency_action",
    "data_outage_policy",
    "entry_order",
    "slot_and_batch_release",
];

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ContractError {
    Json(String),
    Schema(String),
    Mismatch(String),
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ContractStatus {
    pub contract_id: String,
    pub unresolved: Vec<String>,
    pub fees_verified: bool,
    pub emergency: ExitBound,
    /// Entry order resolved as post-only (maker). False = taker bound.
    #[serde(default)]
    pub entry_post_only: bool,
    pub hedge_pre_trigger_orders: bool,
    /// Owner flag in the contract. Production also needs the compiled gate.
    pub production_submission_enabled: bool,
    /// Batch 2+ sizing formula approved.
    pub batch_resize_approved: bool,
}

fn field<'a>(
    root: &'a serde_json::Value,
    name: &str,
) -> Result<&'a serde_json::Value, ContractError> {
    root.get("fields")
        .and_then(|f| f.get(name))
        .ok_or_else(|| ContractError::Schema(format!("fields.{name} missing")))
}

fn status(root: &serde_json::Value, name: &str) -> Result<String, ContractError> {
    field(root, name)?
        .get("status")
        .and_then(|s| s.as_str())
        .map(str::to_string)
        .ok_or_else(|| ContractError::Schema(format!("fields.{name}.status missing")))
}

fn expect_u64(
    root: &serde_json::Value,
    name: &str,
    key: &str,
    want: u16,
) -> Result<(), ContractError> {
    let got = field(root, name)?.get(key).and_then(|v| v.as_u64());
    if got != Some(u64::from(want)) {
        return Err(ContractError::Mismatch(format!(
            "fields.{name}.{key} = {got:?}, compiled {want}"
        )));
    }
    Ok(())
}

impl ContractStatus {
    pub fn parse(json: &str) -> Result<Self, ContractError> {
        let root: serde_json::Value =
            serde_json::from_str(json).map_err(|e| ContractError::Json(e.to_string()))?;
        if root.get("schema_version").and_then(|v| v.as_str()) != Some(CONTRACT_SCHEMA) {
            return Err(ContractError::Schema("schema_version".into()));
        }
        expect_u64(&root, "entry", "entry_cents", ENTRY_CENTS)?;
        expect_u64(&root, "exit_trigger", "stop_cents", STOP_CENTS)?;
        expect_u64(&root, "top_out", "ceiling_cents", TOP_OUT_CENTS)?;
        let cap = field(&root, "hedge_ladder_prices")?
            .get("submittable_limit_range_cents")
            .and_then(|v| v.as_array())
            .and_then(|a| a.get(1))
            .and_then(|v| v.as_u64());
        if cap != Some(u64::from(LADDER_CAP_CENTS)) {
            return Err(ContractError::Mismatch("ladder cap".into()));
        }
        let pre = field(&root, "hedge_pre_trigger_orders")?
            .get("value")
            .and_then(|v| v.as_bool())
            .ok_or_else(|| ContractError::Schema("hedge_pre_trigger_orders.value".into()))?;
        if pre {
            return Err(ContractError::Mismatch(
                "hedge_pre_trigger_orders must be false (owner-resolved)".into(),
            ));
        }
        let mut unresolved = Vec::new();
        for name in ENTRY_PATH_FIELDS {
            if status(&root, name)? != "RESOLVED" {
                unresolved.push(name.to_string());
            }
        }
        let fees_verified = status(&root, "fees")? == "VERIFIED";
        let emergency = if status(&root, "emergency_action")? == "RESOLVED" {
            let f = field(&root, "emergency_action")?;
            let cents = |key: &str| {
                f.get(key)
                    .and_then(|v| v.as_u64())
                    .and_then(|v| u16::try_from(v).ok())
                    .filter(|v| (1..100).contains(v))
            };
            match f.get("action").and_then(|v| v.as_str()) {
                Some("SELL_ORIGINAL_REDUCE_ONLY_IOC") => cents("floor_cents")
                    .map_or(ExitBound::Unbounded, |floor_cents| {
                        ExitBound::SellOriginal { floor_cents }
                    }),
                Some("BUY_OPPONENT_IOC") | None => cents("worst_price_bound_cents")
                    .map_or(ExitBound::Unbounded, |worst_price_cents| {
                        ExitBound::Bounded { worst_price_cents }
                    }),
                Some(_) => ExitBound::Unbounded,
            }
        } else {
            ExitBound::Unbounded
        };
        let entry_post_only = status(&root, "entry_order")? == "RESOLVED"
            && field(&root, "entry_order")?
                .get("post_only")
                .and_then(|v| v.as_bool())
                == Some(true);
        Ok(Self {
            contract_id: root
                .get("contract_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            unresolved,
            fees_verified,
            emergency,
            entry_post_only,
            hedge_pre_trigger_orders: pre,
            production_submission_enabled: root
                .get("production_submission_enabled")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            batch_resize_approved: status(&root, "batch_resize")? == "RESOLVED",
        })
    }
}
