use chrono::Utc;

use momento_research_features::configured_search::{
    ConfiguredSearchSpec, ParameterSpec, run_configured_search,
};

use crate::error::EngineError;
use crate::paths::WorkspacePaths;
use crate::store::EngineStore;
use crate::types::{ExperimentDefinition, ExperimentRecord};

pub const EXHAUSTIVE_ID: &str = "EXP_B1_FIRST83_EXHAUSTIVE_v1";

fn locked_40_49() -> serde_json::Value {
    serde_json::json!({
        "condition": "start_price_band=40_49",
        "train": {"n": 486, "ev_cents": 3.42},
        "validation": {"n": 141, "ev_cents": 1.40},
        "test": {"n": 233, "ev_cents": 2.41},
        "q_value": 0.1731,
        "classification": "CANDIDATE",
        "note": "Research candidate. Not approved. q is from the 6,128-test search."
    })
}

fn locked_primary() -> serde_json::Value {
    serde_json::json!({
        "condition": "inning_grp=7&p_max_vs_83=PEAK_AT",
        "train": {"n": 65, "ev_cents": 7.77},
        "validation": {"n": 25, "ev_cents": 13.0},
        "test": {"n": 48, "ev_cents": 2.42},
        "q_value": 0.1837,
        "classification": "CANDIDATE",
        "note": "VAL-selected simple primary. Research candidate. Not production."
    })
}

fn pin_locked_candidates(store: &EngineStore) -> Result<(), EngineError> {
    store.upsert_candidate(
        "CAND_start_price_band_40_49",
        EXHAUSTIVE_ID,
        "start_price_band=40_49",
        "CANDIDATE",
        &locked_40_49(),
    )?;
    store.upsert_candidate(
        "CAND_primary_inning7_peak",
        EXHAUSTIVE_ID,
        "inning_grp=7&p_max_vs_83=PEAK_AT",
        "CANDIDATE",
        &locked_primary(),
    )?;
    Ok(())
}

fn modeled_unconditional(paths: &WorkspacePaths) -> serde_json::Value {
    let mut uncond = serde_json::json!({
        "condition": "ALL_83",
        "all": {"n": 2906, "win_rate": 0.833, "ev_cents": 0.28, "pnl_usd": 56.14},
        "train": {"n": 1699, "win_rate": 0.831, "ev_cents": 0.11, "pnl_usd": 12.81},
        "validation": {"n": 494, "win_rate": 0.822, "ev_cents": -0.81, "pnl_usd": -28.14},
        "test": {"n": 713, "win_rate": 0.844, "ev_cents": 1.43, "pnl_usd": 71.47},
        "fill_status": "TRADE_PRINT_MODELED",
        "source": "locked characterization / first83 extract"
    });
    if !paths.first83_sqlite.exists() {
        return uncond;
    }
    let spec = ConfiguredSearchSpec {
        features_sqlite: paths.first83_sqlite.clone(),
        parameters: vec![ParameterSpec::list(
            "start_price_band",
            vec!["40_49".into()],
        )],
        include_unconditional: true,
        ..ConfiguredSearchSpec::default()
    };
    if let Ok(report) = run_configured_search(&spec) {
        if let Ok(v) = serde_json::to_value(&report.unconditional) {
            uncond = v;
            uncond["source"] = serde_json::json!("configured_search ALL_83 on first83 sqlite");
            uncond["fill_status"] = serde_json::json!("TRADE_PRINT_MODELED");
        }
    }
    uncond
}

