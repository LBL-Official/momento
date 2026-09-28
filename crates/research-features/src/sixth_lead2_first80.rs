//! Observational: first FIRST01-aligned ≥80¢ print after the 6th starts
//! while the bound team leads by ≥2, then whether settlement YES occurs
//! without a later TRADE print ≤40¢.
//!
//! Research only. Does not change live FIRST01. Does not invent L2.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

use chrono::{DateTime, Utc};
use momento_research_path::PathStore;
use momento_research_state::{StateStore, StoredState};
use rusqlite::{Connection, params};
use serde::Serialize;

use crate::error::B1Error;
use crate::game_state::baseball_features;
use crate::identity::load_envelope_identity;
use crate::outcomes::settlement_from_w6;
use crate::store::load_w8_entries;
use crate::types::SettlementOutcome;

const FIRST80: i32 = 80;
const TOUCH40: i32 = 40;

#[derive(Clone, Debug, Serialize)]
pub struct SixthLead2Row {
    pub game_id: String,
    pub market_id: String,
    pub side: String,
    pub inning: Option<u8>,
    pub lead: Option<i32>,
    pub entry_cents: i32,
    pub first80_of_game: bool,
    pub had_earlier_80: bool,
    pub settlement: String,
    pub post_entry_min_cents: Option<i32>,
    pub touched_40: bool,
    pub win_without_40: bool,
    pub in_first83_universe: bool,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct SliceStats {
    pub n: usize,
    pub n_decided: usize,
    pub wins: usize,
    pub losses: usize,
    pub undecided: usize,
    pub win_rate: Option<f64>,
    pub touched_40: usize,
    pub win_and_touched_40: usize,
    pub loss_and_touched_40: usize,
    pub win_without_40: usize,
    pub pct_win_without_40: Option<f64>,
    pub pct_of_wins_never_40: Option<f64>,
    pub n_in_first83: usize,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct ExclusionCounts {
    pub no_trade_path: usize,
    pub no_first80: usize,
    pub no_sixth_inning_state: usize,
    pub no_80_after_sixth: usize,
    pub inning_before_6: usize,
    pub lead_unknown: usize,
    pub lead_lt_2: usize,
}

#[derive(Clone, Debug, Serialize)]
pub struct SixthLead2Report {
    pub definition: &'static str,
    pub fill_status: &'static str,
    pub touch_source: &'static str,
    pub w7_games_scanned: usize,
    pub first83_universe_n: usize,
    pub exclusions: ExclusionCounts,
    pub after6th_lead2_all: SliceStats,
    pub after6th_lead2_inning6: SliceStats,
    pub after6th_lead2_inning7plus: SliceStats,
    pub first01_first80_late: SliceStats,
    pub first01_first80_inning6: SliceStats,
    pub first83_after6th_lead2_all: SliceStats,
    pub first83_after6th_lead2_inning6: SliceStats,
    pub notes: Vec<String>,
}

#[derive(Clone, Debug)]
struct SlimTrade {
    market_id: String,
    side: String,
    observation_id: String,
    ts: DateTime<Utc>,
    price: i32,
}

fn parse_ts(raw: &str) -> Option<DateTime<Utc>> {
    DateTime::parse_from_rfc3339(raw)
        .ok()
        .map(|d| d.with_timezone(&Utc))
}

fn first_ge80<'a>(
    path: &'a [SlimTrade],
    market_id: Option<&str>,
    side: Option<&str>,
    not_before: Option<DateTime<Utc>>,
) -> Option<&'a SlimTrade> {
    path.iter()
        .filter(|o| o.price >= FIRST80)
        .filter(|o| market_id.is_none_or(|m| o.market_id == m))
        .filter(|o| side.is_none_or(|s| o.side.eq_ignore_ascii_case(s)))
        .filter(|o| not_before.is_none_or(|min| o.ts >= min))
        .min_by(|a, b| {
            a.ts.cmp(&b.ts)
                .then_with(|| a.observation_id.cmp(&b.observation_id))
        })
}

fn post_entry_min(
    path: &[SlimTrade],
    market_id: &str,
    side: &str,
    entry: DateTime<Utc>,
) -> Option<i32> {
    path.iter()
        .filter(|o| o.market_id == market_id)
        .filter(|o| o.side.eq_ignore_ascii_case(side))
        .filter(|o| o.ts > entry)
        .map(|o| o.price)
        .min()
}

