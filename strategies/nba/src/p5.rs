//! Current-season NCAAB P5-vs-P5 membership. Missing evidence blocks NCAAB.
//! This module never guesses conferences or copies a prior season.

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

pub const SEASON: &str = "2026-27";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TeamRow {
    pub canonical_id: String,
    pub display_name: String,
    pub conference: String,
    pub espn_team_id: String,
    pub evidence_url: String,
    pub verified: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Manifest {
    pub season: String,
    pub status: String,
    pub note: String,
    pub conferences: Vec<String>,
    pub teams: Vec<TeamRow>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum P5Error {
    SeasonMismatch,
    EvidenceIncomplete,
    TeamUnverified(String),
    DuplicateId(String),
}

impl Manifest {
    pub fn parse(json: &str) -> Result<Self, String> {
        serde_json::from_str(json).map_err(|e| e.to_string())
    }

    pub fn validate(&self) -> Result<(), P5Error> {
        if self.season != SEASON {
            return Err(P5Error::SeasonMismatch);
        }
        if self.status != "VERIFIED" {
            return Err(P5Error::EvidenceIncomplete);
        }
        let mut seen = BTreeSet::new();
        if self.teams.is_empty() {
            return Err(P5Error::EvidenceIncomplete);
        }
        for t in &self.teams {
            if !t.verified
                || t.canonical_id.is_empty()
                || t.espn_team_id.is_empty()
                || t.evidence_url.is_empty()
            {
                return Err(P5Error::TeamUnverified(t.canonical_id.clone()));
            }
            if !seen.insert(&t.canonical_id) || !seen.insert(&t.espn_team_id) {
                return Err(P5Error::DuplicateId(t.canonical_id.clone()));
            }
        }
        Ok(())
    }

    pub fn both_p5(&self, a: &str, b: &str) -> Result<(), P5Error> {
        self.validate()?;
        let ok = |id: &str| {
            self.teams
                .iter()
                .any(|t| t.verified && (t.canonical_id == id || t.espn_team_id == id))
        };
        if !ok(a) {
            return Err(P5Error::TeamUnverified(a.into()));
        }
        if !ok(b) {
            return Err(P5Error::TeamUnverified(b.into()));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn incomplete_manifest_blocks() {
        let m = Manifest {
            season: SEASON.into(),
            status: "EVIDENCE_INCOMPLETE".into(),
            note: "test".into(),
            conferences: vec![],
            teams: vec![],
        };
        assert_eq!(m.validate(), Err(P5Error::EvidenceIncomplete));
        assert!(m.both_p5("1", "2").is_err());
    }

    #[test]
    fn prior_season_is_rejected() {
        let m = Manifest {
            season: "2025-26".into(),
            status: "VERIFIED".into(),
            note: "legacy".into(),
            conferences: vec![],
            teams: vec![TeamRow {
                canonical_id: "a".into(),
                display_name: "A".into(),
                conference: "ACC".into(),
                espn_team_id: "1".into(),
                evidence_url: "https://example.test".into(),
                verified: true,
            }],
        };
        assert_eq!(m.validate(), Err(P5Error::SeasonMismatch));
    }
}
