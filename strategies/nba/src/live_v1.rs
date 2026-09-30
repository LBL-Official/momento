//! FIRST78 midpoint policy. Pure deterministic reducer; never performs I/O.
//! Whole-contract execution uses the existing audited order/exposure primitives.
//! Production stays blocked until fractional-fill support and all live gates pass.
use crate::sizing_epoch::{AdmissionBudget, ReconciledEquity, SizingEpochs};
use crate::{
    BookSide, EmergencyPolicy, FeeModel, GameBook, Liquidity, OrderEvent, OrderRecord, OrderRole,
    OrderSpec, PlanStep, Residual, TimeInForce,
};
use chrono::{DateTime, Utc};
use chrono_tz::America::Los_Angeles;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Sport {
    NBA,
    NCAAB,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Policy {
    pub quote_max_age_ms: i64,
    pub sports_max_age_ms: i64,
    pub entry_reprice_ms: i64,
    pub emergency_floor_cents: Option<u16>,
    pub fee_model: FeeModel,
    pub fee_version: String,
}
impl Policy {
    pub fn validate(&self) -> Result<(), String> {
        if self.quote_max_age_ms <= 0
            || self.sports_max_age_ms <= 0
            || self.entry_reprice_ms <= 0
            || self.fee_version.is_empty()
            || self
                .emergency_floor_cents
                .is_some_and(|p| !(1..=99).contains(&p))
        {
            return Err("INVALID_V1_POLICY".into());
        }
        self.fee_model
            .order_fee_centicents(Liquidity::Maker, 1, 78)
            .map_err(|e| format!("{e:?}"))?;
        Ok(())
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Mapping {
    pub event_id: String,
    pub sport: Sport,
    pub tickers: [String; 2],
    pub espn_event_id: String,
    pub espn_team_ids: [String; 2], // same order as tickers, verified mapping
    pub season: String,
    pub membership_evidence: Option<String>,
    pub both_p5: bool,
    pub complement_evidence: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SportsState {
    pub event_id: String,
    pub status: String, // pre, in, post
    pub period: u8,
    pub clock_seconds: u16,
    pub scores: [u32; 2],
    pub received_ms: i64,
    pub provider_ms: Option<i64>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Quote {
    pub side: usize,
    pub bid: u16,
    pub ask: u16,
    pub receive_ms: i64,
    pub exchange_ms: Option<i64>,
}
impl Quote {
    pub fn mid2(&self) -> u32 {
        u32::from(self.bid) + u32::from(self.ask)
    }
    pub fn valid(&self, now: i64, max_age: i64) -> bool {
        self.side < 2
            && self.bid <= self.ask
            && self.ask <= 100
            && now >= self.receive_ms
            && now - self.receive_ms <= max_age
            && self
                .exchange_ms
                .is_none_or(|ts| ts <= now && now - ts <= max_age)
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FirstTouch {
    pub quote: Quote,
    pub sports: Option<SportsState>,
    pub reason: Option<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Trade {
    pub selected: usize,
    pub budget: AdmissionBudget,
    pub book: GameBook,
    pub hedge_trigger_mid2: Option<u32>,
    pub hedge_low_mid2: Option<u32>,
    pub hedge_limit: u16,
    pub emergency: bool,
    pub entry_closed: bool,
    pub last_entry_price: u16,
    pub last_entry_ms: i64,
    pub completed: bool,
    pub net_pnl_centicents: Option<i64>,
    pub initial_contracts: u32,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Game {
    pub mapping: Mapping,
    pub sports: Option<SportsState>,
    pub quotes: [Option<Quote>; 2],
    pub history_complete: bool,
    pub pregame_ready: bool,
    pub first_touch: Option<FirstTouch>,
    pub trade: Option<Trade>,
    pub blocker: Option<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Engine {
    pub policy: Policy,
    pub authority: crate::portfolio_v1::Authority,
    pub epochs: Option<SizingEpochs>,
    pub games: BTreeMap<String, Game>,
    pub daily_admissions: BTreeMap<String, u32>,
    pub account_clean: bool,
    pub account_observed_ms: Option<i64>,
    pub account_cash_centicents: i64,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "kind")]
pub enum Input {
    Register {
        mapping: Mapping,
    },
    Sports {
        state: SportsState,
    },
    Quote {
        event_id: String,
        quote: Quote,
    },
    Gap {
        reason: String,
    },
    Account {
        clean: bool,
        cash_centicents: i64,
        equity_cents: u64,
        snapshot_id: String,
        observed_ms: i64,
    },
    Order {
        event_id: String,
        client_order_id: String,
        evidence: OrderEvent,
    },
    Complete {
        event_id: String,
        net_pnl_centicents: i64,
        initial_contracts: u32,
        reconciliation_id: String,
    },
    Resize {
        equity_cents: u64,
        snapshot_id: String,
        observed_ms: i64,
        clean: bool,
    },
    Incident {
        incident: crate::portfolio_v1::Incident,
    },
    ResolveIncident {
        id: String,
        evidence_id: String,
    },
    Tick,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "action")]
pub enum Action {
    Submit {
        event_id: String,
        order: OrderSpec,
    },
    Cancel {
        event_id: String,
        client_order_id: String,
    },
    Block {
        event_id: String,
        reason: String,
    },
    Completed {
        event_id: String,
    },
    Resized {
        epoch: u64,
    },
}
fn utc(ms: i64) -> Result<DateTime<Utc>, String> {
    DateTime::from_timestamp_millis(ms).ok_or_else(|| "INVALID_TIMESTAMP".into())
}
impl Engine {
    pub fn new(policy: Policy, now: i64) -> Result<Self, String> {
        policy.validate()?;
        utc(now)?;
        Ok(Self {
            policy,
            authority: Default::default(),
            epochs: None,
            games: BTreeMap::new(),
            daily_admissions: BTreeMap::new(),
            account_clean: false,
            account_observed_ms: None,
            account_cash_centicents: 0,
        })
    }
    /// Worker calls on a clone, journals input + actions durably, then publishes.
    pub fn apply(&mut self, now: i64, input: Input) -> Result<Vec<Action>, String> {
        let mut out = Vec::new();
        match input {
            Input::Incident { incident } => {
                self.authority.raise(incident)?;
            }
            Input::ResolveIncident { id, evidence_id } => {
                self.authority.resolve(&id, &evidence_id)?;
            }
            Input::Register { mapping } => {
                if mapping.event_id.is_empty()
                    || mapping.tickers[0] == mapping.tickers[1]
                    || mapping.tickers.iter().any(|s| s.is_empty())
                    || mapping.complement_evidence.is_empty()
                    || mapping.espn_team_ids[0] == mapping.espn_team_ids[1]
                {
                    return Err("INVALID_MAPPING".into());
                }
                if let Some(old) = self.games.get(&mapping.event_id) {
                    if serde_json::to_value(&old.mapping).unwrap()
                        != serde_json::to_value(&mapping).unwrap()
                    {
                        return Err("MAPPING_CHANGED_RECONCILIATION_REQUIRED".into());
                    }
                } else {
                    self.games.insert(
                        mapping.event_id.clone(),
                        Game {
                            mapping,
                            sports: None,
                            quotes: [None, None],
                            history_complete: false,
                            pregame_ready: false,
                            first_touch: None,
                            trade: None,
                            blocker: None,
                        },
                    );
                }
            }
            Input::Gap { reason } => {
                self.account_clean = false;
                for g in self.games.values_mut() {
                    g.quotes = [None, None];
                    g.pregame_ready = false;
                    g.history_complete = false;
                    g.blocker = Some(format!("FIRST78_HISTORY_UNCERTAIN:{reason}"));
                }
            }
            Input::Account {
                clean,
                cash_centicents,
                equity_cents,
                snapshot_id,
                observed_ms,
            } => {
                if self
                    .account_observed_ms
                    .is_some_and(|prev| observed_ms < prev)
                {
                    return Err("ACCOUNT_SNAPSHOT_REGRESSION".into());
                }
                self.account_clean = clean
                    && cash_centicents >= 0
                    && !snapshot_id.trim().is_empty()
                    && equity_cents <= (i64::MAX / 100) as u64
                    && observed_ms <= now
                    && now - observed_ms <= self.policy.sports_max_age_ms;
                if self.account_clean && self.epochs.is_none() {
                    self.epochs = Some(
                        SizingEpochs::new(equity_cents, utc(now)?, snapshot_id)
                            .map_err(|e| format!("{e:?}"))?,
                    );
                }
                self.account_cash_centicents = cash_centicents;
                self.account_observed_ms = Some(observed_ms);
            }
            Input::Sports { state } => {
                let g = self.games.get_mut(&state.event_id).ok_or("UNKNOWN_EVENT")?;
                if state.received_ms > now {
                    return Err("FUTURE_SPORTS_TIMESTAMP".into());
                }
                if let Some(prev) = &g.sports {
                    if state.received_ms < prev.received_ms {
                        return Ok(out);
                    }
                    if state.period < prev.period
                        || state.scores.iter().zip(prev.scores).any(|(a, b)| *a < b)
                        || (state.period == prev.period
                            && state.clock_seconds > prev.clock_seconds
                            && prev.status == "in")
                    {
                        g.sports = None;
                        g.history_complete = false;
                        g.pregame_ready = false;
                        g.blocker = Some("SPORTS_STATE_REGRESSION".into());
                        return Ok(out);
                    }
                }
                if state.status == "pre"
                    && g.quotes.iter().all(|q| {
                        q.as_ref()
                            .is_some_and(|q| q.valid(now, self.policy.quote_max_age_ms))
                    })
                    && g.first_touch.is_none()
                {
                    // An observed pregame state establishes start coverage; a late
                    // attachment to an in-progress game cannot invent earlier history.
                    g.pregame_ready = true;
                    g.history_complete = true;
                    g.blocker = None;
                }
                if state.status == "in" && !g.pregame_ready {
                    g.history_complete = false;
                }
                g.sports = Some(state);
            }
            Input::Quote { event_id, quote } => {
                if quote.side >= 2 {
                    return Err("INVALID_SIDE".into());
                }
                let g = self.games.get_mut(&event_id).ok_or("UNKNOWN_EVENT")?;
                if g.quotes[quote.side]
                    .as_ref()
                    .is_some_and(|p| quote.receive_ms < p.receive_ms)
                {
                    return Ok(out);
                }
                if !quote.valid(now, self.policy.quote_max_age_ms) {
                    g.history_complete = false;
                    g.blocker = Some("INVALID_OR_STALE_QUOTE_HISTORY".into());
                    g.quotes[quote.side] = None;
                    return Ok(out);
                }
                g.quotes[quote.side] = Some(quote.clone());
                let in_game = g.sports.as_ref().is_none_or(|s| {
                    s.status != "pre" || now - s.received_ms > self.policy.sports_max_age_ms
                });
                if in_game && quote.mid2() >= 156 && g.first_touch.is_none() {
                    let sports = g.sports.clone();
                    let reason = if !g.history_complete {
                        Some("FIRST78_HISTORY_UNCERTAIN")
                    } else if sports.as_ref().is_none_or(|s| {
                        now < s.received_ms || now - s.received_ms > self.policy.sports_max_age_ms
                    }) {
                        Some("SPORTS_STATE_STALE")
                    } else if !window(g.mapping.sport, sports.as_ref().unwrap()) {
                        Some("PRIOR_FIRST78_OUTSIDE_WINDOW")
                    } else if g.mapping.sport == Sport::NCAAB
                        && (!g.mapping.both_p5 || g.mapping.membership_evidence.is_none())
                    {
                        Some("NCAAB_P5_MEMBERSHIP_UNVERIFIED")
                    } else {
                        None
                    };
                    g.first_touch = Some(FirstTouch {
                        quote: quote.clone(),
                        sports,
                        reason: reason.map(str::to_string),
                    });
                    if let Some(r) = reason {
                        g.blocker = Some(r.into());
                        out.push(Action::Block {
                            event_id: event_id.clone(),
                            reason: r.into(),
                        });
                    } else {
                        self.admit(&event_id, quote.side, now, &mut out)?;
                    }
                }
                self.manage(&event_id, now, &mut out)?;
            }
            Input::Order {
                event_id,
                client_order_id,
                evidence,
            } => {
                let t = self
                    .games
                    .get_mut(&event_id)
                    .and_then(|g| g.trade.as_mut())
                    .ok_or("UNKNOWN_TRADE")?;
                t.book
                    .order_mut(&client_order_id)
                    .ok_or("UNKNOWN_ORDER")?
                    .apply(now, evidence)
                    .map_err(|e| format!("{e:?}"))?;
                self.manage(&event_id, now, &mut out)?;
            }
            Input::Complete {
                event_id,
                net_pnl_centicents,
                initial_contracts,
                reconciliation_id,
            } => {
                let t = self
                    .games
                    .get_mut(&event_id)
                    .and_then(|g| g.trade.as_mut())
                    .ok_or("UNKNOWN_TRADE")?;
                if t.completed {
                    return Ok(out);
                }
                let actual: u32 = t
                    .book
                    .orders
                    .iter()
                    .filter(|o| o.spec.role == OrderRole::Entry)
                    .map(|o| o.confirmed_filled())
                    .sum();
                if reconciliation_id.is_empty()
                    || initial_contracts == 0
                    || actual != initial_contracts
                    || t.book.orders.iter().any(|o| !o.is_settled())
                {
                    return Err("COMPLETION_UNRECONCILED".into());
                }
                // Caller must verify settlement/flatness and authoritative cash-flow
                // P&L. No live caller exists until the ledger reconciler is integrated.
                t.completed = true;
                t.net_pnl_centicents = Some(net_pnl_centicents);
                t.initial_contracts = actual;
                self.epochs
                    .as_mut()
                    .ok_or("ACCOUNT_BASELINE_REQUIRED")?
                    .record_completion(&event_id, true)
                    .map_err(|e| format!("{e:?}"))?;
                out.push(Action::Completed { event_id });
            }
            Input::Resize {
                equity_cents,
                snapshot_id,
                observed_ms,
                clean,
            } => {
                if equity_cents > (i64::MAX / 100) as u64 {
                    return Err("EQUITY_OVERFLOW".into());
                }
                let constructing = self
                    .games
                    .values()
                    .filter_map(|g| g.trade.as_ref())
                    .any(|t| {
                        t.book
                            .orders
                            .iter()
                            .any(|o| o.spec.role == OrderRole::Entry && !o.is_settled())
                    });
                self.epochs = Some(
                    self.epochs
                        .as_ref()
                        .ok_or("ACCOUNT_BASELINE_REQUIRED")?
                        .propose_resize(
                            utc(now)?,
                            &ReconciledEquity {
                                snapshot_id,
                                equity_cents,
                                observed_at: utc(observed_ms)?,
                                reconciliation_clean: clean,
                            },
                            self.policy.sports_max_age_ms,
                            constructing,
                        )
                        .map_err(|e| format!("{e:?}"))?,
                );
                out.push(Action::Resized {
                    epoch: self.epochs.as_ref().unwrap().active().number,
                });
            }
            Input::Tick => {
                for id in self.games.keys().cloned().collect::<Vec<_>>() {
                    self.manage(&id, now, &mut out)?;
                }
            }
        }
        Ok(out)
    }
    fn admit(
        &mut self,
        id: &str,
        side: usize,
        now: i64,
        out: &mut Vec<Action>,
    ) -> Result<(), String> {
        let day = utc(now)?
            .with_timezone(&Los_Angeles)
            .date_naive()
            .to_string();
        let Some(epochs) = self.epochs.as_ref() else {
            out.push(Action::Block {
                event_id: id.into(),
                reason: "ACCOUNT_BASELINE_REQUIRED".into(),
            });
            return Ok(());
        };
        let budget = epochs.admission_budget();
        // Conservative shadow reservation: keep one daily slot for every admitted
        // attempt, including nonfills. Production slot-release policy remains gated.
        let used = *self.daily_admissions.get(&day).unwrap_or(&0);
        let reserved = self
            .games
            .values()
            .filter_map(|g| g.trade.as_ref())
            .filter(|t| !t.completed)
            .try_fold(0i64, |sum, t| {
                sum.checked_add(t.budget.acquisition_budget_cents as i64 * 100)
            })
            .ok_or("RESERVATION_OVERFLOW")?;
        let g = self.games.get_mut(id).unwrap();
        let reason = if !self.authority.entries_allowed() {
            Some("PORTFOLIO_ENTRIES_BLOCKED")
        } else if g.quotes[side].as_ref().unwrap().mid2() >= 172 {
            Some("MID_86_WITHOUT_FILL")
        } else if used >= 8 {
            Some("DAILY_CAP")
        } else if !self.account_clean
            || self
                .account_observed_ms
                .is_none_or(|ts| now < ts || now - ts > self.policy.sports_max_age_ms)
        {
            Some("ACCOUNT_UNRECONCILED")
        } else if self.account_cash_centicents - reserved
            < budget.acquisition_budget_cents as i64 * 100
        {
            Some("INSUFFICIENT_AVAILABLE_CASH")
        } else {
            None
        };
        if let Some(reason) = reason {
            g.blocker = Some(reason.into());
            g.first_touch.as_mut().unwrap().reason = Some(reason.into());
            out.push(Action::Block {
                event_id: id.into(),
                reason: reason.into(),
            });
            return Ok(());
        }
        let book = GameBook::new(id, &g.mapping.tickers[side], &g.mapping.tickers[1 - side]);
        g.trade = Some(Trade {
            selected: side,
            budget,
            book,
            hedge_trigger_mid2: None,
            hedge_low_mid2: None,
            hedge_limit: 35,
            emergency: false,
            entry_closed: false,
            last_entry_price: 78,
            last_entry_ms: now,
            completed: false,
            net_pnl_centicents: None,
            initial_contracts: 0,
        });
        *self.daily_admissions.entry(day).or_default() += 1;
        self.manage(id, now, out)
    }
    fn manage(&mut self, id: &str, now: i64, out: &mut Vec<Action>) -> Result<(), String> {
        let g = self.games.get_mut(id).ok_or("UNKNOWN_EVENT")?;
        let Some(t) = g.trade.as_mut() else {
            return Ok(());
        };
        if t.completed {
            return Ok(());
        }
        if !self.authority.entries_allowed()
            || !self.account_clean
            || self
                .account_observed_ms
                .is_none_or(|ts| now < ts || now - ts > self.policy.sports_max_age_ms)
        {
            t.entry_closed = true;
        }
        if g.sports.as_ref().is_none_or(|s| {
            !window(g.mapping.sport, s)
                || s.received_ms > now
                || now - s.received_ms > self.policy.sports_max_age_ms
        }) {
            t.entry_closed = true;
        }
        let e = t.book.exposure();
        if !e.inconsistent.is_empty() || e.unhedged_original < 0 {
            self.account_clean = false;
            out.push(Action::Block {
                event_id: id.into(),
                reason: "POSITION_RECONCILIATION_REQUIRED".into(),
            });
            return Ok(());
        }
        let selected = g.quotes[t.selected]
            .as_ref()
            .filter(|q| q.valid(now, self.policy.quote_max_age_ms));
        let opp = g.quotes[1 - t.selected]
            .as_ref()
            .filter(|q| q.valid(now, self.policy.quote_max_age_ms));
        if selected.is_some_and(|q| q.mid2() >= 172) {
            t.entry_closed = true;
        }
        if e.original_long > 0
            && opp.is_some_and(|q| q.mid2() >= 72)
            && t.hedge_trigger_mid2.is_none()
        {
            let m = opp.unwrap().mid2();
            t.hedge_trigger_mid2 = Some(m);
            t.hedge_low_mid2 = Some(m);
            t.entry_closed = true;
        }
        if let (Some(low), Some(q)) = (t.hedge_low_mid2, opp) {
            if q.mid2() > low || q.mid2() <= 50 {
                t.emergency = true;
            }
            if q.mid2() < low {
                t.hedge_low_mid2 = Some(q.mid2());
                t.hedge_limit = t
                    .hedge_limit
                    .min((q.mid2() / 2).saturating_sub(1).clamp(25, 35) as u16);
            }
        }
        let mut cancel = Vec::new();
        for o in &t.book.orders {
            if o.status.is_terminal() {
                continue;
            }
            let needs = match o.spec.role {
                OrderRole::Entry => {
                    t.entry_closed
                        || (now - t.last_entry_ms >= self.policy.entry_reprice_ms
                            && t.last_entry_price < 82)
                }
                OrderRole::Hedge => t.emergency || o.spec.price_cents > t.hedge_limit,
                OrderRole::Emergency => false,
            };
            if needs && !matches!(o.status, crate::OrderStatus::CancelRequested) {
                cancel.push(o.spec.client_order_id.clone());
            }
        }
        if !cancel.is_empty() {
            for client_order_id in cancel {
                out.push(Action::Cancel {
                    event_id: id.into(),
                    client_order_id,
                });
            }
            return Ok(());
        }
        if t.book.orders.iter().any(|o| !o.is_settled()) {
            return Ok(());
        }
        if t.emergency {
            let policy = self
                .policy
                .emergency_floor_cents
                .map_or(EmergencyPolicy::Unresolved, |floor_cents| {
                    EmergencyPolicy::SellOriginal { floor_cents }
                });
            let next_id = format!("v1-{}-{}", id, t.book.orders.len());
            match t.book.plan_emergency(policy, &next_id, None) {
                PlanStep::Submit(order) => stage(t, id, order, out)?,
                PlanStep::PolicyUnresolved { .. } => out.push(Action::Block {
                    event_id: id.into(),
                    reason: "EMERGENCY_PRICE_POLICY_UNRESOLVED".into(),
                }),
                _ => {}
            }
            return Ok(());
        }
        if t.hedge_trigger_mid2.is_some() {
            if let Residual::Reconciled { unhedged, .. } = t.book.reconciled_residual() {
                if unhedged > 0 && opp.is_some_and(|q| t.hedge_limit < q.ask) {
                    let order = spec(t, id, OrderRole::Hedge, t.hedge_limit, unhedged);
                    stage(t, id, order, out)?;
                }
            }
        } else if !t.entry_closed {
            let Some(q) = selected else { return Ok(()) };
            let price = if t.book.orders.is_empty() {
                78
            } else {
                t.last_entry_price.saturating_add(1).min(82)
            };
            if price >= q.ask {
                return Ok(());
            } // preserve maker intent
            if t.book
                .orders
                .iter()
                .flat_map(|o| &o.fills)
                .any(|f| f.fee_centicents.is_none())
            {
                return Ok(());
            }
            let spent = t
                .book
                .orders
                .iter()
                .filter(|o| o.spec.role == OrderRole::Entry)
                .flat_map(|o| &o.fills)
                .try_fold(0i64, |sum, f| {
                    i64::from(f.count)
                        .checked_mul(i64::from(f.yes_price_centicents))
                        .and_then(|v| v.checked_add(f.fee_centicents.unwrap()))
                        .and_then(|v| sum.checked_add(v))
                })
                .ok_or("CASHFLOW_OVERFLOW")?;
            let remaining = t.budget.acquisition_budget_cents as i64 * 100 - spent;
            if remaining < 0 {
                self.account_clean = false;
                return Err("ENTRY_BUDGET_BREACH".into());
            }
            let fee = self
                .policy
                .fee_model
                .order_fee_centicents(Liquidity::Maker, 1, price)
                .map_err(|e| format!("{e:?}"))?;
            let qty = u32::try_from(remaining / (i64::from(price) * 100 + fee))
                .map_err(|_| "QUANTITY_OVERFLOW")?;
            if qty > 0 {
                let order = spec(t, id, OrderRole::Entry, price, qty);
                t.last_entry_price = price;
                t.last_entry_ms = now;
                stage(t, id, order, out)?;
            }
        }
        Ok(())
    }
}
fn spec(t: &Trade, id: &str, role: OrderRole, price: u16, count: u32) -> OrderSpec {
    OrderSpec {
        client_order_id: format!("v1-{}-{}", id, t.book.orders.len()),
        role,
        ticker: if role == OrderRole::Hedge {
            t.book.opponent.clone()
        } else {
            t.book.original.clone()
        },
        side: BookSide::Bid,
        price_cents: price,
        count,
        tif: TimeInForce::GoodTillCanceled,
        post_only: true,
        reduce_only: false,
        expiration_ts: None,
        cancel_order_on_pause: true,
        subaccount: None,
    }
}
fn stage(t: &mut Trade, id: &str, order: OrderSpec, out: &mut Vec<Action>) -> Result<(), String> {
    t.book
        .orders
        .push(OrderRecord::new(order.clone()).map_err(|e| format!("{e:?}"))?);
    out.push(Action::Submit {
        event_id: id.into(),
        order,
    });
    Ok(())
}
pub fn window(sport: Sport, s: &SportsState) -> bool {
    s.status == "in"
        && match sport {
            Sport::NBA => s.period == 3 && s.clock_seconds <= 720,
            Sport::NCAAB => s.period == 2 && (600..=1200).contains(&s.clock_seconds),
        }
}
