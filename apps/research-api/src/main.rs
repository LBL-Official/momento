//! Research API. Internal console only. Does not submit Kalshi orders.

use std::net::SocketAddr;
use std::sync::Arc;
use std::thread;

use axum::extract::{Path, State};
use axum::http::{HeaderMap, HeaderValue, Method, StatusCode};
use axum::response::IntoResponse;
use axum::routing::{get, post};
use axum::{Json, Router};
use momento_research_engine::jobs::JobService;
use momento_research_engine::promote::{allowed_transition, promote};
use momento_research_engine::types::{ExperimentDefinition, LifecycleStatus};
use momento_research_engine::{EngineStore, WorkspacePaths, open_engine};
use momento_research_features::configured_search::{
    estimate_hypothesis_count, prepare_search_rows,
};
use serde::Deserialize;
use tower_http::cors::{AllowOrigin, CorsLayer};
use tracing::{info, warn};

#[derive(Clone)]
struct AppState {
    store: Arc<EngineStore>,
    jobs: Arc<JobService>,
    token: String,
    paths: WorkspacePaths,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("momento_research_api=info".parse().unwrap()),
        )
        .init();

    let paths = WorkspacePaths::detect();
    info!(root = %paths.root.display(), "research engine root");
    let store = Arc::new(open_engine(&paths.root).expect("open engine"));
    let jobs = Arc::new(JobService::new(store.clone(), paths.clone()));
    let token = std::env::var("MOMENTO_RESEARCH_TOKEN").unwrap_or_else(|_| "momento-local".into());
    let bind = std::env::var("MOMENTO_RESEARCH_BIND").unwrap_or_else(|_| "127.0.0.1:8787".into());
    let state = AppState {
        store,
        jobs,
        token,
        paths,
    };

    let cors = CorsLayer::new()
        .allow_origin(AllowOrigin::list([
            "http://127.0.0.1:5173".parse::<HeaderValue>().unwrap(),
            "http://localhost:5173".parse::<HeaderValue>().unwrap(),
        ]))
        .allow_methods([Method::GET, Method::POST, Method::OPTIONS])
        .allow_headers([
            axum::http::header::AUTHORIZATION,
            axum::http::header::CONTENT_TYPE,
            "x-research-token".parse().unwrap(),
        ]);

    let app = Router::new()
        .route("/api/health", get(health))
        .route("/api/system", get(system))
        .route("/api/datasets", get(datasets))
        .route("/api/strategies", get(strategies))
        .route("/api/models", get(models))
        .route("/api/candidates", get(candidates))
        .route("/api/experiments", get(experiments).post(create_experiment))
        .route("/api/experiments/{id}", get(get_experiment))
        .route("/api/experiments/{id}/run", post(run_experiment))
        .route("/api/experiments/{id}/reproduce", post(reproduce))
        .route("/api/experiments/{id}/hypotheses", get(hypotheses))
        .route("/api/experiments/{id}/promote", post(promote_exp))
        .route("/api/experiments/{id}/promotions", get(promotions_for))
        .route("/api/orchestration", get(orchestration))
        .route("/api/jobs", get(jobs_list))
        .route("/api/jobs/{id}", get(get_job))
        .route("/api/jobs/{id}/cancel", post(cancel_job))
        .route("/api/features", get(features))
        .route("/api/parameter-catalog", get(parameter_catalog))
        .route("/api/estimate", post(estimate))
        .route("/api/prospective83", get(prospective83))
        .layer(cors)
        .with_state(state);

    let addr: SocketAddr = bind.parse().expect("bind addr");
    info!(%addr, "research API listening (internal, not public website)");
    let listener = tokio::net::TcpListener::bind(addr).await.expect("bind");
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown())
        .await
        .expect("serve");
}

async fn shutdown() {
    let _ = tokio::signal::ctrl_c().await;
}

