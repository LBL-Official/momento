//! SYNTHETIC_TEST_FIXTURE helpers owned by W3. Never counted as historical.

use momento_research_event::event::{CanonicalMlbEvent, FixtureKind};
use momento_research_event::synthetic;

use crate::lifecycle::{MlbGameLifecycle, classify_schedule_status};

pub fn nine_inning_catalog() -> Vec<CanonicalMlbEvent> {
    synthetic::catalog_play_types_valid()
}

pub fn extra_inning() -> Vec<CanonicalMlbEvent> {
    synthetic::extra_inning_walkoff()
}

pub fn scoring_and_runners() -> Vec<CanonicalMlbEvent> {
    synthetic::catalog_play_types_valid()
}

pub fn inning_transition() -> Vec<CanonicalMlbEvent> {
    synthetic::inning_change_after_three_outs()
}

pub fn malformed_envelope() -> &'static str {
    r#"{"envelope_version":"W2.RAW.1.0.0","fixture_kind":"SYNTHETIC_TEST_FIXTURE","source":"mlb_statsapi","source_game_id":"","payload":{}}"#
}

pub fn assert_all_synthetic(events: &[CanonicalMlbEvent]) {
    assert!(
        events
            .iter()
            .all(|e| e.provenance.fixture_kind == FixtureKind::SyntheticTestFixture)
    );
}

pub fn postponed_is_not_final() {
    assert_eq!(
        classify_schedule_status("Postponed"),
        MlbGameLifecycle::Postponed
    );
    assert_eq!(
        classify_schedule_status("Cancelled"),
        MlbGameLifecycle::Cancelled
    );
    assert_eq!(
        classify_schedule_status("Suspended"),
        MlbGameLifecycle::Suspended
    );
}
