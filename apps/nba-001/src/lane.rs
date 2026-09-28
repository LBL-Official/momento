//! Execution lane: turns planner output into adapter calls for one venue.
//! Every owner decision is an explicit `LanePolicy` field; `None` makes the
//! lane hold (`POLICY_UNRESOLVED`) instead of inventing behaviour. The
//! production worker holds no lane in this build (no production permit).

use std::collections::BTreeMap;

use momento_core::Contracts;
use momento_kalshi::KalshiTransport;
use momento_strategy_nba::{
    BookSide, EmergencyPolicy, GameBook, HedgeAction, HedgePlanner, LADDER_CAP_CENTS, OrderRole,
    OrderSpec, PlanStep, STOP_CENTS, TimeInForce,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::executor::{self, ExecError, Sink};
use crate::venue::NbaVenue;

/// First hedge limit when the first close at or below 67 is lower than 67.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum GapPolicy {
    /// `100 − observed close` (60 → 40), capped at 45.
    ObservedClose,
    /// Always start at 33, then follow the ladder.
    FirstRung,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum LadderPolicy {
    /// Raise the resting limit to `100 − close` at each later quality close.
    RepriceOnClose,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "action", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum OutageAction {
    /// Raise the hedge for the reconciled residual to the 45 cap.
    HedgeAtCap,
    /// Run the emergency policy.
    Emergency,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct OutagePolicy {
    pub escalate_after_s: i64,
    pub action: OutageAction,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct LanePolicy {
    pub entry_post_only: bool,
    pub entry_expiry_s: Option<i64>,
    pub gap: Option<GapPolicy>,
    pub ladder: Option<LadderPolicy>,
    pub emergency: EmergencyPolicy,
    pub outage: Option<OutagePolicy>,
    pub subaccount: Option<u8>,
}

impl LanePolicy {
    /// Every owner decision unresolved.
    pub fn unresolved() -> Self {
        Self {
            entry_post_only: true,
            entry_expiry_s: None,
            gap: None,
            ladder: None,
            emergency: EmergencyPolicy::Unresolved,
            outage: None,
            subaccount: None,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "exec", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum GameExec {
    Entering,
    Holding,
    Hedging { limit_cents: u16 },
    Emergency,
    Flat,
    Hold { reason: String },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GameLane {
    pub book: GameBook,
    pub planner: HedgePlanner,
    pub exec: GameExec,
    pub seq: u32,
}

pub struct ExecutionLane<T: KalshiTransport> {
    pub venue: NbaVenue<T>,
    pub games: BTreeMap<String, GameLane>,
    pub policy: LanePolicy,
    /// Client-id namespace. Production ids are deterministic per event, role,
    /// and sequence so a retry after lost state collides (409) instead of
    /// duplicating; demo runs add a run id.
    pub id_namespace: String,
}

fn client_id(namespace: &str, event: &str, role: &str, seq: u32) -> String {
    let d = Sha256::digest(format!("{namespace}|{event}|{role}|{seq}").as_bytes());
    let hex: String = d.iter().take(8).map(|b| format!("{b:02x}")).collect();
    format!("{}{hex}", crate::account::CLIENT_ID_PREFIX)
}

fn hold(reason: &str) -> GameExec {
    GameExec::Hold {
        reason: reason.into(),
    }
}

impl<T: KalshiTransport> ExecutionLane<T> {
    pub fn new(venue: NbaVenue<T>, policy: LanePolicy) -> Self {
        Self {
            venue,
            games: BTreeMap::new(),
            policy,
            id_namespace: "nba-001".into(),
        }
    }

    fn next_id(namespace: &str, g: &mut GameLane, event: &str, role: &str) -> String {
        g.seq += 1;
        client_id(namespace, event, role, g.seq)
    }

    pub fn enter(
        &mut self,
        event: &str,
        original: &str,
        opponent: &str,
        qty: u32,
        now: i64,
        sink: &mut Sink<'_>,
    ) -> Result<(), ExecError> {
        if self.games.contains_key(event) {
            return Err(ExecError::Refused("one entry per game".into()));
        }
        let mut g = GameLane {
            book: GameBook::new(event, original, opponent),
            planner: HedgePlanner::default(),
            exec: GameExec::Entering,
            seq: 0,
        };
        let spec = OrderSpec {
            client_order_id: Self::next_id(&self.id_namespace, &mut g, event, "entry"),
            role: OrderRole::Entry,
            ticker: original.into(),
            side: BookSide::Bid,
            price_cents: momento_strategy_nba::ENTRY_CENTS,
            count: qty,
            tif: TimeInForce::GoodTillCanceled,
            post_only: self.policy.entry_post_only,
            reduce_only: false,
            expiration_ts: self.policy.entry_expiry_s.map(|s| now + s),
            cancel_order_on_pause: true,
            subaccount: self.policy.subaccount,
        };
        let r = executor::submit(&mut g.book, &mut self.venue, spec, now, sink);
        self.games.insert(event.into(), g);
        r
    }

    /// One quality original-YES close after entry. Changes intent only; the
    /// next `step` acts on it.
    #[cfg_attr(not(test), allow(dead_code))]
    pub fn on_close(&mut self, event: &str, close: u16) -> Option<HedgeAction> {
        let policy = self.policy;
        let g = self.games.get_mut(event)?;
        if matches!(g.exec, GameExec::Hold { .. } | GameExec::Emergency) {
            return None;
        }
        let e = g.book.exposure();
        let remaining = u32::try_from((e.original_long - e.opponent_long).max(0)).unwrap_or(0)
            + e.potential_original_buy;
        let action = g.planner.on_close(close, Contracts::from_u32(remaining));
        g.exec = match (&action, &g.exec) {
            (HedgeAction::TriggerProposal { limit_cents, .. }, _) => match policy.gap {
                Some(GapPolicy::ObservedClose) => GameExec::Hedging {
                    limit_cents: *limit_cents,
                },
                Some(GapPolicy::FirstRung) => GameExec::Hedging {
                    limit_cents: 100 - STOP_CENTS,
                },
                None => hold("POLICY_UNRESOLVED:hedge_initial_limit_gap_policy"),
            },
            (
                HedgeAction::LadderProposal { limit_cents, .. },
                GameExec::Hedging { limit_cents: cur },
            ) => match policy.ladder {
                Some(LadderPolicy::RepriceOnClose) => GameExec::Hedging {
                    limit_cents: (*cur).max(*limit_cents).min(LADDER_CAP_CENTS),
                },
                None => hold("POLICY_UNRESOLVED:hedge_ladder_advancement"),
            },
            (HedgeAction::MarketDumpUnresolved { .. }, _) => GameExec::Emergency,
            (_, other) => other.clone(),
        };
        if matches!(g.exec, GameExec::Entering) && g.planner.triggered() {
            g.exec = hold("triggered while entering");
        }
        Some(action)
    }

    /// Candle/clock/account feed stale for `stale_s` with a position open.
    #[cfg_attr(not(test), allow(dead_code))]
    pub fn on_outage(&mut self, event: &str, stale_s: i64) {
        let policy = self.policy;
        let Some(g) = self.games.get_mut(event) else {
            return;
        };
        if matches!(
            g.exec,
            GameExec::Flat | GameExec::Emergency | GameExec::Hold { .. }
        ) {
            return;
        }
        match policy.outage {
            None => g.exec = hold("POLICY_UNRESOLVED:data_outage_policy"),
            Some(o) if stale_s >= o.escalate_after_s => {
                g.exec = match o.action {
                    OutageAction::HedgeAtCap => GameExec::Hedging {
                        limit_cents: LADDER_CAP_CENTS,
                    },
                    OutageAction::Emergency => GameExec::Emergency,
                }
            }
            Some(_) => {}
        }
    }

    /// Reconcile, then perform at most one planner step for the game.
    pub fn step(
        &mut self,
        event: &str,
        now: i64,
        sink: &mut Sink<'_>,
    ) -> Result<PlanStep, ExecError> {
        let policy = self.policy;
        let ns = self.id_namespace.clone();
        let venue = &mut self.venue;
        let g = self
            .games
            .get_mut(event)
            .ok_or_else(|| ExecError::UnknownClientId(event.into()))?;
        let errs = executor::reconcile_book(&mut g.book, venue, now, sink);
        if let Some((_, e)) = errs.into_iter().next() {
            if matches!(e, ExecError::Order(_)) {
                g.exec = hold("ORDER_INCONSISTENT");
            }
            return Err(e);
        }
        let plan = match &g.exec {
            GameExec::Entering => {
                let e = g.book.exposure();
                if e.working.is_empty() && e.unsettled.is_empty() {
                    g.exec = if e.original_long > 0 {
                        GameExec::Holding
                    } else {
                        GameExec::Flat
                    };
                }
                PlanStep::Nothing
            }
            GameExec::Holding | GameExec::Flat => PlanStep::Nothing,
            GameExec::Hold { reason } => PlanStep::Hold {
                reason: reason.clone(),
            },
            GameExec::Hedging { limit_cents } => {
                let id = client_id(&ns, event, "hedge", g.seq + 1);
                g.book.plan_hedge(*limit_cents, &id, policy.subaccount)
            }
            GameExec::Emergency => {
                let id = client_id(&ns, event, "emergency", g.seq + 1);
                g.book
                    .plan_emergency(policy.emergency, &id, policy.subaccount)
            }
        };
        match &plan {
            PlanStep::Submit(spec) => {
                g.seq += 1;
                executor::submit(&mut g.book, venue, spec.clone(), now, sink)?;
            }
            PlanStep::Amend {
                client_order_id,
                price_cents,
                total_count,
            } => executor::amend(
                &mut g.book,
                venue,
                client_order_id,
                *price_cents,
                *total_count,
                now,
                sink,
            )?,
            PlanStep::CancelWorking { client_order_ids } => {
                for c in client_order_ids {
                    executor::cancel(&mut g.book, venue, c, now, sink)?;
                }
            }
            PlanStep::Flat { .. } => g.exec = GameExec::Flat,
            PlanStep::PolicyUnresolved { .. } => {
                g.exec = hold("POLICY_UNRESOLVED:emergency_action");
            }
            PlanStep::Hold { reason } => g.exec = hold(reason),
            PlanStep::AwaitReconciliation { .. } | PlanStep::Nothing => {}
        }
        Ok(plan)
    }
}
