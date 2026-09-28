//! W2-A MLB source contract: inventory, hierarchy, provenance, missing/duplicate rules.

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::versions::SOURCE_CONTRACT_VERSION;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SourceRole {
    Primary,
    Secondary,
    Fallback,
    CandidateUnlicensed,
    Absent,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MlbSourceDescriptor {
    pub provider: String,
    pub api_or_source_name: String,
    pub role: SourceRole,
    pub historical_coverage: String,
    pub timestamp_semantics: String,
    pub game_identifiers: String,
    pub event_identifiers: String,
    pub pitch_level: String,
    pub score: String,
    pub lineup: String,
    pub player_identifiers: String,
    pub venue: String,
    pub inning: String,
    pub base_state: String,
    pub outs: String,
    pub batter_pitcher: String,
    pub review: String,
    pub limitations: String,
    pub licensing: String,
    pub present_in_repository: bool,
    pub local_paths: Vec<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SourceContract {
    pub contract_version: String,
    pub authoritative_hierarchy: Vec<String>,
    pub automatic_substitution: bool,
    pub authoritative_event_definition: String,
    pub missing_data: String,
    pub duplicate_events: String,
    pub corrected_pbp: String,
    pub source_conflict: String,
    pub timestamp_domains: Vec<String>,
    pub sources: Vec<MlbSourceDescriptor>,
}

pub fn source_contract() -> SourceContract {
    SourceContract {
        contract_version: SOURCE_CONTRACT_VERSION.to_string(),
        authoritative_hierarchy: vec![
            "PRIMARY (when licensed/present): MLB StatsAPI game feed (gamePk + liveData.plays)".into(),
            "SECONDARY (pitch enrichment, not a substitute for missing official plays): Baseball Savant / Statcast".into(),
            "FALLBACK: none. Retrosheet/other feeds require a new parser version and explicit authorization.".into(),
        ],
        automatic_substitution: false,
        authoritative_event_definition: "\
An authoritative event is a discrete official PBP record from the primary source that \
identifies a game, a source event id, and a sequence position. Pitches, plays, substitutions, \
reviews, and inning/game boundary records qualify. Kalshi trades are NOT MLB events. \
Market existence never creates a baseball event.".into(),
        missing_data: "\
Missing fields are DataField::Unavailable { reason }. Missing games/seasons are \
MISSING_HISTORICAL_SOURCE. Never synthesize state because a Kalshi market exists.".into(),
        duplicate_events: "\
Same (source, source_game_id, source_event_id): identical payload is idempotent; \
divergent payload is a conflict (fail closed). Sequence collisions fail closed.".into(),
        corrected_pbp: "\
Amendments (review overturn, official correction) are explicit events citing amends_event_id. \
Raw source bytes are never overwritten. Canonical sequence applies amendments in order.".into(),
        source_conflict: "\
Disagreement between primary and secondary is recorded as SOURCE_CONFLICT. \
W2 does not auto-pick a winner.".into(),
        timestamp_domains: vec![
            "source_event_timestamp — official PBP time (nullable + reason)".into(),
            "source_received_timestamp — vendor received, if any".into(),
            "collector_timestamp — Momento ingest wall clock".into(),
            "game_clock — inning/half/outs (not UTC)".into(),
            "canonical_order — sequence number; optional source time for ties".into(),
        ],
        sources: inventory_static(),
    }
}

fn inventory_static() -> Vec<MlbSourceDescriptor> {
    vec![
        MlbSourceDescriptor {
            provider: "MLB / MLB Advanced Media".into(),
            api_or_source_name: "statsapi.mlb.com game feed (liveData.plays.allPlays)".into(),
            role: SourceRole::Primary,
            historical_coverage: "Collected locally for 2026-06-18..30 (Kalshi window) into Foundation/W2/raw/statsapi. Not written to Data-Real.".into(),
            timestamp_semantics: "Play startTime/endTime when present; not Kalshi clocks.".into(),
            game_identifiers: "gamePk".into(),
            event_identifiers: "playId / atBatIndex+playEvents index".into(),
            pitch_level: "playEvents[] when source includes them".into(),
            score: "result.homeScore / awayScore".into(),
            lineup: "boxscore (separate payload; optional)".into(),
            player_identifiers: "MLB player id".into(),
            venue: "gameData.venue".into(),
            inning: "about.inning / halfInning".into(),
            base_state: "runners[] / matchup post-on".into(),
            outs: "count.outs".into(),
            batter_pitcher: "matchup.batter / pitcher".into(),
            review: "about.hasReview / review details when present".into(),
            limitations: "Public StatsAPI; ToS still apply. Pitch-level incomplete vs Savant.".into(),
            licensing: "CEO authorized free StatsAPI collection 2026-08-26 for W2-E/W2-B. Not a Kalshi lake write.".into(),
            present_in_repository: true,
            local_paths: vec!["Backtesting Suite/Foundation/W2/raw/statsapi/".into()],
        },
        MlbSourceDescriptor {
            provider: "Baseball Savant".into(),
            api_or_source_name: "Statcast search / game feed".into(),
            role: SourceRole::Secondary,
            historical_coverage: "Not present locally.".into(),
            timestamp_semantics: "Pitch timestamps independent of Kalshi.".into(),
            game_identifiers: "game_pk".into(),
            event_identifiers: "pitch_number / play_id".into(),
            pitch_level: "Pitch-by-pitch when licensed".into(),
            score: "Often present".into(),
            lineup: "Partial".into(),
            player_identifiers: "MLBAM id".into(),
            venue: "Yes".into(),
            inning: "Yes".into(),
            base_state: "Yes".into(),
            outs: "Yes".into(),
            batter_pitcher: "Yes".into(),
            review: "Not guaranteed".into(),
            limitations: "Not a silent substitute for StatsAPI play sequence.".into(),
            licensing: "Not authorized.".into(),
            present_in_repository: false,
            local_paths: vec![],
        },
        MlbSourceDescriptor {
            provider: "Kalshi".into(),
            api_or_source_name: "KXMLBGAME REST historical (W1 lake)".into(),
            role: SourceRole::Absent,
            historical_coverage: "13 COMPLETE PT days 2026-06-18..30; 2025 probes empty.".into(),
            timestamp_semantics: "Trade created_time / candle end_period_ts — MARKET clocks."
                .into(),
            game_identifiers: "event_ticker → W1 GameId hash. mlb_game_pk UNMAPPED.".into(),
            event_identifiers: "Not PBP.".into(),
            pitch_level: "None".into(),
            score: "None (settlement result is OUTCOME_LABEL, not PBP score)".into(),
            lineup: "None".into(),
            player_identifiers: "None".into(),
            venue: "None".into(),
            inning: "None".into(),
            base_state: "None".into(),
            outs: "None".into(),
            batter_pitcher: "None".into(),
            review: "None".into(),
            limitations: "Cannot reconstruct baseball state. W3/W4 market path only.".into(),
            licensing: "Kalshi public historical REST (already in W1 lake).".into(),
            present_in_repository: true,
            local_paths: vec!["Backtesting Suite/Data-Real/MLB/2025-2026/".into()],
        },
        MlbSourceDescriptor {
            provider: "Retrosheet / other".into(),
            api_or_source_name: "event files".into(),
            role: SourceRole::CandidateUnlicensed,
            historical_coverage: "Not present.".into(),
            timestamp_semantics: "Often play sequence without wall clock.".into(),
            game_identifiers: "Retrosheet id — not used unless a versioned parser is added.".into(),
            event_identifiers: "Event index".into(),
            pitch_level: "Pitch strings when present".into(),
            score: "Yes".into(),
            lineup: "Yes".into(),
            player_identifiers: "Retrosheet ids".into(),
            venue: "Park id".into(),
            inning: "Yes".into(),
            base_state: "Yes".into(),
            outs: "Yes".into(),
            batter_pitcher: "Yes".into(),
            review: "Era-dependent".into(),
            limitations: "No parser in W2. Do not treat as installed.".into(),
            licensing: "Not authorized.".into(),
            present_in_repository: false,
            local_paths: vec![],
        },
    ]
}

/// Discover PBP files on disk. Never downloads. Never fabricates.
pub fn discover_local_pbp(roots: &[PathBuf]) -> LocalPbpDiscovery {
    let mut files = Vec::new();
    for root in roots {
        walk_pbp(root, root, &mut files);
    }
    let env_keys = [
        "MLB_PBP_DIR",
        "MOMENTO_MLB_PBP_DIR",
        "STATSAPI_TOKEN",
        "SAVANT_API_KEY",
    ];
    let env_present: Vec<String> = env_keys
        .iter()
        .filter(|k| std::env::var(k).is_ok())
        .map(|s| (*s).to_string())
        .collect();
    let historical_pbp_available = !files.is_empty();
    LocalPbpDiscovery {
        files,
        env_keys_present: env_present,
        historical_pbp_available,
    }
}

fn walk_pbp(_root: &Path, dir: &Path, out: &mut Vec<PathBuf>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for ent in entries.flatten() {
        let path = ent.path();
        let name = path
            .file_name()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_ascii_lowercase();
        if path.is_dir() {
            if name == "node_modules" || name == "target" || name.starts_with('.') {
                continue;
            }
            walk_pbp(_root, &path, out);
        } else if name.contains("pbp")
            || name.contains("playbyplay")
            || name.contains("play-by-play")
            || name.contains("statsapi")
            || (name.ends_with(".envelope.json")
                && path.components().any(|c| c.as_os_str() == "statsapi"))
        {
            out.push(path);
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct LocalPbpDiscovery {
    pub files: Vec<PathBuf>,
    pub env_keys_present: Vec<String>,
    pub historical_pbp_available: bool,
}

impl LocalPbpDiscovery {
    pub fn note(&self) -> String {
        if self.files.is_empty() {
            "MISSING_HISTORICAL_SOURCE: no local MLB PBP files discovered.".into()
        } else {
            format!(
                "Found {} path(s) matching pbp/statsapi name pattern; treat as unverified until parsed.",
                self.files.len()
            )
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn contract_forbids_auto_substitution() {
        let c = source_contract();
        assert!(!c.automatic_substitution);
        assert!(
            c.sources
                .iter()
                .any(|s| s.api_or_source_name.contains("statsapi"))
        );
        assert!(
            c.sources
                .iter()
                .any(|s| s.provider == "Kalshi" && s.present_in_repository)
        );
    }
}
