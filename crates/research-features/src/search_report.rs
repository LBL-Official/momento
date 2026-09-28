//! Write B1 exhaustive-search artifacts. Research only.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

use crate::a1_targets::EXIT_HOLD_TO_SETTLEMENT;
use crate::error::B1Error;
use crate::recon::{W8ReconReport, late_lead2_at_first80};
use crate::search::{
    BOOTSTRAP_N, BOOTSTRAP_SEED, Candidate, ChronoSplit, ENTRY_KEYS, EXITS, FILL_STATUS, SearchRow,
    attach_train_tertiles, bootstrap_ev_ci, chronological_60_20_20, flatten, generate_candidates,
    metrics,
};
use crate::store::FeatureStore;
use crate::types::B1EntrySnapshot;
use crate::validation::validate_batch;
use crate::versions::{ENGINE_VERSION, FEATURE_SCHEMA_VERSION};

#[derive(Clone, Debug)]
pub struct SearchConfig {
    pub features_sqlite: std::path::PathBuf,
    pub w8_sqlite: std::path::PathBuf,
    pub w6_sqlite: std::path::PathBuf,
    pub identity_landing: std::path::PathBuf,
    pub out_dir: std::path::PathBuf,
}

impl SearchConfig {
    pub fn defaults() -> Self {
        Self {
            features_sqlite: "Backtesting Suite/Foundation/B1/features.sqlite".into(),
            w8_sqlite: "Backtesting Suite/Foundation/W8/replay.sqlite".into(),
            w6_sqlite: "Backtesting Suite/Foundation/W6/state.sqlite".into(),
            identity_landing: "Backtesting Suite/Foundation/Ingest/landing/mlb_statsapi".into(),
            out_dir: "Backtesting Suite/Foundation/B1".into(),
        }
    }
}

fn write_json(path: &Path, v: &impl serde::Serialize) -> Result<(), B1Error> {
    fs::write(path, serde_json::to_string_pretty(v)?)?;
    Ok(())
}

fn rank_raw(cands: &[Candidate]) -> Vec<&Candidate> {
    let mut v: Vec<&Candidate> = cands
        .iter()
        .filter(|c| c.all.n_unique_games >= 20)
        .collect();
    v.sort_by(|a, b| {
        b.all
            .sharpe_game_unann
            .partial_cmp(&a.all.sharpe_game_unann)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| b.all.n_unique_games.cmp(&a.all.n_unique_games))
    });
    v
}

