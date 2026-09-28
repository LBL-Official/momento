//! Game identity from Kalshi event/market metadata. Ticker parsing is fallback only.

use chrono::{Datelike, NaiveDate};
use serde_json::Value;

use crate::sport::ResearchSport;

use super::types::{SeasonPhase, json_str};

const MONTHS: [(&str, u32); 12] = [
    ("JAN", 1),
    ("FEB", 2),
    ("MAR", 3),
    ("APR", 4),
    ("MAY", 5),
    ("JUN", 6),
    ("JUL", 7),
    ("AUG", 8),
    ("SEP", 9),
    ("OCT", 10),
    ("NOV", 11),
    ("DEC", 12),
];

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PhaseClass {
    pub phase: SeasonPhase,
    pub method: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct VenueSides {
    pub away_code: Option<String>,
    pub home_code: Option<String>,
    pub relation: String,
}

/// Tennis has no home/away. A match has two ordered player sides derived from
/// the two market ticker suffixes, never from splitting the event ticker blob.
///
/// The warehouse parquet schema is shared with NBA/NCAAB/MLB/NHL/WNBA and only
/// has `home_team_code`/`away_team_code` slots. For tennis those two slots carry
/// side A and side B respectively; they do **not** mean home and away. ROLLER's
/// canonical layer renames them.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TennisSides {
    pub side_a_code: String,
    pub side_b_code: String,
    /// How the A/B order was decided: `event_ticker_blob_order` or
    /// `market_suffix_lexicographic`.
    pub order_method: String,
}

/// NBA season containing `game_date` (season starts in October).
pub fn season_for_date(date: NaiveDate) -> String {
    if date.month() >= 10 {
        format!("{}-{}", date.year(), date.year() + 1)
    } else {
        format!("{}-{}", date.year() - 1, date.year())
    }
}

/// Exhibition-inclusive NCAAB season (October–April).
///
/// October exhibition belongs to the upcoming season. A November-only cut
/// would mis-label October exhibition as the prior year.
pub fn season_for_date_ncaab(date: NaiveDate) -> String {
    season_for_date(date)
}

/// WNBA campaign year is the calendar year of the May tip-off.
/// Research folder `Y-(Y+1)` holds campaigns Y and Y+1 when Y is odd,
/// so `2025-2026` contains both the 2025 and 2026 WNBA seasons.
pub fn season_for_date_wnba(date: NaiveDate) -> String {
    let campaign = if date.month() >= 5 {
        date.year()
    } else {
        date.year() - 1
    };
    let start = if campaign % 2 == 1 {
        campaign
    } else {
        campaign - 1
    };
    format!("{}-{}", start, start + 1)
}

/// NHL season including September preseason. NBA Oct-cut would put Sep in the prior year.
pub fn season_for_date_nhl(date: NaiveDate) -> String {
    if date.month() >= 9 {
        format!("{}-{}", date.year(), date.year() + 1)
    } else {
        format!("{}-{}", date.year() - 1, date.year())
    }
}

/// MLB campaign year is the calendar year of Opening Day (March/April).
/// Research folder `Y-(Y+1)` holds campaigns Y and Y+1 when Y is odd,
/// so `2025-2026` contains both the 2025 and 2026 MLB seasons.
///
/// NBA October–June labeling would put April–September 2025 in `2024-2025`
/// and drop those games from the 2025–2026 warehouse.
pub fn season_for_date_mlb(date: NaiveDate) -> String {
    let campaign = if date.month() >= 2 {
        date.year()
    } else {
        date.year() - 1
    };
    let start = if campaign % 2 == 1 {
        campaign
    } else {
        campaign - 1
    };
    format!("{}-{}", start, start + 1)
}

/// ATP/WTA tours run on a calendar year (January–November), so there is no
/// cross-year campaign to cut. Follows the WNBA/MLB precedent of folding a
/// calendar campaign into a `Y-(Y+1)` folder that starts on the odd year, so
/// both the 2025 and 2026 tennis seasons land in `2025-2026`.
pub fn season_for_date_tennis(date: NaiveDate) -> String {
    let campaign = date.year();
    let start = if campaign % 2 == 1 {
        campaign
    } else {
        campaign - 1
    };
    format!("{}-{}", start, start + 1)
}

pub fn season_for_date_for_sport(sport: ResearchSport, date: NaiveDate) -> String {
    match sport {
        ResearchSport::Ncaab => season_for_date_ncaab(date),
        ResearchSport::Wnba => season_for_date_wnba(date),
        ResearchSport::Nhl => season_for_date_nhl(date),
        ResearchSport::Mlb => season_for_date_mlb(date),
        ResearchSport::Nba => season_for_date(date),
        ResearchSport::TennisAtp | ResearchSport::TennisWta => season_for_date_tennis(date),
    }
}

pub fn parse_event_date_token(event_ticker: &str) -> Option<NaiveDate> {
    let rest = event_ticker
        .strip_prefix("KXNBAGAME-")
        .or_else(|| event_ticker.strip_prefix("KXNCAAMBGAME-"))
        .or_else(|| event_ticker.strip_prefix("KXWNBAGAME-"))
        .or_else(|| event_ticker.strip_prefix("KXNHLGAME-"))
        .or_else(|| event_ticker.strip_prefix("KXMLBGAME-"))
        .or_else(|| event_ticker.strip_prefix("KXATPMATCH-"))
        .or_else(|| event_ticker.strip_prefix("KXWTAMATCH-"))?;
    parse_yy_mon_dd(rest)
}

