use crate::error::EngineError;
use crate::paths::WorkspacePaths;
use crate::store::EngineStore;
use crate::types::{DatasetRecord, StrategyRecord};

pub fn seed(store: &EngineStore, paths: &WorkspacePaths) -> Result<(), EngineError> {
    store.upsert_strategy(&StrategyRecord {
        id: "B1".into(),
        version: "B1.ENGINE.1.1.0".into(),
        name: "B1 first-exact-83 research family".into(),
        description: "Observational HOLD_TO_SETTLEMENT on the first exact 83¢ TRADE. \
Not a production strategy. Parameters come from experiment config."
            .into(),
        research_status: "RESEARCH".into(),
        production_status: "NONE".into(),
    })?;

    let sqlite = if paths.first83_sqlite.exists() {
        Some(paths.first83_sqlite.display().to_string())
    } else {
        None
    };
    let universe = if paths.first83_universe.exists() {
        serde_json::from_str::<serde_json::Value>(&std::fs::read_to_string(
            &paths.first83_universe,
        )?)
        .ok()
    } else {
        None
    };
    let games = universe
        .as_ref()
        .and_then(|v| v["unique_games"].as_u64())
        .map(|n| n as i64);

    let mut quality = if let Some(u) = &universe {
        serde_json::json!({
            "w7_games": u["w7_games"],
            "never_printed_83": u["skipped_no_83"],
            "bound_never_83": u["skipped_bound_contract_no_83"],
            "canonical_games": u["unique_games"],
            "unbound_earliest": u["unbound_yes_or_earliest"],
            "fill_status": u["fill_status"],
            "l2_status": "UNAVAILABLE_SOURCE",
            "trade_status": "TRADE_PRINT_MODELED",
            "computed_from": "b1_83_universe.json"
        })
    } else {
        serde_json::json!({
            "status": "UNIVERSE_JSON_MISSING",
            "l2_status": "UNAVAILABLE_SOURCE"
        })
    };
    if let Some(p) = sqlite.as_ref() {
        if let Ok(computed) = crate::quality::first83_quality_from_sqlite(std::path::Path::new(p)) {
            if let (Some(base), Some(extra)) = (quality.as_object_mut(), computed.as_object()) {
                for (k, v) in extra {
                    base.insert(k.clone(), v.clone());
                }
            }
        }
    }

    store.upsert_dataset(&DatasetRecord {
        id: "B1_FIRST83".into(),
        version: "v1".into(),
        name: "B1 first exact 83¢ TRADE".into(),
        event_definition: "First W7 TRADE at exactly 83¢ per game on the W8-bound contract; \
otherwise earliest exact 83¢ TRADE. One snapshot per game."
            .into(),
        source: paths.first83_dir.display().to_string(),
        features_sqlite: sqlite,
        game_count: games,
        capabilities: serde_json::json!({
            "price": true,
            "trade": true,
            "quote": false,
            "l1": false,
            "l2": false,
            "order_events": false,
            "queue": false,
            "game_state": true,
            "timestamps": true,
            "volume": false
        }),
        quality,
        provenance: serde_json::json!({
            "feature_schema_version": universe.as_ref().and_then(|v| v["feature_schema_version"].as_str()),
            "engine_version": universe.as_ref().and_then(|v| v["engine_version"].as_str()),
            "split": {
                "train_before": momento_research_features::TRAIN_BEFORE,
                "val_before": momento_research_features::VAL_BEFORE,
                "test_end_observed": momento_research_features::TEST_END_OBSERVED
            },
            "do_not_overwrite": [
                "Backtesting Suite/Foundation/B1/features.sqlite",
                "Backtesting Suite/Foundation/B1/first83/"
            ]
        }),
        status: "REGISTERED".into(),
    })?;

    store.upsert_model(&serde_json::json!({
        "id": "B1_FIRST83_MODEL_v1",
        "strategy_id": "B1",
        "version": "v1",
        "dataset_id": "B1_FIRST83",
        "dataset_version": "v1",
        "parameters": {
            "note": "No production parameters. β / thresholds live on experiments, not here."
        },
        "health": "UNKNOWN",
        "status": "HYPOTHESIS",
        "calibration_at": null
    }))?;

    let manifest_path = paths.prospective83_dir.join("prospective83_manifest.json");
    let summary_path = paths.prospective83_dir.join("prospective83_summary.json");
    let (quality, provenance, status, games) = if manifest_path.exists() {
        let manifest: serde_json::Value =
            serde_json::from_str(&std::fs::read_to_string(&manifest_path)?)?;
        let summary = if summary_path.exists() {
            serde_json::from_str::<serde_json::Value>(&std::fs::read_to_string(&summary_path)?).ok()
        } else {
            None
        };
        let n = summary
            .as_ref()
            .and_then(|s| s["coverage"]["first83_eligible"].as_u64())
            .map(|n| n as i64);
        (
            serde_json::json!({
                "status": manifest["status"],
                "answer": manifest["answer"],
                "cutoff": manifest["cutoff_locked_test_end"],
                "prospective_start": manifest["prospective_start"],
                "prospective_end": manifest["prospective_end"],
                "fill_status": "TRADE_PRINT_MODELED",
                "l2_status": "UNAVAILABLE_SOURCE",
                "production_count": 0,
                "do_not_retune_on_holdout": true
            }),
            serde_json::json!({
                "research_mode": "B1_FIRST83_PROSPECTIVE/v1",
                "artifact_dir": paths.prospective83_dir,
                "command": "./target/release/momento-research-b1 --validate-83-prospective",
                "layers": ["FROZEN_HISTORICAL_RESULT", "PROSPECTIVE_VALIDATION_RESULT", "POST_HOLDOUT_DISCOVERY"]
            }),
            manifest
                .get("status")
                .and_then(|s| s.as_str())
                .unwrap_or("REGISTERED")
                .to_string(),
            n,
        )
    } else {
        (
            serde_json::json!({
                "status": "AWAITING_HOLDOUT",
                "l2_status": "UNAVAILABLE_SOURCE",
                "fill_status": "TRADE_PRINT_MODELED",
                "production_count": 0
            }),
            serde_json::json!({
                "research_mode": "B1_FIRST83_PROSPECTIVE/v1",
                "cutoff": momento_research_features::TEST_END_OBSERVED,
                "prospective_start": "2026-06-28"
            }),
            "AWAITING_HOLDOUT".into(),
            Some(0),
        )
    };
    store.upsert_dataset(&DatasetRecord {
        id: "B1_FIRST83_PROSPECTIVE".into(),
        version: "v1".into(),
        name: "B1 first-exact-83 prospective holdout".into(),
        event_definition: "Same first-exact-83 TRADE definition as B1_FIRST83/v1, restricted to \
games strictly after the locked TEST cutoff 2026-06-27. Frozen candidates only. \
Does not retune on the holdout."
            .into(),
        source: paths.prospective83_dir.display().to_string(),
        features_sqlite: None,
        game_count: games,
        capabilities: serde_json::json!({
            "price": true,
            "trade": true,
            "quote": false,
            "l1": false,
            "l2": false,
            "order_events": false,
            "queue": false,
            "game_state": true,
            "timestamps": true,
            "volume": false
        }),
        quality,
        provenance,
        status,
    })?;

    Ok(())
}
