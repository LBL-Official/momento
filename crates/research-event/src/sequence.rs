//! Ordered PBP sequence infrastructure (not ML features).

use serde::{Deserialize, Serialize};

use crate::event::{CanonicalMlbEvent, MlbEventType};
use crate::identity::CanonicalGameId;
use crate::versions::SEQUENCE_VERSION;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PbpSequence {
    pub game_id: CanonicalGameId,
    pub sequence_version: String,
    pub events: Vec<CanonicalMlbEvent>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScoringBurst {
    pub start_sequence: u32,
    pub end_sequence: u32,
    pub runs: u8,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct LeadChange {
    pub sequence: u32,
    pub from_home: u16,
    pub from_away: u16,
    pub to_home: u16,
    pub to_away: u16,
}

impl PbpSequence {
    pub fn new(game_id: CanonicalGameId, mut events: Vec<CanonicalMlbEvent>) -> Self {
        events.sort_by_key(|e| e.sequence);
        Self {
            game_id,
            sequence_version: SEQUENCE_VERSION.to_string(),
            events,
        }
    }

    pub fn last_n_events(&self, n: usize) -> &[CanonicalMlbEvent] {
        let start = self.events.len().saturating_sub(n);
        &self.events[start..]
    }

    pub fn last_n_of_type(&self, ty: MlbEventType, n: usize) -> Vec<&CanonicalMlbEvent> {
        self.events
            .iter()
            .rev()
            .filter(|e| e.event_type == ty)
            .take(n)
            .collect::<Vec<_>>()
            .into_iter()
            .rev()
            .collect()
    }

    pub fn last_n_plate_appearances(&self, n: usize) -> Vec<&CanonicalMlbEvent> {
        const PA: &[MlbEventType] = &[
            MlbEventType::Walk,
            MlbEventType::Strikeout,
            MlbEventType::Single,
            MlbEventType::Double,
            MlbEventType::Triple,
            MlbEventType::HomeRun,
            MlbEventType::Sacrifice,
            MlbEventType::DoublePlay,
            MlbEventType::HitByPitch,
            MlbEventType::Error,
            MlbEventType::FieldersChoice,
            MlbEventType::WalkOff,
        ];
        self.events
            .iter()
            .rev()
            .filter(|e| PA.contains(&e.event_type))
            .take(n)
            .collect::<Vec<_>>()
            .into_iter()
            .rev()
            .collect()
    }

    pub fn last_n_scoring(&self, n: usize) -> Vec<&CanonicalMlbEvent> {
        self.events
            .iter()
            .rev()
            .filter(|e| e.runs_scored.as_value().copied().unwrap_or(0) > 0)
            .take(n)
            .collect::<Vec<_>>()
            .into_iter()
            .rev()
            .collect()
    }

    pub fn last_n_pitching_changes(&self, n: usize) -> Vec<&CanonicalMlbEvent> {
        self.last_n_of_type(MlbEventType::PitchingChange, n)
    }

    pub fn last_n_reviews(&self, n: usize) -> Vec<&CanonicalMlbEvent> {
        self.last_n_of_type(MlbEventType::Review, n)
    }

    pub fn event_type_transitions(&self) -> Vec<(MlbEventType, MlbEventType)> {
        self.events
            .windows(2)
            .map(|w| (w[0].event_type, w[1].event_type))
            .collect()
    }

    pub fn time_between_ms(&self, a_seq: u32, b_seq: u32) -> Option<i64> {
        let a = self.events.iter().find(|e| e.sequence == a_seq)?;
        let b = self.events.iter().find(|e| e.sequence == b_seq)?;
        let ta = a.source_timestamp.as_value()?.timestamp_millis();
        let tb = b.source_timestamp.as_value()?.timestamp_millis();
        Some(tb - ta)
    }

    pub fn scoring_bursts(&self) -> Vec<ScoringBurst> {
        let mut bursts = Vec::new();
        let mut cur: Option<ScoringBurst> = None;
        for e in &self.events {
            let runs = e.runs_scored.as_value().copied().unwrap_or(0);
            if runs > 0 {
                match &mut cur {
                    Some(b) => {
                        b.end_sequence = e.sequence;
                        b.runs = b.runs.saturating_add(runs);
                    }
                    None => {
                        cur = Some(ScoringBurst {
                            start_sequence: e.sequence,
                            end_sequence: e.sequence,
                            runs,
                        });
                    }
                }
            } else if let Some(b) = cur.take() {
                bursts.push(b);
            }
        }
        if let Some(b) = cur {
            bursts.push(b);
        }
        bursts
    }

    pub fn lead_changes(&self) -> Vec<LeadChange> {
        let mut out = Vec::new();
        for w in self.events.windows(2) {
            let Some(a) = w[0].score_after.as_value() else {
                continue;
            };
            let Some(b) = w[1].score_after.as_value() else {
                continue;
            };
            let lead_a = a.home.cmp(&a.away);
            let lead_b = b.home.cmp(&b.away);
            if lead_a != lead_b {
                out.push(LeadChange {
                    sequence: w[1].sequence,
                    from_home: a.home,
                    from_away: a.away,
                    to_home: b.home,
                    to_away: b.away,
                });
            }
        }
        out
    }
}