fn load_game_trades(
    conn: &Connection,
    run_id: &str,
    game_id: &str,
) -> Result<Vec<SlimTrade>, B1Error> {
    let mut stmt = conn.prepare_cached(
        "SELECT market_id, contract_side, observation_id, market_timestamp_utc, trade_price_cents
         FROM path_observations
         WHERE run_id = ?1
           AND game_id = ?2
           AND observation_kind = 'TRADE'
           AND trade_price_cents IS NOT NULL
           AND market_timestamp_utc IS NOT NULL
         ORDER BY market_timestamp_utc, observation_id",
    )?;
    let rows = stmt.query_map(params![run_id, game_id], |r| {
        Ok((
            r.get::<_, String>(0)?,
            r.get::<_, String>(1)?,
            r.get::<_, String>(2)?,
            r.get::<_, String>(3)?,
            r.get::<_, i32>(4)?,
        ))
    })?;
    let mut out = Vec::new();
    for row in rows {
        let (market_id, side, observation_id, raw_ts, price) = row?;
        let Some(ts) = parse_ts(&raw_ts) else {
            continue;
        };
        out.push(SlimTrade {
            market_id,
            side,
            observation_id,
            ts,
            price,
        });
    }
    Ok(out)
}

fn sixth_start(states: &[StoredState]) -> Option<DateTime<Utc>> {
    states
        .iter()
        .filter(|s| s.inning >= 6 && s.canonical_timestamp.is_some())
        .min_by_key(|s| (s.canonical_timestamp, s.state_seq))
        .and_then(|s| s.canonical_timestamp)
}

fn load_w6_game_index(
    w6: &Path,
) -> Result<BTreeMap<String, (Option<String>, Option<String>)>, B1Error> {
    let conn = Connection::open(w6)?;
    conn.execute_batch("PRAGMA query_only = ON;")?;
    let mut stmt = conn.prepare("SELECT game_id, game_pk, status FROM games")?;
    let rows = stmt.query_map([], |r| {
        Ok((
            r.get::<_, String>(0)?,
            r.get::<_, Option<String>>(1)?,
            r.get::<_, Option<String>>(2)?,
        ))
    })?;
    let mut out = BTreeMap::new();
    for row in rows {
        let (gid, pk, status) = row?;
        out.insert(gid, (pk, status));
    }
    Ok(out)
}

fn load_first83_ids(path: &Path) -> Result<BTreeSet<String>, B1Error> {
    let conn = Connection::open(path)?;
    conn.execute_batch("PRAGMA query_only = ON;")?;
    let mut stmt = conn.prepare("SELECT DISTINCT game_id FROM entry_snapshots")?;
    let rows = stmt.query_map([], |r| r.get::<_, String>(0))?;
    let mut out = BTreeSet::new();
    for row in rows {
        out.insert(row?);
    }
    Ok(out)
}

fn slice_of<'a>(rows: impl Iterator<Item = &'a SixthLead2Row>) -> SliceStats {
    let rows: Vec<_> = rows.collect();
    let decided: Vec<_> = rows
        .iter()
        .copied()
        .filter(|r| r.settlement == "WIN" || r.settlement == "LOSS")
        .collect();
    let wins = decided.iter().filter(|r| r.settlement == "WIN").count();
    let losses = decided.iter().filter(|r| r.settlement == "LOSS").count();
    let touched = rows.iter().filter(|r| r.touched_40).count();
    let win_touch = rows
        .iter()
        .filter(|r| r.settlement == "WIN" && r.touched_40)
        .count();
    let loss_touch = rows
        .iter()
        .filter(|r| r.settlement == "LOSS" && r.touched_40)
        .count();
    let win_clean = rows.iter().filter(|r| r.win_without_40).count();
    SliceStats {
        n: rows.len(),
        n_decided: decided.len(),
        wins,
        losses,
        undecided: rows.len() - decided.len(),
        win_rate: if decided.is_empty() {
            None
        } else {
            Some(wins as f64 / decided.len() as f64)
        },
        touched_40: touched,
        win_and_touched_40: win_touch,
        loss_and_touched_40: loss_touch,
        win_without_40: win_clean,
        pct_win_without_40: if decided.is_empty() {
            None
        } else {
            Some(win_clean as f64 / decided.len() as f64)
        },
        pct_of_wins_never_40: if wins == 0 {
            None
        } else {
            Some((wins - win_touch) as f64 / wins as f64)
        },
        n_in_first83: rows.iter().filter(|r| r.in_first83_universe).count(),
    }
}

