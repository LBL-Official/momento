//! W8 audit reconciliation. Uses W6 state at first80, not at entry.

use std::path::Path;

use momento_research_state::StateStore;

use crate::error::B1Error;
use crate::game_state::baseball_features;
use crate::identity::load_envelope_identity;
use crate::outcomes::settlement_from_w6;
use crate::store::{load_w6_game_meta, load_w8_entries};
use crate::types::SettlementOutcome;

pub const STAKE_CENTS: i32 = 625;
pub const BANKROLL_CENTS: i32 = 5000;
pub const PUBLISHED_110_HOLD_USD: f64 = 21.07;
pub const PUBLISHED_254_HOLD_USD: f64 = 33.88;
pub const PUBLISHED_254_N: usize = 254;

#[derive(Clone, Debug, serde::Serialize)]
pub struct ReconRow {
    pub game_id: String,
    pub opportunity_id: String,
    pub entry_cents: i32,
    pub qty: i32,
    pub first80_inning: Option<u8>,
    pub first80_lead: Option<i32>,
    pub settlement: String,
    pub hold_return_cents: Option<i32>,
    pub hold_pnl_cents: Option<i32>,
}

#[derive(Clone, Debug, serde::Serialize)]
pub struct W8ReconReport {
    pub observability: &'static str,
    pub fill_status: &'static str,
    pub filter: &'static str,
    pub stake_note: &'static str,
    pub w8_entries: usize,
    pub first80_late_lead2_entries: usize,
    pub n_games: usize,
    pub wins: usize,
    pub losses: usize,
    pub hold_sized_usd: f64,
    pub published_254_n: usize,
    pub published_254_hold_usd: f64,
    pub published_110_hold_usd: f64,
    pub matches_published_254: bool,
    pub prior_110_keys_available: bool,
    pub notes: Vec<String>,
    pub rows: Vec<ReconRow>,
}

pub fn qty_for_entry(entry_cents: i32) -> i32 {
    if entry_cents <= 0 {
        0
    } else {
        STAKE_CENTS / entry_cents
    }
}

pub fn late_lead2_at_first80(
    w8: &Path,
    w6: &Path,
    identity_landing: &Path,
) -> Result<W8ReconReport, B1Error> {
    let entries = load_w8_entries(w8)?;
    let w8_n = entries.len();
    let w6s = StateStore::open_existing(w6)?;
    let identity = load_envelope_identity(identity_landing);
    let mut rows = Vec::new();
    for mut e in entries {
        let (date, pk, status) = load_w6_game_meta(w6, &e.game_id)?;
        e.official_date = date;
        e.game_pk = pk.clone();
        e.game_status = status;
        let Some(first80) = e.first80_timestamp else {
            continue;
        };
        let states = w6s.load_states(&e.game_id)?;
        let ident = pk.as_ref().and_then(|p| identity.get(p));
        let bb = baseball_features(&states, first80, &e.side, ident);
        let inn_ok = bb.inning.is_some_and(|i| (6..=9).contains(&i));
        let lead_ok = bb.bound_team_lead.is_some_and(|l| l >= 2);
        if !inn_ok || !lead_ok {
            continue;
        }
        let (settlement, _, _) =
            settlement_from_w6(states.last(), e.game_status.as_deref(), ident, &e.side);
        let hold = match settlement {
            SettlementOutcome::Win => Some(100 - e.entry_price_cents),
            SettlementOutcome::Loss => Some(-e.entry_price_cents),
            _ => None,
        };
        let qty = qty_for_entry(e.entry_price_cents);
        rows.push(ReconRow {
            game_id: e.game_id,
            opportunity_id: e.opportunity_id,
            entry_cents: e.entry_price_cents,
            qty,
            first80_inning: bb.inning,
            first80_lead: bb.bound_team_lead,
            settlement: settlement.as_str().to_string(),
            hold_return_cents: hold,
            hold_pnl_cents: hold.map(|r| r * qty),
        });
    }
    let n = rows.len();
    let games: std::collections::BTreeSet<&str> = rows.iter().map(|r| r.game_id.as_str()).collect();
    let wins = rows.iter().filter(|r| r.settlement == "WIN").count();
    let losses = rows.iter().filter(|r| r.settlement == "LOSS").count();
    let pnl: i32 = rows.iter().filter_map(|r| r.hold_pnl_cents).sum();
    let hold_usd = f64::from(pnl) / 100.0;
    let matches = n == PUBLISHED_254_N && (hold_usd - PUBLISHED_254_HOLD_USD).abs() < 0.02;
    Ok(W8ReconReport {
        observability: "TRADE_PRINT_NOT_YES_BID",
        fill_status: "TRADE_PRINT_MODELED",
        filter: "W6 state at first80: inning in {6,7,8,9} AND bound team lead >= 2",
        stake_note: "qty = 625 // entry_cents; uncompounded; $6.25 of $50",
        w8_entries: w8_n,
        first80_late_lead2_entries: n,
        n_games: games.len(),
        wins,
        losses,
        hold_sized_usd: hold_usd,
        published_254_n: PUBLISHED_254_N,
        published_254_hold_usd: PUBLISHED_254_HOLD_USD,
        published_110_hold_usd: PUBLISHED_110_HOLD_USD,
        matches_published_254: matches,
        prior_110_keys_available: false,
        notes: vec![
            "Prior 110-trade curiosity JSON has aggregates only; row keys were not persisted."
                .into(),
            "Reconciliation target is the published full-universe 254 / +$33.88 hold path.".into(),
            "B1 primary search uses state at ENTRY. This recon uses state at first80.".into(),
        ],
        rows,
    })
}
