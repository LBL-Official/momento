//! Supervised FIRST78 Live V1 loop. Production orders stay compiled out.

use std::collections::VecDeque;
use std::path::Path;
use std::time::Duration;

use momento_strategy_nba::live_v1::{Action, Engine, Input, Mapping, Policy, Sport};
use momento_strategy_nba::p5::Manifest;
use momento_strategy_nba::portfolio_v1::{Incident, Priority};
use momento_strategy_nba::sizing_epoch::SizingEpochs;
use serde::Serialize;
use sha2::{Digest, Sha256};

use crate::config::Config;
use crate::journal::write_json_atomic;
use crate::lease::Lease;
use crate::ledger::Ledger;
use crate::public::Public;
use crate::recon::Reconciler;
use crate::v1::alerts::{Alert, AlertOutbox};
use crate::v1::discovery::pair_from_event;
use crate::v1::outbox::OrderOutbox;
use crate::venue;

const INGEST_CAP: usize = 4096;
const ORDER_CAP: usize = 1024;
const TELEMETRY_CAP: usize = 1024;

#[derive(Clone, Debug, Serialize)]
pub struct ControlRoom {
    pub mode: &'static str,
    pub production_orders_compiled: bool,
    pub armed: bool,
    pub executing: bool,
    pub policy_hash: String,
    pub config_hash: String,
    pub account: serde_json::Value,
    pub authority: serde_json::Value,
    pub epochs: serde_json::Value,
    pub p5: serde_json::Value,
    pub drevo: &'static str,
    pub positman: &'static str,
    pub discovery: serde_json::Value,
    pub ingest_queue: usize,
    pub outbox_len: usize,
    pub alerts_pending: usize,
    pub backpressure: Option<String>,
    pub fractional_fills: &'static str,
}