/// Register the already-run exhaustive first-83 experiment without re-running it.
pub fn import_first83_if_present(
    store: &EngineStore,
    paths: &WorkspacePaths,
) -> Result<(), EngineError> {
    if !paths.first83_rankings.exists() || !paths.first83_summary.exists() {
        return Ok(());
    }
    let already = store.get_experiment(EXHAUSTIVE_ID).ok();
    let hyp_n = already
        .as_ref()
        .and_then(|_| store.list_hypotheses(EXHAUSTIVE_ID).ok().map(|h| h.len()))
        .unwrap_or(0);
    if already.is_some() && hyp_n >= 6000 {
        pin_locked_candidates(store)?;
        return Ok(());
    }
    let summary: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(&paths.first83_summary)?)?;
    let csv = std::fs::read_to_string(&paths.first83_rankings)?;
    let mut hyps = Vec::new();
    let mut candidates = Vec::new();
    for (i, line) in csv.lines().skip(1).enumerate() {
        let cols: Vec<&str> = line.split(',').collect();
        if cols.len() < 19 {
            continue;
        }
        let condition = cols[1].to_string();
        let payload = serde_json::json!({
            "rank": cols[0].parse::<u32>().unwrap_or(i as u32 + 1),
            "condition": condition,
            "depth": cols[2].parse::<u8>().ok(),
            "train_n": cols[4].parse::<u64>().ok(),
            "val_n": cols[5].parse::<u64>().ok(),
            "test_n": cols[6].parse::<u64>().ok(),
            "train_ev": cols[7].parse::<f64>().ok(),
            "val_ev": cols[8].parse::<f64>().ok(),
            "test_ev": cols[9].parse::<f64>().ok(),
            "train_wr": cols[10].parse::<f64>().ok(),
            "val_wr": cols[11].parse::<f64>().ok(),
            "test_wr": cols[12].parse::<f64>().ok(),
            "test_sharpe": cols[15].parse::<f64>().ok(),
            "test_pnl": cols[16].parse::<f64>().ok(),
            "classification": cols[17],
            "q_value": cols[18].parse::<f64>().ok(),
            "imported": true,
            "search_space": 6128
        });
        if matches!(
            cols[17],
            "CANDIDATE" | "ROBUST" | "CANDIDATE_THIN_VALIDATION"
        ) {
            candidates.push((condition.clone(), cols[17].to_string(), payload.clone()));
        }
        hyps.push((condition, payload));
    }

    let now = Utc::now().to_rfc3339();
    let def = ExperimentDefinition {
        name: "B1 first-exact-83 exhaustive (imported)".into(),
        description: "Imported locked exhaustive search. 6,128 hypotheses. \
TEST locked. Not a production strategy. FDR q values are from the original 6,128-test space."
            .into(),
        tags: vec!["imported".into(), "exhaustive".into(), "first83".into()],
        search_method: "exhaustive_imported".into(),
        ..ExperimentDefinition::default()
    };

    let uncond = modeled_unconditional(paths);

    let rec = ExperimentRecord {
        id: EXHAUSTIVE_ID.into(),
        status: "COMPLETED".into(),
        definition: def,
        created_at: already
            .as_ref()
            .map(|e| e.created_at.clone())
            .unwrap_or_else(|| now.clone()),
        updated_at: now,
        hypothesis_count: summary["candidates_stored"].as_i64().unwrap_or(6128),
        result_summary: Some(serde_json::json!({
            "imported": true,
            "number_of_tests": 6128,
            "unconditional": uncond,
            "primary": locked_primary(),
            "benchmark_40_49": locked_40_49(),
            "fill_status": "TRADE_PRINT_MODELED",
            "summary": summary
        })),
        artifact_dir: Some(paths.first83_dir.display().to_string()),
    };
    if already.is_some() {
        store.update_experiment(&rec)?;
    } else {
        store.insert_experiment(&rec)?;
    }
    store.replace_hypotheses(EXHAUSTIVE_ID, &hyps)?;
    for (cond, status, payload) in candidates.into_iter().take(40) {
        let cid = format!("CAND_{}", cond.replace(['=', '&'], "_"));
        store.upsert_candidate(&cid, EXHAUSTIVE_ID, &cond, &status, &payload)?;
    }
    pin_locked_candidates(store)?;
    Ok(())
}

/// Attach ALL_83 equity to the imported experiment when first83 sqlite exists.
pub fn ensure_imported_equity(
    store: &EngineStore,
    paths: &WorkspacePaths,
    exp: &mut ExperimentRecord,
) -> Result<(), EngineError> {
    if exp.id != EXHAUSTIVE_ID {
        return Ok(());
    }
    let has = exp
        .result_summary
        .as_ref()
        .and_then(|s| s.get("unconditional"))
        .and_then(|u| u.get("equity"))
        .and_then(|e| e.as_array())
        .is_some_and(|a| !a.is_empty());
    if has || !paths.first83_sqlite.exists() {
        return Ok(());
    }
    let uncond = modeled_unconditional(paths);
    if let Some(summary) = exp.result_summary.as_mut() {
        summary["unconditional"] = uncond;
        summary["benchmark_40_49"] = locked_40_49();
        summary["primary"] = locked_primary();
    }
    store.update_experiment(exp)?;
    Ok(())
}