fn auth(state: &AppState, headers: &HeaderMap) -> Result<(), (StatusCode, String)> {
    let provided = headers
        .get("x-research-token")
        .and_then(|v| v.to_str().ok())
        .map(str::to_string)
        .or_else(|| {
            headers
                .get(axum::http::header::AUTHORIZATION)
                .and_then(|v| v.to_str().ok())
                .and_then(|v| v.strip_prefix("Bearer "))
                .map(str::to_string)
        });
    if provided.as_deref() == Some(state.token.as_str()) {
        Ok(())
    } else {
        Err((StatusCode::UNAUTHORIZED, "unauthorized".into()))
    }
}

async fn health() -> impl IntoResponse {
    Json(serde_json::json!({
        "ok": true,
        "service": "momento-research-api",
        "fill_status": "TRADE_PRINT_MODELED",
        "production": 0
    }))
}

async fn system(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    Ok(Json(serde_json::json!({
        "root": state.paths.root,
        "first83_sqlite": state.paths.first83_sqlite.exists(),
        "first83_dir": state.paths.first83_dir,
        "engine_sqlite": state.paths.engine_sqlite,
        "fill_status": "TRADE_PRINT_MODELED",
        "l2": "UNAVAILABLE_SOURCE",
        "live_trading": false,
        "public_website": false,
        "auth": "bearer / x-research-token",
        "official_split": {
            "train_before": momento_research_features::TRAIN_BEFORE,
            "val_before": momento_research_features::VAL_BEFORE,
            "test_end_observed": momento_research_features::TEST_END_OBSERVED
        },
        "research_modes": ["B1_FIRST83/v1", "B1_FIRST83_PROSPECTIVE/v1"],
        "prospective83_dir": state.paths.prospective83_dir,
        "prospective83_artifacts": state.paths.prospective83_dir.join("prospective83_summary.json").exists()
    })))
}

async fn datasets(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    state
        .store
        .list_datasets()
        .map(Json)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

async fn strategies(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    state
        .store
        .list_strategies()
        .map(Json)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

async fn models(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    state
        .store
        .list_models()
        .map(Json)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

async fn candidates(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    state
        .store
        .list_candidates()
        .map(Json)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

async fn experiments(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    state
        .store
        .list_experiments()
        .map(Json)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

async fn create_experiment(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(def): Json<ExperimentDefinition>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    warn_test_lock(&def);
    state
        .jobs
        .create_experiment(def)
        .map(Json)
        .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))
}

async fn get_experiment(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    let mut exp = state
        .store
        .get_experiment(&id)
        .map_err(|e| (StatusCode::NOT_FOUND, e.to_string()))?;
    momento_research_engine::import::ensure_imported_equity(&state.store, &state.paths, &mut exp)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    Ok(Json(exp))
}

async fn promotions_for(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    state
        .store
        .list_promotions_for(&id)
        .map(Json)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

async fn orchestration(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    Ok(Json(
        momento_research_engine::orchestration::orchestration_snapshot(),
    ))
}

async fn run_experiment(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    let job = state
        .jobs
        .queue_run(&id)
        .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;
    let jobs = state.jobs.clone();
    let jid = job.id.clone();
    thread::spawn(move || {
        if let Err(e) = jobs.execute_job(&jid) {
            warn!(error = %e, "job failed");
        }
    });
    Ok(Json(job))
}

async fn reproduce(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    state
        .jobs
        .reproduce(&id)
        .map(Json)
        .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))
}

async fn hypotheses(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    state
        .store
        .list_hypotheses(&id)
        .map(Json)
        .map_err(|e| (StatusCode::NOT_FOUND, e.to_string()))
}

#[derive(Deserialize)]
struct PromoteBody {
    to: String,
    reason: String,
}

async fn promote_exp(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
    Json(body): Json<PromoteBody>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    let to = LifecycleStatus::parse(&body.to)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "unknown status".into()))?;
    if body.to == "PRODUCTION" {
        let exp = state
            .store
            .get_experiment(&id)
            .map_err(|e| (StatusCode::NOT_FOUND, e.to_string()))?;
        if let Some(from) = LifecycleStatus::parse(&exp.status) {
            if !allowed_transition(from, to) {
                return Err((
                    StatusCode::FORBIDDEN,
                    format!("cannot promote {} → PRODUCTION", exp.status),
                ));
            }
        }
    }
    promote(&state.store, &id, to, &body.reason, "console")
        .map(Json)
        .map_err(|e| (StatusCode::FORBIDDEN, e.to_string()))
}

