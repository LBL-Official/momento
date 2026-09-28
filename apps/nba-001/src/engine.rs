//! Worker state and one tick. Collects production data, detects FIRST78_67
//! signals, evaluates admission, and runs the SHADOW hedge path. The order
//! adapter is linked for fixture and demo use only; production submission is
//! compiled out, so this worker never submits.

use std::collections::BTreeMap;
use std::path::PathBuf;

use chrono::DateTime;
use momento_core::{Bps, Contracts, Money, Price};
use momento_strategy_nba::{
    ALLOCATION_BPS, AdmissionDecision, AdmissionInput, BalancePrecision, Blocker, ClockHistory,
    CollateralPool, ComplementPair, ContractStatus, CrossOutcome, CrossTracker, ENTRY_CENTS,
    EntryReserve, EntrySignal, EquityLedger, FeeModel, FeeType, HedgeAction, HedgePlanner,
    LADDER_CAP_CENTS, Lifecycle, LifecycleEvent, Liquidity, MinuteBar, ModeInputs, ReserveError,
    Route, SHARED_SLOTS, StopEvent, StopTracker, bucket_for, capacity_positions,
    contracts_for_reference, derive_mode, evaluate_admission, multiplier_milli, reserve_for_entry,
    route_for_pair, top_out_at_signal, verify_complement,
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

use crate::account::{Account, AccountView};
use crate::config::Config;
use crate::controls::Controls;
use crate::journal::{Journal, write_json_atomic};
use crate::public::{CANDLE_CHUNK_S, EventView, Public, SeriesInfo};

pub const SHADOW_LABEL: &str = "SHADOW_NOT_A_FILL";
/// Analytical modules. They emit no approval and no probability.
pub const PLACEHOLDERS: [&str; 7] = [
    "Ontologic",
    "TK Ultra",
    "Ball Hog",
    "Choosin Texas",
    "Austin",
    "Positman",
    "Drevo",
];
/// A bar is closed once its end is this many seconds in the past.
const BAR_SETTLE_S: i64 = 5;
const GAME_HORIZON_S: i64 = 5 * 3600;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MarketTrack {
    pub ticker: String,
    pub event_ticker: String,
    pub team: Option<String>,
    pub open_time: Option<String>,
    pub cross: CrossTracker,
    pub backfilled: bool,
    pub last_bar: Option<MinuteBar>,
    pub bars_seen: u64,
    pub last_fetch_at: Option<i64>,
    pub last_fetch_error: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exclusion {
    pub ticker: String,
    pub reason: String,
    pub signal_ts: Option<i64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CandidateRecord {
    pub ticker: String,
    pub opponent: Option<String>,
    pub signal: EntrySignal,
    pub bucket: String,
    pub detected_at: i64,
    pub decision_latency_s: i64,
    pub client_order_id: String,
    pub qty: Option<u32>,
    pub reserve: Option<EntryReserve>,
    pub reserve_error: Option<String>,
    pub route: Route,
    pub pair: Result<ComplementPair, String>,
    pub decision: AdmissionDecision,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ShadowPath {
    pub label: String,
    pub ticker: String,
    pub opponent: Option<String>,
    pub qty: u32,
    pub stop: StopTracker,
    pub planner: HedgePlanner,
    pub events: Vec<Value>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GameTrack {
    pub event_ticker: String,
    pub title: Option<String>,
    pub milestone_id: Option<String>,
    pub milestone_checked_at: Option<i64>,
    pub start: Option<String>,
    #[serde(default)]
    pub clock: ClockHistory,
    pub candidate: Option<CandidateRecord>,
    #[serde(default)]
    pub exclusions: Vec<Exclusion>,
    pub lifecycle: Option<Lifecycle>,
    pub shadow: Option<ShadowPath>,
    pub last_seen_open_at: i64,
}

impl GameTrack {
    fn start_ts(&self) -> Option<i64> {
        self.start
            .as_deref()
            .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
            .map(|d| d.timestamp())
    }

    fn clock_live(&self) -> bool {
        self.clock
            .latest()
            .is_some_and(|c| matches!(c.status.as_str(), "inprogress" | "halftime"))
    }

    fn clock_final(&self) -> bool {
        self.clock
            .latest()
            .is_some_and(|c| matches!(c.status.as_str(), "closed" | "complete" | "completed"))
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct WorkerState {
    pub markets: BTreeMap<String, MarketTrack>,
    pub games: BTreeMap<String, GameTrack>,
    /// v2 equity ledger. The v1 `batch` key in older state files is ignored.
    #[serde(default)]
    pub equity: EquityLedger,
}

pub struct Engine {
    pub cfg: Config,
    pub state_dir: PathBuf,
    pub contract: ContractStatus,
    pub contract_sha256: String,
    pub binary_sha256: String,
    pub public: Public,
    pub account: Account,
    pub account_view: AccountView,
    pub journal: Journal,
    pub state: WorkerState,
    pub series: Option<SeriesInfo>,
    pub events: BTreeMap<String, EventView>,
    pub started_at: i64,
    pub ticks: u64,
    pub last_discovery_at: Option<i64>,
    pub last_discovery_error: Option<String>,
    pub last_account_at: Option<i64>,
    pub last_candle_at: Option<i64>,
    pub last_clock_at: Option<i64>,
    pub controls: Controls,
}

/// The configuration the account evidence verified: `quadratic_with_maker_fees`
/// at multiplier 1. Anything else, or an unread series, is unverified.
pub fn fees_verified_for(contract_verified: bool, model: Option<FeeModel>) -> bool {
    contract_verified
        && model.is_some_and(|m| {
            m.fee_type == FeeType::QuadraticWithMakerFees && m.multiplier_milli == 1000
        })
}

pub fn now_ms() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| i64::try_from(d.as_millis()).unwrap_or(i64::MAX))
}

pub fn client_order_id(game: &str, ticker: &str, signal_ts: i64) -> String {
    use sha2::{Digest, Sha256};
    let digest = Sha256::digest(format!("nba-001|{game}|{ticker}|{signal_ts}").as_bytes());
    let hex: String = digest.iter().take(8).map(|b| format!("{b:02x}")).collect();
    format!("{}{hex}", crate::account::CLIENT_ID_PREFIX)
}

impl Engine {
    /// Series fee model. Reservations round to whole cents (the upper bound
    /// for either balance precision).
    pub fn fee_model(&self) -> Option<FeeModel> {
        let series = self.series.as_ref()?;
        let milli = multiplier_milli(&series.fee_multiplier_raw)?;
        let fee_type = FeeType::parse(series.fee_type.as_deref()?)?;
        Some(FeeModel::new(fee_type, milli, BalancePrecision::Cent))
    }

    /// Account fills verified the rule for `quadratic_with_maker_fees` at
    /// multiplier 1 only (FEES.md §5). KXMLBGAME publishes 0.5 but was charged
    /// at 1, so a published multiplier other than 1 is not taken as verified.
    pub fn fees_verified(&self) -> bool {
        fees_verified_for(self.contract.fees_verified, self.fee_model())
    }

    pub fn entry_liquidity(&self) -> Liquidity {
        if self.contract.entry_post_only {
            Liquidity::Maker
        } else {
            Liquidity::Taker
        }
    }

    pub fn production_permit(&self, now: i64) -> Result<(), String> {
        let collateral_ok = matches!(
            self.collateral_pool(),
            CollateralPool::VerifiedIsolation { .. }
                | CollateralPool::AtomicAccountReservations { .. }
        );
        let _ = now;
        crate::venue::production_permit(
            &self.contract.unresolved,
            self.contract.production_submission_enabled,
            self.fees_verified(),
            self.cfg.live_gates_set(),
            collateral_ok,
        )
        .map(|_| ())
        .map_err(|why| why.join(","))
    }

    pub fn standard_qty(&self) -> Option<Contracts> {
        contracts_for_reference(
            self.state.equity.reference_equity(),
            Bps::from_bps(ALLOCATION_BPS),
            Price::from_cents(ENTRY_CENTS).ok()?,
        )
    }

    pub fn standard_reserve(&self) -> Result<EntryReserve, ReserveError> {
        let qty = self.standard_qty().ok_or(ReserveError::InputUnread)?;
        let fees = self.fee_model().ok_or(ReserveError::InputUnread)?;
        let entry = Price::from_cents(ENTRY_CENTS).map_err(|_| ReserveError::InvalidPrice)?;
        let cap = Price::from_cents(LADDER_CAP_CENTS).map_err(|_| ReserveError::InvalidPrice)?;
        reserve_for_entry(
            qty,
            entry,
            self.entry_liquidity(),
            cap,
            self.contract.emergency,
            &fees,
        )
    }

    fn collateral_pool(&self) -> CollateralPool {
        let c = &self.cfg.collateral;
        if !c.isolation_evidence.trim().is_empty() {
            return CollateralPool::VerifiedIsolation {
                evidence: c.isolation_evidence.clone(),
            };
        }
        if !c.reservation_ledger.trim().is_empty() {
            return CollateralPool::AtomicAccountReservations {
                ledger: c.reservation_ledger.clone(),
            };
        }
        let mut others = c.shared_credential_submitters.clone();
        for (series, n) in &self.account_view.resting_orders_by_series {
            if series != &self.cfg.series {
                others.push(format!("resting:{series}={n}"));
            }
        }
        if others.is_empty() && !self.account_view.ok {
            return CollateralPool::Unknown;
        }
        CollateralPool::SharedUnaccounted {
            other_submitters: others,
        }
    }

    fn account_fresh(&self, now: i64) -> bool {
        self.account_view.ok
            && self
                .account_view
                .read_at
                .is_some_and(|t| now - t <= 3 * self.cfg.account_seconds)
    }

    pub fn reconciliation_healthy(&self, now: i64) -> bool {
        self.account_fresh(now)
            && self.account_view.bot_client_orders_found == 0
            && !self.account_view.non_get_sent
    }

    fn outstanding_reserved(&self) -> Money {
        let cents: i64 = self
            .state
            .games
            .values()
            .filter(|g| g.lifecycle.as_ref().is_some_and(Lifecycle::holds_slot))
            .filter_map(|g| {
                g.candidate
                    .as_ref()
                    .and_then(|c| c.reserve.map(|r| r.total.cents()))
            })
            .sum();
        Money::from_cents(cents)
    }

    fn open_slots(&self) -> u32 {
        let n = self
            .state
            .games
            .values()
            .filter(|g| g.lifecycle.as_ref().is_some_and(Lifecycle::holds_slot))
            .count();
        u32::try_from(n).unwrap_or(u32::MAX)
    }

    fn cash_on(&self, index: Option<i64>, now: i64) -> Option<Money> {
        if !self.account_fresh(now) {
            return None;
        }
        let idx = index?;
        self.account_view
            .shard_cash_cents
            .get(&idx)
            .copied()
            .flatten()
            .map(Money::from_cents)
    }

    fn route_and_pair(&self, event: &str, ticker: &str) -> (Route, Result<ComplementPair, String>) {
        let Some(ev) = self.events.get(event) else {
            return (Route::Unread, Err("event not in discovery".into()));
        };
        let series_index = self.series.as_ref().and_then(|s| s.exchange_index);
        let idx: Vec<Option<i64>> = ev.markets.iter().map(|m| m.desc.exchange_index).collect();
        let route = route_for_pair(
            series_index,
            idx.first().copied().flatten(),
            idx.get(1).copied().flatten(),
        );
        let descs: Vec<_> = ev.markets.iter().map(|m| m.desc.clone()).collect();
        (route, verify_complement(&ev.desc, &descs, ticker))
    }

    pub fn admission_for(
        &self,
        event: &str,
        ticker: &str,
        now: i64,
    ) -> (AdmissionInput, AdmissionDecision) {
        let (route, pair) = self.route_and_pair(event, ticker);
        let reserve = self.standard_reserve();
        let input = AdmissionInput {
            unresolved_fields: self.contract.unresolved.clone(),
            fees_verified: self.fees_verified(),
            available_cash: self.cash_on(route.market_index(), now),
            route,
            pair: pair.map(|_| ()),
            reserve,
            collateral: self.collateral_pool(),
            outstanding_reserved: self.outstanding_reserved(),
            open_slots: self.open_slots(),
            max_slots: SHARED_SLOTS,
            live_gates_set: self.cfg.live_gates_set(),
            production_permit: self.production_permit(now),
            reconciliation_healthy: self.reconciliation_healthy(now),
            paused: self.controls.pause_entries,
            batch_number: self.state.equity.current().number,
            batch_resize_approved: self.contract.batch_resize_approved,
        };
        let decision = evaluate_admission(&input);
        (input, decision)
    }

    // ---- data collection ----

    pub fn discover(&mut self, now: i64) {
        self.last_discovery_at = Some(now);
        match self.public.series(&self.cfg.series.clone(), now) {
            Ok(s) => {
                if self.series.as_ref().map(|p| p.exchange_index) != Some(s.exchange_index) {
                    self.journal
                        .record(now_ms(), "SERIES_ROUTE", None, None, json!(s));
                }
                self.series = Some(s);
            }
            Err(e) => self.last_discovery_error = Some(e),
        }
        let events = match self.public.open_events(&self.cfg.series.clone(), now) {
            Ok(ev) => ev,
            Err(e) => {
                self.last_discovery_error = Some(e);
                return;
            }
        };
        self.last_discovery_error = None;
        let mut fresh = BTreeMap::new();
        for ev in events {
            let key = ev.desc.event_ticker.clone();
            let game = self
                .state
                .games
                .entry(key.clone())
                .or_insert_with(|| GameTrack {
                    event_ticker: key.clone(),
                    title: ev.title.clone(),
                    milestone_id: None,
                    milestone_checked_at: None,
                    start: None,
                    clock: ClockHistory::default(),
                    candidate: None,
                    exclusions: Vec::new(),
                    lifecycle: None,
                    shadow: None,
                    last_seen_open_at: now,
                });
            game.last_seen_open_at = now;
            for m in &ev.markets {
                let entry = self
                    .state
                    .markets
                    .entry(m.desc.ticker.clone())
                    .or_insert_with(|| MarketTrack {
                        ticker: m.desc.ticker.clone(),
                        event_ticker: key.clone(),
                        team: m.desc.yes_sub_title.clone(),
                        open_time: m.open_time.clone(),
                        cross: CrossTracker::new(),
                        backfilled: false,
                        last_bar: None,
                        bars_seen: 0,
                        last_fetch_at: None,
                        last_fetch_error: None,
                    });
                entry.open_time = m.open_time.clone();
            }
            fresh.insert(key, ev);
        }
        let new_events: Vec<String> = fresh
            .keys()
            .filter(|k| !self.events.contains_key(*k))
            .cloned()
            .collect();
        for k in new_events {
            self.journal.record(now_ms(), "EVENT_DISCOVERED", Some(&k), None, json!({
                "markets": fresh[&k].markets.iter().map(|m| json!({
                    "ticker": m.desc.ticker, "team": m.desc.yes_sub_title, "exchange_index": m.desc.exchange_index,
                })).collect::<Vec<_>>(),
            }));
        }
        self.events = fresh;
        let stale: Vec<String> = self
            .state
            .games
            .iter()
            .filter(|(_, g)| now - g.last_seen_open_at > 3 * 86_400)
            .map(|(k, _)| k.clone())
            .collect();
        for k in stale {
            self.state.games.remove(&k);
            self.state.markets.retain(|_, m| m.event_ticker != k);
        }
        let need_milestone: Vec<String> = self
            .state
            .games
            .values()
            .filter(|g| g.milestone_id.is_none())
            .map(|g| g.event_ticker.clone())
            .collect();
        for k in need_milestone {
            let found = self.public.milestone(&k, now);
            if let Some(g) = self.state.games.get_mut(&k) {
                g.milestone_checked_at = Some(now);
                if let Ok(Some((id, start))) = found {
                    g.milestone_id = Some(id);
                    g.start = start;
                }
            }
        }
    }

    fn phase(&self, g: &GameTrack, now: i64) -> &'static str {
        if g.clock_final() {
            return "FINAL";
        }
        if g.clock_live() {
            return "LIVE";
        }
        let Some(start) = g.start_ts() else {
            return "SCHEDULE_UNAVAILABLE";
        };
        let to_start = start - now;
        if to_start <= self.cfg.active_minutes_before_start * 60 && now - start < GAME_HORIZON_S {
            "ACTIVE_WINDOW"
        } else if to_start <= self.cfg.backfill_hours_before_start * 3600 && to_start > 0 {
            "BACKFILL_WINDOW"
        } else if now - start >= GAME_HORIZON_S {
            "PAST_HORIZON"
        } else {
            "IDLE"
        }
    }

    fn poll_clock(&mut self, event: &str, now: i64) {
        let Some(mid) = self
            .state
            .games
            .get(event)
            .and_then(|g| g.milestone_id.clone())
        else {
            return;
        };
        if let Ok(obs) = self.public.live_data(&mid, now) {
            self.last_clock_at = Some(now);
            if let Some(g) = self.state.games.get_mut(event) {
                let prev = g.clock.latest().map(|c| (c.status.clone(), c.period));
                if prev != Some((obs.status.clone(), obs.period)) {
                    self.journal
                        .record(now_ms(), "CLOCK", Some(event), None, json!(obs));
                }
                g.clock.push(obs);
            }
        }
    }

    fn fetch_new_bars(&mut self, ticker: &str, now: i64) -> Vec<MinuteBar> {
        let Some(m) = self.state.markets.get(ticker).cloned() else {
            return Vec::new();
        };
        let open_ts = m
            .open_time
            .as_deref()
            .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
            .map(|d| d.timestamp())
            .unwrap_or(now - 86_400);
        let mut start = m.cross.last_ts().map_or(open_ts, |t| t + 1);
        let end_cap = now - BAR_SETTLE_S;
        let mut out = Vec::new();
        let mut error = None;
        while start < end_cap {
            let end = (start + CANDLE_CHUNK_S).min(end_cap);
            match self
                .public
                .candles(&self.cfg.series.clone(), ticker, start, end, now)
            {
                Ok(bars) => out.extend(
                    bars.into_iter()
                        .filter(|b| b.end_ts >= start && b.end_ts <= end_cap),
                ),
                Err(e) => {
                    error = Some(e);
                    break;
                }
            }
            start = end + 1;
        }
        out.sort_by_key(|b| b.end_ts);
        out.dedup_by_key(|b| b.end_ts);
        if let Some(t) = self.state.markets.get_mut(ticker) {
            t.last_fetch_at = Some(now);
            t.last_fetch_error = error.clone();
            if error.is_none() {
                t.backfilled = true;
            }
        }
        if error.is_none() && !out.is_empty() {
            self.last_candle_at = Some(now);
        }
        out
    }

    fn feed(&mut self, event: &str, bars: Vec<(String, MinuteBar)>, now: i64) {
        for (ticker, bar) in bars {
            let Some(track) = self.state.markets.get_mut(&ticker) else {
                continue;
            };
            if track.cross.last_ts().is_some_and(|t| bar.end_ts <= t) {
                continue;
            }
            let before = track.cross.outcome();
            let after = track.cross.push(&bar);
            track.last_bar = Some(bar);
            track.bars_seen += 1;
            if before == CrossOutcome::Pending && after != CrossOutcome::Pending {
                match after {
                    CrossOutcome::Crossed(signal) => {
                        self.evaluate_signal(event, &ticker, signal, now)
                    }
                    other => {
                        let reason = serde_json::to_value(other)
                            .ok()
                            .and_then(|v| {
                                v.get("outcome")
                                    .and_then(|o| o.as_str())
                                    .map(str::to_string)
                            })
                            .unwrap_or_else(|| "UNKNOWN".into());
                        self.journal.record(
                            now_ms(),
                            "CONTRACT_EXCLUDED",
                            Some(event),
                            Some(&ticker),
                            json!({"reason": reason}),
                        );
                        if let Some(g) = self.state.games.get_mut(event) {
                            g.exclusions.push(Exclusion {
                                ticker: ticker.clone(),
                                reason,
                                signal_ts: None,
                            });
                        }
                    }
                }
            }
            self.shadow_step(event, &ticker, &bar, now);
        }
    }

    fn evaluate_signal(&mut self, event: &str, ticker: &str, signal: EntrySignal, now: i64) {
        let max_age = self.cfg.clock_max_age_seconds;
        let Some(game) = self.state.games.get(event) else {
            return;
        };
        let bucket = bucket_for(&game.clock, signal.signal_ts, max_age);
        let label = bucket.label();
        if !bucket.eligible() {
            self.journal.record(now_ms(), "SIGNAL_EXCLUDED", Some(event), Some(ticker), json!({
                "reason": if label.starts_with("CLOCK_UNAVAILABLE") { "CLOCK_UNAVAILABLE" } else { "OUTSIDE_SLICE" },
                "bucket": label, "signal": signal,
            }));
            if let Some(g) = self.state.games.get_mut(event) {
                g.exclusions.push(Exclusion {
                    ticker: ticker.into(),
                    reason: label,
                    signal_ts: Some(signal.signal_ts),
                });
            }
            return;
        }
        if game.candidate.is_some() {
            if let Some(g) = self.state.games.get_mut(event) {
                g.exclusions.push(Exclusion {
                    ticker: ticker.into(),
                    reason: "NOT_SELECTED_LATER_CONTRACT".into(),
                    signal_ts: Some(signal.signal_ts),
                });
            }
            return;
        }
        match self.public.event(event, now) {
            Ok(fresh) => {
                self.events.insert(event.to_string(), fresh);
            }
            Err(e) => {
                self.events.remove(event);
                self.journal.record(
                    now_ms(),
                    "EVENT_REFRESH_FAILED",
                    Some(event),
                    Some(ticker),
                    json!({"error": e}),
                );
            }
        }
        let (input, mut decision) = self.admission_for(event, ticker, now);
        if top_out_at_signal(&signal) {
            let top = Blocker::TopOut {
                cents: signal
                    .close_cents
                    .max(signal.bar.yes_ask_close.unwrap_or(0)),
            };
            decision = match decision {
                AdmissionDecision::Blocked(mut b) => {
                    b.insert(0, top);
                    AdmissionDecision::Blocked(b)
                }
                AdmissionDecision::Admit => AdmissionDecision::Blocked(vec![top]),
            };
        }
        let (route, pair) = self.route_and_pair(event, ticker);
        let qty = self.standard_qty().map(|q| q.get());
        let (reserve, reserve_error) = match self.standard_reserve() {
            Ok(r) => (Some(r), None),
            Err(e) => (None, Some(format!("{e:?}"))),
        };
        let cid = client_order_id(event, ticker, signal.signal_ts);
        let record = CandidateRecord {
            ticker: ticker.into(),
            opponent: pair.as_ref().ok().map(|p| p.opponent.clone()),
            signal,
            bucket: label,
            detected_at: now,
            decision_latency_s: now - signal.signal_ts,
            client_order_id: cid.clone(),
            qty,
            reserve,
            reserve_error,
            route,
            pair: pair.clone(),
            decision: decision.clone(),
        };
        let mut lc = Lifecycle::new(event, ticker);
        let _ = lc.apply(now, LifecycleEvent::Eligible);
        let _ = lc.apply(now, LifecycleEvent::IntentStaged);
        let codes: Vec<String> = match &decision {
            AdmissionDecision::Blocked(b) => b.iter().map(|x| x.code().to_string()).collect(),
            AdmissionDecision::Admit => vec!["PRODUCTION_SUBMISSION_DISABLED".into()],
        };
        let _ = lc.apply(
            now,
            LifecycleEvent::Blocked {
                codes: codes.clone(),
            },
        );
        self.journal.record(
            now_ms(),
            "ENTRY_INTENT_LOCAL",
            Some(event),
            Some(ticker),
            json!({
                "client_order_id": cid,
                "not_submitted": true,
                "signal": signal,
                "qty": qty,
                "admission_input": input,
                "decision": decision,
                "blocker_codes": codes,
            }),
        );
        let shadow =
            if self.cfg.config_mode().ok() == Some(momento_strategy_nba::ConfigMode::Shadow) {
                Some(ShadowPath {
                    label: SHADOW_LABEL.into(),
                    ticker: ticker.into(),
                    opponent: record.opponent.clone(),
                    qty: qty.unwrap_or(0),
                    stop: StopTracker::new(&signal),
                    planner: HedgePlanner::default(),
                    events: Vec::new(),
                })
            } else {
                None
            };
        if let Some(g) = self.state.games.get_mut(event) {
            g.candidate = Some(record);
            g.lifecycle = Some(lc);
            g.shadow = shadow;
        }
    }

    fn shadow_step(&mut self, event: &str, ticker: &str, bar: &MinuteBar, now: i64) {
        let Some(g) = self.state.games.get_mut(event) else {
            return;
        };
        let Some(sh) = g.shadow.as_mut() else {
            return;
        };
        if sh.ticker != ticker {
            return;
        }
        let Some(ev) = sh.stop.push(bar) else {
            return;
        };
        let close = match ev {
            StopEvent::Prepare { close_cents, .. }
            | StopEvent::Trigger { close_cents, .. }
            | StopEvent::PostTrigger { close_cents, .. } => close_cents,
        };
        let action = sh.planner.on_close(close, Contracts::from_u32(sh.qty));
        if matches!(action, HedgeAction::None) {
            return;
        }
        let rec = json!({"label": SHADOW_LABEL, "at": now, "stop_event": ev, "action": action});
        if sh.events.len() >= 200 {
            sh.events.remove(0);
        }
        sh.events.push(rec.clone());
        self.journal
            .record(now_ms(), "SHADOW_HEDGE", Some(event), Some(ticker), rec);
    }

    pub fn observe_account(&mut self, now: i64) {
        self.last_account_at = Some(now);
        let view = self.account.observe(now);
        if view.ok != self.account_view.ok
            || view.shard_cash_cents != self.account_view.shard_cash_cents
        {
            self.journal.record(
                now_ms(),
                "ACCOUNT_OBSERVED",
                None,
                None,
                json!({
                    "ok": view.ok,
                    "shard_cash_cents": view.shard_cash_cents,
                    "resting_orders_by_series": view.resting_orders_by_series,
                    "positions_by_series": view.positions_by_series,
                    "error": view.error,
                }),
            );
        }
        self.account_view = view;
    }

    pub fn tick(&mut self, now: i64) {
        self.ticks += 1;
        if self
            .last_discovery_at
            .is_none_or(|t| now - t >= self.cfg.discovery_seconds)
        {
            self.discover(now);
        }
        let games: Vec<(String, &'static str)> = self
            .state
            .games
            .values()
            .map(|g| (g.event_ticker.clone(), self.phase(g, now)))
            .collect();
        for (event, phase) in games {
            let tickers: Vec<String> = self
                .state
                .markets
                .values()
                .filter(|m| m.event_ticker == event)
                .map(|m| m.ticker.clone())
                .collect();
            let fetch = match phase {
                "LIVE" | "ACTIVE_WINDOW" => {
                    self.poll_clock(&event, now);
                    true
                }
                "BACKFILL_WINDOW" => {
                    let due = tickers.iter().any(|t| {
                        self.state.markets.get(t).is_some_and(|m| {
                            !m.backfilled
                                || m.last_fetch_at
                                    .is_none_or(|f| now - f >= self.cfg.discovery_seconds)
                        })
                    });
                    if due {
                        self.poll_clock(&event, now);
                    }
                    due
                }
                "FINAL" => {
                    let unfinished = tickers.iter().any(|t| {
                        self.state
                            .markets
                            .get(t)
                            .is_some_and(|m| m.last_fetch_at.is_none_or(|f| now - f >= 300))
                    });
                    if unfinished {
                        self.poll_clock(&event, now);
                    }
                    false
                }
                _ => false,
            };
            if !fetch {
                continue;
            }
            let mut merged: Vec<(String, MinuteBar)> = Vec::new();
            for t in &tickers {
                for b in self.fetch_new_bars(t, now) {
                    merged.push((t.clone(), b));
                }
            }
            merged.sort_by(|a, b| (a.1.end_ts, &a.0).cmp(&(b.1.end_ts, &b.0)));
            self.feed(&event, merged, now);
        }
        if self
            .last_account_at
            .is_none_or(|t| now - t >= self.cfg.account_seconds)
        {
            self.observe_account(now);
        }
    }

    // ---- status ----

    pub fn status_json(&self, now: i64) -> Value {
        let mode_cfg = self.cfg.config_mode().ok();
        let standard = self.standard_reserve();
        let reserved = self.outstanding_reserved();
        let open_slots = self.open_slots();
        let series_index = self.series.as_ref().and_then(|s| s.exchange_index);
        let mut global: BTreeMap<String, Value> = BTreeMap::new();
        let mut games_out = Vec::new();
        let mut any_listed = false;
        let mut capacity_by_shard: BTreeMap<String, Value> = BTreeMap::new();
        for (key, g) in &self.state.games {
            let ev = self.events.get(key);
            let phase = self.phase(g, now);
            let markets: Vec<Value> = self
                .state
                .markets
                .values()
                .filter(|m| &m.event_ticker == key)
                .map(|m| {
                    let live =
                        ev.and_then(|e| e.markets.iter().find(|x| x.desc.ticker == m.ticker));
                    json!({
                        "ticker": m.ticker,
                        "team": m.team,
                        "exchange_index": live.and_then(|x| x.desc.exchange_index),
                        "status": live.and_then(|x| x.desc.status.clone()),
                        "yes_bid_cents": live.and_then(|x| x.yes_bid_cents),
                        "yes_ask_cents": live.and_then(|x| x.yes_ask_cents),
                        "backfilled": m.backfilled,
                        "bars_seen": m.bars_seen,
                        "last_bar": m.last_bar,
                        "cross": m.cross.outcome(),
                        "quality_bars": m.cross.quality_bars(),
                        "last_fetch_error": m.last_fetch_error,
                    })
                })
                .collect();
            let first_ticker = ev
                .and_then(|e| e.markets.first())
                .map(|m| m.desc.ticker.clone());
            let (route, pair, standing) = match &first_ticker {
                Some(t) => {
                    any_listed = true;
                    let (route, pair) = self.route_and_pair(key, t);
                    let (_, decision) = self.admission_for(key, t, now);
                    (Some(route), Some(pair), Some(decision))
                }
                None => (None, None, None),
            };
            if let Some(AdmissionDecision::Blocked(bs)) = &standing {
                for b in bs {
                    global
                        .entry(b.code().to_string())
                        .or_insert_with(|| json!(b));
                }
            }
            if let Some(r) = &route {
                let shard = r.market_index();
                let cap = capacity_positions(
                    self.cash_on(shard, now),
                    reserved,
                    standard.as_ref().map_err(|e| *e),
                    open_slots,
                    SHARED_SLOTS,
                );
                capacity_by_shard.insert(
                    shard.map_or("UNREAD".into(), |s| s.to_string()),
                    cap.map_or(json!("UNAVAILABLE"), |c| json!(c)),
                );
            }
            let clock = g.clock.latest().map(|c| {
                json!({
                    "status": c.status, "period": c.period, "period_type": c.period_type,
                    "remaining": c.period_remaining, "received_at": c.received_at,
                    "source_updated_at": c.source_updated_at,
                    "bucket": momento_strategy_nba::slice::classify(c).label(),
                    "age_s": now - c.received_at,
                })
            });
            games_out.push(json!({
                "event_ticker": key,
                "title": g.title,
                "start": g.start,
                "milestone_id": g.milestone_id,
                "phase": phase,
                "listed_open": ev.is_some(),
                "series_exchange_index": series_index,
                "event_exchange_index": ev.and_then(|e| e.event_exchange_index),
                "route": route,
                "pair": pair.map(|p| match p { Ok(pp) => json!({"ok": true, "pair": pp}), Err(e) => json!({"ok": false, "reason": e}) }),
                "clock": clock,
                "markets": markets,
                "candidate": g.candidate,
                "exclusions": g.exclusions,
                "lifecycle": g.lifecycle.as_ref().map(|l| json!({"state": l.state(), "history": l.history(), "filled": l.filled(), "hedged": l.hedged(), "residual": l.residual()})),
                "shadow": g.shadow,
            }));
        }
        let fees = self.fee_model();
        let hard: Vec<String> = global
            .keys()
            .filter(|k| {
                !matches!(
                    k.as_str(),
                    "BLOCKED_INSUFFICIENT_CASH" | "FUNDS_UNREAD" | "SLOTS_FULL"
                )
            })
            .cloned()
            .collect();
        let capacity_any = capacity_by_shard.values().filter_map(|v| v.as_u64()).max();
        let mode = derive_mode(&ModeInputs {
            config: mode_cfg.unwrap_or(momento_strategy_nba::ConfigMode::LiveDataOnly),
            live_gates_set: self.cfg.live_gates_set(),
            reconciliation_healthy: self.reconciliation_healthy(now),
            hard_blockers: hard,
            funds_sufficient: capacity_any.is_some_and(|c| c > 0),
            eligible_market_listed: any_listed,
        });
        let oct3 = self.state.games.keys().find(|k| k.contains("26OCT03"));
        let placeholders: Vec<Value> = PLACEHOLDERS
            .iter()
            .map(|n| json!({"module": n, "status": "PLACEHOLDER", "approval": null, "probability": null}))
            .collect();
        let feed_age = self.public.last_ok_at.map(|t| now - t);
        json!({
            "schema": "nba_001_status_v1",
            "bot_id": "nba-001",
            "alias": "nba-first80-001",
            "policy_version": momento_strategy_nba::POLICY_VERSION,
            "strategy_id": momento_strategy_nba::STRATEGY_ID,
            "service": "momento-nba-001.service",
            "binary": "/usr/local/bin/momento-nba-001",
            "version": env!("CARGO_PKG_VERSION"),
            "build_id": option_env!("NBA001_BUILD_ID").unwrap_or("local"),
            "binary_sha256": self.binary_sha256,
            "contract_id": self.contract.contract_id,
            "contract_sha256": self.contract_sha256,
            "host": std::fs::read_to_string("/etc/hostname").ok().map(|h| h.trim().to_string()),
            "pid": std::process::id(),
            "started_at": self.started_at,
            "heartbeat_at": now,
            "uptime_s": now - self.started_at,
            "ticks": self.ticks,
            "mode": mode,
            "config_mode": mode_cfg,
            "live_gates": {"enabled": self.cfg.live.enabled, "confirmation_set": self.cfg.live.confirmation == crate::config::LIVE_CONFIRMATION},
            "submits": false,
            "submission_adapter_linked": crate::SUBMISSION_ADAPTER_LINKED,
            "submission_adapter_environments": ["FIXTURE", "DEMO"],
            "production_orders_compiled": crate::venue::PRODUCTION_ORDERS_COMPILED,
            "production_permit": match self.production_permit(now) { Ok(()) => json!("PERMITTED"), Err(w) => json!({"denied": w.split(',').collect::<Vec<_>>()}) },
            "live_execution": false,
            "feed": {
                "last_public_ok_at": self.public.last_ok_at,
                "feed_age_s": feed_age,
                "public_calls_total": self.public.calls_total,
                "public_errors_total": self.public.errors_total,
                "last_public_error": self.public.last_error,
                "last_discovery_at": self.last_discovery_at,
                "last_discovery_error": self.last_discovery_error,
                "last_candle_at": self.last_candle_at,
                "last_clock_at": self.last_clock_at,
                "clock_source": "kalshi live_data basketball_game",
            },
            "series": self.series,
            "fees": {
                "model": fees,
                "entry_liquidity": self.entry_liquidity(),
                "verified": self.fees_verified(),
                "contract_status_verified": self.contract.fees_verified,
                "verified_scope": "quadratic_with_maker_fees, fee_multiplier 1",
                "status": if self.fees_verified() { "VERIFIED" } else { "FEE_UNVERIFIED" },
            },
            "games": games_out,
            "october_3": match oct3 {
                Some(k) => json!({"status": "LISTED", "event_ticker": k}),
                None => json!({"status": "UNAVAILABLE", "detail": "no KXNBAGAME event for 2026-10-03 listed open"}),
            },
            "account": self.account_view,
            "capital": {
                "reference_capital_cents": self.cfg.capital.reference_capital_cents,
                "funded_target_cents": self.cfg.capital.funded_target_cents,
                "external_reserve_cents": self.cfg.capital.external_reserve_cents,
                "external_reserve_spendable": false,
                "batch": self.state.equity.current(),
                "batches": self.state.equity.batches(),
                "batch_resize_approved": self.contract.batch_resize_approved,
                "sizing_equity_centicents": self.state.equity.equity_centicents(),
                "capital_base_cents": self.state.equity.capital_base_cents(),
                "external_reserve_outstanding_cents": self.state.equity.external_reserve_outstanding_cents(),
                "realized_pnl_cents": "UNAVAILABLE",
                "capital_flows": self.state.equity.flows(),
                "reserved_cents": reserved.cents(),
                "standard_qty": self.standard_qty().map(|q| q.get()),
                "standard_reserve": match &standard { Ok(r) => json!(r), Err(e) => json!({"unavailable": format!("{e:?}")}) },
                "capacity_positions_by_shard": capacity_by_shard,
                "slots": {"open": open_slots, "max": SHARED_SLOTS},
                "allocation": {"bps_of_reference": ALLOCATION_BPS, "pct_of_reference": "6%", "pct_of_funded_target": "24%"},
            },
            "collateral": self.collateral_pool(),
            "contract": {
                "unresolved": self.contract.unresolved,
                "emergency": self.contract.emergency,
                "hedge_pre_trigger_orders": self.contract.hedge_pre_trigger_orders,
            },
            "blockers": global,
            "orders": [],
            "fills": "UNAVAILABLE",
            "positions": "UNAVAILABLE",
            "pnl": "UNAVAILABLE",
            "reconciliation": {
                "healthy": self.reconciliation_healthy(now),
                "account_fresh": self.account_fresh(now),
                "bot_client_orders_found": self.account_view.bot_client_orders_found,
                "bot_orders_submitted": 0,
            },
            "controls": self.controls,
            "placeholders": placeholders,
            "journal": self.journal.path(),
            "journal_write_errors": self.journal.write_errors,
        })
    }

    pub fn persist(&self, now: i64) -> Result<(), String> {
        write_json_atomic(&self.state_dir.join("state.json"), &json!(self.state))?;
        write_json_atomic(&self.state_dir.join("status.json"), &self.status_json(now))
    }
}