pub fn run_sixth_lead2_first80(
    w6: &Path,
    w7: &Path,
    w8: &Path,
    identity_landing: &Path,
    first83_sqlite: Option<&Path>,
    out_dir: &Path,
) -> Result<SixthLead2Report, B1Error> {
    let w7s = PathStore::open_existing(w7)?;
    let w7_run = w7s.run_id().to_string();
    let w7_conn = Connection::open(w7)?;
    w7_conn.execute_batch(
        "PRAGMA query_only = ON;
         PRAGMA cache_size = -262144;",
    )?;
    let w6s = StateStore::open_existing(w6)?;
    let games = w7s.list_game_ids()?;
    let w8_entries = load_w8_entries(w8).unwrap_or_default();
    let mut w8_by_game = BTreeMap::new();
    for e in w8_entries {
        w8_by_game.entry(e.game_id.clone()).or_insert(e);
    }
    let identity = load_envelope_identity(identity_landing);
    let w6_meta = load_w6_game_index(w6)?;
    let first83: BTreeSet<String> = match first83_sqlite {
        Some(p) if p.exists() => load_first83_ids(p)?,
        _ => BTreeSet::new(),
    };

    let mut rows = Vec::new();
    let mut exclusions = ExclusionCounts::default();
    let n_games = games.len();
    for (i, gid) in games.iter().enumerate() {
        let path = load_game_trades(&w7_conn, &w7_run, gid)?;
        if path.is_empty() {
            exclusions.no_trade_path += 1;
            continue;
        }
        let bound = w8_by_game
            .get(gid)
            .map(|e| (e.market_id.as_str(), e.side.as_str()));
        let bind_obs = match bound {
            Some((m, s)) => first_ge80(&path, Some(m), Some(s), None),
            None => first_ge80(&path, None, None, None),
        };
        let Some(bind) = bind_obs else {
            exclusions.no_first80 += 1;
            continue;
        };
        let market_id = bind.market_id.as_str();
        let side = bind.side.as_str();
        let first80_game = first_ge80(&path, Some(market_id), Some(side), None);
        let states = w6s.load_states(gid)?;
        let Some(sixth) = sixth_start(&states) else {
            exclusions.no_sixth_inning_state += 1;
            continue;
        };
        let Some(obs) = first_ge80(&path, Some(market_id), Some(side), Some(sixth)) else {
            exclusions.no_80_after_sixth += 1;
            continue;
        };
        let ts = obs.ts;
        let (pk, status) = w6_meta.get(gid).cloned().unwrap_or((None, None));
        let ident = pk.as_ref().and_then(|p| identity.get(p));
        let bb = baseball_features(&states, ts, side, ident);
        if !bb.inning.is_some_and(|inn| inn >= 6) {
            exclusions.inning_before_6 += 1;
            continue;
        }
        match bb.bound_team_lead {
            None => {
                exclusions.lead_unknown += 1;
                continue;
            }
            Some(l) if l < 2 => {
                exclusions.lead_lt_2 += 1;
                continue;
            }
            Some(_) => {}
        }
        let min_px = post_entry_min(&path, market_id, side, ts);
        let touched = min_px.is_some_and(|p| p <= TOUCH40);
        let (settlement, _, _) = settlement_from_w6(states.last(), status.as_deref(), ident, side);
        let win = settlement == SettlementOutcome::Win;
        let first_of_game = first80_game.is_some_and(|o| o.observation_id == obs.observation_id);
        let had_earlier = first80_game.is_some_and(|o| o.ts < sixth);
        rows.push(SixthLead2Row {
            game_id: gid.clone(),
            market_id: market_id.to_string(),
            side: side.to_string(),
            inning: bb.inning,
            lead: bb.bound_team_lead,
            entry_cents: obs.price,
            first80_of_game: first_of_game,
            had_earlier_80: had_earlier,
            settlement: settlement.as_str().to_string(),
            post_entry_min_cents: min_px,
            touched_40: touched,
            win_without_40: win && !touched,
            in_first83_universe: first83.contains(gid),
        });
        if (i + 1) % 400 == 0 || i + 1 == n_games {
            eprintln!(
                "sixth-lead2 first80 {}/{} kept {}",
                i + 1,
                n_games,
                rows.len()
            );
        }
    }

    let report = SixthLead2Report {
        definition: "First TRADE print ≥80¢ on the FIRST01-bound contract (W8 market+side \
when present, else the contract that first printed ≥80¢) at or after the first W6 \
state with inning≥6, kept only if bound-team lead ≥2 at that print. \
Headline slice is inning==6. first01_first80_* requires that print to also be \
the first ≥80¢ of the entire game. \
touched_40 = a later TRADE print on the same contract ≤40¢. \
Win-without-40 = settlement YES and never printed ≤40 after entry. \
TRADE print ≠ fill. L2 unavailable. Not a live FIRST01 change.",
        fill_status: "TRADE_PRINT_MODELED",
        touch_source: "W7_TRADE_PRINTS",
        w7_games_scanned: n_games,
        first83_universe_n: first83.len(),
        exclusions,
        after6th_lead2_all: slice_of(rows.iter()),
        after6th_lead2_inning6: slice_of(rows.iter().filter(|r| r.inning == Some(6))),
        after6th_lead2_inning7plus: slice_of(rows.iter().filter(|r| r.inning.is_some_and(|i| i >= 7))),
        first01_first80_late: slice_of(rows.iter().filter(|r| r.first80_of_game)),
        first01_first80_inning6: slice_of(
            rows.iter()
                .filter(|r| r.first80_of_game && r.inning == Some(6)),
        ),
        first83_after6th_lead2_all: slice_of(rows.iter().filter(|r| r.in_first83_universe)),
        first83_after6th_lead2_inning6: slice_of(
            rows.iter()
                .filter(|r| r.in_first83_universe && r.inning == Some(6)),
        ),
        notes: vec![
            "Path lows use W7 TRADE prints. No reconstructed 1m candle lake is present; candles were not invented.".into(),
            "Score difference is bound-team lead at the qualifying 80¢ print, not at first pitch of the 6th.".into(),
            "FIRST01 live thresholds (80/81/83/89) were not changed.".into(),
        ],
    };

    fs::create_dir_all(out_dir)?;
    fs::write(
        out_dir.join("sixth_lead2_first80_rows.json"),
        serde_json::to_string_pretty(&rows)?,
    )?;
    fs::write(
        out_dir.join("sixth_lead2_first80_report.json"),
        serde_json::to_string_pretty(&report)?,
    )?;
    fs::write(
        out_dir.join("sixth_lead2_first80_report.md"),
        render(&report),
    )?;
    Ok(report)
}

