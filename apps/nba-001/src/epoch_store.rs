//! Durable V1 sizing store. Not yet wired into the legacy worker loop.
//! Its exclusive lease must also cover future V1 admission/reservation writes.
//! The store fails closed after any failed commit; reopen and reconcile before use.
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

use chrono::{DateTime, Utc};
use momento_strategy_nba::sizing_epoch::{AdmissionBudget, ReconciledEquity, SizingEpochs};

use crate::lease::Lease;

pub struct EpochStore {
    dir: PathBuf,
    _lease: Lease,
    state: SizingEpochs,
    healthy: bool,
}

impl EpochStore {
    /// Initialization is explicit and refuses any existing directory. Restart
    /// must call open(), never initialize a new bankroll on missing/corrupt state.
    pub fn create(dir: &Path, state: SizingEpochs) -> Result<Self, String> {
        state.validate().map_err(|e| format!("{e:?}"))?;
        std::fs::create_dir(dir).map_err(|e| e.to_string())?;
        let lease = Lease::acquire(dir)?;
        let mut store = Self {
            dir: dir.into(),
            _lease: lease,
            state,
            healthy: false,
        };
        let initial = store.state.clone();
        store.commit(initial)?;
        Ok(store)
    }

    pub fn open(dir: &Path) -> Result<Self, String> {
        let lease = Lease::acquire(dir)?;
        let bytes = std::fs::read(dir.join("sizing_epochs.json")).map_err(|e| e.to_string())?;
        let state: SizingEpochs = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
        state.validate().map_err(|e| format!("{e:?}"))?;
        Ok(Self {
            dir: dir.into(),
            _lease: lease,
            state,
            healthy: true,
        })
    }

    fn require_healthy(&self) -> Result<(), String> {
        if self.healthy {
            Ok(())
        } else {
            Err("SIZING_STORE_RECONCILIATION_REQUIRED".into())
        }
    }

    pub fn admission_budget(&self) -> Result<AdmissionBudget, String> {
        self.require_healthy()?;
        Ok(self.state.admission_budget())
    }

    pub fn record_completion(&mut self, id: &str, fully_reconciled: bool) -> Result<bool, String> {
        self.require_healthy()?;
        let mut proposed = self.state.clone();
        let changed = proposed
            .record_completion(id, fully_reconciled)
            .map_err(|e| format!("{e:?}"))?;
        if changed {
            self.commit(proposed)?;
        }
        Ok(changed)
    }

    pub fn resize(
        &mut self,
        now: DateTime<Utc>,
        snapshot: &ReconciledEquity,
        max_age_ms: i64,
        entry_construction_in_flight: bool,
    ) -> Result<(), String> {
        self.require_healthy()?;
        let next = self
            .state
            .propose_resize(now, snapshot, max_age_ms, entry_construction_in_flight)
            .map_err(|e| format!("{e:?}"))?;
        self.commit(next)
    }

    fn commit(&mut self, next: SizingEpochs) -> Result<(), String> {
        next.validate().map_err(|e| format!("{e:?}"))?;
        let bytes = serde_json::to_vec_pretty(&next).map_err(|e| e.to_string())?;
        self.healthy = false;
        let tmp = self.dir.join("sizing_epochs.tmp");
        let mut file = OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .open(&tmp)
            .map_err(|e| e.to_string())?;
        file.write_all(&bytes).map_err(|e| e.to_string())?;
        file.sync_all().map_err(|e| e.to_string())?;
        std::fs::rename(&tmp, self.dir.join("sizing_epochs.json")).map_err(|e| e.to_string())?;
        File::open(&self.dir)
            .and_then(|f| f.sync_all())
            .map_err(|e| e.to_string())?;
        self.state = next;
        self.healthy = true;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn durable_resize_reopen_and_single_writer() {
        let suffix = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir =
            std::env::temp_dir().join(format!("momento-epoch-{}-{suffix}", std::process::id()));
        let at: DateTime<Utc> = "2026-09-29T08:00:00Z".parse().unwrap();
        let state = SizingEpochs::new(2_000_000, at, "initial".into()).unwrap();
        let mut store = EpochStore::create(&dir, state).unwrap();
        assert!(EpochStore::open(&dir).is_err());
        for n in 0..13 {
            store.record_completion(&format!("t{n}"), true).unwrap();
        }
        drop(store);
        let mut store = EpochStore::open(&dir).unwrap();
        assert_eq!(
            store.admission_budget().unwrap().acquisition_budget_cents,
            120_000
        );
        assert!(!store.record_completion("t0", true).unwrap());
        let snapshot = ReconciledEquity {
            snapshot_id: "recon".into(),
            equity_cents: 2_100_000,
            observed_at: at,
            reconciliation_clean: true,
        };
        store.resize(at, &snapshot, 1000, false).unwrap();
        drop(store);
        let store = EpochStore::open(&dir).unwrap();
        assert_eq!(store.admission_budget().unwrap().epoch, 2);
        assert_eq!(
            store.admission_budget().unwrap().acquisition_budget_cents,
            126_000
        );
        drop(store);
        std::fs::write(dir.join("sizing_epochs.json"), b"broken").unwrap();
        assert!(EpochStore::open(&dir).is_err());
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
