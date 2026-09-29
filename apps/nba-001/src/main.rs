//! momento-nba-001 — NBA Bot 001 FIRST78_67 worker.
//!
//! `momento-nba-001 [run]`  supervised loop (systemd `momento-nba-001.service`)
//! `momento-nba-001 probe`  one-shot read-only routing/funding evidence (JSON)
//!
//! `momento-nba-001 evidence` one-shot read-only fee/routing/subaccount evidence (JSON)
//! `momento-nba-001 demo-exercise` order lifecycle against the Kalshi demo
//!     environment only (demo credentials; refuses production)
//!
//! Production market data plus signed GET-only account observe. The NBA
//! order adapter is linked for fixture and demo use; production submission
//! is compiled out (`venue::PRODUCTION_ORDERS_COMPILED = false`). This binary
//! cannot place, amend, or cancel production orders, and cannot move funds.

#![forbid(unsafe_code)]
#![recursion_limit = "256"]

mod account;
mod config;
mod controls;
mod demo;
mod engine;
mod epoch_store;
#[cfg(test)]
mod exec_tests;
mod executor;
#[cfg(test)]
mod fake;
mod journal;
mod lane;
#[cfg(test)]
mod lane_tests;
mod lease;
mod public;
#[cfg(test)]
mod tests;
mod venue;

use std::collections::BTreeMap;
use std::env;
use std::path::{Path, PathBuf};
use std::time::Duration;

use momento_kalshi::redact_secrets;
use momento_strategy_nba::ContractStatus;
use serde_json::json;
use sha2::{Digest, Sha256};

use crate::account::Account;
use crate::config::Config;
use crate::engine::{Engine, WorkerState};
use crate::journal::Journal;
use crate::public::Public;

/// The NBA order adapter is linked (fixture + demo). Production submission is
/// a separate compile-time gate: `venue::PRODUCTION_ORDERS_COMPILED`.
pub const SUBMISSION_ADAPTER_LINKED: bool = true;
const _: () = assert!(!venue::PRODUCTION_ORDERS_COMPILED);
/// systemd `RestartPreventExitStatus=78`: stay down on fail-closed exits.
const EXIT_FAIL_CLOSED: i32 = 78;
/// Journal heartbeat line cadence; status.json is written every tick.
const HEARTBEAT_EVERY_TICKS: u64 = 4;

fn sha256_file(path: &Path) -> Option<String> {
    let bytes = std::fs::read(path).ok()?;
    Some(
        Sha256::digest(&bytes)
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect(),
    )
}

fn now_s() -> i64 {
    engine::now_ms() / 1000
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let code = match args.first().map(String::as_str) {
        None | Some("run") => run(),
        Some("probe") => probe(),
        Some("evidence") => evidence(),
        Some("demo-exercise") => demo::exercise(),
        Some("--version") => {
            println!(
                "momento-nba-001 {} build={} submission_adapter_linked={SUBMISSION_ADAPTER_LINKED} production_orders_compiled={}",
                env!("CARGO_PKG_VERSION"),
                option_env!("NBA001_BUILD_ID").unwrap_or("local"),
                venue::PRODUCTION_ORDERS_COMPILED
            );
            Ok(())
        }
        Some(other) => Err((
            2,
            format!(
                "unknown command {other}; expected run, probe, evidence, demo-exercise, --version"
            ),
        )),
    };
    if let Err((exit, msg)) = code {
        eprintln!("momento-nba-001 fatal: {}", redact_secrets(&msg));
        std::process::exit(exit);
    }
}

struct Paths {
    config: PathBuf,
    state_dir: PathBuf,
    secret: Option<PathBuf>,
}

fn paths() -> Paths {
    Paths {
        config: env::var("MOMENTO_NBA_CONFIG")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("config/nba-001.toml")),
        state_dir: env::var("MOMENTO_NBA_STATE_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("data/nba-001")),
        secret: env::var(momento_kalshi::ENV_KALSHI_SECRET_FILE)
            .ok()
            .map(PathBuf::from),
    }
}