fn pct(x: Option<f64>) -> String {
    x.map(|v| format!("{:.1}%", v * 100.0))
        .unwrap_or_else(|| "—".into())
}

fn render_slice(name: &str, s: &SliceStats) -> String {
    format!(
        "### {name}\n\n\
n={n}  decided={dec}  WIN={w}  LOSS={l}  undecided={u}\n\
Settlement win rate: {wr}\n\
Touched ≤40¢ after entry: {t}\n\
Won after touching 40: {wt}\n\
Lost after touching 40: {lt}\n\
**Won without ever printing ≤40¢: {wc} ({p} of decided)**\n\
Share of wins that never printed 40: {pw}\n\
Also in first-exact-83 universe: {f83}\n",
        n = s.n,
        dec = s.n_decided,
        w = s.wins,
        l = s.losses,
        u = s.undecided,
        wr = pct(s.win_rate),
        t = s.touched_40,
        wt = s.win_and_touched_40,
        lt = s.loss_and_touched_40,
        wc = s.win_without_40,
        p = pct(s.pct_win_without_40),
        pw = pct(s.pct_of_wins_never_40),
        f83 = s.n_in_first83,
    )
}

fn render(r: &SixthLead2Report) -> String {
    format!(
        "# 6th-inning+ lead≥2 first-80, never-touch-40\n\n\
W7 games scanned: {}\n\
First-exact-83 universe: {}\n\n\
Exclusions: {:?}\n\n\
{}\n{}\n{}\n{}\n{}\n{}\n{}\n\
Fill = `TRADE_PRINT_MODELED`. Touch source = `W7_TRADE_PRINTS`.\n\
Not a live FIRST01 change.\n",
        r.w7_games_scanned,
        r.first83_universe_n,
        r.exclusions,
        render_slice(
            "Headline: first ≥80¢ after 6th start, inning==6, lead≥2",
            &r.after6th_lead2_inning6
        ),
        render_slice(
            "Sensitivity: first ≥80¢ after 6th start, inning≥6, lead≥2",
            &r.after6th_lead2_all
        ),
        render_slice("inning≥7 only", &r.after6th_lead2_inning7plus),
        render_slice(
            "FIRST01 first-80-of-game after 6th, inning≥6, lead≥2",
            &r.first01_first80_late
        ),
        render_slice(
            "FIRST01 first-80-of-game, inning==6, lead≥2",
            &r.first01_first80_inning6
        ),
        render_slice(
            "First-exact-83 games only, inning≥6",
            &r.first83_after6th_lead2_all
        ),
        render_slice(
            "First-exact-83 games only, inning==6",
            &r.first83_after6th_lead2_inning6
        ),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{TimeZone, Utc};

    fn obs(ts: i64, px: i32, id: &str) -> SlimTrade {
        SlimTrade {
            market_id: "m".into(),
            side: "LAD".into(),
            observation_id: id.into(),
            ts: Utc.timestamp_opt(ts, 0).unwrap(),
            price: px,
        }
    }

    #[test]
    fn first80_is_earliest_ge_80() {
        let path = vec![obs(1, 79, "a"), obs(2, 81, "b"), obs(3, 80, "c")];
        let hit = first_ge80(&path, Some("m"), Some("LAD"), None).unwrap();
        assert_eq!(hit.observation_id, "b");
    }

    #[test]
    fn first80_after_cutoff_skips_earlier() {
        let path = vec![obs(1, 82, "a"), obs(10, 80, "b")];
        let min = Utc.timestamp_opt(5, 0).unwrap();
        let hit = first_ge80(&path, Some("m"), Some("LAD"), Some(min)).unwrap();
        assert_eq!(hit.observation_id, "b");
    }

    #[test]
    fn post_entry_min_detects_40() {
        let path = vec![obs(10, 80, "e"), obs(11, 55, "x"), obs(12, 39, "y")];
        let ts = Utc.timestamp_opt(10, 0).unwrap();
        assert_eq!(post_entry_min(&path, "m", "LAD", ts), Some(39));
    }

    #[test]
    fn slice_win_without_40() {
        let rows = [
            SixthLead2Row {
                game_id: "a".into(),
                market_id: "m".into(),
                side: "LAD".into(),
                inning: Some(6),
                lead: Some(2),
                entry_cents: 80,
                first80_of_game: true,
                had_earlier_80: false,
                settlement: "WIN".into(),
                post_entry_min_cents: Some(61),
                touched_40: false,
                win_without_40: true,
                in_first83_universe: true,
            },
            SixthLead2Row {
                game_id: "b".into(),
                market_id: "m".into(),
                side: "LAD".into(),
                inning: Some(6),
                lead: Some(3),
                entry_cents: 81,
                first80_of_game: true,
                had_earlier_80: false,
                settlement: "WIN".into(),
                post_entry_min_cents: Some(38),
                touched_40: true,
                win_without_40: false,
                in_first83_universe: false,
            },
            SixthLead2Row {
                game_id: "c".into(),
                market_id: "m".into(),
                side: "LAD".into(),
                inning: Some(6),
                lead: Some(2),
                entry_cents: 80,
                first80_of_game: true,
                had_earlier_80: false,
                settlement: "LOSS".into(),
                post_entry_min_cents: Some(20),
                touched_40: true,
                win_without_40: false,
                in_first83_universe: false,
            },
        ];
        let s = slice_of(rows.iter());
        assert_eq!(s.n_decided, 3);
        assert_eq!(s.wins, 2);
        assert_eq!(s.win_without_40, 1);
        assert!((s.pct_win_without_40.unwrap() - 1.0 / 3.0).abs() < 1e-12);
        assert!((s.pct_of_wins_never_40.unwrap() - 0.5).abs() < 1e-12);
    }
}
