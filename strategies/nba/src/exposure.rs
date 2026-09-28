//! Per-game exposure from confirmed fills only, plus the pure hedge and
//! emergency planners. An emergency sale is sized from a *reconciled*
//! residual: every order on both legs terminal, final counts known, fill
//! records received. Otherwise the planner cancels or waits; it never sells a
//! stale "unhedged quantity".

use serde::{Deserialize, Serialize};

use crate::orders::{BookSide, OrderRecord, OrderRole, OrderSpec, OrderStatus, TimeInForce};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct GameBook {
    pub event_ticker: String,
    pub original: String,
    pub opponent: String,
    pub orders: Vec<OrderRecord>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Exposure {
    /// Confirmed YES contracts held on the original market.
    pub original_long: i64,
    /// Confirmed YES contracts held on the opponent market.
    pub opponent_long: i64,
    pub hedged_pairs: i64,
    /// `original_long − opponent_long`. Negative = over-hedged.
    pub unhedged_original: i64,
    /// Unfilled quantity that could still fill, by leg and direction.
    pub potential_original_buy: u32,
    pub potential_original_sell: u32,
    pub potential_opponent_buy: u32,
    pub working: Vec<String>,
    pub unsettled: Vec<String>,
    pub inconsistent: Vec<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "residual", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Residual {
    Reconciled {
        original_long: u32,
        opponent_long: u32,
        unhedged: u32,
    },
    NotReconciled {
        reasons: Vec<String>,
    },
    OverHedged {
        excess: u32,
    },
    Inconsistent {
        reasons: Vec<String>,
    },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "policy", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum EmergencyPolicy {
    Unresolved,
    /// Reduce-only IOC sale of the reconciled original residual.
    SellOriginal {
        floor_cents: u16,
    },
    /// IOC buy of opponent YES for the reconciled residual.
    BuyOpponent {
        worst_price_cents: u16,
    },
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "step", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PlanStep {
    Hold {
        reason: String,
    },
    CancelWorking {
        client_order_ids: Vec<String>,
    },
    AwaitReconciliation {
        reasons: Vec<String>,
    },
    Submit(OrderSpec),
    /// Raise a resting hedge in place. `total_count` = already filled on that
    /// order + the reconciled need, so a race cannot over-hedge.
    Amend {
        client_order_id: String,
        price_cents: u16,
        total_count: u32,
    },
    /// No residual: every original contract is paired or gone.
    Flat {
        hedged_pairs: u32,
    },
    PolicyUnresolved {
        unhedged: u32,
    },
    Nothing,
}

fn signed(o: &OrderRecord) -> i64 {
    let n = i64::from(o.confirmed_filled());
    match o.spec.side {
        BookSide::Bid => n,
        BookSide::Ask => -n,
    }
}

fn why(o: &OrderRecord) -> String {
    let s = serde_json::to_value(&o.status)
        .ok()
        .and_then(|v| v.get("status").and_then(|x| x.as_str().map(str::to_string)))
        .unwrap_or_default();
    format!("{}:{}", o.spec.client_order_id, s)
}

impl GameBook {
    pub fn new(event_ticker: &str, original: &str, opponent: &str) -> Self {
        Self {
            event_ticker: event_ticker.into(),
            original: original.into(),
            opponent: opponent.into(),
            orders: Vec::new(),
        }
    }

    pub fn order(&self, client_order_id: &str) -> Option<&OrderRecord> {
        self.orders
            .iter()
            .find(|o| o.spec.client_order_id == client_order_id)
    }

    pub fn order_mut(&mut self, client_order_id: &str) -> Option<&mut OrderRecord> {
        self.orders
            .iter_mut()
            .find(|o| o.spec.client_order_id == client_order_id)
    }

    pub fn exposure(&self) -> Exposure {
        let mut e = Exposure {
            original_long: 0,
            opponent_long: 0,
            hedged_pairs: 0,
            unhedged_original: 0,
            potential_original_buy: 0,
            potential_original_sell: 0,
            potential_opponent_buy: 0,
            working: Vec::new(),
            unsettled: Vec::new(),
            inconsistent: Vec::new(),
        };
        for o in &self.orders {
            let on_original = o.spec.ticker == self.original;
            if on_original {
                e.original_long += signed(o);
            } else if o.spec.ticker == self.opponent {
                e.opponent_long += signed(o);
            } else {
                e.inconsistent
                    .push(format!("{}: foreign ticker", o.spec.client_order_id));
                continue;
            }
            let pot = o.potential_additional();
            match (on_original, o.spec.side) {
                (true, BookSide::Bid) => e.potential_original_buy += pot,
                (true, BookSide::Ask) => e.potential_original_sell += pot,
                (false, BookSide::Bid) => e.potential_opponent_buy += pot,
                (false, BookSide::Ask) => {}
            }
            match &o.status {
                OrderStatus::Inconsistent { .. } => e.inconsistent.push(why(o)),
                OrderStatus::Resting => e.working.push(o.spec.client_order_id.clone()),
                _ if !o.is_settled() => e.unsettled.push(why(o)),
                _ => {}
            }
        }
        e.hedged_pairs = e.original_long.min(e.opponent_long).max(0);
        e.unhedged_original = e.original_long - e.opponent_long;
        e
    }

    pub fn reconciled_residual(&self) -> Residual {
        let e = self.exposure();
        if !e.inconsistent.is_empty() {
            return Residual::Inconsistent {
                reasons: e.inconsistent,
            };
        }
        let mut reasons = e.unsettled.clone();
        reasons.extend(e.working.iter().map(|c| format!("{c}:RESTING")));
        if !reasons.is_empty() {
            return Residual::NotReconciled { reasons };
        }
        if e.original_long < 0 || e.opponent_long < 0 {
            return Residual::Inconsistent {
                reasons: vec!["negative leg".into()],
            };
        }
        if e.unhedged_original < 0 {
            return Residual::OverHedged {
                excess: u32::try_from(-e.unhedged_original).unwrap_or(u32::MAX),
            };
        }
        Residual::Reconciled {
            original_long: u32::try_from(e.original_long).unwrap_or(u32::MAX),
            opponent_long: u32::try_from(e.opponent_long).unwrap_or(u32::MAX),
            unhedged: u32::try_from(e.unhedged_original).unwrap_or(u32::MAX),
        }
    }

    /// Emergency path: cancel everything working, wait for every order to
    /// settle, then act on the reconciled residual only.
    pub fn plan_emergency(
        &self,
        policy: EmergencyPolicy,
        next_client_id: &str,
        subaccount: Option<u8>,
    ) -> PlanStep {
        let e = self.exposure();
        if !e.inconsistent.is_empty() {
            return PlanStep::Hold {
                reason: e.inconsistent.join(","),
            };
        }
        if !e.working.is_empty() {
            return PlanStep::CancelWorking {
                client_order_ids: e.working,
            };
        }
        match self.reconciled_residual() {
            Residual::Inconsistent { reasons } => PlanStep::Hold {
                reason: reasons.join(","),
            },
            Residual::NotReconciled { reasons } => PlanStep::AwaitReconciliation { reasons },
            Residual::OverHedged { excess } => PlanStep::Hold {
                reason: format!("over-hedged by {excess}; no automatic action"),
            },
            Residual::Reconciled {
                unhedged: 0,
                opponent_long,
                ..
            } => PlanStep::Flat {
                hedged_pairs: opponent_long,
            },
            Residual::Reconciled { unhedged, .. } => match policy {
                EmergencyPolicy::Unresolved => PlanStep::PolicyUnresolved { unhedged },
                EmergencyPolicy::SellOriginal { floor_cents } => PlanStep::Submit(OrderSpec {
                    client_order_id: next_client_id.into(),
                    role: OrderRole::Emergency,
                    ticker: self.original.clone(),
                    side: BookSide::Ask,
                    price_cents: floor_cents,
                    count: unhedged,
                    tif: TimeInForce::ImmediateOrCancel,
                    post_only: false,
                    reduce_only: true,
                    expiration_ts: None,
                    cancel_order_on_pause: false,
                    subaccount,
                }),
                EmergencyPolicy::BuyOpponent { worst_price_cents } => PlanStep::Submit(OrderSpec {
                    client_order_id: next_client_id.into(),
                    role: OrderRole::Emergency,
                    ticker: self.opponent.clone(),
                    side: BookSide::Bid,
                    price_cents: worst_price_cents,
                    count: unhedged,
                    tif: TimeInForce::ImmediateOrCancel,
                    post_only: false,
                    reduce_only: false,
                    expiration_ts: None,
                    cancel_order_on_pause: false,
                    subaccount,
                }),
            },
        }
    }

    /// Normal hedge path for the current ladder limit. Cancels a working entry
    /// first, waits on anything unsettled, then places or amends one resting
    /// opponent bid sized to the confirmed original position.
    pub fn plan_hedge(
        &self,
        limit_cents: u16,
        next_client_id: &str,
        subaccount: Option<u8>,
    ) -> PlanStep {
        let e = self.exposure();
        if !e.inconsistent.is_empty() {
            return PlanStep::Hold {
                reason: e.inconsistent.join(","),
            };
        }
        let working_entries: Vec<String> = self
            .orders
            .iter()
            .filter(|o| o.spec.role == OrderRole::Entry && o.status == OrderStatus::Resting)
            .map(|o| o.spec.client_order_id.clone())
            .collect();
        if !working_entries.is_empty() {
            return PlanStep::CancelWorking {
                client_order_ids: working_entries,
            };
        }
        if !e.unsettled.is_empty() {
            return PlanStep::AwaitReconciliation {
                reasons: e.unsettled,
            };
        }
        let resting_hedges: Vec<&OrderRecord> = self
            .orders
            .iter()
            .filter(|o| o.spec.ticker == self.opponent && o.status == OrderStatus::Resting)
            .collect();
        if resting_hedges.len() > 1 {
            return PlanStep::CancelWorking {
                client_order_ids: resting_hedges
                    .iter()
                    .map(|o| o.spec.client_order_id.clone())
                    .collect(),
            };
        }
        let need = e.unhedged_original;
        if need < 0 {
            return PlanStep::Hold {
                reason: format!("over-hedged by {}", -need),
            };
        }
        let need = u32::try_from(need).unwrap_or(u32::MAX);
        match resting_hedges.first() {
            None if need == 0 => PlanStep::Flat {
                hedged_pairs: u32::try_from(e.hedged_pairs).unwrap_or(u32::MAX),
            },
            None => PlanStep::Submit(OrderSpec {
                client_order_id: next_client_id.into(),
                role: OrderRole::Hedge,
                ticker: self.opponent.clone(),
                side: BookSide::Bid,
                price_cents: limit_cents,
                count: need,
                tif: TimeInForce::GoodTillCanceled,
                post_only: false,
                reduce_only: false,
                expiration_ts: None,
                cancel_order_on_pause: false,
                subaccount,
            }),
            Some(h) => {
                let own = h.confirmed_filled();
                let resting = h.max_count.saturating_sub(own);
                // `need` already counts this order's fills as hedged.
                let price = h.spec.price_cents.max(limit_cents);
                if resting == need && price == h.spec.price_cents {
                    PlanStep::Nothing
                } else if need == 0 {
                    PlanStep::CancelWorking {
                        client_order_ids: vec![h.spec.client_order_id.clone()],
                    }
                } else {
                    PlanStep::Amend {
                        client_order_id: h.spec.client_order_id.clone(),
                        price_cents: price,
                        total_count: own + need,
                    }
                }
            }
        }
    }
}