fn parse_yy_mon_dd(rest: &str) -> Option<NaiveDate> {
    if rest.len() < 7 {
        return None;
    }
    let yy: i32 = rest.get(0..2)?.parse().ok()?;
    let mon = rest.get(2..5)?;
    let dd: u32 = rest.get(5..7)?.parse().ok()?;
    let month = MONTHS.iter().find(|(n, _)| *n == mon).map(|(_, m)| *m)?;
    NaiveDate::from_ymd_opt(2000 + yy, month, dd)
}

/// Classify phase from event title/subtitle first; calendar only when metadata is silent.
pub fn classify_phase(
    title: Option<&str>,
    subtitle: Option<&str>,
    date: Option<NaiveDate>,
) -> PhaseClass {
    let blob = format!(
        "{} {}",
        title.unwrap_or_default(),
        subtitle.unwrap_or_default()
    );
    let lower = blob.to_ascii_lowercase();
    if lower.contains("play-in") || lower.contains("play in") {
        return PhaseClass {
            phase: SeasonPhase::PlayIn,
            method: "event_title".into(),
        };
    }
    if lower.contains("finals") {
        return PhaseClass {
            phase: SeasonPhase::Finals,
            method: "event_title".into(),
        };
    }
    if looks_like_playoff_game_title(title.unwrap_or_default()) {
        if date.is_some_and(|d| d.month() == 6) {
            return PhaseClass {
                phase: SeasonPhase::Finals,
                method: "event_title_game_n_plus_june".into(),
            };
        }
        return PhaseClass {
            phase: SeasonPhase::Playoffs,
            method: "event_title_game_n".into(),
        };
    }
    if date.is_some_and(|d| d.month() == 10 && d.day() <= 17) {
        return PhaseClass {
            phase: SeasonPhase::Preseason,
            method: "calendar_preseason_window".into(),
        };
    }
    PhaseClass {
        phase: SeasonPhase::RegularSeason,
        method: "default_unlabeled".into(),
    }
}

/// NCAAB phases from event title/subtitle. Never invent March Madness from month.
pub fn classify_ncaab_phase(
    title: Option<&str>,
    subtitle: Option<&str>,
    _date: Option<NaiveDate>,
) -> PhaseClass {
    let blob = format!(
        "{} {}",
        title.unwrap_or_default(),
        subtitle.unwrap_or_default()
    );
    let lower = blob.to_ascii_lowercase();
    if ncaa_tournament_title(&lower) {
        return PhaseClass {
            phase: SeasonPhase::NcaaTournament,
            method: "event_title".into(),
        };
    }
    if other_postseason_title(&lower) {
        return PhaseClass {
            phase: SeasonPhase::OtherPostseason,
            method: "event_title".into(),
        };
    }
    if conference_tournament_title(&lower) {
        return PhaseClass {
            phase: SeasonPhase::ConferenceTournament,
            method: "event_title".into(),
        };
    }
    if exhibition_or_preseason_title(&lower) {
        let phase = if lower.contains("exhibition") || lower.contains("friendly") {
            SeasonPhase::Exhibition
        } else {
            SeasonPhase::Preseason
        };
        return PhaseClass {
            phase,
            method: "event_title".into(),
        };
    }
    PhaseClass {
        phase: SeasonPhase::RegularSeason,
        method: "default_unlabeled".into(),
    }
}

/// WNBA phases from title. Do not reuse the NBA October preseason calendar window.
pub fn classify_wnba_phase(
    title: Option<&str>,
    subtitle: Option<&str>,
    date: Option<NaiveDate>,
) -> PhaseClass {
    let blob = format!(
        "{} {}",
        title.unwrap_or_default(),
        subtitle.unwrap_or_default()
    );
    let lower = blob.to_ascii_lowercase();
    if lower.contains("exhibition") {
        return PhaseClass {
            phase: SeasonPhase::Exhibition,
            method: "event_title".into(),
        };
    }
    if lower.contains("preseason") || lower.contains("pre-season") {
        return PhaseClass {
            phase: SeasonPhase::Preseason,
            method: "event_title".into(),
        };
    }
    if lower.contains("all-star") || lower.contains("all star") {
        return PhaseClass {
            phase: SeasonPhase::OtherPostseason,
            method: "event_title".into(),
        };
    }
    if lower.contains("finals") {
        return PhaseClass {
            phase: SeasonPhase::Finals,
            method: "event_title".into(),
        };
    }
    if looks_like_playoff_game_title(title.unwrap_or_default()) {
        if date.is_some_and(|d| d.month() == 10) {
            return PhaseClass {
                phase: SeasonPhase::Finals,
                method: "event_title_game_n_plus_october".into(),
            };
        }
        return PhaseClass {
            phase: SeasonPhase::Playoffs,
            method: "event_title_game_n".into(),
        };
    }
    if lower.contains("playoff") {
        return PhaseClass {
            phase: SeasonPhase::Playoffs,
            method: "event_title".into(),
        };
    }
    PhaseClass {
        phase: SeasonPhase::RegularSeason,
        method: "default_unlabeled".into(),
    }
}

pub fn classify_phase_for_sport(
    sport: ResearchSport,
    title: Option<&str>,
    subtitle: Option<&str>,
    date: Option<NaiveDate>,
) -> PhaseClass {
    match sport {
        ResearchSport::Ncaab => classify_ncaab_phase(title, subtitle, date),
        ResearchSport::Wnba => classify_wnba_phase(title, subtitle, date),
        ResearchSport::Nhl => classify_nhl_phase(title, subtitle, date),
        ResearchSport::Mlb => classify_mlb_phase(title, subtitle, date),
        ResearchSport::Nba => classify_phase(title, subtitle, date),
        // Tennis phase comes from `product_metadata.competition`, which is not
        // reachable from the title/subtitle. Callers holding the raw event must
        // use `classify_tennis_phase`; anything else stays honestly UNKNOWN.
        ResearchSport::TennisAtp | ResearchSport::TennisWta => PhaseClass {
            phase: SeasonPhase::Unknown,
            method: "tennis_competition_unavailable".into(),
        },
    }
}