fn rank_validated(cands: &[Candidate]) -> Vec<&Candidate> {
    let mut v: Vec<&Candidate> = cands
        .iter()
        .filter(|c| {
            c.test.n_unique_games >= 50
                && c.validation.ev_cents.unwrap_or(0.0) > 0.0
                && c.test.sharpe_game_unann.unwrap_or(f64::NEG_INFINITY) > f64::NEG_INFINITY
        })
        .collect();
    v.sort_by(|a, b| {
        b.test
            .sharpe_game_unann
            .partial_cmp(&a.test.sharpe_game_unann)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    v
}

fn rank_robust(cands: &[Candidate]) -> Vec<&Candidate> {
    let mut v: Vec<&Candidate> = cands
        .iter()
        .filter(|c| c.test.ev_cents.unwrap_or(0.0) > 0.0 && c.test.n_unique_games >= 20)
        .collect();
    v.sort_by(|a, b| {
        b.robust_score
            .partial_cmp(&a.robust_score)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    v
}

fn lopo(rows: &[SearchRow], c: &Candidate) -> serde_json::Value {
    let months: BTreeSet<String> = rows.iter().map(|r| r.month.clone()).collect();
    let mut out = Vec::new();
    for m in months {
        let kept: Vec<&SearchRow> = rows
            .iter()
            .filter(|r| r.month != m)
            .filter(|r| match c.entry.as_str() {
                "ENTRY_80" => r.entry_cents == 80,
                "ENTRY_81" => r.entry_cents == 81,
                "ENTRY_82" => r.entry_cents == 82,
                "ENTRY_83" => r.entry_cents == 83,
                _ => (80..=83).contains(&r.entry_cents),
            })
            .filter(|r| {
                if c.condition == "ALL" {
                    return true;
                }
                c.condition.split('&').all(|pair| {
                    let Some((k, v)) = pair.split_once('=') else {
                        return false;
                    };
                    r.feats.get(k).is_some_and(|x| x == v)
                })
            })
            .collect();
        let met = metrics(&kept, &c.exit);
        out.push(serde_json::json!({
            "left_out_month": m,
            "n_games": met.n_unique_games,
            "ev_cents": met.ev_cents,
            "total_pnl_usd": met.total_pnl_usd,
            "remains_positive": met.total_pnl_cents > 0
        }));
    }
    serde_json::json!(out)
}

fn shape(rows: &[SearchRow], key: &str, exit: &str) -> serde_json::Value {
    let mut by: BTreeMap<String, Vec<&SearchRow>> = BTreeMap::new();
    for r in rows.iter().filter(|r| r.chrono == ChronoSplit::Test) {
        if let Some(v) = r.feats.get(key) {
            by.entry(v.clone()).or_default().push(r);
        }
    }
    let cells: Vec<_> = by
        .into_iter()
        .map(|(k, rs)| {
            let m = metrics(&rs, exit);
            serde_json::json!({"bucket": k, "n_games": m.n_unique_games, "ev_cents": m.ev_cents, "pnl_usd": m.total_pnl_usd})
        })
        .collect();
    serde_json::json!({"feature": key, "exit": exit, "split": "TEST", "cells": cells})
}

fn integrity(
    rows: &[SearchRow],
    snaps: &[B1EntrySnapshot],
    recon: &W8ReconReport,
) -> Result<serde_json::Value, B1Error> {
    let mut games = BTreeSet::new();
    let mut dup = 0;
    for s in snaps {
        if !games.insert(s.game_id.as_str()) {
            dup += 1;
        }
        if let Some(ts) = s.baseball.state_timestamp {
            if ts > s.entry_timestamp {
                return Err(B1Error::validation("LOOKAHEAD_STATE", "future W6 state"));
            }
        }
        if s.microstructure.bid != crate::availability::FeatureAvailability::UnavailableSource {
            return Err(B1Error::validation("FAKE_L2", "L2 entered search"));
        }
        if s.fair_value.fair_value_cents.is_some() {
            return Err(B1Error::validation("FAIR_VALUE_LEAK", "fair value present"));
        }
    }
    let mut train_g = BTreeSet::new();
    let mut test_g = BTreeSet::new();
    for r in rows {
        match r.chrono {
            ChronoSplit::Train => {
                train_g.insert(r.game_id.as_str());
            }
            ChronoSplit::Test => {
                test_g.insert(r.game_id.as_str());
            }
            _ => {}
        }
    }
    if !train_g.is_disjoint(&test_g) {
        return Err(B1Error::validation("SPLIT_LEAK", "train/test game overlap"));
    }
    if !recon.matches_published_254 {
        return Err(B1Error::validation(
            "RECON_FAIL",
            format!(
                "first80 late-lead2 hold is n={} ${:.2}, expected 254 / $33.88",
                recon.first80_late_lead2_entries, recon.hold_sized_usd
            ),
        ));
    }
    Ok(serde_json::json!({
        "duplicate_games": dup,
        "train_test_overlap": 0,
        "l2_used": false,
        "recon_254_ok": true,
        "gate": "COMPLETE"
    }))
}

pub fn run_bucket_search(cfg: &SearchConfig) -> Result<serde_json::Value, B1Error> {
    fs::create_dir_all(&cfg.out_dir)?;
    let recon = late_lead2_at_first80(&cfg.w8_sqlite, &cfg.w6_sqlite, &cfg.identity_landing)?;
    let mut recon_out = recon.clone();
    recon_out.rows.clear();
    write_json(&cfg.out_dir.join("b1_w8_recon.json"), &recon_out)?;
    if !recon.matches_published_254 {
        write_json(
            &cfg.out_dir.join("b1_search_halted.json"),
            &serde_json::json!({
                "halted": true,
                "reason": "W8 first80 late-lead2 hold did not match published 254 / +$33.88",
                "observed_n": recon.first80_late_lead2_entries,
                "observed_hold_usd": recon.hold_sized_usd
            }),
        )?;
        return Err(B1Error::validation(
            "RECON_FAIL",
            "STOP: W8 audit reconciliation failed before search",
        ));
    }
    if !cfg.features_sqlite.exists() {
        write_json(
            &cfg.out_dir.join("b1_search_halted.json"),
            &serde_json::json!({
                "halted": true,
                "reason": "features.sqlite missing after successful W8 recon. Run --extract then --search.",
                "recon_ok": true
            }),
        )?;
        return Ok(serde_json::json!({
            "recon_ok": true,
            "extract_required": true,
            "first80_late_lead2_n": recon.first80_late_lead2_entries,
            "hold_sized_usd": recon.hold_sized_usd
        }));
    }

    let store = FeatureStore::open_existing(&cfg.features_sqlite)?;
    let snaps = store.load_all()?;
    validate_batch(&snaps, snaps.len())?;
    let meta = store.run_meta()?;
    let mut rows: Vec<SearchRow> = snaps.iter().map(flatten).collect();
    let (train_cut, val_cut, test_end) = chronological_60_20_20(&mut rows);
    attach_train_tertiles(&mut rows, &snaps);
    let integ = integrity(&rows, &snaps, &recon)?;
    eprintln!("b1 search evaluating candidates…");
    let mut cands = generate_candidates(&rows);
    cands.sort_by(|a, b| a.id.cmp(&b.id));
    eprintln!("b1 search {} candidates", cands.len());

    let raw = rank_raw(&cands);
    let validated = rank_validated(&cands);
    let robust = rank_robust(&cands);

    let mut entry_cmp = Vec::new();
    for exit in EXITS {
        for entry in ENTRY_KEYS {
            let rs: Vec<&SearchRow> = rows
                .iter()
                .filter(|r| match *entry {
                    "ENTRY_80" => r.entry_cents == 80,
                    "ENTRY_81" => r.entry_cents == 81,
                    "ENTRY_82" => r.entry_cents == 82,
                    "ENTRY_83" => r.entry_cents == 83,
                    _ => true,
                })
                .collect();
            let m = metrics(&rs, exit);
            entry_cmp.push(serde_json::json!({
                "entry": entry, "exit": exit,
                "n": m.n_entries, "games": m.n_unique_games,
                "win_rate": m.win_rate, "ev_cents": m.ev_cents,
                "pnl_usd": m.total_pnl_usd, "return_pct_of_50": m.return_pct_of_50,
                "sharpe_game_unann": m.sharpe_game_unann,
                "sharpe_monthly_ann": m.sharpe_monthly_ann,
                "max_dd_usd": m.max_dd_usd,
                "fill_status": FILL_STATUS
            }));
        }
    }

    let mut monthly = BTreeMap::new();
    for r in &rows {
        if let Some(&ret) = r.exit_ret.get(EXIT_HOLD_TO_SETTLEMENT) {
            let e = monthly.entry(r.month.clone()).or_insert((0i32, 0usize));
            e.0 += ret * r.qty;
            e.1 += 1;
        }
    }

    let top_robust: Vec<&Candidate> = robust.iter().copied().take(20).collect();
    let mut boot = Vec::new();
    let mut lopo_rows = Vec::new();
    for c in top_robust.iter().take(8) {
        let all: Vec<&SearchRow> = rows.iter().collect();
        // reuse slice via condition parse — bootstrap on TEST rows of this cohort
        let test_rows: Vec<&SearchRow> = rows
            .iter()
            .filter(|r| r.chrono == ChronoSplit::Test)
            .filter(|r| match c.entry.as_str() {
                "ENTRY_80" => r.entry_cents == 80,
                "ENTRY_81" => r.entry_cents == 81,
                "ENTRY_82" => r.entry_cents == 82,
                "ENTRY_83" => r.entry_cents == 83,
                _ => true,
            })
            .filter(|r| {
                if c.condition == "ALL" {
                    true
                } else {
                    c.condition.split('&').all(|pair| {
                        pair.split_once('=')
                            .is_some_and(|(k, v)| r.feats.get(k).is_some_and(|x| x == v))
                    })
                }
            })
            .collect();
        let _ = all;
        boot.push(serde_json::json!({
            "id": c.id,
            "test_ev_usd_ci95": bootstrap_ev_ci(&test_rows, &c.exit, BOOTSTRAP_N, BOOTSTRAP_SEED)
        }));
        lopo_rows.push(serde_json::json!({"id": c.id, "leave_one_month_out": lopo(&rows, c)}));
    }

    let n_pos = cands
        .iter()
        .filter(|c| c.train.ev_cents.unwrap_or(0.0) > 0.0)
        .count();
    let n_fdr = cands.iter().filter(|c| c.bh_reject_q10).count();

    let false_winners: Vec<_> = rank_raw(&cands)
        .into_iter()
        .filter(|c| c.test.ev_cents.unwrap_or(0.0) <= 0.0)
        .take(15)
        .map(|c| {
            let why = if c.all.n_unique_games < 50 {
                "small sample"
            } else if c.one_month_domination {
                "one-month concentration"
            } else if c.validation.ev_cents.unwrap_or(0.0) <= 0.0 {
                "train/test decay / validation fail"
            } else {
                "train/test decay"
            };
            serde_json::json!({
                "id": c.id, "train_sharpe": c.train.sharpe_game_unann,
                "test_ev": c.test.ev_cents, "test_pnl_usd": c.test.total_pnl_usd,
                "n_games_all": c.all.n_unique_games, "failure": why,
                "research_status": c.research_status
            })
        })
        .collect();

    let best = {
        let mut robust_only: Vec<&Candidate> = cands
            .iter()
            .filter(|c| c.research_status == "ROBUST_CANDIDATE")
            .collect();
        robust_only.sort_by(|a, b| {
            b.robust_score
                .partial_cmp(&a.robust_score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        robust_only
            .first()
            .copied()
            .or_else(|| validated.first().copied())
            .or_else(|| robust.first().copied())
    };
    let best_json = match best {
        Some(c) => serde_json::json!({
            "entry_bucket": c.entry,
            "exit_bucket": c.exit,
            "condition_definition": c.condition,
            "feature_conditions": c.condition,
            "train_metrics": c.train,
            "validation_metrics": c.validation,
            "test_metrics": c.test,
            "n_entries": c.all.n_entries,
            "n_unique_games": c.all.n_unique_games,
            "win_rate": c.all.win_rate,
            "ev": c.all.ev_cents,
            "total_pnl": c.all.total_pnl_usd,
            "return_pct": c.all.return_pct_of_50,
            "sharpe": c.all.sharpe_game_unann,
            "sharpe_monthly_ann": c.all.sharpe_monthly_ann,
            "sortino": c.all.sortino_game_unann,
            "max_drawdown": c.all.max_dd_usd,
            "mfe": c.all.mean_mfe_cents,
            "mae": c.all.mean_mae_cents,
            "bootstrap_ci": boot.iter().find(|b| b.get("id").and_then(|v| v.as_str()) == Some(c.id.as_str())),
            "multiple_testing_adjustment": "Benjamini-Hochberg FDR q=0.10 on TRAIN P(EV<=0)",
            "concentration_metrics": {"month_concentration": c.month_concentration, "one_month_domination": c.one_month_domination},
            "fill_status": FILL_STATUS,
            "executable_fill_confirmed": false,
            "research_status": c.research_status,
            "classification": c.research_status,
            "note": "DESCRIPTIVE_ONLY. Not a trading rule."
        }),
        None => serde_json::json!({
            "research_status": "NO_ROBUST_CANDIDATE",
            "fill_status": FILL_STATUS,
            "executable_fill_confirmed": false
        }),
    };

    let best_by_exit: BTreeMap<_, _> = EXITS
        .iter()
        .map(|ex| {
            let top = robust
                .iter()
                .copied()
                .find(|c| c.exit == *ex)
                .or_else(|| validated.iter().copied().find(|c| c.exit == *ex));
            (
                (*ex).to_string(),
                top.map(|c| {
                    serde_json::json!({"id": c.id, "status": c.research_status, "test_sharpe": c.test.sharpe_game_unann, "test_pnl_usd": c.test.total_pnl_usd, "n_test_games": c.test.n_unique_games})
                }),
            )
        })
        .collect();

    write_json(
        &cfg.out_dir.join("b1_bucket_search_manifest.json"),
        &serde_json::json!({
            "b1_run": meta,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "fill_status": FILL_STATUS,
            "executable_fill_confirmed": false,
            "stake": "qty = 625 // entry_cents; uncompounded vs $50",
            "split": {"method": "chronological unique official_date 60/20/20", "train_before": train_cut, "validation_before": val_cut, "test_end": test_end},
            "thresholds": "TRAIN tertiles only; frozen on VAL/TEST",
            "bootstrap": {"n": BOOTSTRAP_N, "seed": BOOTSTRAP_SEED, "unit": "GAME"},
            "multiple_testing": "BH FDR q=0.10 on TRAIN one-sided P(mean PnL <= 0)",
            "candidates_tested": cands.len(),
            "integrity": integ
        }),
    )?;
    write_json(
        &cfg.out_dir.join("b1_entry_price_comparison.json"),
        &entry_cmp,
    )?;
    write_json(&cfg.out_dir.join("b1_exit_comparison.json"), &entry_cmp)?;
    let matrix: Vec<_> = cands
        .iter()
        .filter(|c| c.tier <= 1 && c.condition != "ALL" || c.condition == "ALL")
        .map(|c| {
            serde_json::json!({
                "entry": c.entry, "exit": c.exit, "condition": c.condition,
                "n_entries": c.all.n_entries, "n_games": c.all.n_unique_games,
                "win_rate": c.all.win_rate, "ev": c.all.ev_cents,
                "pnl_usd": c.all.total_pnl_usd, "sharpe": c.all.sharpe_game_unann,
                "max_dd_usd": c.all.max_dd_usd, "status": c.research_status
            })
        })
        .collect();
    write_json(&cfg.out_dir.join("b1_condition_matrix.json"), &matrix)?;
    write_json(
        &cfg.out_dir.join("b1_top_raw_candidates.json"),
        &raw.iter().take(50).collect::<Vec<_>>(),
    )?;
    write_json(
        &cfg.out_dir.join("b1_top_validated_candidates.json"),
        &validated.iter().take(50).collect::<Vec<_>>(),
    )?;
    write_json(
        &cfg.out_dir.join("b1_top_robust_candidates.json"),
        &robust.iter().take(50).collect::<Vec<_>>(),
    )?;
    write_json(
        &cfg.out_dir.join("b1_oos_results.json"),
        &serde_json::json!({
            "split": {"train_before": train_cut, "validation_before": val_cut, "test_end": test_end},
            "n_train": rows.iter().filter(|r| r.chrono==ChronoSplit::Train).count(),
            "n_val": rows.iter().filter(|r| r.chrono==ChronoSplit::Validation).count(),
            "n_test": rows.iter().filter(|r| r.chrono==ChronoSplit::Test).count(),
            "top_validated": validated.iter().take(20).map(|c| c.id.clone()).collect::<Vec<_>>()
        }),
    )?;
    write_json(&cfg.out_dir.join("b1_bootstrap_results.json"), &boot)?;
    write_json(
        &cfg.out_dir.join("b1_multiple_testing.json"),
        &serde_json::json!({
            "method": "Benjamini-Hochberg",
            "q": 0.10,
            "candidates_with_pvalue": n_pos,
            "discoveries_q10": n_fdr,
            "note": "p = one-sided normal approx P(mean game PnL <= 0) on TRAIN"
        }),
    )?;
    write_json(
        &cfg.out_dir.join("b1_stability_results.json"),
        &serde_json::json!({"top": top_robust.iter().map(|c| serde_json::json!({"id": c.id, "month_concentration": c.month_concentration, "one_month_domination": c.one_month_domination})).collect::<Vec<_>>()}),
    )?;
    write_json(
        &cfg.out_dir.join("b1_monthly_results.json"),
        &monthly
            .iter()
            .map(|(k, (pnl, n))| serde_json::json!({"month": k, "hold_pnl_usd": f64::from(*pnl)/100.0, "n": n}))
            .collect::<Vec<_>>(),
    )?;
    write_json(
        &cfg.out_dir.join("b1_leave_one_period_out.json"),
        &lopo_rows,
    )?;
    write_json(&cfg.out_dir.join("b1_best_cohort.json"), &best_json)?;
    write_json(&cfg.out_dir.join("b1_false_winners.json"), &false_winners)?;
    write_json(&cfg.out_dir.join("b1_best_by_exit.json"), &best_by_exit)?;
    let shapes = [
        "p_start_tertile",
        "start_move_tertile",
        "vel_1m_tertile",
        "vol_5m_tertile",
        "inning_band",
        "lead_regime",
        "start_sentiment",
    ]
    .iter()
    .map(|k| shape(&rows, k, EXIT_HOLD_TO_SETTLEMENT))
    .collect::<Vec<_>>();
    write_json(&cfg.out_dir.join("b1_edge_shape.json"), &shapes)?;

    let report = render_report(
        &snaps,
        &cands,
        &raw,
        &validated,
        &robust,
        &entry_cmp,
        &false_winners,
        &best_json,
        &recon,
        &train_cut,
        &val_cut,
    );
    fs::write(cfg.out_dir.join("b1_research_report.md"), &report)?;
    fs::write(
        cfg.out_dir.join("b1_search_summary.md"),
        render_summary(&cands, best, &recon),
    )?;

    Ok(serde_json::json!({
        "candidates": cands.len(),
        "best": best.map(|c| c.id.clone()),
        "recon_ok": recon.matches_published_254,
        "fill_status": FILL_STATUS
    }))
}

fn render_summary(cands: &[Candidate], best: Option<&Candidate>, recon: &W8ReconReport) -> String {
    let robust_n = cands
        .iter()
        .filter(|c| c.research_status == "ROBUST_CANDIDATE")
        .count();
    format!(
        "# B1 search summary\n\n- fill_status: `{FILL_STATUS}`\n- executable_fill_confirmed: false\n- W8 first80 late-lead2 recon: n={} hold=${:.2} match_254={}\n- candidates tested: {}\n- ROBUST_CANDIDATE count: {}\n- best: {}\n- status: DESCRIPTIVE_ONLY. Not a trading rule.\n- STOP. No live FIRST01 change.\n",
        recon.first80_late_lead2_entries,
        recon.hold_sized_usd,
        recon.matches_published_254,
        cands.len(),
        robust_n,
        best.map(|c| c.id.as_str()).unwrap_or("NONE")
    )
}

#[allow(clippy::too_many_arguments)]
fn render_report(
    snaps: &[B1EntrySnapshot],
    cands: &[Candidate],
    raw: &[&Candidate],
    validated: &[&Candidate],
    robust: &[&Candidate],
    entry_cmp: &[serde_json::Value],
    false_winners: &[serde_json::Value],
    best: &serde_json::Value,
    recon: &W8ReconReport,
    train_cut: &str,
    val_cut: &str,
) -> String {
    let mut md = String::new();
    md.push_str("# B1 exhaustive 80–83¢ / A1 exit search\n\n");
    md.push_str("**Classification:** DESCRIPTIVE RESEARCH FINDING. Not a trading rule.\n\n");
    md.push_str(&format!(
        "**Fill status:** `{FILL_STATUS}`. `executable_fill_confirmed: false`.\n\n"
    ));
    md.push_str("P&L is uncompounded, `qty = 625 // entry_cents` ($6.25 of $50). No fees.\n\n");
    md.push_str("## Reconciliation\n\n");
    md.push_str(&format!(
        "W8 first80 late-lead2 hold: n={} games={} hold=${:.2}. Published 254 / $33.88 match={}.\n\n",
        recon.first80_late_lead2_entries, recon.n_games, recon.hold_sized_usd, recon.matches_published_254
    ));
    md.push_str("Prior 110-trade JSON has no row keys; the reproducible audit target is the 254-trade full-universe hold path.\n\n");
    md.push_str(&format!(
        "B1 snapshots: {}. Chronological date split TRAIN < `{}`, VALIDATION < `{}`.\n\n",
        snaps.len(),
        train_cut,
        val_cut
    ));
    md.push_str("## A. What entry price performed best?\n\n");
    md.push_str("| Entry | Exit | N | Games | Win | EV¢ | P&L $ | Sharpe | MaxDD $|\n|---|---|---:|---:|---:|---:|---:|---:|---:|\n");
    for row in entry_cmp
        .iter()
        .filter(|r| r["exit"] == EXIT_HOLD_TO_SETTLEMENT)
    {
        md.push_str(&format!(
            "| {} | hold | {} | {} | {:.3} | {:.2} | {:.2} | {:.3} | {:.2} |\n",
            row["entry"].as_str().unwrap_or(""),
            row["n"],
            row["games"],
            row["win_rate"].as_f64().unwrap_or(f64::NAN),
            row["ev_cents"].as_f64().unwrap_or(f64::NAN),
            row["pnl_usd"].as_f64().unwrap_or(f64::NAN),
            row["sharpe_game_unann"].as_f64().unwrap_or(f64::NAN),
            row["max_dd_usd"].as_f64().unwrap_or(f64::NAN),
        ));
    }
    md.push_str("\n## B. What exit performed best?\n\nSee `b1_exit_comparison.json` and `b1_best_by_exit.json`. Hold is settlement prediction; horizons are short-term price prediction; stops are path-dependent TRADE prints.\n\n");
    md.push_str("## C–E. Baseball / start / path\n\nSee `b1_edge_shape.json` (TEST-only buckets) and Tier-1 cells in `b1_condition_matrix.json`.\n\n");
    md.push_str("## F. Highest raw performance\n\n");
    for (i, c) in raw.iter().take(5).enumerate() {
        md.push_str(&format!(
            "{}. `{}` Sharpe(all)={:.3} n_games={} P&L=${:.2} status={}\n",
            i + 1,
            c.id,
            c.all.sharpe_game_unann.unwrap_or(f64::NAN),
            c.all.n_unique_games,
            c.all.total_pnl_usd,
            c.research_status
        ));
    }
    md.push_str("\n## G. Chronological OOS\n\n");
    if validated.is_empty() {
        md.push_str("No candidate met N_test_games >= 50 and positive validation EV.\n\n");
    } else {
        for (i, c) in validated.iter().take(5).enumerate() {
            md.push_str(&format!(
                "{}. `{}` test Sharpe={:.3} test EV¢={:.2} test P&L=${:.2} n_test={}\n",
                i + 1,
                c.id,
                c.test.sharpe_game_unann.unwrap_or(f64::NAN),
                c.test.ev_cents.unwrap_or(f64::NAN),
                c.test.total_pnl_usd,
                c.test.n_unique_games
            ));
        }
        md.push('\n');
    }
    md.push_str("## H–I. Bootstrap and concentration\n\nGame-level bootstrap (n=1000, seed=42) is in `b1_bootstrap_results.json`. One-month domination flag is on each candidate.\n\n");
    md.push_str("## J. Most robust historical cohort\n\n");
    md.push_str("```json\n");
    md.push_str(&serde_json::to_string_pretty(best).unwrap_or_default());
    md.push_str("\n```\n\n");
    md.push_str("## K. Economic caveats\n\nNo fees. TRADE print ≠ maker fill. No L2, size, or queue. Live FIRST01 is unchanged. A positive cell is not an executable edge.\n\n");
    md.push_str("## Top 20 validated / robust\n\n");
    md.push_str("| Rank | Entry | Exit | Condition | N | Games | TrEV | VaEV | TeEV | TrSh | VaSh | TeSh | TeP&L | MaxDD | WR | Status |\n|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|\n");
    let table = if validated.is_empty() {
        robust
    } else {
        validated
    };
    for (i, c) in table.iter().take(20).enumerate() {
        md.push_str(&format!(
            "| {} | {} | {} | {} | {} | {} | {:.2} | {:.2} | {:.2} | {:.2} | {:.2} | {:.2} | {:.2} | {:.2} | {:.3} | {} |\n",
            i + 1, c.entry, c.exit, c.condition,
            c.all.n_entries, c.all.n_unique_games,
            c.train.ev_cents.unwrap_or(f64::NAN),
            c.validation.ev_cents.unwrap_or(f64::NAN),
            c.test.ev_cents.unwrap_or(f64::NAN),
            c.train.sharpe_game_unann.unwrap_or(f64::NAN),
            c.validation.sharpe_game_unann.unwrap_or(f64::NAN),
            c.test.sharpe_game_unann.unwrap_or(f64::NAN),
            c.test.total_pnl_usd, c.test.max_dd_usd,
            c.all.win_rate.unwrap_or(f64::NAN),
            c.research_status
        ));
    }
    md.push_str("\n## False winners\n\n");
    for w in false_winners {
        md.push_str(&format!(
            "- `{}` — {}\n",
            w["id"].as_str().unwrap_or(""),
            w["failure"].as_str().unwrap_or("")
        ));
    }
    md.push_str(&format!(
        "\n## Universe\n\n{} candidates tested. This is a multiple-comparison search. RAW BEST ≠ VALIDATED BEST.\n\n**STOP.** No B2, W9, or live change.\n",
        cands.len()
    ));
    md
}
