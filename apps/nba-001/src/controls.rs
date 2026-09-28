//! Operator controls file. Missing file = all off. Malformed = paused.

use std::path::Path;

use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Controls {
    #[serde(default)]
    pub pause_entries: bool,
    #[serde(default)]
    pub cancel_pending_entries: bool,
    #[serde(default)]
    pub emergency_exit: bool,
    #[serde(default)]
    pub full_stop: bool,
    #[serde(skip_deserializing)]
    pub read_error: Option<String>,
}

pub fn read_controls(state_dir: &Path) -> Controls {
    let path = state_dir.join("control.json");
    match std::fs::read_to_string(&path) {
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Controls::default(),
        Err(e) => Controls {
            pause_entries: true,
            read_error: Some(e.to_string()),
            ..Controls::default()
        },
        Ok(raw) => serde_json::from_str(&raw).unwrap_or_else(|e| Controls {
            pause_entries: true,
            read_error: Some(format!("control.json: {e}")),
            ..Controls::default()
        }),
    }
}