/// Tennis phases from `product_metadata.competition`.
///
/// Tennis has no preseason, play-in, or playoffs, and tour tiers (250/500/1000)
/// are not present in the Kalshi payload, so they are not invented here. Only
/// the four majors are detectable from the competition string; everything else
/// with a competition is an ordinary tour event, and a missing competition is
/// UNKNOWN rather than a guess.
pub fn classify_tennis_phase(competition: Option<&str>) -> PhaseClass {
    let Some(raw) = competition.map(str::trim).filter(|s| !s.is_empty()) else {
        return PhaseClass {
            phase: SeasonPhase::Unknown,
            method: "tennis_competition_unclassified".into(),
        };
    };
    let lower = raw.to_ascii_lowercase();
    if is_grand_slam_competition(&lower) {
        return PhaseClass {
            phase: SeasonPhase::GrandSlam,
            method: "tennis_competition_grand_slam".into(),
        };
    }
    PhaseClass {
        phase: SeasonPhase::RegularSeason,
        method: "tennis_competition_tour_event".into(),
    }
}

fn is_grand_slam_competition(lower: &str) -> bool {
    lower.contains("australian open")
        || lower.contains("roland garros")
        || lower.contains("french open")
        || lower.contains("wimbledon")
        || lower.contains("us open")
}

/// `product_metadata.competition` — the tournament identity for a tennis event.
pub fn tennis_competition(event: &Value) -> Option<String> {
    event
        .get("product_metadata")
        .and_then(|m| m.get("competition"))
        .and_then(|c| c.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
}

pub const TENNIS_COMPETITION_FROM_METADATA: &str = "product_metadata";
pub const TENNIS_COMPETITION_FROM_TITLE: &str = "event_title_prefix";
pub const TENNIS_COMPETITION_UNAVAILABLE: &str = "unavailable";

/// Tournament identity plus where it came from.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TennisCompetition {
    pub name: Option<String>,
    pub source: &'static str,
}

/// Tournament identity, preferring `product_metadata.competition`.
///
/// Older tennis events predate `product_metadata` and instead carry the
/// tournament as a title prefix, e.g. `"WTA Eastbourne: Joint or Pavlyuchenkova
/// advances?"`. Across the observed WTA catalog the prefix equals
/// `product_metadata.competition` on every event that has both (225 of 225), so
/// the prefix is a measured fallback rather than a guess. The source is
/// reported so a title-derived competition is never mistaken for exchange
/// metadata.
pub fn tennis_competition_resolved(event: &Value) -> TennisCompetition {
    if let Some(name) = tennis_competition(event) {
        return TennisCompetition {
            name: Some(name),
            source: TENNIS_COMPETITION_FROM_METADATA,
        };
    }
    if let Some(name) = tennis_competition_from_title(json_str(event, "title").as_deref()) {
        return TennisCompetition {
            name: Some(name),
            source: TENNIS_COMPETITION_FROM_TITLE,
        };
    }
    TennisCompetition {
        name: None,
        source: TENNIS_COMPETITION_UNAVAILABLE,
    }
}

fn tennis_competition_from_title(title: Option<&str>) -> Option<String> {
    let (prefix, rest) = title?.split_once(':')?;
    let prefix = prefix.trim();
    if prefix.is_empty() || rest.trim().is_empty() {
        return None;
    }
    // A head-to-head title has no tournament prefix; do not invent one.
    if prefix.to_ascii_lowercase().contains(" vs ") {
        return None;
    }
    Some(prefix.to_string())
}

/// Tennis phase for a raw Kalshi event, resolving the competition first.
pub fn classify_tennis_phase_for_event(event: &Value) -> PhaseClass {
    let resolved = tennis_competition_resolved(event);
    let mut class = classify_tennis_phase(resolved.name.as_deref());
    if resolved.source == TENNIS_COMPETITION_FROM_TITLE {
        class.method = format!("{}_from_event_title", class.method);
    }
    class
}

