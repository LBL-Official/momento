//! Raw PBP ingestion boundary. Raw files are never overwritten.

use std::collections::BTreeSet;
use std::fs;
use std::io::{BufRead, BufReader};
use std::path::Path;

use chrono::{DateTime, Datelike, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::error::EventError;
use crate::event::{
    BaseOccupancy, CanonicalMlbEvent, EventProvenance, FixtureKind, GameStatus, HalfInning,
    MlbEventType, Score,
};
use crate::field::DataField;
use crate::identity::{CanonicalGameId, OfficialMlbGameRef, PlayerRef, SourceRef, event_id};
use crate::versions::{NORMALIZATION_VERSION, PARSER_VERSION, SCHEMA_VERSION};
use crate::w1_bridge::MlbTimestampKind;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct RawSourceRef {
    pub path: String,
    pub line: Option<u64>,
    pub sha256: String,
    pub source: String,
    pub retrieved_at: Option<DateTime<Utc>>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct IngestEnvelope {
    pub envelope_version: String,
    pub fixture_kind: FixtureKind,
    pub source: String,
    pub source_game_id: String,
    pub retrieved_at: Option<DateTime<Utc>>,
    pub payload: serde_json::Value,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct IngestReport {
    pub source: String,
    pub raw_ref: RawSourceRef,
    pub parser_version: String,
    pub events: usize,
    pub malformed: Vec<String>,
    pub duplicates: Vec<String>,
    pub fixture_kind: FixtureKind,
}

pub fn sha256_bytes(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

pub fn ingest_path(
    path: &Path,
) -> Result<(Vec<CanonicalMlbEvent>, IngestReport, OfficialMlbGameRef), EventError> {
    let bytes = fs::read(path)?;
    ingest_bytes(path.to_string_lossy().as_ref(), &bytes)
}

pub fn ingest_bytes(
    path_label: &str,
    bytes: &[u8],
) -> Result<(Vec<CanonicalMlbEvent>, IngestReport, OfficialMlbGameRef), EventError> {
    let sha = sha256_bytes(bytes);
    let raw = RawSourceRef {
        path: path_label.to_string(),
        line: None,
        sha256: sha.clone(),
        source: "file".into(),
        retrieved_at: None,
    };
    let env: IngestEnvelope = serde_json::from_slice(bytes)
        .map_err(|e| EventError::Malformed(format!("{path_label}: {e}")))?;
    parse_envelope(env, raw)
}

fn parse_envelope(
    env: IngestEnvelope,
    raw: RawSourceRef,
) -> Result<(Vec<CanonicalMlbEvent>, IngestReport, OfficialMlbGameRef), EventError> {
    if env.source_game_id.trim().is_empty() {
        return Err(EventError::MissingSourceId("source_game_id".into()));
    }
    let official = official_from_payload(&env)?;
    let game_id = CanonicalGameId::from_official_source(&env.source, &env.source_game_id)?;
    let plays = env
        .payload
        .pointer("/liveData/plays/allPlays")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    let mut events = Vec::new();
    let mut seen = BTreeSet::new();
    let mut malformed = Vec::new();
    let mut duplicates = Vec::new();
    let mut prev_outs = 0u8;
    let mut prev_score = Score::tied_zero();
    let mut prev_half = HalfInning::Top;
    let mut prev_inning = 1u8;

    events.push(game_start_event(&game_id, &env, &raw, &official, 1));

    let mut seq = 2u32;
    for (idx, play) in plays.iter().enumerate() {
        match play_to_event(
            &game_id,
            &env,
            &raw,
            &official,
            play,
            seq,
            idx,
            prev_outs,
            prev_score,
            prev_inning,
            prev_half,
        ) {
            Ok(ev) => {
                if !seen.insert(ev.source_event_id.clone()) {
                    duplicates.push(ev.source_event_id.clone());
                    continue;
                }
                if let Some(o) = ev.outs_after.as_value() {
                    prev_outs = *o;
                }
                if let Some(s) = ev.score_after.as_value() {
                    prev_score = *s;
                }
                if let Some(h) = ev.half.as_value() {
                    prev_half = *h;
                }
                if let Some(i) = ev.inning.as_value() {
                    prev_inning = *i;
                }
                events.push(ev);
                seq += 1;
            }
            Err(EventError::Malformed(m)) => malformed.push(m),
            Err(e) => return Err(e),
        }
    }

    let is_final = env
        .payload
        .pointer("/gameData/status/detailedState")
        .and_then(|v| v.as_str())
        == Some("Final")
        || env
            .payload
            .pointer("/gameData/status/abstractGameState")
            .and_then(|v| v.as_str())
            == Some("Final");
    if is_final {
        if let Some(last) = events.last_mut() {
            last.game_status_after = DataField::observed(GameStatus::Final);
        }
    }

    let report = IngestReport {
        source: env.source,
        raw_ref: raw,
        parser_version: PARSER_VERSION.to_string(),
        events: events.len(),
        malformed,
        duplicates,
        fixture_kind: env.fixture_kind,
    };
    Ok((events, report, official))
}

/// Identity-only parse of a landed StatsAPI envelope. Does not invent `gamePk`.
pub fn official_ref_from_envelope_bytes(bytes: &[u8]) -> Result<OfficialMlbGameRef, EventError> {
    let env: IngestEnvelope = serde_json::from_slice(bytes)
        .map_err(|e| EventError::Malformed(format!("envelope: {e}")))?;
    if env.source_game_id.trim().is_empty() {
        return Err(EventError::MissingSourceId("source_game_id".into()));
    }
    official_from_payload(&env)
}

fn official_from_payload(env: &IngestEnvelope) -> Result<OfficialMlbGameRef, EventError> {
    let game_pk = env
        .payload
        .pointer("/gameData/game/pk")
        .and_then(|v| {
            v.as_i64()
                .map(|n| n.to_string())
                .or_else(|| v.as_str().map(str::to_string))
        })
        .unwrap_or_else(|| env.source_game_id.clone());
    if game_pk != env.source_game_id && env.fixture_kind == FixtureKind::HistoricalSource {
        return Err(EventError::Malformed(
            "payload gamePk does not match envelope source_game_id".into(),
        ));
    }
    let date_s = env
        .payload
        .pointer("/gameData/datetime/officialDate")
        .and_then(|v| v.as_str())
        .ok_or_else(|| EventError::Malformed("missing gameData.datetime.officialDate".into()))?;
    let official_date = chrono::NaiveDate::parse_from_str(date_s, "%Y-%m-%d")
        .map_err(|e| EventError::Malformed(format!("officialDate: {e}")))?;
    let home_id = required_id(
        env.payload.pointer("/gameData/teams/home/id"),
        "home team id",
    )?;
    let away_id = required_id(
        env.payload.pointer("/gameData/teams/away/id"),
        "away team id",
    )?;
    let venue = env.payload.pointer("/gameData/venue/id").and_then(|v| {
        v.as_i64()
            .map(|n| n.to_string())
            .or_else(|| v.as_str().map(str::to_string))
            .map(|id| SourceRef {
                source: env.source.clone(),
                source_id: id,
            })
    });
    let game_number = env
        .payload
        .pointer("/gameData/game/gameNumber")
        .and_then(|v| v.as_u64())
        .map(|n| n as u8)
        .unwrap_or(1);
    let home_abbr = env
        .payload
        .pointer("/gameData/teams/home/abbreviation")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let away_abbr = env
        .payload
        .pointer("/gameData/teams/away/abbreviation")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    Ok(OfficialMlbGameRef {
        source: env.source.clone(),
        game_pk,
        season: crate::identity::DataYear(official_date.year()),
        official_date,
        home_team: SourceRef {
            source: env.source.clone(),
            source_id: home_id,
        },
        away_team: SourceRef {
            source: env.source.clone(),
            source_id: away_id,
        },
        venue,
        game_number,
        competition: "MLB".into(),
        home_abbreviation: home_abbr,
        away_abbreviation: away_abbr,
    })
}

fn required_id(v: Option<&serde_json::Value>, label: &str) -> Result<String, EventError> {
    v.and_then(|x| {
        x.as_i64()
            .map(|n| n.to_string())
            .or_else(|| x.as_str().map(str::to_string))
    })
    .ok_or_else(|| EventError::Malformed(format!("missing {label}")))
}

fn game_start_event(
    game_id: &CanonicalGameId,
    env: &IngestEnvelope,
    raw: &RawSourceRef,
    official: &OfficialMlbGameRef,
    seq: u32,
) -> CanonicalMlbEvent {
    let src_id = format!("{}:game_start", env.source_game_id);
    CanonicalMlbEvent {
        event_id: event_id(game_id, seq, &src_id),
        game_id: game_id.clone(),
        sequence: seq,
        source_event_id: src_id,
        source_timestamp: DataField::unavailable("game start wall time not in envelope"),
        source_timestamp_kind: MlbTimestampKind::CanonicalOrder,
        collector_timestamp: env
            .retrieved_at
            .map(DataField::observed)
            .unwrap_or_else(|| DataField::unavailable("no retrieval timestamp")),
        canonical_order: seq,
        inning: DataField::observed(1),
        half: DataField::observed(HalfInning::Top),
        outs_before: DataField::observed(0),
        outs_after: DataField::observed(0),
        score_before: DataField::observed(Score::tied_zero()),
        score_after: DataField::observed(Score::tied_zero()),
        batting_team: DataField::observed(official.away_team.source_id.clone()),
        fielding_team: DataField::observed(official.home_team.source_id.clone()),
        batter: DataField::unavailable("not on game_start"),
        pitcher: DataField::unavailable("not on game_start"),
        runners_before: DataField::observed(BaseOccupancy::empty()),
        runners_after: DataField::observed(BaseOccupancy::empty()),
        event_type: MlbEventType::GameStart,
        event_description: DataField::observed("game_start".into()),
        runs_scored: DataField::observed(0),
        balls: DataField::observed(0),
        strikes: DataField::observed(0),
        pitch: None,
        review: None,
        substitution: DataField::unavailable("none"),
        amends_event_id: None,
        game_status_after: DataField::observed(GameStatus::InProgress),
        provenance: provenance(env, raw, &format!("{}:game_start", env.source_game_id)),
    }
}

#[allow(clippy::too_many_arguments)]
fn play_to_event(
    game_id: &CanonicalGameId,
    env: &IngestEnvelope,
    raw: &RawSourceRef,
    official: &OfficialMlbGameRef,
    play: &serde_json::Value,
    seq: u32,
    idx: usize,
    prev_outs: u8,
    prev_score: Score,
    prev_inning: u8,
    prev_half: HalfInning,
) -> Result<CanonicalMlbEvent, EventError> {
    let about = play
        .get("about")
        .ok_or_else(|| EventError::Malformed(format!("play {idx} missing about")))?;
    let result = play
        .get("result")
        .ok_or_else(|| EventError::Malformed(format!("play {idx} missing result")))?;
    let count = play.get("count");
    let inning = about
        .get("inning")
        .and_then(|v| v.as_u64())
        .ok_or_else(|| EventError::Malformed(format!("play {idx} missing inning")))?
        as u8;
    let half = match about
        .get("halfInning")
        .and_then(|v| v.as_str())
        .unwrap_or("")
    {
        "top" | "Top" => HalfInning::Top,
        "bottom" | "Bottom" => HalfInning::Bottom,
        other => {
            return Err(EventError::Malformed(format!(
                "play {idx} bad halfInning {other}"
            )));
        }
    };
    let outs_after = count
        .and_then(|c| c.get("outs"))
        .and_then(|v| v.as_u64())
        .map(|n| n as u8);
    let balls = count
        .and_then(|c| c.get("balls"))
        .and_then(|v| v.as_u64())
        .map(|n| n as u8);
    let strikes = count
        .and_then(|c| c.get("strikes"))
        .and_then(|v| v.as_u64())
        .map(|n| n as u8);
    let home = result
        .get("homeScore")
        .and_then(|v| v.as_u64())
        .map(|n| n as u16);
    let away = result
        .get("awayScore")
        .and_then(|v| v.as_u64())
        .map(|n| n as u16);
    let event_label = result
        .get("eventType")
        .and_then(|v| v.as_str())
        .or_else(|| result.get("event").and_then(|v| v.as_str()))
        .unwrap_or("other");
    let event_type = map_event_type(event_label);
    let source_event_id = play
        .get("playId")
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .unwrap_or_else(|| format!("{}:play:{idx}", env.source_game_id));
    let outs_before = if inning != prev_inning || half != prev_half {
        0
    } else {
        prev_outs
    };
    let score_after = match (home, away) {
        (Some(h), Some(a)) => Some(Score { home: h, away: a }),
        _ => None,
    };
    let runs = score_after.map(|s| (s.total().saturating_sub(prev_score.total())) as u8);
    let batter = player_from(play.pointer("/matchup/batter"));
    let pitcher = player_from(play.pointer("/matchup/pitcher"));
    let (bat, field) = match half {
        HalfInning::Top => (
            official.away_team.source_id.clone(),
            official.home_team.source_id.clone(),
        ),
        HalfInning::Bottom => (
            official.home_team.source_id.clone(),
            official.away_team.source_id.clone(),
        ),
    };
    let runners_after = runners_from_play(play);
    let start_time = play
        .pointer("/about/startTime")
        .and_then(|v| v.as_str())
        .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
        .map(|d| d.with_timezone(&Utc));

    Ok(CanonicalMlbEvent {
        event_id: event_id(game_id, seq, &source_event_id),
        game_id: game_id.clone(),
        sequence: seq,
        source_event_id: source_event_id.clone(),
        source_timestamp: start_time
            .map(DataField::observed)
            .unwrap_or_else(|| DataField::unavailable("no about.startTime")),
        source_timestamp_kind: if start_time.is_some() {
            MlbTimestampKind::PbpOfficial
        } else {
            MlbTimestampKind::CanonicalOrder
        },
        collector_timestamp: env
            .retrieved_at
            .map(DataField::observed)
            .unwrap_or_else(|| DataField::unavailable("no retrieval timestamp")),
        canonical_order: seq,
        inning: DataField::observed(inning),
        half: DataField::observed(half),
        outs_before: DataField::observed(outs_before),
        outs_after: outs_after
            .map(DataField::observed)
            .unwrap_or_else(|| DataField::unavailable("count.outs missing")),
        score_before: DataField::observed(prev_score),
        score_after: score_after
            .map(DataField::observed)
            .unwrap_or_else(|| DataField::unavailable("result scores missing")),
        batting_team: DataField::observed(bat),
        fielding_team: DataField::observed(field),
        batter: batter
            .map(DataField::observed)
            .unwrap_or_else(|| DataField::unavailable("matchup.batter missing")),
        pitcher: pitcher
            .map(DataField::observed)
            .unwrap_or_else(|| DataField::unavailable("matchup.pitcher missing")),
        runners_before: DataField::unavailable(
            "statsapi play does not always include pre-play occupancy",
        ),
        runners_after: runners_after
            .map(DataField::observed)
            .unwrap_or_else(|| DataField::unavailable("runners[] missing/unparsed")),
        event_type,
        event_description: DataField::observed(
            result
                .get("description")
                .and_then(|v| v.as_str())
                .unwrap_or(event_label)
                .to_string(),
        ),
        runs_scored: runs
            .map(DataField::observed)
            .unwrap_or_else(|| DataField::unavailable("cannot derive runs without scores")),
        balls: balls
            .map(DataField::observed)
            .unwrap_or_else(|| DataField::unavailable("count.balls missing")),
        strikes: strikes
            .map(DataField::observed)
            .unwrap_or_else(|| DataField::unavailable("count.strikes missing")),
        pitch: None,
        review: about.get("hasReview").and_then(|v| v.as_bool()).map(|b| {
            crate::event::ReviewInfo {
                in_review: b,
                overturned: DataField::unavailable("not in this play subset"),
                challenge_team: DataField::unavailable("not in this play subset"),
            }
        }),
        substitution: DataField::unavailable("not a substitution record"),
        amends_event_id: None,
        game_status_after: DataField::observed(GameStatus::InProgress),
        provenance: provenance(env, raw, &source_event_id),
    })
}

fn provenance(env: &IngestEnvelope, raw: &RawSourceRef, source_event_id: &str) -> EventProvenance {
    EventProvenance {
        source: env.source.clone(),
        source_game_id: env.source_game_id.clone(),
        source_event_id: source_event_id.to_string(),
        raw_file: DataField::observed(raw.path.clone()),
        raw_line: DataField::unavailable("json object, not jsonl line"),
        payload_sha256: DataField::observed(raw.sha256.clone()),
        parser_version: PARSER_VERSION.to_string(),
        normalization_version: NORMALIZATION_VERSION.to_string(),
        schema_version: SCHEMA_VERSION.to_string(),
        retrieval_timestamp: env
            .retrieved_at
            .map(DataField::observed)
            .unwrap_or_else(|| DataField::unavailable("no retrieval timestamp")),
        fixture_kind: env.fixture_kind,
    }
}

fn player_from(v: Option<&serde_json::Value>) -> Option<PlayerRef> {
    let id = v.and_then(|p| p.get("id"))?;
    let sid = id
        .as_i64()
        .map(|n| n.to_string())
        .or_else(|| id.as_str().map(str::to_string))?;
    Some(PlayerRef {
        source: "mlb_statsapi".into(),
        source_player_id: sid,
    })
}

fn runners_from_play(play: &serde_json::Value) -> Option<BaseOccupancy> {
    let runners = play.get("runners")?.as_array()?;
    // StatsAPI runners[] is a movement log. The same player may appear on
    // multiple sequential ends (1B→2B then 2B→3B). Final occupancy is the
    // last remaining base per player, not the union of every end.
    let mut pos: std::collections::BTreeMap<String, PlayerRef> = std::collections::BTreeMap::new();
    let mut base_of: std::collections::BTreeMap<String, u8> = std::collections::BTreeMap::new();
    let mut any = false;
    for r in runners {
        let end = r
            .pointer("/movement/end")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let is_out = r
            .pointer("/details/isOut")
            .and_then(|v| v.as_bool())
            .unwrap_or(false)
            || r.pointer("/movement/isOut")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
        let id = r
            .pointer("/details/runner/id")
            .or_else(|| r.pointer("/runner/id"));
        let player = id.and_then(|v| {
            v.as_i64()
                .map(|n| n.to_string())
                .or_else(|| v.as_str().map(str::to_string))
                .map(|sid| PlayerRef {
                    source: "mlb_statsapi".into(),
                    source_player_id: sid,
                })
        });
        let Some(player) = player else {
            continue;
        };
        any = true;
        let pid = player.source_player_id.clone();
        if is_out || matches!(end, "score" | "home" | "4B") {
            pos.remove(&pid);
            base_of.remove(&pid);
            continue;
        }
        let base = match end {
            "1B" | "1st" => 1u8,
            "2B" | "2nd" => 2,
            "3B" | "3rd" => 3,
            _ => continue,
        };
        pos.insert(pid.clone(), player);
        base_of.insert(pid, base);
    }
    let mut occ = BaseOccupancy::empty();
    for (pid, player) in pos {
        match base_of.get(&pid).copied() {
            Some(1) => occ.first = Some(player),
            Some(2) => occ.second = Some(player),
            Some(3) => occ.third = Some(player),
            _ => {}
        }
    }
    if any || !runners.is_empty() {
        Some(occ)
    } else {
        Some(BaseOccupancy::empty())
    }
}

pub fn map_event_type(label: &str) -> MlbEventType {
    match label.to_ascii_lowercase().replace(' ', "_").as_str() {
        "game_start" => MlbEventType::GameStart,
        "pitch" => MlbEventType::Pitch,
        "ball" => MlbEventType::Ball,
        "strike" => MlbEventType::Strike,
        "foul" => MlbEventType::Foul,
        "walk" | "intent_walk" | "intentional_walk" => MlbEventType::Walk,
        "hit_by_pitch" | "hbp" => MlbEventType::HitByPitch,
        "strikeout" | "strikeout_looking" | "strikeout_swinging" => MlbEventType::Strikeout,
        "single" => MlbEventType::Single,
        "double" => MlbEventType::Double,
        "triple" => MlbEventType::Triple,
        "home_run" | "homerun" => MlbEventType::HomeRun,
        "field_out" | "flyout" | "groundout" | "lineout" | "pop_out" | "popout" => {
            MlbEventType::FieldOut
        }
        "force_out" | "forceout" => MlbEventType::ForceOut,
        "fielders_choice_out" => MlbEventType::FieldersChoice,
        "sac_bunt" | "sac_fly" | "sacrifice" => MlbEventType::Sacrifice,
        "double_play" | "grounded_into_double_play" => MlbEventType::DoublePlay,
        "error" | "field_error" => MlbEventType::Error,
        "stolen_base"
        | "caught_stealing"
        | "pickoff_caught_stealing_2b"
        | "pickoff_caught_stealing_3b"
        | "pickoff_caught_stealing_home"
        | "caught_stealing_2b"
        | "caught_stealing_3b"
        | "caught_stealing_home" => MlbEventType::StolenBase,
        "wild_pitch" => MlbEventType::WildPitch,
        "passed_ball" => MlbEventType::PassedBall,
        "balk" => MlbEventType::Balk,
        "fielders_choice" => MlbEventType::FieldersChoice,
        "catcher_interf" | "catchers_interference" => MlbEventType::CatchersInterference,
        "pitching_substitution" | "pitching_change" => MlbEventType::PitchingChange,
        "offensive_substitution" | "batting_change" => MlbEventType::BattingChange,
        "substitution" => MlbEventType::Substitution,
        "review" => MlbEventType::Review,
        "amendment" => MlbEventType::Amendment,
        "inning_start" => MlbEventType::InningStart,
        "inning_end" => MlbEventType::InningEnd,
        "walkoff" | "walk_off" => MlbEventType::WalkOff,
        "game_end" => MlbEventType::GameEnd,
        _ => MlbEventType::Other,
    }
}

/// JSONL ingest for already-canonical events (normalized layer, not raw archive).
pub fn ingest_canonical_jsonl(path: &Path) -> Result<Vec<CanonicalMlbEvent>, EventError> {
    let f = fs::File::open(path)?;
    let reader = BufReader::new(f);
    let mut out = Vec::new();
    let mut seen = BTreeSet::new();
    for (i, line) in reader.lines().enumerate() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        let ev: CanonicalMlbEvent = serde_json::from_str(&line)
            .map_err(|e| EventError::Malformed(format!("{}:{}: {e}", path.display(), i + 1)))?;
        if !seen.insert(ev.source_event_id.clone()) {
            return Err(EventError::DuplicateEvent {
                game_id: ev.game_id.as_str().to_string(),
                source_event_id: ev.source_event_id,
            });
        }
        out.push(ev);
    }
    out.sort_by_key(|e| e.sequence);
    Ok(out)
}
