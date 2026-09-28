//! Cloud worker execution boundary. Does not claim a live deploy.

use serde::{Deserialize, Serialize};

use crate::types::ExecutionMode;

pub const CLOUD_STATUS_IMPLEMENTED_NOT_DEPLOYED: &str = "IMPLEMENTED_NOT_DEPLOYED";
pub const CLOUD_STATUS_DEPLOYED: &str = "DEPLOYED";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CloudWorkerSpec {
    pub execution_mode: ExecutionMode,
    pub timezone: String,
    pub weekly_weekday: String,
    pub weekly_hour_local: u32,
    pub resumable: bool,
    pub idempotent: bool,
    pub bounded_retries: bool,
    pub structured_logs: bool,
    pub persistent_run_state: bool,
    pub failure_notification: bool,
    pub deployment_status: String,
}

impl CloudWorkerSpec {
    pub fn specified_not_deployed(mode: ExecutionMode) -> Self {
        Self {
            execution_mode: mode,
            timezone: "America/Los_Angeles".into(),
            weekly_weekday: "Sunday".into(),
            weekly_hour_local: 0,
            resumable: true,
            idempotent: true,
            bounded_retries: true,
            structured_logs: true,
            persistent_run_state: true,
            failure_notification: true,
            deployment_status: cloud_deployment_status(),
        }
    }
}

pub fn cloud_deployment_status() -> String {
    std::env::var("MOMENTO_INGEST_CLOUD_STATUS")
        .ok()
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| CLOUD_STATUS_IMPLEMENTED_NOT_DEPLOYED.to_string())
}
