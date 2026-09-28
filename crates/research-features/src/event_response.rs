//! Observed TRADE response following W6 events. Not causal proof.

use chrono::{DateTime, Utc};
use momento_research_state::StoredTransition;

use crate::availability::FeatureAvailability;
use crate::price_history::PricedTrade;
use crate::types::{EventClassResponse, EventPathPoint, EventResponseFeatures};
use crate::versions::EVENT_HISTORY_CAP;

pub fn classify_event(raw: &str) -> &'static str {
    match raw {
        "HOME_RUN" | "WALK_OFF" => "RUN",
        "SINGLE" | "DOUBLE" | "TRIPLE" => "HIT",
        "WALK" | "HIT_BY_PITCH" | "CATCHERS_INTERFERENCE" => "WALK",
        "STRIKEOUT" => "STRIKEOUT",
        "FIELD_OUT" | "FORCE_OUT" | "DOUBLE_PLAY" | "SACRIFICE" | "FIELDERS_CHOICE" => "OUT",
        "STOLEN_BASE" | "WILD_PITCH" | "PASSED_BALL" | "BALK" => "RUNNER_ADVANCEMENT",
        "INNING_START" | "INNING_END" => "INNING_CHANGE",
        "PITCHING_CHANGE" => "PITCHING_CHANGE",
        _ => "UNMAPPED",
    }
}

pub fn event_responses(
    transitions: &[StoredTransition],
    prior_and_entry: &[PricedTrade<'_>],
    entry: DateTime<Utc>,
) -> EventResponseFeatures {
    let mut by_class: Vec<EventClassResponse> = Vec::new();
    let classes = [
        "RUN",
        "HIT",
        "WALK",
        "STRIKEOUT",
        "OUT",
        "RUNNER_ADVANCEMENT",
        "INNING_CHANGE",
        "PITCHING_CHANGE",
    ];
    for class in classes {
        by_class.push(EventClassResponse {
            event_class: class.to_string(),
            n_events: 0,
            n_with_price_response: 0,
            last_delta_cents: None,
            last_event_id: None,
            last_event_timestamp: None,
        });
    }

    let mut event_history = Vec::new();
    for tr in transitions {
        let Some(ts) = tr.event_timestamp else {
            continue;
        };
        if ts > entry {
            continue;
        }
        let class = classify_event(&tr.event_type);
        let before = prior_and_entry
            .iter()
            .rev()
            .find(|t| t.ts <= ts)
            .map(|t| t.price);
        // Feature responses use only trades at or before entry.
        let after_feature = prior_and_entry
            .iter()
            .filter(|t| t.ts > ts && t.ts <= entry)
            .min_by_key(|t| (t.ts, t.observation_id))
            .map(|t| t.price);
        let delta = match (before, after_feature) {
            (Some(b), Some(a)) => Some(a - b),
            _ => None,
        };
        event_history.push(EventPathPoint {
            event_id: tr.event_id.clone(),
            event_class: class.to_string(),
            event_type: tr.event_type.clone(),
            event_timestamp: ts,
            p_before_cents: before,
            p_after_cents: after_feature,
            delta_cents: delta,
        });
        if class == "UNMAPPED" {
            continue;
        }
        let slot = by_class.iter_mut().find(|c| c.event_class == class);
        let Some(slot) = slot else {
            continue;
        };
        slot.n_events += 1;
        if let Some(d) = delta {
            slot.n_with_price_response += 1;
            slot.last_delta_cents = Some(d);
            slot.last_event_id = Some(tr.event_id.clone());
            slot.last_event_timestamp = Some(ts);
        }
    }
    if event_history.len() > EVENT_HISTORY_CAP {
        let skip = event_history.len() - EVENT_HISTORY_CAP;
        event_history.drain(0..skip);
    }

    EventResponseFeatures {
        availability: FeatureAvailability::Available,
        note: "Observed TRADE response following W6 event. Not a causal claim.".to_string(),
        responses: by_class,
        event_history,
    }
}
