//! Single-writer lease on the state directory. Held for the process life.
//! A lease protects this worker's state only, not shared collateral.

use std::fs::{File, OpenOptions};
use std::path::Path;

pub struct Lease {
    _file: File,
}

impl Lease {
    pub fn acquire(state_dir: &Path) -> Result<Self, String> {
        let path = state_dir.join("lease.lock");
        let file = OpenOptions::new()
            .create(true)
            .truncate(false)
            .write(true)
            .open(&path)
            .map_err(|e| format!("lease {}: {e}", path.display()))?;
        file.try_lock()
            .map_err(|_| "ALREADY_RUNNING: another momento-nba-001 holds the lease".to_string())?;
        Ok(Self { _file: file })
    }
}
