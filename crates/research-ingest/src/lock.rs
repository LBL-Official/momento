//! Exclusive ingest lock. Fail closed if another writer holds it.
//! A lock file whose recorded PID is dead is stale and may be reclaimed.

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::PathBuf;
use std::process;

use crate::error::IngestError;

pub struct IngestLock {
    path: PathBuf,
}

impl IngestLock {
    pub fn acquire(path: PathBuf) -> Result<Self, IngestError> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        if path.exists() && lock_pid_is_dead(&path) {
            let _ = fs::remove_file(&path);
        }
        match OpenOptions::new().write(true).create_new(true).open(&path) {
            Ok(mut f) => {
                let _ = writeln!(f, "{}", process::id());
                Ok(Self { path })
            }
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {
                Err(IngestError::ConcurrentWriter(path.display().to_string()))
            }
            Err(e) => Err(e.into()),
        }
    }
}

fn lock_pid_is_dead(path: &std::path::Path) -> bool {
    let Ok(raw) = fs::read_to_string(path) else {
        return false;
    };
    let Ok(pid) = raw.trim().parse::<u32>() else {
        return false;
    };
    !pid_is_alive(pid)
}

fn pid_is_alive(pid: u32) -> bool {
    std::process::Command::new("kill")
        .args(["-0", &pid.to_string()])
        .status()
        .map(|s| s.success())
        .unwrap_or(true)
}

impl Drop for IngestLock {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.path);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn live_holder_blocks_second_acquire() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("ingest.lock");
        let _held = IngestLock::acquire(path.clone()).unwrap();
        assert!(matches!(
            IngestLock::acquire(path),
            Err(IngestError::ConcurrentWriter(_))
        ));
    }

    #[test]
    fn dead_pid_lock_is_reclaimed() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("ingest.lock");
        fs::write(&path, "999999999\n").unwrap();
        let _held = IngestLock::acquire(path.clone()).unwrap();
        assert!(path.exists());
    }

    #[test]
    fn empty_lock_stays_fail_closed() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("ingest.lock");
        fs::write(&path, "").unwrap();
        assert!(matches!(
            IngestLock::acquire(path),
            Err(IngestError::ConcurrentWriter(_))
        ));
    }
}
