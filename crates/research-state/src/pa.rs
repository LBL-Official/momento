//! Plate-appearance lifecycle derived from canonical events. No fabricated pitches.

use chrono::{DateTime, Utc};
use momento_research_event::event::{CanonicalMlbEvent, MlbEventType};
use momento_research_event::field::DataField;

use crate::fingerprint::sha256_hex;
use crate::types::{PA_UNAVAILABLE, PaPhase, is_pa_result, is_pitch, pa_version};

#[derive(Clone, Debug)]
pub struct PaTracker {
    pub seq: u32,
    pub id: DataField<String>,
    pub phase: PaPhase,
    pub start_ts: DataField<DateTime<Utc>>,
    pub end_ts: DataField<DateTime<Utc>>,
    pub result: DataField<String>,
    pub pitch_of_pa: DataField<u8>,
    open: bool,
}

impl PaTracker {
    pub fn new() -> Self {
        Self {
            seq: 0,
            id: DataField::unavailable("no PA yet"),
            phase: PaPhase::None,
            start_ts: DataField::unavailable("no PA yet"),
            end_ts: DataField::unavailable("no PA yet"),
            result: DataField::unavailable("no PA yet"),
            pitch_of_pa: DataField::unavailable(PA_UNAVAILABLE),
            open: false,
        }
    }

    fn open_pa(&mut self, game_id: &str, ts: &DataField<DateTime<Utc>>) {
        self.seq += 1;
        self.id = DataField::derived(
            sha256_hex("w6.pa.id", &[game_id, &self.seq.to_string()]),
            pa_version(),
        );
        self.start_ts = match ts.as_value() {
            Some(t) => DataField::derived(*t, pa_version()),
            None => DataField::unavailable("PA start timestamp missing"),
        };
        self.end_ts = DataField::unavailable("PA in progress");
        self.result = DataField::unavailable("PA in progress");
        self.pitch_of_pa = DataField::unavailable(PA_UNAVAILABLE);
        self.open = true;
        self.phase = PaPhase::Start;
    }

    pub fn apply(&mut self, game_id: &str, event: &CanonicalMlbEvent) {
        let ty = event.event_type;
        let ts = &event.source_timestamp;
        if is_pitch(ty) {
            if !self.open {
                self.open_pa(game_id, ts);
            }
            self.phase = PaPhase::Pitch;
            if let Some(p) = event.pitch.as_ref().and_then(|p| p.pitch_of_pa.as_value()) {
                self.pitch_of_pa = DataField::observed(*p);
            } else {
                let n = self
                    .pitch_of_pa
                    .as_value()
                    .copied()
                    .unwrap_or(0)
                    .saturating_add(1);
                self.pitch_of_pa = DataField::derived(n, pa_version());
            }
            return;
        }
        if is_pa_result(ty) {
            if !self.open {
                self.open_pa(game_id, ts);
            }
            self.phase = PaPhase::Result;
            self.result = DataField::observed(super::fingerprint::event_type_token(ty).to_string());
            self.end_ts = match ts.as_value() {
                Some(t) => DataField::derived(*t, pa_version()),
                None => DataField::unavailable("PA end timestamp missing"),
            };
            self.open = false;
            return;
        }
        if matches!(
            ty,
            MlbEventType::InningEnd | MlbEventType::GameEnd | MlbEventType::GameStart
        ) {
            if self.open {
                self.phase = PaPhase::End;
                self.open = false;
            } else {
                self.phase = PaPhase::None;
            }
            return;
        }
        if self.open {
            if self.phase == PaPhase::Start {
                self.phase = PaPhase::Start;
            }
        } else if self.phase == PaPhase::Result {
            self.phase = PaPhase::End;
        }
    }

    pub fn seq_field(&self) -> DataField<u32> {
        if self.seq == 0 {
            DataField::unavailable("no PA yet")
        } else {
            DataField::derived(self.seq, pa_version())
        }
    }
}

impl Default for PaTracker {
    fn default() -> Self {
        Self::new()
    }
}