async fn jobs_list(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    state
        .store
        .list_jobs()
        .map(Json)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

async fn cancel_job(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    state
        .jobs
        .request_cancel(&id)
        .map(Json)
        .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))
}

async fn parameter_catalog(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    Ok(Json(
        momento_research_engine::strategy::b1_parameter_catalog(),
    ))
}

async fn get_job(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    state
        .store
        .get_job(&id)
        .map(Json)
        .map_err(|e| (StatusCode::NOT_FOUND, e.to_string()))
}

async fn features(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    if !state.paths.first83_sqlite.exists() {
        return Ok(Json(serde_json::json!({
            "available": false,
            "reason": "first83 features.sqlite missing"
        })));
    }
    let (_, _, _, _, values) = prepare_search_rows(
        &state.paths.first83_sqlite,
        momento_research_features::TRAIN_BEFORE,
        momento_research_features::VAL_BEFORE,
    )
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    Ok(Json(serde_json::json!({
        "available": true,
        "values": values
    })))
}

#[derive(Deserialize)]
struct EstimateBody {
    parameters: Vec<momento_research_features::ParameterSpec>,
}

async fn estimate(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<EstimateBody>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    Ok(Json(serde_json::json!({
        "hypotheses": estimate_hypothesis_count(&body.parameters),
        "includes_unconditional": true
    })))
}

async fn prospective83(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    auth(&state, &headers)?;
    let args = momento_research_features::ProspectiveArgs::defaults(&state.paths.root);
    let engine_path = state
        .paths
        .prospective83_dir
        .join("b1_83_prospective_engine.json");
    let engine = if engine_path.exists() {
        serde_json::from_str(
            &std::fs::read_to_string(&engine_path)
                .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?,
        )
        .ok()
    } else {
        None
    };
    let envelope = momento_research_features::prospective83_api_envelope(&args, engine.as_ref())
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let summary =
        momento_research_features::load_prospective_summary(&state.paths.prospective83_dir)
            .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    Ok(Json(serde_json::json!({
        "engine_version": envelope["engine_version"],
        "universe": "B1_FIRST83/v1",
        "entry_definition": "FIRST_EXACT_83",
        "target": "HOLD_TO_SETTLEMENT",
        "status": envelope["status"],
        "reason": envelope["reason"],
        "historical_cutoff": envelope["historical_cutoff"],
        "candidate": envelope["candidate"],
        "prospective": envelope["prospective"],
        "requirements": envelope["requirements"],
        "provenance": envelope["provenance"],
        "research_mode": "B1_FIRST83_PROSPECTIVE/v1",
        "layers": {
            "FROZEN_HISTORICAL_RESULT": "locked TRAIN/VAL/TEST; do not retune",
            "PROSPECTIVE_VALIDATION_RESULT": envelope["status"],
            "POST_HOLDOUT_DISCOVERY": "not run"
        },
        "frozen_candidates": envelope["frozen_candidates"],
        "summary": summary,
        "engine": envelope["engine"],
        "reproducibility": "./target/release/momento-research-b1 --prospective-83",
        "production_count": 0,
        "fill_status": "TRADE_PRINT_MODELED",
        "l2_status": "UNAVAILABLE_SOURCE"
    })))
}

fn warn_test_lock(def: &ExperimentDefinition) {
    if def.train_before >= def.val_before {
        warn!("invalid split: train_before >= val_before");
    }
}
