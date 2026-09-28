//! One venue order, driven only by venue evidence. A submitted order is not a
//! fill; a cancel request is not a cancel; a timeout is `Unknown`, never
//! `Rejected`. Fills are deduplicated by `fill_id` and capped by the order's
//! maximum fillable count. Late fills after a cancel request are accepted up
//! to that cap and counted separately.

use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum OrderRole {
    Entry,
    Hedge,
    Emergency,
}

/// Kalshi V2 `side`: `bid` buys YES, `ask` sells YES.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BookSide {
    Bid,
    Ask,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TimeInForce {
    GoodTillCanceled,
    ImmediateOrCancel,
    FillOrKill,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct OrderSpec {
    pub client_order_id: String,
    pub role: OrderRole,
    pub ticker: String,
    pub side: BookSide,
    /// Limit in whole cents, 1..=99.
    pub price_cents: u16,
    pub count: u32,
    pub tif: TimeInForce,
    pub post_only: bool,
    pub reduce_only: bool,
    /// Unix seconds. Only with `GoodTillCanceled`.
    pub expiration_ts: Option<i64>,
    pub cancel_order_on_pause: bool,
    pub subaccount: Option<u8>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum SpecError {
    ClientIdInvalid,
    PriceOutOfRange(u16),
    ZeroCount,
    ReduceOnlyRequiresIoc,
    ExpirationRequiresGtc,
    PostOnlyWithImmediate,
    SubaccountOutOfRange(u8),
}

impl OrderSpec {
    pub fn validate(&self) -> Result<(), SpecError> {
        let id = &self.client_order_id;
        if id.is_empty()
            || id.len() > 64
            || !id
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
        {
            return Err(SpecError::ClientIdInvalid);
        }
        if !(1..=99).contains(&self.price_cents) {
            return Err(SpecError::PriceOutOfRange(self.price_cents));
        }
        if self.count == 0 {
            return Err(SpecError::ZeroCount);
        }
        if self.reduce_only && self.tif != TimeInForce::ImmediateOrCancel {
            return Err(SpecError::ReduceOnlyRequiresIoc);
        }
        if self.expiration_ts.is_some() && self.tif != TimeInForce::GoodTillCanceled {
            return Err(SpecError::ExpirationRequiresGtc);
        }
        if self.post_only && self.tif != TimeInForce::GoodTillCanceled {
            return Err(SpecError::PostOnlyWithImmediate);
        }
        if let Some(s) = self.subaccount
            && s > 63
        {
            return Err(SpecError::SubaccountOutOfRange(s));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Fill {
    pub fill_id: String,
    pub count: u32,
    /// YES price in centicents (Kalshi `yes_price_dollars` × 10⁴).
    pub yes_price_centicents: u32,
    pub is_taker: Option<bool>,
    /// Kalshi `fee_cost` in centicents. `None` = unread, never 0.
    pub fee_centicents: Option<i64>,
    pub ts: i64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum VenueStatus {
    Resting,
    Canceled,
    Executed,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum OrderStatus {
    /// Journaled locally; not yet sent.
    Staged,
    /// Create request in flight. Persisted before the request is sent.
    Sending,
    Resting,
    /// Cancel requested; the order can still fill until confirmed.
    CancelRequested,
    Filled,
    /// Canceled, expired, or IOC remainder. May carry partial fills.
    Cancelled,
    Rejected {
        http_status: u16,
        code: String,
    },
    /// Refused before any request left the process.
    NotSent {
        reason: String,
    },
    /// Venue state unknown. Must reconcile before any dependent action.
    Unknown {
        reason: String,
    },
    /// Evidence contradicts itself (e.g. overfill). Hold; never auto-repair.
    Inconsistent {
        reason: String,
    },
}

impl OrderStatus {
    pub fn is_terminal(&self) -> bool {
        matches!(
            self,
            OrderStatus::Filled
                | OrderStatus::Cancelled
                | OrderStatus::Rejected { .. }
                | OrderStatus::NotSent { .. }
        )
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "event", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum OrderEvent {
    Sending,
    Acked {
        venue_order_id: String,
        fill_count: u32,
        remaining_count: u32,
    },
    Rejected {
        http_status: u16,
        code: String,
    },
    Ambiguous {
        reason: String,
    },
    LocalRefusal {
        reason: String,
    },
    Fill(Fill),
    CancelSent,
    /// `reduced_by` = contracts still resting when the cancel was processed.
    CancelAcked {
        reduced_by: u32,
    },
    /// Cancel returned 404: the order is no longer resting (filled, canceled,
    /// or expired). The final fill count is unknown until a snapshot.
    CancelNotFound,
    /// Venue accepted an amend. The response's counts are not order totals
    /// (`fill_count` is fills caused by the amend only, and both counts are
    /// omitted when the size did not change), so counts come from the next
    /// snapshot.
    Amended {
        price_cents: u16,
        max_count: u32,
        client_order_id: Option<String>,
    },
    /// The amend's outcome is unknown: the venue total is now either the
    /// prior total or `requested_total` until a snapshot shows which.
    AmendAmbiguous {
        requested_total: u32,
        reason: String,
    },
    /// GET order / list result. A resting snapshot may lag (demo: about 1 s
    /// after create or amend); a canceled or executed one is final.
    Snapshot {
        venue_order_id: String,
        status: VenueStatus,
        fill_count: u32,
        remaining_count: u32,
    },
    /// Reconciliation proved the create never reached the book.
    NotFoundOnVenue,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderError {
    InvalidTransition { from: String, event: String },
    Overfill { max: u32, would_be: u32 },
    Contradiction(String),
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct OrderTransition {
    pub at: i64,
    pub event: String,
    pub to: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct OrderRecord {
    pub spec: OrderSpec,
    pub status: OrderStatus,
    pub venue_order_id: Option<String>,
    /// Current maximum fillable count (changes only through an amend).
    pub max_count: u32,
    /// Venue-reported cumulative fill count.
    pub venue_fill_count: u32,
    /// True once the venue has reported a final count for a terminal order.
    pub final_count_known: bool,
    pub fills: Vec<Fill>,
    fill_ids: BTreeSet<String>,
    /// Contracts filled after a cancel request was sent.
    pub late_fill_count: u32,
    /// Set while an amend's outcome is unknown. `max_count` then holds the
    /// larger of the two possible totals.
    #[serde(default)]
    pub amend_unresolved: Option<UnresolvedAmend>,
    pub history: Vec<OrderTransition>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct UnresolvedAmend {
    pub prior_total: u32,
    pub requested_total: u32,
}

fn label<T: Serialize>(v: &T) -> String {
    serde_json::to_value(v)
        .ok()
        .and_then(|j| {
            j.get("status")
                .or_else(|| j.get("event"))
                .and_then(|s| s.as_str().map(str::to_string))
        })
        .unwrap_or_else(|| "?".into())
}

impl OrderRecord {
    pub fn new(spec: OrderSpec) -> Result<Self, SpecError> {
        spec.validate()?;
        Ok(Self {
            max_count: spec.count,
            spec,
            status: OrderStatus::Staged,
            venue_order_id: None,
            venue_fill_count: 0,
            final_count_known: false,
            fills: Vec::new(),
            fill_ids: BTreeSet::new(),
            late_fill_count: 0,
            amend_unresolved: None,
            history: Vec::new(),
        })
    }

    pub fn fill_record_count(&self) -> u32 {
        self.fills.iter().map(|f| f.count).sum()
    }

    /// Contracts confirmed filled (venue count or fill records, whichever is
    /// higher; both come from the venue).
    pub fn confirmed_filled(&self) -> u32 {
        self.venue_fill_count.max(self.fill_record_count())
    }

    /// Contracts that could still fill. For `Unknown` the whole unfilled
    /// count is treated as live.
    pub fn potential_additional(&self) -> u32 {
        match self.status {
            OrderStatus::Filled
            | OrderStatus::Cancelled
            | OrderStatus::Rejected { .. }
            | OrderStatus::NotSent { .. } => 0,
            _ => self.max_count.saturating_sub(self.confirmed_filled()),
        }
    }

    /// Terminal with a known final count and every fill record received.
    pub fn is_settled(&self) -> bool {
        match self.status {
            OrderStatus::Rejected { .. } | OrderStatus::NotSent { .. } => {
                self.fill_record_count() == 0
            }
            OrderStatus::Filled | OrderStatus::Cancelled => {
                self.final_count_known && self.fill_record_count() == self.venue_fill_count
            }
            _ => false,
        }
    }

    fn set(&mut self, at: i64, event: &OrderEvent, to: OrderStatus) {
        self.history.push(OrderTransition {
            at,
            event: label(event),
            to: label(&to),
        });
        self.status = to;
    }

    fn invalid(&self, event: &OrderEvent) -> OrderError {
        OrderError::InvalidTransition {
            from: label(&self.status),
            event: label(event),
        }
    }

    fn hold(&mut self, at: i64, event: &OrderEvent, reason: String) -> OrderError {
        self.set(
            at,
            event,
            OrderStatus::Inconsistent {
                reason: reason.clone(),
            },
        );
        OrderError::Contradiction(reason)
    }

    fn after_counts(&self, remaining: u32) -> OrderStatus {
        if remaining > 0 {
            if matches!(self.status, OrderStatus::CancelRequested) {
                OrderStatus::CancelRequested
            } else {
                OrderStatus::Resting
            }
        } else if self.confirmed_filled() >= self.max_count {
            OrderStatus::Filled
        } else {
            OrderStatus::Cancelled
        }
    }

    pub fn apply(&mut self, at: i64, event: OrderEvent) -> Result<(), OrderError> {
        if matches!(self.status, OrderStatus::Inconsistent { .. }) {
            // Evidence is still recorded, but the status never auto-repairs.
            if let OrderEvent::Fill(f) = &event
                && self.fill_ids.insert(f.fill_id.clone())
            {
                self.fills.push(f.clone());
            }
            return Err(self.invalid(&event));
        }
        match &event {
            OrderEvent::Sending => match self.status {
                OrderStatus::Staged => self.set(at, &event, OrderStatus::Sending),
                _ => return Err(self.invalid(&event)),
            },
            OrderEvent::LocalRefusal { reason } => match self.status {
                OrderStatus::Staged | OrderStatus::Sending => self.set(
                    at,
                    &event,
                    OrderStatus::NotSent {
                        reason: reason.clone(),
                    },
                ),
                _ => return Err(self.invalid(&event)),
            },
            OrderEvent::Acked {
                venue_order_id,
                fill_count,
                remaining_count,
            } => {
                if !matches!(
                    self.status,
                    OrderStatus::Sending | OrderStatus::Unknown { .. }
                ) {
                    return Err(self.invalid(&event));
                }
                if fill_count + remaining_count > self.max_count {
                    let r = format!(
                        "ack fill {fill_count} + remaining {remaining_count} > {}",
                        self.max_count
                    );
                    return Err(self.hold(at, &event, r));
                }
                self.venue_order_id = Some(venue_order_id.clone());
                self.venue_fill_count = self.venue_fill_count.max(*fill_count);
                if *remaining_count == 0 {
                    self.final_count_known = true;
                }
                let to = self.after_counts(*remaining_count);
                self.set(at, &event, to);
            }
            OrderEvent::Rejected { http_status, code } => match self.status {
                OrderStatus::Sending | OrderStatus::Unknown { .. } => {
                    if self.confirmed_filled() > 0 {
                        return Err(self.hold(at, &event, "rejected after fills".into()));
                    }
                    self.set(
                        at,
                        &event,
                        OrderStatus::Rejected {
                            http_status: *http_status,
                            code: code.clone(),
                        },
                    );
                }
                _ => return Err(self.invalid(&event)),
            },
            OrderEvent::Ambiguous { reason } => {
                if self.status.is_terminal() {
                    return Err(self.invalid(&event));
                }
                self.set(
                    at,
                    &event,
                    OrderStatus::Unknown {
                        reason: reason.clone(),
                    },
                );
            }
            OrderEvent::Fill(f) => {
                if !self.fill_ids.insert(f.fill_id.clone()) {
                    return Ok(());
                }
                if matches!(
                    self.status,
                    OrderStatus::Rejected { .. }
                        | OrderStatus::NotSent { .. }
                        | OrderStatus::Staged
                ) {
                    self.fills.push(f.clone());
                    return Err(self.hold(at, &event, "fill on an order that never rested".into()));
                }
                let would_be = self.fill_record_count() + f.count;
                self.fills.push(f.clone());
                if would_be > self.max_count {
                    let max = self.max_count;
                    self.hold(at, &event, format!("overfill {would_be} > {max}"));
                    return Err(OrderError::Overfill { max, would_be });
                }
                if matches!(
                    self.status,
                    OrderStatus::CancelRequested | OrderStatus::Cancelled
                ) {
                    self.late_fill_count += f.count;
                }
                if self.final_count_known && would_be > self.venue_fill_count {
                    return Err(self.hold(
                        at,
                        &event,
                        format!(
                            "fill records {would_be} exceed final count {}",
                            self.venue_fill_count
                        ),
                    ));
                }
                if matches!(self.status, OrderStatus::Resting) && would_be >= self.max_count {
                    self.venue_fill_count = self.venue_fill_count.max(would_be);
                    self.final_count_known = true;
                    self.set(at, &event, OrderStatus::Filled);
                }
            }
            OrderEvent::CancelSent => match self.status {
                OrderStatus::Resting | OrderStatus::Unknown { .. }
                    if self.venue_order_id.is_some() =>
                {
                    self.set(at, &event, OrderStatus::CancelRequested)
                }
                _ => return Err(self.invalid(&event)),
            },
            OrderEvent::CancelAcked { reduced_by } => match self.status {
                OrderStatus::CancelRequested
                | OrderStatus::Resting
                | OrderStatus::Unknown { .. } => {
                    if let Some(u) = self.amend_unresolved {
                        // Fills = total - reduced_by, and the total is one of two
                        // values; only a final snapshot settles it.
                        let floor = u.prior_total.min(u.requested_total);
                        self.venue_fill_count =
                            self.venue_fill_count.max(floor.saturating_sub(*reduced_by));
                        self.set(
                            at,
                            &event,
                            OrderStatus::Unknown {
                                reason: format!(
                                    "cancel reduced_by {reduced_by} with amend unresolved \
                                     (total {} or {}); final count unread",
                                    u.prior_total, u.requested_total
                                ),
                            },
                        );
                        return Ok(());
                    }
                    let final_fill = self.max_count.saturating_sub(*reduced_by);
                    if *reduced_by > self.max_count || final_fill < self.fill_record_count() {
                        let r = format!(
                            "cancel reduced_by {reduced_by}, max {}, fill records {}",
                            self.max_count,
                            self.fill_record_count()
                        );
                        return Err(self.hold(at, &event, r));
                    }
                    self.venue_fill_count = final_fill;
                    self.final_count_known = true;
                    let to = if final_fill >= self.max_count {
                        OrderStatus::Filled
                    } else {
                        OrderStatus::Cancelled
                    };
                    self.set(at, &event, to);
                }
                _ => return Err(self.invalid(&event)),
            },
            OrderEvent::CancelNotFound => {
                if self.status.is_terminal() {
                    return Ok(());
                }
                self.set(
                    at,
                    &event,
                    OrderStatus::Unknown {
                        reason: "cancel 404: not resting; final count unread".into(),
                    },
                );
            }
            OrderEvent::Amended {
                price_cents,
                max_count,
                client_order_id,
            } => {
                if !matches!(self.status, OrderStatus::Resting) {
                    return Err(self.invalid(&event));
                }
                if *max_count < self.confirmed_filled() {
                    let r = format!(
                        "amend total {max_count} below confirmed fills {}",
                        self.confirmed_filled()
                    );
                    return Err(self.hold(at, &event, r));
                }
                self.spec.price_cents = *price_cents;
                self.max_count = *max_count;
                self.amend_unresolved = None;
                if let Some(id) = client_order_id {
                    self.spec.client_order_id = id.clone();
                }
                self.set(at, &event, OrderStatus::Resting);
            }
            OrderEvent::AmendAmbiguous {
                requested_total,
                reason,
            } => {
                if !matches!(self.status, OrderStatus::Resting) {
                    return Err(self.invalid(&event));
                }
                if *requested_total != self.max_count {
                    let prior_total = match self.amend_unresolved {
                        Some(u) => u.prior_total.max(u.requested_total),
                        None => self.max_count,
                    };
                    self.amend_unresolved = Some(UnresolvedAmend {
                        prior_total,
                        requested_total: *requested_total,
                    });
                    self.max_count = self.max_count.max(*requested_total);
                }
                self.set(
                    at,
                    &event,
                    OrderStatus::Unknown {
                        reason: reason.clone(),
                    },
                );
            }
            OrderEvent::Snapshot {
                venue_order_id,
                status,
                fill_count,
                remaining_count,
            } => {
                if matches!(
                    self.status,
                    OrderStatus::Rejected { .. } | OrderStatus::NotSent { .. }
                ) {
                    return Err(self.hold(at, &event, "order found after rejection".into()));
                }
                if let Some(known) = &self.venue_order_id
                    && known != venue_order_id
                {
                    return Err(self.hold(at, &event, "snapshot order id mismatch".into()));
                }
                // This bot is the only writer of its orders, so the venue total
                // never exceeds max_count.
                if *fill_count > self.max_count {
                    let r = format!("snapshot fill {fill_count} > max {}", self.max_count);
                    return Err(self.hold(at, &event, r));
                }
                self.venue_order_id = Some(venue_order_id.clone());
                let total = fill_count + remaining_count;
                match status {
                    VenueStatus::Resting => {
                        let known_final = self.final_count_known
                            && matches!(self.status, OrderStatus::Cancelled | OrderStatus::Filled);
                        let resolves_amend = self
                            .amend_unresolved
                            .is_some_and(|u| total == u.requested_total);
                        let stale = known_final
                            || *fill_count < self.venue_fill_count
                            || (total > self.max_count && !resolves_amend);
                        if stale {
                            // An older read than evidence already applied.
                            return Ok(());
                        }
                        if resolves_amend {
                            self.max_count = total;
                            self.amend_unresolved = None;
                        }
                        if *fill_count < self.fill_record_count() {
                            // Fill records are newer than this read.
                            return Ok(());
                        }
                        self.venue_fill_count = *fill_count;
                        let to = self.after_counts((*remaining_count).max(1));
                        self.set(at, &event, to);
                    }
                    VenueStatus::Canceled | VenueStatus::Executed => {
                        if self.final_count_known && *fill_count != self.venue_fill_count {
                            let r = format!(
                                "final snapshot fill {fill_count} != final count {}",
                                self.venue_fill_count
                            );
                            return Err(self.hold(at, &event, r));
                        }
                        if *fill_count < self.venue_fill_count {
                            let r = format!(
                                "final snapshot fill {fill_count} < confirmed {}",
                                self.venue_fill_count
                            );
                            return Err(self.hold(at, &event, r));
                        }
                        if *fill_count < self.fill_record_count() {
                            self.set(
                                at,
                                &event,
                                OrderStatus::Unknown {
                                    reason: "fill records exceed snapshot; re-read".into(),
                                },
                            );
                            return Ok(());
                        }
                        if matches!(status, VenueStatus::Executed) {
                            let possible = match self.amend_unresolved {
                                Some(u) => total == u.prior_total || total == u.requested_total,
                                None => total == self.max_count,
                            };
                            if !possible {
                                let r = format!(
                                    "executed total {total} not a known total (max {})",
                                    self.max_count
                                );
                                return Err(self.hold(at, &event, r));
                            }
                            self.max_count = total;
                        }
                        self.amend_unresolved = None;
                        self.venue_fill_count = *fill_count;
                        self.final_count_known = true;
                        let to = if matches!(status, VenueStatus::Executed) {
                            OrderStatus::Filled
                        } else {
                            OrderStatus::Cancelled
                        };
                        self.set(at, &event, to);
                    }
                }
            }
            OrderEvent::NotFoundOnVenue => match self.status {
                OrderStatus::Sending | OrderStatus::Unknown { .. }
                    if self.venue_order_id.is_none() && self.confirmed_filled() == 0 =>
                {
                    self.set(
                        at,
                        &event,
                        OrderStatus::Rejected {
                            http_status: 0,
                            code: "NOT_FOUND_ON_VENUE".into(),
                        },
                    )
                }
                _ => return Err(self.hold(at, &event, "not found but evidence exists".into())),
            },
        }
        Ok(())
    }
}