pub fn run_supervised(cfg: &Config, state_dir: &Path, secret: Option<&Path>) -> Result<(), String> {
    if venue::PRODUCTION_ORDERS_COMPILED {
        return Err("V1_REFUSES_COMPILED_PRODUCTION_UNTIL_GATES".into());
    }
    let policy = load_policy(&cfg.contract_path)?;
    if policy.emergency_floor_cents.is_some() {
        return Err("PRODUCTION_POLICY_MUST_LEAVE_EMERGENCY_FLOOR_UNRESOLVED".into());
    }
    let policy_hash = hex(&serde_json::to_vec(&policy).map_err(|e| e.to_string())?);
    let config_hash = hex(&std::fs::read(
        std::env::var("MOMENTO_NBA_CONFIG")
            .map(std::path::PathBuf::from)
            .unwrap_or_else(|_| std::path::PathBuf::from("config/nba-001.toml")),
    )
    .unwrap_or_default());
    let _lease = Lease::acquire(state_dir)?;
    // V1 never reads Config.capital / FIRST78_67 reference bankrolls.
    let _ = &cfg.capital;
    let mut engine = Engine::new(policy, 0)?;
    restore_epochs(&mut engine, state_dir);
    let mut public = Public::production();
    let mappings = load_explicit_mappings(state_dir);
    let mut exec = Ledger::open(state_dir, "execution.jsonl")?;
    let mut port = Ledger::open(state_dir, "portfolio.jsonl")?;
    let mut dev = Ledger::open(state_dir, "development.jsonl")?;
    let mut outbox = OrderOutbox::open(&state_dir.join("outbox"), ORDER_CAP)?;
    let mut alerts = AlertOutbox::open(&state_dir.join("alerts"), TELEMETRY_CAP)?;
    let mut recon = Reconciler::from_secret_file(secret);
    let p5 = load_p5(state_dir);
    let mut ingest: VecDeque<Input> = VecDeque::new();
    let mut ticks = 0u64;
    let tick = Duration::from_secs(cfg.tick_seconds.max(5));
    loop {
        ticks += 1;
        let now = crate::engine::now_ms();
        if ingest.len() >= INGEST_CAP {
            engine
                .authority
                .raise(Incident {
                    id: "ingest-backpressure".into(),
                    priority: Priority::P1,
                    state: momento_strategy_nba::portfolio_v1::PortfolioState::NoNewEntries,
                    evidence_id: format!("q={}", ingest.len()),
                    first_seen_ms: now,
                })
                .ok();
            alerts
                .raise(Alert {
                    id: "ingest-backpressure".into(),
                    at_ms: now,
                    priority: Priority::P1,
                    reason: "INGEST_BACKPRESSURE".into(),
                    evidence_id: format!("q={}", ingest.len()),
                    delivered: false,
                    retries: 0,
                })
                .ok();
        }
        if ticks == 1 || ticks % 4 == 0 {
            let report = recon.reconcile(now, format!("recon-{now}"));
            if let Some(snap) = report.snapshot.clone() {
                if let Ok(eq) = snap.equity() {
                    let equity_cents = u64::try_from(eq / 100).unwrap_or(0);
                    ingest.push_back(Input::Account {
                        clean: report.ok,
                        cash_centicents: snap.cash,
                        equity_cents,
                        snapshot_id: snap.id.clone(),
                        observed_ms: snap.observed_ms,
                    });
                }
            } else {
                ingest.push_back(Input::Account {
                    clean: false,
                    cash_centicents: 0,
                    equity_cents: 0,
                    snapshot_id: String::new(),
                    observed_ms: now,
                });
            }
            port.append(
                now,
                "ACCOUNT_RECON",
                serde_json::to_value(&report).unwrap_or_default(),
                &policy_hash,
                &config_hash,
                "nba-001",
            )?;
        }
        if ticks == 1 || ticks % 20 == 0 {
            let discovered = discover_and_register(
                &mut public,
                &mut engine,
                &cfg.series,
                &mappings,
                &p5,
                now,
                &mut ingest,
            );
            dev.append(
                now,
                "V1_DISCOVERY",
                discovered,
                &policy_hash,
                &config_hash,
                "nba-001",
            )?;
        }
        ingest.push_back(Input::Tick);
        while let Some(input) = ingest.pop_front() {
            let actions = engine.apply(now, input)?;
            persist_epochs(&engine, state_dir)?;
            for action in actions {
                exec.append(
                    now,
                    "V1_ACTION",
                    serde_json::to_value(&action).unwrap_or_default(),
                    &policy_hash,
                    &config_hash,
                    "nba-001",
                )?;
                match &action {
                    Action::Submit { order, .. } => {
                        let blocked = outbox.dispatch_blocked(order);
                        outbox.enqueue(now, action.clone())?;
                        let _ = blocked;
                    }
                    Action::Cancel { .. } | Action::Block { .. } => {
                        outbox.enqueue(now, action)?;
                    }
                    _ => {}
                }
            }
        }
        let room = ControlRoom {
            mode: "FIRST78_LIVE_V1_SHADOW",
            production_orders_compiled: venue::PRODUCTION_ORDERS_COMPILED,
            armed: false,
            executing: false,
            policy_hash: policy_hash.clone(),
            config_hash: config_hash.clone(),
            account: serde_json::json!({
                "clean": engine.account_clean,
                "cash_centicents": engine.account_cash_centicents,
                "epochs": engine.epochs.is_some(),
            }),
            authority: serde_json::to_value(&engine.authority).unwrap_or_default(),
            epochs: serde_json::to_value(&engine.epochs).unwrap_or_default(),
            p5: serde_json::to_value(&p5).unwrap_or_default(),
            drevo: "UNAVAILABLE",
            positman: "UNAVAILABLE",
            discovery: serde_json::json!({
                "explicit_mappings": mappings.len(),
                "name_join": "REFUSED",
            }),
            ingest_queue: ingest.len(),
            fractional_fills: "FRACTIONAL_FILLS_UNSUPPORTED",
            outbox_len: outbox.len(),
            alerts_pending: alerts.pending(),
            backpressure: None,
        };
        let room_v = serde_json::to_value(&room).map_err(|e| e.to_string())?;
        write_json_atomic(&state_dir.join("v1_control_room.json"), &room_v)?;
        if ticks == 1 {
            dev.append(
                now,
                "V1_SUPERVISOR_START",
                serde_json::json!({"production_orders_compiled": false}),
                &policy_hash,
                &config_hash,
                "nba-001",
            )?;
        }
        if std::env::var("MOMENTO_NBA_V1_ONCE").ok().as_deref() == Some("1") {
            return Ok(());
        }
        std::thread::sleep(tick);
    }
}

fn load_policy(path: &Path) -> Result<Policy, String> {
    let raw = std::fs::read(path).map_err(|e| e.to_string())?;
    let v: serde_json::Value = serde_json::from_slice(&raw).map_err(|e| e.to_string())?;
    if let Some(p) = v.get("v1_runtime_policy") {
        return serde_json::from_value(p.clone()).map_err(|e| e.to_string());
    }
    Err("V1_RUNTIME_POLICY_MISSING".into())
}

fn load_p5(state_dir: &Path) -> serde_json::Value {
    let candidates = [
        state_dir.join("p5_membership_2026_27.json"),
        Path::new("research/vital/bots/nba-001/ncaab/p5_membership_2026_27.json").to_path_buf(),
    ];
    for p in candidates {
        if let Ok(raw) = std::fs::read_to_string(&p) {
            return match Manifest::parse(&raw) {
                Ok(m) => match m.validate() {
                    Ok(()) => {
                        serde_json::json!({"status":"VERIFIED","path":p.display().to_string()})
                    }
                    Err(e) => {
                        serde_json::json!({"status":format!("{e:?}"),"path":p.display().to_string()})
                    }
                },
                Err(e) => serde_json::json!({"status":"PARSE_ERROR","error":e}),
            };
        }
    }
    serde_json::json!({"status":"EVIDENCE_INCOMPLETE"})
}