fn load_contract(cfg: &Config) -> Result<(ContractStatus, String), (i32, String)> {
    let raw = std::fs::read_to_string(&cfg.contract_path).map_err(|e| {
        (
            EXIT_FAIL_CLOSED,
            format!("contract {}: {e}", cfg.contract_path.display()),
        )
    })?;
    let sha = Sha256::digest(raw.as_bytes())
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect();
    let status =
        ContractStatus::parse(&raw).map_err(|e| (EXIT_FAIL_CLOSED, format!("contract: {e:?}")))?;
    Ok((status, sha))
}

/// Missing state starts empty. Unreadable state is kept aside under a
/// timestamped name and reported; it is never silently overwritten. The
/// worker holds no orders or positions in this state, so a fresh start loses
/// collection history only.
fn load_state(dir: &Path, now: i64) -> Result<(WorkerState, serde_json::Value), (i32, String)> {
    let path = dir.join("state.json");
    let raw = match std::fs::read_to_string(&path) {
        Ok(raw) => raw,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            return Ok((WorkerState::default(), json!({"state": "ABSENT"})));
        }
        Err(e) => return Err((EXIT_FAIL_CLOSED, format!("state.json unreadable: {e}"))),
    };
    match serde_json::from_str::<WorkerState>(&raw) {
        Ok(state) => {
            let v = json!({
                "state": "LOADED",
                "games": state.games.len(),
                "markets": state.markets.len(),
            });
            Ok((state, v))
        }
        Err(e) => {
            let aside = dir.join(format!("state.json.unreadable-{now}"));
            std::fs::rename(&path, &aside).map_err(|re| {
                (
                    EXIT_FAIL_CLOSED,
                    format!("state.json kept aside failed: {re}"),
                )
            })?;
            Ok((
                WorkerState::default(),
                json!({
                    "state": "UNREADABLE_KEPT_ASIDE",
                    "error": e.to_string(),
                    "kept_as": aside.file_name().map(|n| n.to_string_lossy().to_string()),
                }),
            ))
        }
    }
}

fn run() -> Result<(), (i32, String)> {
    let p = paths();
    let cfg = Config::load(&p.config).map_err(|e| (EXIT_FAIL_CLOSED, e))?;
    std::fs::create_dir_all(&p.state_dir)
        .map_err(|e| (EXIT_FAIL_CLOSED, format!("state dir: {e}")))?;
    let _lease = lease::Lease::acquire(&p.state_dir).map_err(|e| (EXIT_FAIL_CLOSED, e))?;
    let (contract, contract_sha256) = load_contract(&cfg)?;
    let (state, state_load) = load_state(&p.state_dir, now_s())?;
    let binary_sha256 = env::current_exe()
        .ok()
        .and_then(|exe| sha256_file(&exe))
        .unwrap_or_else(|| "UNAVAILABLE".into());
    let tick = Duration::from_secs(cfg.tick_seconds);
    let mut engine = Engine {
        account: Account::from_secret_file(p.secret.as_deref()),
        journal: Journal::new(&p.state_dir),
        public: Public::production(),
        state_dir: p.state_dir.clone(),
        contract,
        contract_sha256,
        binary_sha256,
        account_view: Default::default(),
        state,
        series: None,
        events: BTreeMap::new(),
        started_at: now_s(),
        ticks: 0,
        last_discovery_at: None,
        last_discovery_error: None,
        last_account_at: None,
        last_candle_at: None,
        last_clock_at: None,
        controls: Default::default(),
        cfg,
    };
    engine.journal.record(
        engine::now_ms(),
        "WORKER_START",
        None,
        None,
        json!({
            "version": env!("CARGO_PKG_VERSION"),
            "build_id": option_env!("NBA001_BUILD_ID").unwrap_or("local"),
            "binary_sha256": engine.binary_sha256,
            "contract_sha256": engine.contract_sha256,
            "config_mode": engine.cfg.mode,
            "submission_adapter_linked": SUBMISSION_ADAPTER_LINKED,
            "production_orders_compiled": venue::PRODUCTION_ORDERS_COMPILED,
            "account_load_error": engine.account.load_error,
            "state_load": state_load,
        }),
    );
    eprintln!(
        "momento-nba-001 start mode={} contract={} unresolved={} production_orders_compiled=false",
        engine.cfg.mode,
        &engine.contract_sha256[..12],
        engine.contract.unresolved.len()
    );
    loop {
        let now = now_s();
        engine.controls = controls::read_controls(&p.state_dir);
        if engine.controls.emergency_exit {
            engine.journal.record(now * 1000, "EMERGENCY_EXIT_BLOCKED", None, None, json!({
                "reason": "emergency action unresolved; no position held; production submission compiled out",
            }));
        }
        if engine.controls.full_stop {
            engine
                .journal
                .record(now * 1000, "FULL_STOP", None, None, json!({}));
            let _ = engine.persist(now);
            return Err((EXIT_FAIL_CLOSED, "FULL_STOP control set".into()));
        }
        engine.tick(now);
        let status = engine.status_json(now);
        if let Err(e) = engine.persist(now) {
            eprintln!("momento-nba-001 persist_error={}", redact_secrets(&e));
        }
        if engine.ticks % HEARTBEAT_EVERY_TICKS != 1 {
            std::thread::sleep(tick);
            continue;
        }
        let shard = |i: i64| {
            engine
                .account_view
                .shard_cash_cents
                .get(&i)
                .copied()
                .flatten()
                .map_or("UNREAD".to_string(), |c| c.to_string())
        };
        println!(
            "momento-nba-001 heartbeat mode={} games={} feed_age_s={} account_ok={} shard0_cents={} shard3_cents={} blockers={} submits=false production_orders_compiled=false",
            status["mode"].as_str().unwrap_or("?"),
            engine.state.games.len(),
            status["feed"]["feed_age_s"],
            engine.account_view.ok,
            shard(0),
            shard(3),
            status["blockers"].as_object().map_or(0, |b| b.len()),
        );
        std::thread::sleep(tick);
    }
}

