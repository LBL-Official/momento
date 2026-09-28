//! Observed home/away abbreviations. Never invent a mapping.

use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use serde_json::Value;

const ALIASES: &[(&str, &str)] = &[
    ("OAK", "ATH"),
    ("ARI", "AZ"),
    ("CHW", "CWS"),
    ("WAS", "WSH"),
    ("TBR", "TB"),
    ("KCR", "KC"),
    ("SFG", "SF"),
    ("SDP", "SD"),
];

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TeamIdentity {
    pub home: String,
    pub away: String,
    pub source: String,
}

pub fn normalize_abbr(raw: &str) -> String {
    let a = raw.trim().to_ascii_uppercase();
    for (from, to) in ALIASES {
        if a == *from {
            return (*to).to_string();
        }
    }
    a
}

/// Bound-team lead from home run differential. None if side is not on the game.
pub fn bound_team_lead(side: &str, home: &str, away: &str, home_rd: i32) -> Option<i32> {
    let s = normalize_abbr(side);
    let h = normalize_abbr(home);
    let a = normalize_abbr(away);
    if s == h {
        Some(home_rd)
    } else if s == a {
        Some(-home_rd)
    } else {
        None
    }
}

pub fn load_envelope_identity(landing_root: &Path) -> BTreeMap<String, TeamIdentity> {
    let mut out = BTreeMap::new();
    if !landing_root.exists() {
        return out;
    }
    let Ok(walker) = walk_envelopes(landing_root) else {
        return out;
    };
    for path in walker {
        let Some(pk) = game_pk_from_path(&path) else {
            continue;
        };
        let Ok(text) = fs::read_to_string(&path) else {
            continue;
        };
        let Ok(env) = serde_json::from_str::<Value>(&text) else {
            continue;
        };
        let teams = env
            .get("payload")
            .and_then(|p| p.get("gameData"))
            .and_then(|g| g.get("teams"));
        let Some(teams) = teams else {
            continue;
        };
        let home = teams
            .get("home")
            .and_then(|t| t.get("abbreviation"))
            .and_then(|v| v.as_str());
        let away = teams
            .get("away")
            .and_then(|t| t.get("abbreviation"))
            .and_then(|v| v.as_str());
        if let (Some(home), Some(away)) = (home, away) {
            out.insert(
                pk,
                TeamIdentity {
                    home: normalize_abbr(home),
                    away: normalize_abbr(away),
                    source: "OBSERVED_STATSAPI_ENVELOPE".to_string(),
                },
            );
        }
    }
    out
}

fn game_pk_from_path(path: &Path) -> Option<String> {
    let name = path.file_name()?.to_str()?;
    let rest = name.strip_prefix("gamePk=")?;
    Some(rest.split('.').next()?.to_string())
}

fn walk_envelopes(root: &Path) -> std::io::Result<Vec<std::path::PathBuf>> {
    let mut out = Vec::new();
    fn rec(dir: &Path, out: &mut Vec<std::path::PathBuf>) -> std::io::Result<()> {
        for entry in fs::read_dir(dir)? {
            let entry = entry?;
            let p = entry.path();
            if p.is_dir() {
                rec(&p, out)?;
            } else if p
                .file_name()
                .and_then(|s| s.to_str())
                .is_some_and(|n| n.starts_with("gamePk=") && n.ends_with(".envelope.json"))
            {
                out.push(p);
            }
        }
        Ok(())
    }
    rec(root, &mut out)?;
    Ok(out)
}