fn restore_epochs(engine: &mut Engine, state_dir: &Path) {
    let path = state_dir.join("sizing_epochs.json");
    let Ok(bytes) = std::fs::read(&path) else {
        return;
    };
    let Ok(state) = serde_json::from_slice::<SizingEpochs>(&bytes) else {
        return;
    };
    if state.validate().is_ok() {
        engine.epochs = Some(state);
    }
}

fn persist_epochs(engine: &Engine, state_dir: &Path) -> Result<(), String> {
    let Some(epochs) = engine.epochs.as_ref() else {
        return Ok(());
    };
    let value = serde_json::to_value(epochs).map_err(|e| e.to_string())?;
    write_json_atomic(&state_dir.join("sizing_epochs.json"), &value)
}

#[derive(Clone, Debug, serde::Deserialize)]
struct ExplicitMapping {
    event_id: String,
    sport: String,
    espn_event_id: String,
    espn_team_ids: [String; 2],
    season: String,
}

fn load_explicit_mappings(state_dir: &Path) -> Vec<ExplicitMapping> {
    let candidates = [
        state_dir.join("espn_mappings.json"),
        Path::new("research/vital/bots/nba-001/strategy/espn_mappings.json").to_path_buf(),
    ];
    for p in candidates {
        if let Ok(raw) = std::fs::read_to_string(&p)
            && let Ok(rows) = serde_json::from_str::<Vec<ExplicitMapping>>(&raw)
        {
            return rows
                .into_iter()
                .filter(|m| {
                    !m.event_id.is_empty()
                        && !m.espn_event_id.is_empty()
                        && m.espn_team_ids[0] != m.espn_team_ids[1]
                })
                .collect();
        }
    }
    Vec::new()
}

fn discover_and_register(
    public: &mut Public,
    engine: &Engine,
    series: &str,
    mappings: &[ExplicitMapping],
    p5: &serde_json::Value,
    now: i64,
    ingest: &mut VecDeque<Input>,
) -> serde_json::Value {
    let now_s = now / 1000;
    let events = match public.open_events(series, now_s) {
        Ok(v) => v,
        Err(e) => {
            return serde_json::json!({
                "availability": "UNAVAILABLE",
                "series": series,
                "error": e,
            });
        }
    };
    let p5_verified = p5.get("status").and_then(|s| s.as_str()) == Some("VERIFIED");
    let mut accepted = 0u32;
    let mut refused = 0u32;
    for ev in &events {
        let payload = serde_json::json!({
            "event_ticker": ev.desc.event_ticker,
            "mutually_exclusive": ev.desc.mutually_exclusive.unwrap_or(false),
            "markets": ev.markets.iter().map(|m| serde_json::json!({
                "ticker": m.desc.ticker,
                "exchange_index": m.desc.exchange_index,
            })).collect::<Vec<_>>(),
        });
        let Ok(pair) = pair_from_event(&payload) else {
            refused += 1;
            continue;
        };
        if !pair.complement_ok {
            refused += 1;
            continue;
        }
        let Some(map) = mappings.iter().find(|m| m.event_id == pair.event_ticker) else {
            refused += 1;
            continue;
        };
        if engine.games.contains_key(&pair.event_ticker) {
            continue;
        }
        let sport = match map.sport.as_str() {
            "NBA" => Sport::NBA,
            "NCAAB" => Sport::NCAAB,
            _ => {
                refused += 1;
                continue;
            }
        };
        let both_p5 = sport == Sport::NCAAB && p5_verified;
        if sport == Sport::NCAAB && !both_p5 {
            refused += 1;
            continue;
        }
        ingest.push_back(Input::Register {
            mapping: Mapping {
                event_id: pair.event_ticker,
                sport,
                tickers: pair.tickers,
                espn_event_id: map.espn_event_id.clone(),
                espn_team_ids: map.espn_team_ids.clone(),
                season: map.season.clone(),
                membership_evidence: if both_p5 {
                    Some("p5_membership_2026_27".into())
                } else {
                    None
                },
                both_p5,
                complement_evidence: "kalshi_mutually_exclusive_two_market_same_route".into(),
            },
        });
        accepted += 1;
    }
    serde_json::json!({
        "availability": "OBSERVED",
        "series": series,
        "events": events.len(),
        "accepted": accepted,
        "refused_without_explicit_espn_or_complement": refused,
        "name_similarity_join": false,
    })
}

fn hex(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}
