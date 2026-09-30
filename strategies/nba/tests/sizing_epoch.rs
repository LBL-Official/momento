use chrono::{DateTime, Utc};
use momento_strategy_nba::sizing_epoch::{ReconciledEquity, ResizeError, SizingEpochs};

fn at(s: &str) -> DateTime<Utc> { s.parse().unwrap() }
fn ledger(n: usize) -> SizingEpochs {
    let mut e = SizingEpochs::new(2_000_000, at("2026-09-28T07:00:00Z"), "initial".into()).unwrap();
    for i in 0..n { e.record_completion(&format!("t{i}"), true).unwrap(); }
    e
}
fn snapshot(now: DateTime<Utc>) -> ReconciledEquity {
    ReconciledEquity { snapshot_id: "recon-2".into(), equity_cents: 2_100_000,
        observed_at: now, reconciliation_clean: true }
}

#[test]
fn tenth_and_extended_epoch_keep_old_size_until_window() {
    let e = ledger(13);
    assert!(e.resize_pending());
    assert_eq!(e.admission_budget().acquisition_budget_cents, 120_000);
    let evening = at("2026-09-29T02:00:00Z"); // 19:00 PDT
    assert_eq!(e.propose_resize(evening, &snapshot(evening), 1000, false), Err(ResizeError::OutsideWindow));
    let now = at("2026-09-29T08:00:00Z");
    let old_admission = e.admission_budget();
    let mut next = e.propose_resize(now, &snapshot(now), 1000, false).unwrap();
    assert_eq!(next.admission_budget().acquisition_budget_cents, 126_000);
    assert_eq!(old_admission.acquisition_budget_cents, 120_000);
    assert_eq!(e.active().number, 1); // proposal never mutates active state
    assert!(!next.resize_pending());
    assert!(!next.record_completion("t0", true).unwrap());
    assert_eq!(next.propose_resize(now, &snapshot(now), 1000, false), Err(ResizeError::NotPending));
}

#[test]
fn boundaries_and_both_dst_transitions_use_local_time() {
    for (utc, expected) in [
        ("2026-09-29T07:59:59Z", false), ("2026-09-29T08:00:00Z", true),
        ("2026-09-29T09:59:59Z", true), ("2026-09-29T10:00:00Z", false),
        ("2026-01-29T09:00:00Z", true), ("2026-01-29T11:00:00Z", false),
        ("2026-03-08T09:59:59Z", true), ("2026-03-08T10:00:00Z", false),
        ("2026-11-01T08:30:00Z", true), ("2026-11-01T09:30:00Z", true),
        ("2026-11-01T11:00:00Z", false),
    ] { assert_eq!(SizingEpochs::in_resize_window(at(utc)), expected, "{utc}"); }
}

#[test]
fn reconciliation_and_construction_guards_preserve_pending_epoch() {
    let e = ledger(10);
    let now = at("2026-09-29T08:00:00Z");
    let mut s = snapshot(now);
    assert_eq!(e.propose_resize(now, &s, 1000, true), Err(ResizeError::EntryConstructionInFlight));
    s.reconciliation_clean = false;
    assert_eq!(e.propose_resize(now, &s, 1000, false), Err(ResizeError::ReconciliationRequired));
    s.reconciliation_clean = true;
    s.observed_at = at("2026-09-29T07:59:00Z");
    assert_eq!(e.propose_resize(now, &s, 1000, false), Err(ResizeError::ReconciliationRequired));
    s.observed_at = at("2026-09-29T08:01:00Z");
    assert_eq!(e.propose_resize(now, &s, 1000, false), Err(ResizeError::ReconciliationRequired));
    assert_eq!(e.active().number, 1);
    assert!(e.resize_pending());
}

#[test]
fn restart_roundtrip_preserves_pending_and_duplicate_memory() {
    let e = ledger(10);
    let mut restored: SizingEpochs = serde_json::from_str(&serde_json::to_string(&e).unwrap()).unwrap();
    restored.validate().unwrap();
    assert!(restored.resize_pending());
    assert!(!restored.record_completion("t9", true).unwrap());
    assert!(restored.record_completion("unreconciled", false).is_err());
    assert_eq!(restored, e);
    let now = at("2026-09-29T08:00:00Z");
    let next = restored.propose_resize(now, &snapshot(now), 1000, false).unwrap();
    let next: SizingEpochs = serde_json::from_str(&serde_json::to_string(&next).unwrap()).unwrap();
    next.validate().unwrap();
    assert_eq!(next.active().number, 2);
    assert!(!next.resize_pending());
}

#[test]
fn corrupt_persisted_budget_is_rejected() {
    let mut raw = serde_json::to_value(ledger(10)).unwrap();
    raw["epochs"][0]["trade_budget_cents"] = 999_999.into();
    let invalid: SizingEpochs = serde_json::from_value(raw).unwrap();
    assert_eq!(invalid.validate(), Err(ResizeError::InvalidEvidence));
}

#[test]
fn fewer_than_ten_and_duplicate_completions_cannot_resize() {
    let mut e = ledger(9);
    for _ in 0..10 { assert!(!e.record_completion("t8", true).unwrap()); }
    let now = at("2026-09-29T08:00:00Z");
    assert_eq!(e.propose_resize(now, &snapshot(now), 1000, false), Err(ResizeError::NotPending));
}
