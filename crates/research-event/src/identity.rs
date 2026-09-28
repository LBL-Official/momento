//! Canonical MLB identity. Does not invent Kalshi ↔ MLB pk mappings.

use std::collections::BTreeMap;

use chrono::{Datelike, NaiveDate};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use momento_kalshi::game_id_for_event_ticker;
use momento_research_data::foundation::IdentityStubV1;

use crate::error::EventError;
use crate::versions::IDENTITY_VERSION;
use crate::w1_bridge::{
    RawMarketIdentity, identity_to_w1_stub, kalshi_unmapped_canonical_id, unmapped_kalshi_identity,
};

#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize, PartialOrd, Ord)]
pub struct CanonicalGameId(pub String);

#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct SourceRef {
    pub source: String,
    pub source_id: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MlbMatchStatus {
    Unmapped,
    Mapped,
    Unmatched,
    Collision,
    Ambiguous,
    MissingId,
}

/// Official MLB identity only when observed from an authorized PBP/game source.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct OfficialMlbGameRef {
    pub source: String,
    pub game_pk: String,
    pub season: DataYear,
    pub official_date: NaiveDate,
    pub home_team: SourceRef,
    pub away_team: SourceRef,
    pub venue: Option<SourceRef>,
    pub game_number: u8,
    pub competition: String,
    /// Observed StatsAPI team abbreviation (e.g. NYY). Empty if source omitted it.
    pub home_abbreviation: String,
    pub away_abbreviation: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct DataYear(pub i32);

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PlayerRef {
    pub source: String,
    pub source_player_id: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventRef {
    pub game_id: CanonicalGameId,
    pub source_event_id: String,
    pub sequence: u32,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MappingRecord {
    pub from: SourceRef,
    pub to: SourceRef,
    pub status: MlbMatchStatus,
    pub provenance_note: String,
    pub identity_version: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct GameIdentity {
    pub canonical_game_id: CanonicalGameId,
    pub official: Option<OfficialMlbGameRef>,
    pub kalshi: Option<RawMarketIdentity>,
    pub match_status: MlbMatchStatus,
    pub mappings: Vec<MappingRecord>,
    pub identity_version: String,
}

impl CanonicalGameId {
    /// Deterministic id from an observed official source game id. Fails if missing.
    pub fn from_official_source(source: &str, source_game_id: &str) -> Result<Self, EventError> {
        if source.trim().is_empty() || source_game_id.trim().is_empty() {
            return Err(EventError::MissingSourceId(
                "canonical GameId requires source and source_game_id".into(),
            ));
        }
        Ok(Self(stable_hex(
            "research.mlb.game.v1",
            &[source, source_game_id],
        )))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

pub fn stable_hex(kind: &str, parts: &[&str]) -> String {
    let mut h = Sha256::new();
    h.update(kind.as_bytes());
    for p in parts {
        h.update([0u8]);
        h.update(p.as_bytes());
    }
    let out = h.finalize();
    let mut bytes = [0u8; 16];
    bytes.copy_from_slice(&out[..16]);
    hex16(bytes)
}

fn hex16(bytes: [u8; 16]) -> String {
    let mut s = String::with_capacity(32);
    for b in bytes {
        s.push_str(&format!("{b:02x}"));
    }
    s
}

pub fn event_id(game: &CanonicalGameId, sequence: u32, source_event_id: &str) -> String {
    stable_hex(
        "research.mlb.event.v1",
        &[game.as_str(), &sequence.to_string(), source_event_id],
    )
}

pub fn kalshi_alias_from_event_ticker(event_ticker: &str, ticker: &str) -> RawMarketIdentity {
    let gid = game_id_for_event_ticker(event_ticker);
    let mid = momento_kalshi::market_id_for_ticker(ticker);
    unmapped_kalshi_identity(
        gid.raw().to_string(),
        mid.raw().to_string(),
        ticker,
        event_ticker,
        "KXMLBGAME",
    )
}

/// Parse Kalshi event ticker date tokens. Does **not** split concatenated team abbreviations.
pub fn kalshi_event_date_token(event_ticker: &str) -> Option<String> {
    let rest = event_ticker.strip_prefix("KXMLBGAME-")?;
    let y = rest.get(0..2)?;
    let mon = rest.get(2..5)?;
    let d = rest.get(5..7)?;
    let month = match mon {
        "JAN" => 1,
        "FEB" => 2,
        "MAR" => 3,
        "APR" => 4,
        "MAY" => 5,
        "JUN" => 6,
        "JUL" => 7,
        "AUG" => 8,
        "SEP" => 9,
        "OCT" => 10,
        "NOV" => 11,
        "DEC" => 12,
        _ => return None,
    };
    Some(format!("20{y}-{month:02}-{d}"))
}

/// Team-code suffix of a Kalshi MLB event ticker after date and optional HHMM.
/// Does not invent abbreviations; it only slices the observed ticker string.
pub fn kalshi_event_team_suffix(event_ticker: &str) -> Option<String> {
    let rest = event_ticker.strip_prefix("KXMLBGAME-")?;
    if rest.len() < 7 {
        return None;
    }
    let after_date = &rest[7..];
    let teams = if after_date.len() >= 4 && after_date.chars().take(4).all(|c| c.is_ascii_digit()) {
        &after_date[4..]
    } else {
        after_date
    };
    if teams.is_empty() {
        None
    } else {
        Some(teams.to_ascii_uppercase())
    }
}

/// Observed team concat plus optional trailing doubleheader digit from a ticker.
///
/// Kalshi encodes game 2 as a final `2` (`ATHMIL2`) or `G2` (`TBBOSG2`).
/// Game 1 is either undigited or `G1`. The marker is sliced from the observed
/// ticker; it is not an invented `gamePk`. Non-digit suffixes default to game 1.
pub fn kalshi_event_team_and_game(event_ticker: &str) -> Option<(String, u8)> {
    let suffix = kalshi_event_team_suffix(event_ticker)?;
    let bytes = suffix.as_bytes();
    if bytes.len() >= 6 {
        let digit = bytes[bytes.len() - 1];
        let marker = bytes[bytes.len() - 2];
        let rest = &bytes[..bytes.len() - 2];
        if marker == b'G'
            && (b'1'..=b'9').contains(&digit)
            && rest.len() >= 4
            && rest.iter().all(|b| b.is_ascii_alphabetic())
        {
            let teams = String::from_utf8(rest.to_vec()).ok()?;
            return Some((teams, digit - b'0'));
        }
    }
    if let Some((&last, rest)) = bytes.split_last() {
        if (b'1'..=b'9').contains(&last)
            && rest.len() >= 4
            && rest.iter().all(|b| b.is_ascii_alphabetic())
        {
            let teams = String::from_utf8(rest.to_vec()).ok()?;
            return Some((teams, last - b'0'));
        }
    }
    if suffix.chars().all(|c| c.is_ascii_alphabetic()) {
        Some((suffix, 1))
    } else {
        None
    }
}

/// Observed StatsAPI ↔ Kalshi team abbreviation aliases. Both strings are
/// observed from source catalogs; this does not invent a `gamePk`.
const OBSERVED_ABBR_ALIASES: &[(&str, &str)] = &[
    ("AZ", "ARI"), // StatsAPI AZ; Kalshi ARI
];

fn observed_abbr_variants(abbr: &str) -> Vec<String> {
    let u = abbr.to_ascii_uppercase();
    let mut out = vec![u.clone()];
    for (a, b) in OBSERVED_ABBR_ALIASES {
        if u == *a {
            out.push((*b).to_string());
        } else if u == *b {
            out.push((*a).to_string());
        }
    }
    out.sort();
    out.dedup();
    out
}

fn official_team_concats(away: &str, home: &str) -> Vec<String> {
    let mut out = Vec::new();
    for a in observed_abbr_variants(away) {
        for h in observed_abbr_variants(home) {
            out.push(format!("{a}{h}"));
            out.push(format!("{h}{a}"));
        }
    }
    out.sort();
    out.dedup();
    out
}

/// Match an official StatsAPI game to Kalshi event tickers on the same date.
///
/// The official `gamePk` is OBSERVED from StatsAPI. Tickers are OBSERVED from the
/// lake. A unique concatenation of observed abbreviations is a DERIVED crosswalk,
/// not an invented pk. Non-unique → AMBIGUOUS. None → UNMATCHED.
///
/// Official `game_number` must equal the observed ticker trailing digit (default 1).
/// Two same-club games that only differ by HHMM and both parse as game 1 stay
/// AMBIGUOUS — time-of-day is not used to invent a mapping.
pub fn match_official_to_kalshi_tickers(
    official: &OfficialMlbGameRef,
    tickers_same_date: &[String],
) -> (MlbMatchStatus, Vec<String>) {
    let away = official.away_abbreviation.to_ascii_uppercase();
    let home = official.home_abbreviation.to_ascii_uppercase();
    if away.is_empty() || home.is_empty() {
        return (MlbMatchStatus::Unmapped, vec![]);
    }
    let concats = official_team_concats(&away, &home);
    let want_game = if official.game_number == 0 {
        1
    } else {
        official.game_number
    };
    let mut hits = Vec::new();
    for t in tickers_same_date {
        let Some((teams, game_no)) = kalshi_event_team_and_game(t) else {
            continue;
        };
        if game_no != want_game {
            continue;
        }
        if concats.iter().any(|c| c == &teams) {
            hits.push(t.clone());
        }
    }
    hits.sort();
    hits.dedup();
    match hits.len() {
        0 => (MlbMatchStatus::Unmatched, hits),
        1 => (MlbMatchStatus::Mapped, hits),
        _ => (MlbMatchStatus::Ambiguous, hits),
    }
}

#[derive(Clone, Debug, Default)]
pub struct IdentityRegistry {
    by_source: BTreeMap<(String, String), CanonicalGameId>,
    by_canonical: BTreeMap<CanonicalGameId, GameIdentity>,
}

impl IdentityRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register_official(
        &mut self,
        official: OfficialMlbGameRef,
    ) -> Result<CanonicalGameId, EventError> {
        if official.home_team.source_id == official.away_team.source_id {
            return Err(EventError::invariant(
                "TEAM_VALIDATION",
                "home and away source ids must differ",
            ));
        }
        let year = official.official_date.year();
        if year != official.season.0 {
            return Err(EventError::invariant(
                "SEASON_VALIDATION",
                format!(
                    "season {} does not match official_date year {year}",
                    official.season.0
                ),
            ));
        }
        let id = CanonicalGameId::from_official_source(&official.source, &official.game_pk)?;
        let key = (official.source.clone(), official.game_pk.clone());
        if let Some(existing) = self.by_source.get(&key) {
            if existing != &id {
                return Err(EventError::IdentityCollision(format!(
                    "source {}/{} already bound to {}",
                    key.0,
                    key.1,
                    existing.as_str()
                )));
            }
            return Ok(id);
        }
        if let Some(prev) = self.by_canonical.get(&id) {
            if prev.official.as_ref().map(|o| o.game_pk.as_str()) != Some(official.game_pk.as_str())
            {
                return Err(EventError::IdentityCollision(format!(
                    "canonical {} collided",
                    id.as_str()
                )));
            }
        }
        let ident = GameIdentity {
            canonical_game_id: id.clone(),
            official: Some(official),
            kalshi: None,
            match_status: MlbMatchStatus::Unmapped,
            mappings: vec![],
            identity_version: IDENTITY_VERSION.to_string(),
        };
        self.by_source.insert(key, id.clone());
        self.by_canonical.insert(id.clone(), ident);
        Ok(id)
    }

    /// Attach a Kalshi alias only when an explicit mapping record is supplied.
    /// Ticker parse is not a mapping.
    pub fn attach_kalshi_mapping(
        &mut self,
        game_id: &CanonicalGameId,
        kalshi: RawMarketIdentity,
        mapping: MappingRecord,
    ) -> Result<(), EventError> {
        let ident = self
            .by_canonical
            .get_mut(game_id)
            .ok_or_else(|| EventError::MissingSourceId(game_id.as_str().into()))?;
        if mapping.status == MlbMatchStatus::Mapped && kalshi.mlb_game_pk.is_none() {
            return Err(EventError::invariant(
                "MAPPING",
                "refusing MAPPED Kalshi alias without observed mlb_game_pk on the mapping payload",
            ));
        }
        ident.kalshi = Some(kalshi);
        ident.match_status = mapping.status;
        ident.mappings.push(mapping);
        Ok(())
    }

    pub fn get(&self, id: &CanonicalGameId) -> Option<&GameIdentity> {
        self.by_canonical.get(id)
    }

    pub fn kalshi_only_unmapped(event_ticker: &str, ticker: &str) -> GameIdentity {
        let kalshi = kalshi_alias_from_event_ticker(event_ticker, ticker);
        GameIdentity {
            canonical_game_id: CanonicalGameId(kalshi_unmapped_canonical_id(&kalshi.game_id)),
            official: None,
            kalshi: Some(kalshi),
            match_status: MlbMatchStatus::Unmapped,
            mappings: vec![],
            identity_version: IDENTITY_VERSION.to_string(),
        }
    }

    pub fn to_w1_stub(ident: &GameIdentity) -> Option<IdentityStubV1> {
        ident.kalshi.as_ref().map(identity_to_w1_stub)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::NaiveDate;

    fn official() -> OfficialMlbGameRef {
        OfficialMlbGameRef {
            source: "mlb_statsapi".into(),
            game_pk: "424242".into(),
            season: DataYear(2026),
            official_date: NaiveDate::from_ymd_opt(2026, 6, 18).expect("date"),
            home_team: SourceRef {
                source: "mlb_statsapi".into(),
                source_id: "147".into(),
            },
            away_team: SourceRef {
                source: "mlb_statsapi".into(),
                source_id: "111".into(),
            },
            venue: None,
            game_number: 1,
            competition: "MLB".into(),
            home_abbreviation: "NYY".into(),
            away_abbreviation: "BOS".into(),
        }
    }

    #[test]
    fn missing_source_id_refuses_mint() {
        let err = CanonicalGameId::from_official_source("mlb", "").unwrap_err();
        assert!(matches!(err, EventError::MissingSourceId(_)));
    }

    #[test]
    fn ids_are_deterministic() {
        let a = CanonicalGameId::from_official_source("mlb_statsapi", "424242").unwrap();
        let b = CanonicalGameId::from_official_source("mlb_statsapi", "424242").unwrap();
        assert_eq!(a, b);
    }

    #[test]
    fn does_not_invent_kalshi_map() {
        let mut reg = IdentityRegistry::new();
        let id = reg.register_official(official()).unwrap();
        let ident = reg.get(&id).unwrap();
        assert_eq!(ident.match_status, MlbMatchStatus::Unmapped);
        assert!(ident.kalshi.is_none());
    }

    #[test]
    fn season_mismatch_fails() {
        let mut o = official();
        o.season = DataYear(2025);
        let mut reg = IdentityRegistry::new();
        let err = reg.register_official(o).unwrap_err();
        assert!(matches!(err, EventError::Invariant { code, .. } if code == "SEASON_VALIDATION"));
    }

    #[test]
    fn kalshi_unmapped_keeps_prefix_and_never_invents_pk() {
        let ident = IdentityRegistry::kalshi_only_unmapped(
            "KXMLBGAME-26JUN18NYYBOS",
            "KXMLBGAME-26JUN18NYYBOS-NYY",
        );
        assert!(
            ident
                .canonical_game_id
                .as_str()
                .starts_with(crate::w1_bridge::KALSHI_UNMAPPED_PREFIX)
        );
        let k = ident.kalshi.as_ref().expect("kalshi alias");
        assert!(k.mlb_game_pk.is_none());
        assert_eq!(
            k.starting_price_class,
            crate::w1_bridge::StartingPriceClass::StartingPriceUnverified
        );
        assert_ne!(
            k.starting_price_class,
            crate::w1_bridge::StartingPriceClass::MarketOpenPrice
        );
    }

    #[test]
    fn kalshi_suffix_match_is_unique_and_does_not_invent_pk() {
        let mut o = official();
        o.home_abbreviation = "PHI".into();
        o.away_abbreviation = "NYM".into();
        o.official_date = NaiveDate::from_ymd_opt(2026, 6, 18).expect("date");
        let tickers = vec![
            "KXMLBGAME-26JUN181840NYMPHI".into(),
            "KXMLBGAME-26JUN181905CWSNYY".into(),
        ];
        let (st, hits) = match_official_to_kalshi_tickers(&o, &tickers);
        assert_eq!(st, MlbMatchStatus::Mapped);
        assert_eq!(hits, vec!["KXMLBGAME-26JUN181840NYMPHI".to_string()]);
        assert_eq!(o.game_pk, "424242");
    }

    #[test]
    fn kalshi_suffix_no_hit_is_unmatched() {
        let o = official();
        let tickers = vec!["KXMLBGAME-26JUN181840NYMPHI".into()];
        let (st, hits) = match_official_to_kalshi_tickers(&o, &tickers);
        assert_eq!(st, MlbMatchStatus::Unmatched);
        assert!(hits.is_empty());
    }

    #[test]
    fn trailing_game_digit_is_sliced_not_invented() {
        assert_eq!(
            kalshi_event_team_and_game("KXMLBGAME-25APR18ATHMIL"),
            Some(("ATHMIL".into(), 1))
        );
        assert_eq!(
            kalshi_event_team_and_game("KXMLBGAME-25APR18ATHMIL2"),
            Some(("ATHMIL".into(), 2))
        );
        assert_eq!(
            kalshi_event_team_and_game("KXMLBGAME-25APR181205ATHMIL2"),
            Some(("ATHMIL".into(), 2))
        );
        assert_eq!(
            kalshi_event_team_and_game("KXMLBGAME-26JUL171335TBBOSG1"),
            Some(("TBBOS".into(), 1))
        );
        assert_eq!(
            kalshi_event_team_and_game("KXMLBGAME-26JUL171910TBBOSG2"),
            Some(("TBBOS".into(), 2))
        );
    }

    #[test]
    fn numbered_doubleheader_maps_uniquely_without_inventing_pk() {
        let mut g1 = official();
        g1.home_abbreviation = "MIL".into();
        g1.away_abbreviation = "ATH".into();
        g1.game_number = 1;
        g1.game_pk = "746001".into();
        let mut g2 = g1.clone();
        g2.game_number = 2;
        g2.game_pk = "746002".into();
        let tickers = vec![
            "KXMLBGAME-25APR18ATHMIL".into(),
            "KXMLBGAME-25APR18ATHMIL2".into(),
        ];
        let (s1, h1) = match_official_to_kalshi_tickers(&g1, &tickers);
        let (s2, h2) = match_official_to_kalshi_tickers(&g2, &tickers);
        assert_eq!(s1, MlbMatchStatus::Mapped);
        assert_eq!(h1, vec!["KXMLBGAME-25APR18ATHMIL".to_string()]);
        assert_eq!(s2, MlbMatchStatus::Mapped);
        assert_eq!(h2, vec!["KXMLBGAME-25APR18ATHMIL2".to_string()]);
        assert_eq!(g1.game_pk, "746001");
        assert_eq!(g2.game_pk, "746002");
    }

    #[test]
    fn g1_g2_doubleheader_maps_uniquely_without_inventing_pk() {
        let mut g1 = official();
        g1.home_abbreviation = "BOS".into();
        g1.away_abbreviation = "TB".into();
        g1.game_number = 1;
        g1.game_pk = "824766".into();
        let mut g2 = g1.clone();
        g2.game_number = 2;
        g2.game_pk = "824737".into();
        let tickers = vec![
            "KXMLBGAME-26JUL171335TBBOSG1".into(),
            "KXMLBGAME-26JUL171910TBBOSG2".into(),
        ];
        let (s1, h1) = match_official_to_kalshi_tickers(&g1, &tickers);
        let (s2, h2) = match_official_to_kalshi_tickers(&g2, &tickers);
        assert_eq!(s1, MlbMatchStatus::Mapped);
        assert_eq!(h1, vec!["KXMLBGAME-26JUL171335TBBOSG1".to_string()]);
        assert_eq!(s2, MlbMatchStatus::Mapped);
        assert_eq!(h2, vec!["KXMLBGAME-26JUL171910TBBOSG2".to_string()]);
        assert_eq!(g1.game_pk, "824766");
        assert_eq!(g2.game_pk, "824737");
    }

    #[test]
    fn game_one_does_not_map_to_trailing_two_ticker() {
        let mut o = official();
        o.home_abbreviation = "MIL".into();
        o.away_abbreviation = "ATH".into();
        o.game_number = 1;
        let tickers = vec!["KXMLBGAME-25APR18ATHMIL2".into()];
        let (st, hits) = match_official_to_kalshi_tickers(&o, &tickers);
        assert_eq!(st, MlbMatchStatus::Unmatched);
        assert!(hits.is_empty());
    }

    #[test]
    fn az_ari_observed_alias_maps_without_inventing_pk() {
        let mut o = official();
        o.home_abbreviation = "AZ".into();
        o.away_abbreviation = "SF".into();
        o.official_date = NaiveDate::from_ymd_opt(2025, 7, 1).expect("date");
        o.game_pk = "776001".into();
        let tickers = vec![
            "KXMLBGAME-25JUL01SFARI".into(),
            "KXMLBGAME-25JUL01NYYBOS".into(),
        ];
        let (st, hits) = match_official_to_kalshi_tickers(&o, &tickers);
        assert_eq!(st, MlbMatchStatus::Mapped);
        assert_eq!(hits, vec!["KXMLBGAME-25JUL01SFARI".to_string()]);
        assert_eq!(o.game_pk, "776001");
    }
}