/// `custom_strike.tennis_competitor` — the stable per-player UUID Kalshi assigns
/// to the YES side of a tennis market. This is the crosswalk key to external
/// player identity; it is never derived or invented.
pub fn market_tennis_competitor(market: &Value) -> Option<String> {
    market
        .get("custom_strike")
        .and_then(|m| m.get("tennis_competitor"))
        .and_then(|c| c.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
}

/// Ordered player sides for a tennis event, derived from the market ticker
/// suffixes rather than from splitting the event ticker blob.
///
/// Splitting the blob in half is wrong: sampled ATP/WTA events include
/// `KXATPMATCH-26SEP03VANDE` (5-char blob), `KXATPMATCH-26AUG24KWONLAJ`
/// (`KWON` + `LAJ`), and `KXWTAMATCH-26AUG01MARMAR2` (numeric disambiguation
/// suffix). The market suffixes are unambiguous.
///
/// Fails closed: an event that does not resolve to exactly two distinct market
/// suffixes returns `None`, and the caller leaves both side slots empty.
pub fn tennis_player_sides(event_ticker: &str, market_tickers: &[String]) -> Option<TennisSides> {
    if market_tickers.len() != 2 {
        return None;
    }
    let first = ticker_yes_code(&market_tickers[0]).filter(|c| !c.is_empty())?;
    let second = ticker_yes_code(&market_tickers[1]).filter(|c| !c.is_empty())?;
    if first == second {
        return None;
    }
    let blob = tennis_event_blob(event_ticker);
    let positions = blob.as_deref().and_then(|b| {
        let a = b.find(&first)?;
        let c = b.find(&second)?;
        if a == c { None } else { Some((a, c)) }
    });
    let (side_a_code, side_b_code, order_method) = match positions {
        Some((a, b)) if a < b => (first, second, "event_ticker_blob_order"),
        Some(_) => (second, first, "event_ticker_blob_order"),
        None => {
            let (lo, hi) = if first <= second {
                (first, second)
            } else {
                (second, first)
            };
            (lo, hi, "market_suffix_lexicographic")
        }
    };
    Some(TennisSides {
        side_a_code,
        side_b_code,
        order_method: order_method.into(),
    })
}

/// The player-code portion of a tennis event ticker: everything after the
/// series prefix and the `YYMONDD` date token.
fn tennis_event_blob(event_ticker: &str) -> Option<String> {
    let rest = event_ticker
        .strip_prefix("KXATPMATCH-")
        .or_else(|| event_ticker.strip_prefix("KXWTAMATCH-"))?;
    let blob = rest.get(7..)?;
    if blob.is_empty() {
        None
    } else {
        Some(blob.to_string())
    }
}

/// MLB phases from title. Do not reuse the NBA October preseason calendar window.
pub fn classify_mlb_phase(
    title: Option<&str>,
    subtitle: Option<&str>,
    _date: Option<NaiveDate>,
) -> PhaseClass {
    let blob = format!(
        "{} {}",
        title.unwrap_or_default(),
        subtitle.unwrap_or_default()
    );
    let lower = blob.to_ascii_lowercase();
    if lower.contains("exhibition") {
        return PhaseClass {
            phase: SeasonPhase::Exhibition,
            method: "event_title".into(),
        };
    }
    if lower.contains("spring training")
        || lower.contains("preseason")
        || lower.contains("pre-season")
    {
        return PhaseClass {
            phase: SeasonPhase::Preseason,
            method: "event_title".into(),
        };
    }
    if lower.contains("all-star") || lower.contains("all star") || lower.contains("allstar") {
        return PhaseClass {
            phase: SeasonPhase::OtherPostseason,
            method: "event_title".into(),
        };
    }
    if lower.contains("world series") {
        return PhaseClass {
            phase: SeasonPhase::Finals,
            method: "event_title".into(),
        };
    }
    if mlb_playoff_title(&lower) {
        return PhaseClass {
            phase: SeasonPhase::Playoffs,
            method: "event_title".into(),
        };
    }
    PhaseClass {
        phase: SeasonPhase::RegularSeason,
        method: "default_unlabeled".into(),
    }
}

fn mlb_playoff_title(lower: &str) -> bool {
    lower.contains("wild card")
        || lower.contains("wildcard")
        || lower.contains("wild-card")
        || lower.contains("alds")
        || lower.contains("nlds")
        || lower.contains("alcs")
        || lower.contains("nlcs")
        || lower.contains("division series")
        || lower.contains("league championship")
        || lower.contains("playoff")
}

/// NHL phases. Does not reuse the NBA Oct 1–17 preseason window (NHL RS starts ~Oct 7).
pub fn classify_nhl_phase(
    title: Option<&str>,
    subtitle: Option<&str>,
    date: Option<NaiveDate>,
) -> PhaseClass {
    let blob = format!(
        "{} {}",
        title.unwrap_or_default(),
        subtitle.unwrap_or_default()
    );
    let lower = blob.to_ascii_lowercase();
    if exhibition_or_preseason_title(&lower) {
        return PhaseClass {
            phase: SeasonPhase::Preseason,
            method: "event_title".into(),
        };
    }
    if lower.contains("stanley cup") || lower.contains("finals") {
        return PhaseClass {
            phase: SeasonPhase::Finals,
            method: "event_title".into(),
        };
    }
    if looks_like_playoff_game_title(title.unwrap_or_default()) {
        if date.is_some_and(|d| d.month() == 6) {
            return PhaseClass {
                phase: SeasonPhase::Finals,
                method: "event_title_game_n_plus_june".into(),
            };
        }
        return PhaseClass {
            phase: SeasonPhase::Playoffs,
            method: "event_title_game_n".into(),
        };
    }
    if lower.contains("playoff") {
        return PhaseClass {
            phase: SeasonPhase::Playoffs,
            method: "event_title".into(),
        };
    }
    if date.is_some_and(|d| d.month() == 9) {
        return PhaseClass {
            phase: SeasonPhase::Preseason,
            method: "calendar_september_preseason".into(),
        };
    }
    PhaseClass {
        phase: SeasonPhase::RegularSeason,
        method: "default_unlabeled".into(),
    }
}

fn ncaa_tournament_title(lower: &str) -> bool {
    lower.contains("first four")
        || lower.contains("round of 64")
        || lower.contains("round of 32")
        || lower.contains("sweet 16")
        || lower.contains("sweet sixteen")
        || lower.contains("elite 8")
        || lower.contains("elite eight")
        || lower.contains("final four")
        || lower.contains("national championship")
        || lower.contains("ncaa tournament")
        || lower.contains("march madness")
}

fn other_postseason_title(lower: &str) -> bool {
    lower.contains(" nit")
        || lower.starts_with("nit")
        || lower.contains("cbi")
        || lower.contains("nit championship")
}

fn conference_tournament_title(lower: &str) -> bool {
    lower.contains("conference tournament")
        || lower.contains("championship week")
        || lower.contains("conference championship")
}

fn exhibition_or_preseason_title(lower: &str) -> bool {
    lower.contains("exhibition") || lower.contains("preseason") || lower.contains("friendly")
}

fn looks_like_playoff_game_title(title: &str) -> bool {
    let t = title.trim();
    t.starts_with("Game ") && t.chars().nth(5).is_some_and(|c| c.is_ascii_digit())
}

/// Prefer subtitle `NYK at SAS` / `OKC vs SAS`.
pub fn parse_venue_sides(subtitle: Option<&str>, title: Option<&str>) -> VenueSides {
    if let Some(sides) = parse_at_or_vs(subtitle) {
        return sides;
    }
    if let Some(sides) = parse_at_or_vs(title) {
        return sides;
    }
    VenueSides {
        away_code: None,
        home_code: None,
        relation: "UNKNOWN".into(),
    }
}

fn parse_at_or_vs(raw: Option<&str>) -> Option<VenueSides> {
    let s = raw?;
    let core = s.split('(').next().unwrap_or(s).trim();
    if let Some((left, right)) = split_ci(core, " at ") {
        return Some(VenueSides {
            away_code: Some(normalize_code(&left)),
            home_code: Some(normalize_code(&right)),
            relation: "AT".into(),
        });
    }
    if let Some((left, right)) = split_ci(core, " vs ") {
        return Some(VenueSides {
            away_code: Some(normalize_code(&left)),
            home_code: Some(normalize_code(&right)),
            relation: "VS".into(),
        });
    }
    None
}

fn split_ci(s: &str, sep: &str) -> Option<(String, String)> {
    let lower = s.to_ascii_lowercase();
    let idx = lower.find(sep)?;
    let left = s[..idx].trim().to_string();
    let right = s[idx + sep.len()..].trim().to_string();
    if left.is_empty() || right.is_empty() {
        return None;
    }
    Some((left, right))
}

fn normalize_code(raw: &str) -> String {
    let t = raw.trim();
    if t.chars().all(|c| c.is_ascii_uppercase()) && (2..=4).contains(&t.len()) {
        return t.to_string();
    }
    t.to_string()
}

pub fn market_yes_team(market: &Value) -> Option<String> {
    json_str(market, "yes_sub_title").filter(|s| !s.is_empty())
}

pub fn market_no_team(market: &Value) -> Option<String> {
    json_str(market, "no_sub_title").filter(|s| !s.is_empty())
}

pub fn ticker_yes_code(ticker: &str) -> Option<String> {
    ticker.rsplit_once('-').map(|(_, code)| code.to_string())
}

pub fn hex_u128(v: u128) -> String {
    format!("{v:032x}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::NaiveDate;

    #[test]
    fn play_in_from_title() {
        let p = classify_phase(
            Some("West Play-In: Golden State at Los Angeles C"),
            Some("GSW at LAC (Apr 15)"),
            NaiveDate::from_ymd_opt(2026, 4, 15),
        );
        assert_eq!(p.phase, SeasonPhase::PlayIn);
        assert_eq!(p.method, "event_title");
    }

    #[test]
    fn playoffs_from_game_n() {
        let p = classify_phase(
            Some("Game 1: Atlanta at New York"),
            Some("ATL at NYK (Apr 18)"),
            NaiveDate::from_ymd_opt(2026, 4, 18),
        );
        assert_eq!(p.phase, SeasonPhase::Playoffs);
    }

    #[test]
    fn finals_from_game_n_in_june() {
        let p = classify_phase(
            Some("Game 5: New York at San Antonio"),
            Some("NYK at SAS (Jun 13)"),
            NaiveDate::from_ymd_opt(2026, 6, 13),
        );
        assert_eq!(p.phase, SeasonPhase::Finals);
        assert_eq!(p.method, "event_title_game_n_plus_june");
    }

    #[test]
    fn preseason_calendar_when_unlabeled() {
        let p = classify_phase(
            Some("Sacramento vs Portland"),
            Some("SAC at POR (Oct 10)"),
            NaiveDate::from_ymd_opt(2025, 10, 10),
        );
        assert_eq!(p.phase, SeasonPhase::Preseason);
    }

    #[test]
    fn venue_at() {
        let v = parse_venue_sides(Some("NYK at SAS (Jun 13)"), None);
        assert_eq!(v.away_code.as_deref(), Some("NYK"));
        assert_eq!(v.home_code.as_deref(), Some("SAS"));
        assert_eq!(v.relation, "AT");
    }

    #[test]
    fn season_labels() {
        assert_eq!(
            season_for_date(NaiveDate::from_ymd_opt(2025, 10, 22).unwrap()),
            "2025-2026"
        );
        assert_eq!(
            season_for_date(NaiveDate::from_ymd_opt(2026, 6, 13).unwrap()),
            "2025-2026"
        );
        assert_eq!(
            season_for_date(NaiveDate::from_ymd_opt(2025, 4, 15).unwrap()),
            "2024-2025"
        );
    }

    #[test]
    fn mlb_date_token_and_season() {
        let with_hhmm = parse_event_date_token("KXMLBGAME-26MAY091805COLPHI").unwrap();
        assert_eq!(with_hhmm, NaiveDate::from_ymd_opt(2026, 5, 9).unwrap());
        let no_hhmm = parse_event_date_token("KXMLBGAME-25AUG25WSHCOL").unwrap();
        assert_eq!(no_hhmm, NaiveDate::from_ymd_opt(2025, 8, 25).unwrap());
        assert_eq!(season_for_date_mlb(no_hhmm), "2025-2026");
        assert_eq!(season_for_date_mlb(with_hhmm), "2025-2026");
        // NBA Oct-June labeling would put August 2025 in 2024-2025; MLB must not.
        assert_eq!(
            season_for_date(NaiveDate::from_ymd_opt(2025, 8, 25).unwrap()),
            "2024-2025"
        );
        assert_eq!(
            season_for_date_mlb(NaiveDate::from_ymd_opt(2025, 4, 16).unwrap()),
            "2025-2026"
        );
    }

    #[test]
    fn mlb_phase_does_not_use_nba_october_preseason() {
        let regular = classify_mlb_phase(
            Some("Washington at Colorado"),
            Some("WSH at COL (Oct 10)"),
            NaiveDate::from_ymd_opt(2025, 10, 10),
        );
        assert_eq!(regular.phase, SeasonPhase::RegularSeason);
        let ws = classify_mlb_phase(
            Some("World Series Game 3: Los Angeles at New York"),
            Some("LAD at NYY (Oct 28)"),
            NaiveDate::from_ymd_opt(2025, 10, 28),
        );
        assert_eq!(ws.phase, SeasonPhase::Finals);
        let spring = classify_mlb_phase(
            Some("Spring Training: Boston at New York"),
            Some("BOS at NYY (Mar 02)"),
            NaiveDate::from_ymd_opt(2026, 3, 2),
        );
        assert_eq!(spring.phase, SeasonPhase::Preseason);
    }

    #[test]
    fn wnba_date_token_and_season() {
        let d = parse_event_date_token("KXWNBAGAME-25MAY16NYLA").unwrap();
        assert_eq!(d, NaiveDate::from_ymd_opt(2025, 5, 16).unwrap());
        assert_eq!(season_for_date_wnba(d), "2025-2026");
        assert_eq!(
            season_for_date_wnba(NaiveDate::from_ymd_opt(2026, 8, 25).unwrap()),
            "2025-2026"
        );
        // NBA Oct-June labeling would put May 2025 in 2024-2025; WNBA must not.
        assert_eq!(
            season_for_date(NaiveDate::from_ymd_opt(2025, 5, 16).unwrap()),
            "2024-2025"
        );
    }

    #[test]
    fn wnba_phase_does_not_use_nba_october_preseason() {
        let p = classify_wnba_phase(
            Some("New York at Las Vegas"),
            Some("NY at LV (Oct 10)"),
            NaiveDate::from_ymd_opt(2025, 10, 10),
        );
        assert_eq!(p.phase, SeasonPhase::RegularSeason);
        let finals = classify_wnba_phase(
            Some("Game 3: Minnesota at New York"),
            Some("MIN at NY (Oct 10)"),
            NaiveDate::from_ymd_opt(2025, 10, 10),
        );
        assert_eq!(finals.phase, SeasonPhase::Finals);
    }

    #[test]
    fn ncaab_date_token_and_season() {
        let d = parse_event_date_token("KXNCAAMBGAME-26JAN18TLSAUAB").unwrap();
        assert_eq!(d, NaiveDate::from_ymd_opt(2026, 1, 18).unwrap());
        assert_eq!(season_for_date_ncaab(d), "2025-2026");
        assert_eq!(
            season_for_date_ncaab(NaiveDate::from_ymd_opt(2025, 10, 28).unwrap()),
            "2025-2026"
        );
    }

    #[test]
    fn ncaab_phases_from_title_not_calendar() {
        let ncaa = classify_ncaab_phase(
            Some("Sweet 16: Duke at Houston"),
            Some("DUKE at HOU (Mar 27)"),
            NaiveDate::from_ymd_opt(2026, 3, 27),
        );
        assert_eq!(ncaa.phase, SeasonPhase::NcaaTournament);
        let conf = classify_ncaab_phase(
            Some("Big Ten Conference Tournament"),
            Some("IU at PUR"),
            NaiveDate::from_ymd_opt(2026, 3, 14),
        );
        assert_eq!(conf.phase, SeasonPhase::ConferenceTournament);
        let regular = classify_ncaab_phase(
            Some("Tulsa at UAB"),
            Some("TLSA at UAB (Jan 18)"),
            NaiveDate::from_ymd_opt(2026, 1, 18),
        );
        assert_eq!(regular.phase, SeasonPhase::RegularSeason);
        let march_regular = classify_ncaab_phase(
            Some("Tulsa at UAB"),
            Some("TLSA at UAB (Mar 02)"),
            NaiveDate::from_ymd_opt(2026, 3, 2),
        );
        assert_eq!(march_regular.phase, SeasonPhase::RegularSeason);
    }

    #[test]
    fn nhl_date_token_and_september_season() {
        let d = parse_event_date_token("KXNHLGAME-25OCT07TORBOS").unwrap();
        assert_eq!(d, NaiveDate::from_ymd_opt(2025, 10, 7).unwrap());
        assert_eq!(season_for_date_nhl(d), "2025-2026");
        assert_eq!(
            season_for_date_nhl(NaiveDate::from_ymd_opt(2025, 9, 21).unwrap()),
            "2025-2026"
        );
        assert_eq!(
            season_for_date(NaiveDate::from_ymd_opt(2025, 9, 21).unwrap()),
            "2024-2025"
        );
        assert_eq!(
            season_for_date_nhl(NaiveDate::from_ymd_opt(2026, 6, 17).unwrap()),
            "2025-2026"
        );
    }

    #[test]
    fn tennis_date_token_and_calendar_season() {
        let atp = parse_event_date_token("KXATPMATCH-26SEP11ZVEKHA").unwrap();
        assert_eq!(atp, NaiveDate::from_ymd_opt(2026, 9, 11).unwrap());
        let wta = parse_event_date_token("KXWTAMATCH-25AUG01MARMAR2").unwrap();
        assert_eq!(wta, NaiveDate::from_ymd_opt(2025, 8, 1).unwrap());
        // Both calendar campaigns land in the same 2025-2026 folder.
        assert_eq!(season_for_date_tennis(atp), "2025-2026");
        assert_eq!(season_for_date_tennis(wta), "2025-2026");
        assert_eq!(
            season_for_date_tennis(NaiveDate::from_ymd_opt(2026, 1, 19).unwrap()),
            "2025-2026"
        );
        assert_eq!(
            season_for_date_tennis(NaiveDate::from_ymd_opt(2027, 5, 30).unwrap()),
            "2027-2028"
        );
        // NBA Oct-June labeling would scatter the tennis calendar year.
        assert_eq!(
            season_for_date(NaiveDate::from_ymd_opt(2025, 8, 1).unwrap()),
            "2024-2025"
        );
    }

    #[test]
    fn tennis_phase_from_competition_only() {
        assert_eq!(
            classify_tennis_phase(Some("US Open Men Singles")).phase,
            SeasonPhase::GrandSlam
        );
        assert_eq!(
            classify_tennis_phase(Some("US Open Women Singles")).method,
            "tennis_competition_grand_slam"
        );
        for slam in [
            "Australian Open Men Singles",
            "Roland Garros Women Singles",
            "Wimbledon Men Singles",
        ] {
            assert_eq!(
                classify_tennis_phase(Some(slam)).phase,
                SeasonPhase::GrandSlam,
                "{slam}"
            );
        }
        let tour = classify_tennis_phase(Some("ATP Cincinnati"));
        assert_eq!(tour.phase, SeasonPhase::RegularSeason);
        assert_eq!(tour.method, "tennis_competition_tour_event");
        let unknown = classify_tennis_phase(None);
        assert_eq!(unknown.phase, SeasonPhase::Unknown);
        assert_eq!(unknown.method, "tennis_competition_unclassified");
        assert_eq!(
            classify_tennis_phase(Some("   ")).phase,
            SeasonPhase::Unknown
        );
    }

    #[test]
    fn tennis_dispatcher_never_guesses_a_phase_from_the_title() {
        let p = classify_phase_for_sport(
            ResearchSport::TennisAtp,
            Some("Zverev vs Khachanov"),
            Some("Zverev vs Khachanov (Sep 11)"),
            NaiveDate::from_ymd_opt(2026, 9, 11),
        );
        assert_eq!(p.phase, SeasonPhase::Unknown);
        assert_eq!(p.method, "tennis_competition_unavailable");
    }

    #[test]
    fn tennis_competition_falls_back_to_the_title_prefix_and_says_so() {
        // Events predating `product_metadata` carry the tournament in the title.
        let legacy = serde_json::json!({
            "event_ticker": "KXWTAMATCH-25JUN27JOIPAV",
            "title": "WTA Eastbourne: Joint or Pavlyuchenkova advances?",
            "sub_title": "Joint vs Pavlyuchenkova"
        });
        let resolved = tennis_competition_resolved(&legacy);
        assert_eq!(resolved.name.as_deref(), Some("WTA Eastbourne"));
        assert_eq!(resolved.source, TENNIS_COMPETITION_FROM_TITLE);
        assert_eq!(
            classify_tennis_phase_for_event(&legacy).method,
            "tennis_competition_tour_event_from_event_title"
        );

        // Exchange metadata always wins and is labeled as such.
        let modern = serde_json::json!({
            "event_ticker": "KXATPMATCH-26SEP11ZVEKHA",
            "title": "Zverev vs Khachanov",
            "product_metadata": {"competition": "US Open Men Singles"}
        });
        let resolved = tennis_competition_resolved(&modern);
        assert_eq!(resolved.source, TENNIS_COMPETITION_FROM_METADATA);
        let class = classify_tennis_phase_for_event(&modern);
        assert_eq!(class.phase, SeasonPhase::GrandSlam);
        assert_eq!(class.method, "tennis_competition_grand_slam");

        // A head-to-head title is not a tournament name.
        let bare = serde_json::json!({
            "event_ticker": "KXATPMATCH-26SEP11ZVEKHA",
            "title": "Zverev vs Khachanov"
        });
        let resolved = tennis_competition_resolved(&bare);
        assert_eq!(resolved.name, None);
        assert_eq!(resolved.source, TENNIS_COMPETITION_UNAVAILABLE);
        let class = classify_tennis_phase_for_event(&bare);
        assert_eq!(class.phase, SeasonPhase::Unknown);
        assert_eq!(class.method, "tennis_competition_unclassified");
        assert_eq!(
            tennis_competition_resolved(&serde_json::json!({
                "title": "Alcaraz vs Sinner: who advances?"
            }))
            .name,
            None
        );
    }

    #[test]
    fn tennis_sides_come_from_market_suffixes_not_a_blob_split() {
        // A naive 3+3 split of "KWONLAJ" would produce KWO / NLA.
        let sides = tennis_player_sides(
            "KXATPMATCH-26AUG24KWONLAJ",
            &[
                "KXATPMATCH-26AUG24KWONLAJ-KWON".into(),
                "KXATPMATCH-26AUG24KWONLAJ-LAJ".into(),
            ],
        )
        .unwrap();
        assert_eq!(sides.side_a_code, "KWON");
        assert_eq!(sides.side_b_code, "LAJ");
        assert_eq!(sides.order_method, "event_ticker_blob_order");

        // 5-char blob: "VANDE" is VAN + DE, not a 3+3 split.
        let short = tennis_player_sides(
            "KXATPMATCH-26SEP03VANDE",
            &[
                "KXATPMATCH-26SEP03VANDE-DE".into(),
                "KXATPMATCH-26SEP03VANDE-VAN".into(),
            ],
        )
        .unwrap();
        assert_eq!(short.side_a_code, "VAN");
        assert_eq!(short.side_b_code, "DE");

        // Trailing numeric disambiguation suffix.
        let numeric = tennis_player_sides(
            "KXWTAMATCH-26AUG01MARMAR2",
            &[
                "KXWTAMATCH-26AUG01MARMAR2-MAR".into(),
                "KXWTAMATCH-26AUG01MARMAR2-MAR2".into(),
            ],
        )
        .unwrap();
        assert_eq!(numeric.side_a_code, "MAR");
        assert_eq!(numeric.side_b_code, "MAR2");
    }

    #[test]
    fn tennis_sides_are_stable_regardless_of_market_order() {
        let a = tennis_player_sides(
            "KXATPMATCH-26SEP11ZVEKHA",
            &[
                "KXATPMATCH-26SEP11ZVEKHA-ZVE".into(),
                "KXATPMATCH-26SEP11ZVEKHA-KHA".into(),
            ],
        )
        .unwrap();
        let b = tennis_player_sides(
            "KXATPMATCH-26SEP11ZVEKHA",
            &[
                "KXATPMATCH-26SEP11ZVEKHA-KHA".into(),
                "KXATPMATCH-26SEP11ZVEKHA-ZVE".into(),
            ],
        )
        .unwrap();
        assert_eq!(a, b);
        assert_eq!(a.side_a_code, "ZVE");
    }

    #[test]
    fn tennis_sides_fall_back_to_lexicographic_when_blob_is_ambiguous() {
        // Both codes match the blob at index 0, so position cannot order them.
        let sides = tennis_player_sides(
            "KXATPMATCH-26SEP11ABC",
            &[
                "KXATPMATCH-26SEP11ABC-ABC".into(),
                "KXATPMATCH-26SEP11ABC-AB".into(),
            ],
        )
        .unwrap();
        assert_eq!(sides.side_a_code, "AB");
        assert_eq!(sides.side_b_code, "ABC");
        assert_eq!(sides.order_method, "market_suffix_lexicographic");
    }

    #[test]
    fn tennis_sides_fail_closed_without_exactly_two_distinct_markets() {
        assert!(tennis_player_sides("KXATPMATCH-26SEP11ZVEKHA", &[]).is_none());
        assert!(
            tennis_player_sides(
                "KXATPMATCH-26SEP11ZVEKHA",
                &["KXATPMATCH-26SEP11ZVEKHA-ZVE".into()]
            )
            .is_none()
        );
        assert!(
            tennis_player_sides(
                "KXATPMATCH-26SEP11ZVEKHA",
                &[
                    "KXATPMATCH-26SEP11ZVEKHA-ZVE".into(),
                    "KXATPMATCH-26SEP11ZVEKHA-KHA".into(),
                    "KXATPMATCH-26SEP11ZVEKHA-XXX".into(),
                ]
            )
            .is_none()
        );
        assert!(
            tennis_player_sides(
                "KXATPMATCH-26SEP11ZVEKHA",
                &[
                    "KXATPMATCH-26SEP11ZVEKHA-ZVE".into(),
                    "KXATPMATCH-26SEP11ZVEKHA-ZVE".into(),
                ]
            )
            .is_none()
        );
    }

    #[test]
    fn tennis_metadata_accessors_read_verbatim_kalshi_fields() {
        let event = serde_json::json!({
            "event_ticker": "KXATPMATCH-26SEP11ZVEKHA",
            "product_metadata": {"competition": "US Open Men Singles", "competition_scope": "Game"}
        });
        assert_eq!(
            tennis_competition(&event).as_deref(),
            Some("US Open Men Singles")
        );
        assert_eq!(tennis_competition(&serde_json::json!({})), None);
        let market = serde_json::json!({
            "ticker": "KXATPMATCH-26SEP09ZVEVAN-ZVE",
            "custom_strike": {"tennis_competitor": "dc4002ad-fb32-4f36-b59f-7c7af1927c57"}
        });
        assert_eq!(
            market_tennis_competitor(&market).as_deref(),
            Some("dc4002ad-fb32-4f36-b59f-7c7af1927c57")
        );
        assert_eq!(market_tennis_competitor(&serde_json::json!({})), None);
    }

    #[test]
    fn nhl_phase_does_not_use_nba_october_preseason() {
        let rs = classify_nhl_phase(
            Some("Toronto at Boston"),
            Some("TOR at BOS (Oct 07)"),
            NaiveDate::from_ymd_opt(2025, 10, 7),
        );
        assert_eq!(rs.phase, SeasonPhase::RegularSeason);
        let pre = classify_nhl_phase(
            Some("Toronto at Boston"),
            Some("TOR at BOS (Sep 21)"),
            NaiveDate::from_ymd_opt(2025, 9, 21),
        );
        assert_eq!(pre.phase, SeasonPhase::Preseason);
        let cup = classify_nhl_phase(
            Some("Stanley Cup Final Game 6"),
            Some("EDM at FLA (Jun 17)"),
            NaiveDate::from_ymd_opt(2026, 6, 17),
        );
        assert_eq!(cup.phase, SeasonPhase::Finals);
    }
}