fn evidence() -> Result<(), (i32, String)> {
    let p = paths();
    let series_ticker = Config::load(&p.config)
        .map(|c| c.series)
        .unwrap_or_else(|_| "KXNBAGAME".into());
    let mut account = Account::from_secret_file(p.secret.as_deref());
    let mut out = account.evidence(now_s(), &series_ticker);
    out["evidence"] = json!("nba-001 read-only fee/routing/subaccount evidence");
    out["production_orders_compiled"] = json!(venue::PRODUCTION_ORDERS_COMPILED);
    out["funds_moved"] = json!(false);
    println!("{out}");
    Ok(())
}

fn probe() -> Result<(), (i32, String)> {
    let p = paths();
    let now = now_s();
    let mut public = Public::production();
    let series_ticker = Config::load(&p.config)
        .map(|c| c.series)
        .unwrap_or_else(|_| "KXNBAGAME".into());
    let series = public.series(&series_ticker, now);
    let events = public.open_events(&series_ticker, now);
    let mut account = Account::from_secret_file(p.secret.as_deref());
    let view = account.observe(now);
    let routes: Vec<_> = events
        .as_ref()
        .map(|evs| {
            evs.iter()
                .map(|e| {
                    json!({
                        "event_ticker": e.desc.event_ticker,
                        "event_exchange_index": e.event_exchange_index,
                        "mutually_exclusive": e.desc.mutually_exclusive,
                        "markets": e.markets.iter().map(|m| json!({
                            "ticker": m.desc.ticker,
                            "exchange_index": m.desc.exchange_index,
                            "status": m.desc.status,
                        })).collect::<Vec<_>>(),
                    })
                })
                .collect()
        })
        .unwrap_or_default();
    let out = json!({
        "probe": "nba-001 read-only routing evidence",
        "observed_at": now,
        "series": series.as_ref().ok(),
        "series_error": series.as_ref().err(),
        "events": routes,
        "events_error": events.as_ref().err(),
        "account": {
            "ok": view.ok,
            "error": view.error,
            "balance_total_cents": view.balance_total_cents,
            "portfolio_value_cents": view.portfolio_value_cents,
            "balance_breakdown": view.balance_breakdown_raw,
            "shard_cash_cents": view.shard_cash_cents,
            "positions_by_series": view.positions_by_series,
            "resting_orders_by_series": view.resting_orders_by_series,
            "resting_orders_total": view.resting_orders_total,
            "bot_client_orders_found": view.bot_client_orders_found,
            "gets_sent": view.gets_sent,
            "non_get_sent": view.non_get_sent,
        },
        "submission_adapter_linked": SUBMISSION_ADAPTER_LINKED,
        "production_orders_compiled": venue::PRODUCTION_ORDERS_COMPILED,
        "funds_moved": false,
    });
    println!("{out}");
    Ok(())
}
