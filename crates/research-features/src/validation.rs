//! Fail-closed B1 invariants.

use crate::availability::FeatureAvailability;
use crate::error::B1Error;
use crate::types::B1EntrySnapshot;
use crate::versions::EXECUTION_STATUS;

#[derive(Clone, Debug, Default, serde::Serialize, serde::Deserialize)]
pub struct ValidationReport {
    pub w8_input_count: usize,
    pub b1_output_count: usize,
    pub games_attempted: usize,
    pub games_represented: usize,
    pub unique_games: usize,
    pub missing_w6_state: usize,
    pub missing_starting_price: usize,
    pub missing_1m: usize,
    pub missing_5m: usize,
    pub missing_15m: usize,
    pub missing_30m: usize,
    pub settlement_unavailable: usize,
    pub feature_lookahead_violations: usize,
    pub outcome_lookahead_violations: usize,
    pub duplicate_entry_ids: usize,
    pub duplicate_game_primary_entries: usize,
    pub unavailable_l2_features: usize,
    pub fake_l2_from_trade: usize,
    pub notes: Vec<String>,
    pub gate: String,
}

pub fn validate_snapshot(s: &B1EntrySnapshot) -> Result<(), B1Error> {
    if s.execution_status != EXECUTION_STATUS {
        return Err(B1Error::validation(
            "NOT_A_FILL",
            format!("execution_status must be {EXECUTION_STATUS}"),
        ));
    }
    if let Some(ts) = s.baseball.state_timestamp {
        if ts > s.entry_timestamp {
            return Err(B1Error::validation(
                "LOOKAHEAD_STATE",
                "W6 state timestamp after entry",
            ));
        }
    }
    for lb in [
        &s.price_dynamics.p_1m,
        &s.price_dynamics.p_5m,
        &s.price_dynamics.p_15m,
        &s.price_dynamics.p_30m,
    ] {
        if let Some(ts) = lb.feature_timestamp {
            if ts > s.entry_timestamp {
                return Err(B1Error::validation(
                    "LOOKAHEAD_FEATURE",
                    "lookback timestamp after entry",
                ));
            }
        }
    }
    if let Some(ts) = s.starting_market.start_timestamp {
        if ts > s.entry_timestamp {
            return Err(B1Error::validation(
                "LOOKAHEAD_START",
                "start timestamp after entry",
            ));
        }
    }
    for ev in &s.event_response.event_history {
        if ev.event_timestamp > s.entry_timestamp {
            return Err(B1Error::validation(
                "LOOKAHEAD_EVENT",
                "event history timestamp after entry",
            ));
        }
    }
    for ex in &s.a1_targets.exits {
        if let Some(ts) = ex.exit_timestamp {
            if ex.triggered && ts <= s.entry_timestamp {
                return Err(B1Error::validation(
                    "A1_EXIT_NOT_FUTURE",
                    format!("{} exit timestamp not after entry", ex.exit_target),
                ));
            }
        }
    }
    for fr in [
        &s.outcomes.future_1m,
        &s.outcomes.future_5m,
        &s.outcomes.future_15m,
        &s.outcomes.future_30m,
    ] {
        if let Some(ts) = fr.outcome_timestamp {
            if ts <= s.entry_timestamp {
                return Err(B1Error::validation(
                    "OUTCOME_NOT_FUTURE",
                    "outcome timestamp not after entry",
                ));
            }
        }
    }
    if s.microstructure.bid != FeatureAvailability::UnavailableSource
        || s.microstructure.ask != FeatureAvailability::UnavailableSource
        || s.microstructure.mid != FeatureAvailability::UnavailableSource
        || s.microstructure.obi_1 != FeatureAvailability::UnavailableSource
        || s.microstructure.ofi_1m != FeatureAvailability::UnavailableSource
        || s.microstructure.microprice != FeatureAvailability::UnavailableSource
        || s.current_market.mid != FeatureAvailability::UnavailableSource
        || s.current_market.d80_mid != FeatureAvailability::UnavailableSource
    {
        return Err(B1Error::validation(
            "FAKE_L2",
            "TRADE-only provider populated bid/ask/mid/OBI/OFI/microprice",
        ));
    }
    if s.fair_value.fair_value_cents.is_some() {
        return Err(B1Error::validation(
            "FAIR_VALUE_LEAK",
            "fair value must stay reserved in B1.1",
        ));
    }
    Ok(())
}

pub fn validate_batch(
    rows: &[B1EntrySnapshot],
    w8_input: usize,
) -> Result<ValidationReport, B1Error> {
    let mut ids = std::collections::BTreeSet::new();
    let mut games = std::collections::BTreeSet::new();
    let mut dup_id = 0;
    let mut dup_game = 0;
    let mut report = ValidationReport {
        w8_input_count: w8_input,
        b1_output_count: rows.len(),
        games_attempted: w8_input,
        notes: vec![
            "B1 is observational. TRADE != maker fill.".into(),
            "Historical L2 UNAVAILABLE. No invented bid/ask/OBI/OFI.".into(),
            "Settlement is W6 only. W9 was not started.".into(),
        ],
        ..ValidationReport::default()
    };
    for s in rows {
        validate_snapshot(s)?;
        if !ids.insert(s.snapshot_id.clone()) {
            dup_id += 1;
        }
        if !games.insert(s.game_id.clone()) {
            dup_game += 1;
        }
        if s.baseball.availability != FeatureAvailability::Available {
            report.missing_w6_state += 1;
        }
        if s.starting_market.p_start_cents.is_none() {
            report.missing_starting_price += 1;
        }
        if s.price_dynamics.p_1m.price_cents.is_none() {
            report.missing_1m += 1;
        }
        if s.price_dynamics.p_5m.price_cents.is_none() {
            report.missing_5m += 1;
        }
        if s.price_dynamics.p_15m.price_cents.is_none() {
            report.missing_15m += 1;
        }
        if s.price_dynamics.p_30m.price_cents.is_none() {
            report.missing_30m += 1;
        }
        if matches!(
            s.outcomes.settlement,
            crate::types::SettlementOutcome::SettlementUnavailable
        ) {
            report.settlement_unavailable += 1;
        }
        report.unavailable_l2_features += 1;
    }
    report.unique_games = games.len();
    report.games_represented = games.len();
    report.duplicate_entry_ids = dup_id;
    report.duplicate_game_primary_entries = dup_game;
    if dup_id > 0 {
        return Err(B1Error::validation(
            "DUPLICATE_SNAPSHOT",
            format!("{dup_id} duplicate snapshot ids"),
        ));
    }
    if dup_game > 0 {
        return Err(B1Error::validation(
            "DUPLICATE_GAME",
            format!("{dup_game} games with more than one primary entry"),
        ));
    }
    report.gate = "COMPLETE".into();
    Ok(report)
}
