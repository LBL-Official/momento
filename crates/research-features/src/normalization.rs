//! State-conditioned z-scores. μ/σ must come from TRAIN only.

use crate::availability::FeatureAvailability;
use crate::types::{B1EntrySnapshot, SplitGroup};

/// Minimum unique TRAIN games in a regime before a z-score is attached.
const MIN_TRAIN_GAMES_FOR_Z: usize = 20;

#[derive(Clone, Debug, PartialEq)]
pub struct TrainMoments {
    pub n: usize,
    pub mean: f64,
    pub stdev: f64,
}

/// Population moments from the training slice only.
pub fn train_moments(values: &[f64]) -> Option<TrainMoments> {
    if values.len() < 2 {
        return None;
    }
    let n = values.len() as f64;
    let mean = values.iter().sum::<f64>() / n;
    let var = values.iter().map(|v| (v - mean) * (v - mean)).sum::<f64>() / n;
    Some(TrainMoments {
        n: values.len(),
        mean,
        stdev: var.sqrt(),
    })
}

pub fn z_score(x: f64, moments: &TrainMoments) -> Option<f64> {
    if moments.stdev == 0.0 {
        None
    } else {
        Some((x - moments.mean) / moments.stdev)
    }
}

pub fn chronological_split(official_or_entry_date: &str, cutoff: &str) -> SplitGroup {
    if official_or_entry_date < cutoff {
        SplitGroup::Train
    } else {
        SplitGroup::Test
    }
}

fn z_e3(x: f64, moments: &TrainMoments) -> Option<i32> {
    z_score(x, moments).map(|z| (z * 1000.0).round() as i32)
}

/// Attach regime-conditioned z-scores using TRAIN μ/σ only.
/// L2 residuals stay UNAVAILABLE. This never uses TEST to fit.
pub fn attach_train_conditioned_z(rows: &mut [B1EntrySnapshot]) {
    use std::collections::{BTreeMap, BTreeSet};
    let mut vol_by_regime: BTreeMap<String, Vec<f64>> = BTreeMap::new();
    let mut move_by_regime: BTreeMap<String, Vec<f64>> = BTreeMap::new();
    let mut games_by_regime: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for s in rows.iter() {
        if s.split_group != SplitGroup::Train {
            continue;
        }
        let key = s.baseball.regime.as_str().to_string();
        games_by_regime
            .entry(key.clone())
            .or_default()
            .insert(s.game_id.clone());
        if let Some(v) = s.market_history.volatility_5m_cents {
            vol_by_regime
                .entry(key.clone())
                .or_default()
                .push(f64::from(v));
        }
        if let Some(v) = s.market_history.start_to_entry_move_cents {
            move_by_regime.entry(key).or_default().push(f64::from(v));
        }
    }
    let vol_moments: BTreeMap<String, TrainMoments> = vol_by_regime
        .into_iter()
        .filter_map(|(k, xs)| {
            if games_by_regime.get(&k).map(|g| g.len()).unwrap_or(0) < MIN_TRAIN_GAMES_FOR_Z {
                return None;
            }
            train_moments(&xs).map(|m| (k, m))
        })
        .collect();
    let move_moments: BTreeMap<String, TrainMoments> = move_by_regime
        .into_iter()
        .filter_map(|(k, xs)| {
            if games_by_regime.get(&k).map(|g| g.len()).unwrap_or(0) < MIN_TRAIN_GAMES_FOR_Z {
                return None;
            }
            train_moments(&xs).map(|m| (k, m))
        })
        .collect();
    for s in rows.iter_mut() {
        let key = s.baseball.regime.as_str();
        match (s.market_history.volatility_5m_cents, vol_moments.get(key)) {
            (Some(v), Some(m)) => {
                s.market_history.volatility_5m_z_e3 = z_e3(f64::from(v), m);
                s.market_history.volatility_z_availability =
                    if s.market_history.volatility_5m_z_e3.is_some() {
                        FeatureAvailability::Available
                    } else {
                        FeatureAvailability::NotApplicable
                    };
            }
            _ => {
                s.market_history.volatility_z_availability =
                    FeatureAvailability::InsufficientHistory;
            }
        }
        match (
            s.market_history.start_to_entry_move_cents,
            move_moments.get(key),
        ) {
            (Some(v), Some(m)) => {
                s.market_history.start_to_entry_move_z_e3 = z_e3(f64::from(v), m);
                s.market_history.start_to_entry_move_z_availability =
                    if s.market_history.start_to_entry_move_z_e3.is_some() {
                        FeatureAvailability::Available
                    } else {
                        FeatureAvailability::NotApplicable
                    };
            }
            _ => {
                s.market_history.start_to_entry_move_z_availability =
                    FeatureAvailability::InsufficientHistory;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn train_only_cutoff() {
        assert_eq!(
            chronological_split("2025-08-01", "2026-01-01"),
            SplitGroup::Train
        );
        assert_eq!(
            chronological_split("2026-04-01", "2026-01-01"),
            SplitGroup::Test
        );
    }
}
