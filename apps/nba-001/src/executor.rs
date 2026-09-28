//! Drives a game's orders through the venue. Every mutation is persisted
//! (`BeforeSend`) before the request leaves; if persistence fails nothing is
//! sent. Ambiguous outcomes become `Unknown` and are reconciled by venue id
//! or client order id before any dependent action. Nothing here decides
//! trading behaviour; the pure planners in `momento_strategy_nba` do.

use momento_kalshi::KalshiTransport;
use momento_strategy_nba::{
    GameBook, OrderError, OrderEvent, OrderRecord, OrderSpec, OrderStatus, SpecError,
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

use crate::venue::{AmendOutcome, CancelOutcome, CreateOutcome, NbaVenue, ReadError};

/// An order not found by client id this long after it was sent is treated as
/// never accepted. Later sightings still hold the game (ghost check).
pub const NOT_FOUND_GRACE_S: i64 = 10;
/// Ghost orders are re-checked for this long after being declared absent.
pub const GHOST_WATCH_S: i64 = 600;
/// A known order id may 404 on `GET` right after a mutation (demo: ~1 s).
/// Within this window that is "not yet visible"; after it, an error.
pub const READ_VISIBILITY_GRACE_S: i64 = 15;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ExecError {
    Spec(SpecError),
    DuplicateClientId(String),
    UnknownClientId(String),
    NoVenueOrderId(String),
    Refused(String),
    Persist(String),
    Order(OrderError),
    Read(ReadError),
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ExecEvent {
    /// Persist the book now; a failure aborts the send.
    BeforeSend {
        client_order_id: String,
        action: String,
    },
    /// Journal only.
    Outcome {
        client_order_id: String,
        action: String,
        detail: Value,
    },
}

pub type Sink<'a> = dyn FnMut(&GameBook, ExecEvent) -> Result<(), String> + 'a;

fn apply(book: &mut GameBook, cid: &str, at: i64, ev: OrderEvent) -> Result<(), ExecError> {
    let o = book
        .order_mut(cid)
        .ok_or_else(|| ExecError::UnknownClientId(cid.into()))?;
    o.apply(at, ev).map_err(ExecError::Order)
}

fn outcome(sink: &mut Sink<'_>, book: &GameBook, cid: &str, action: &str, detail: Value) {
    let _ = sink(
        book,
        ExecEvent::Outcome {
            client_order_id: cid.into(),
            action: action.into(),
            detail,
        },
    );
}

pub fn submit<T: KalshiTransport>(
    book: &mut GameBook,
    venue: &mut NbaVenue<T>,
    spec: OrderSpec,
    now: i64,
    sink: &mut Sink<'_>,
) -> Result<(), ExecError> {
    let cid = spec.client_order_id.clone();
    if book.order(&cid).is_some() {
        return Err(ExecError::DuplicateClientId(cid));
    }
    let record = OrderRecord::new(spec.clone()).map_err(ExecError::Spec)?;
    book.orders.push(record);
    apply(book, &cid, now, OrderEvent::Sending)?;
    if let Err(e) = sink(
        book,
        ExecEvent::BeforeSend {
            client_order_id: cid.clone(),
            action: "CREATE".into(),
        },
    ) {
        apply(
            book,
            &cid,
            now,
            OrderEvent::LocalRefusal {
                reason: format!("persist failed: {e}"),
            },
        )?;
        return Err(ExecError::Persist(e));
    }
    let result = venue.create(&spec);
    let ev = match &result {
        CreateOutcome::Acked {
            venue_order_id,
            fill_count,
            remaining_count,
        } => OrderEvent::Acked {
            venue_order_id: venue_order_id.clone(),
            fill_count: *fill_count,
            remaining_count: *remaining_count,
        },
        CreateOutcome::Rejected { http_status, code } => OrderEvent::Rejected {
            http_status: *http_status,
            code: code.clone(),
        },
        CreateOutcome::Ambiguous { reason } => OrderEvent::Ambiguous {
            reason: reason.clone(),
        },
        CreateOutcome::NotSent { reason } => OrderEvent::LocalRefusal {
            reason: reason.clone(),
        },
    };
    let applied = apply(book, &cid, now, ev);
    outcome(sink, book, &cid, "CREATE", json!(result));
    applied
}

pub fn cancel<T: KalshiTransport>(
    book: &mut GameBook,
    venue: &mut NbaVenue<T>,
    cid: &str,
    now: i64,
    sink: &mut Sink<'_>,
) -> Result<(), ExecError> {
    let o = book
        .order(cid)
        .ok_or_else(|| ExecError::UnknownClientId(cid.into()))?;
    let vid = o
        .venue_order_id
        .clone()
        .ok_or_else(|| ExecError::NoVenueOrderId(cid.into()))?;
    let ticker = o.spec.ticker.clone();
    if !venue.can_mutate() {
        return Err(ExecError::Refused("venue refuses mutations".into()));
    }
    apply(book, cid, now, OrderEvent::CancelSent)?;
    sink(
        book,
        ExecEvent::BeforeSend {
            client_order_id: cid.into(),
            action: "CANCEL".into(),
        },
    )
    .map_err(ExecError::Persist)?;
    let result = venue.cancel(&vid, &ticker);
    let ev = match &result {
        CancelOutcome::Cancelled { reduced_by } => OrderEvent::CancelAcked {
            reduced_by: *reduced_by,
        },
        CancelOutcome::NotFound => OrderEvent::CancelNotFound,
        CancelOutcome::Rejected { http_status, code } => OrderEvent::Ambiguous {
            reason: format!("cancel rejected {http_status} {code}"),
        },
        CancelOutcome::Ambiguous { reason } => OrderEvent::Ambiguous {
            reason: format!("cancel {reason}"),
        },
        CancelOutcome::NotSent { reason } => OrderEvent::Ambiguous {
            reason: format!("cancel not sent after CancelSent: {reason}"),
        },
    };
    let applied = apply(book, cid, now, ev);
    outcome(sink, book, cid, "CANCEL", json!(result));
    applied
}

pub fn amend<T: KalshiTransport>(
    book: &mut GameBook,
    venue: &mut NbaVenue<T>,
    cid: &str,
    price_cents: u16,
    total_count: u32,
    now: i64,
    sink: &mut Sink<'_>,
) -> Result<(), ExecError> {
    let o = book
        .order(cid)
        .ok_or_else(|| ExecError::UnknownClientId(cid.into()))?;
    if o.status != OrderStatus::Resting {
        return Err(ExecError::Refused("amend needs a resting order".into()));
    }
    let vid = o
        .venue_order_id
        .clone()
        .ok_or_else(|| ExecError::NoVenueOrderId(cid.into()))?;
    let spec = o.spec.clone();
    if !venue.can_mutate() {
        return Err(ExecError::Refused("venue refuses mutations".into()));
    }
    sink(
        book,
        ExecEvent::BeforeSend {
            client_order_id: cid.into(),
            action: format!("AMEND {price_cents} x {total_count}"),
        },
    )
    .map_err(ExecError::Persist)?;
    let result = venue.amend(&vid, &spec, price_cents, total_count, None);
    let ev = match &result {
        AmendOutcome::Amended { venue_order_id, .. } if *venue_order_id != vid => {
            Some(OrderEvent::AmendAmbiguous {
                requested_total: total_count,
                reason: format!("amend returned order id {venue_order_id}, expected {vid}"),
            })
        }
        AmendOutcome::Amended { .. } => Some(OrderEvent::Amended {
            price_cents,
            max_count: total_count,
            client_order_id: None,
        }),
        // A refused amend leaves the old order as it was, but the reason
        // (filled, canceled) is unknown until a snapshot.
        AmendOutcome::Rejected { http_status, code } => Some(OrderEvent::Ambiguous {
            reason: format!("amend rejected {http_status} {code}"),
        }),
        AmendOutcome::Ambiguous { reason } => Some(OrderEvent::AmendAmbiguous {
            requested_total: total_count,
            reason: format!("amend {reason}"),
        }),
        AmendOutcome::NotSent { .. } => None,
    };
    let applied = match ev {
        Some(ev) => apply(book, cid, now, ev),
        None => Err(ExecError::Refused("amend not sent".into())),
    };
    outcome(sink, book, cid, "AMEND", json!(result));
    applied?;
    // Counts after an amend come only from a snapshot.
    let sent_at = book.order(cid).map_or(now, sent_at_of);
    reconcile_order(book, venue, cid, sent_at, now, sink)
}

/// Brings one order to venue truth: snapshot by venue id or client id, then
/// every fill record. `sent_at` is when the create was first sent.
pub fn reconcile_order<T: KalshiTransport>(
    book: &mut GameBook,
    venue: &mut NbaVenue<T>,
    cid: &str,
    sent_at: i64,
    now: i64,
    sink: &mut Sink<'_>,
) -> Result<(), ExecError> {
    let o = book
        .order(cid)
        .ok_or_else(|| ExecError::UnknownClientId(cid.into()))?
        .clone();
    let ghost_candidate =
        matches!(&o.status, OrderStatus::Rejected { code, .. } if code == "NOT_FOUND_ON_VENUE");
    if o.is_settled() && !ghost_candidate {
        return Ok(());
    }
    let found = match &o.venue_order_id {
        Some(vid) => venue.get_order(vid).map_err(ExecError::Read)?,
        None => venue
            .find_by_client_id(&o.spec.ticker, cid)
            .map_err(ExecError::Read)?,
    };
    match found {
        Some(v) => apply(
            book,
            cid,
            now,
            OrderEvent::Snapshot {
                venue_order_id: v.venue_order_id.clone(),
                status: v.status,
                fill_count: v.fill_count,
                remaining_count: v.remaining_count,
            },
        )?,
        None if ghost_candidate => return Ok(()),
        None if o.venue_order_id.is_some() => {
            let last_change = o.history.last().map_or(sent_at, |t| t.at);
            if now - last_change < READ_VISIBILITY_GRACE_S {
                return Ok(());
            }
            return Err(ExecError::Read(ReadError::Malformed(format!(
                "{cid}: known venue id not found {}s after its last change",
                now - last_change
            ))));
        }
        None if now - sent_at >= NOT_FOUND_GRACE_S => {
            apply(book, cid, now, OrderEvent::NotFoundOnVenue)?;
        }
        None => return Ok(()),
    }
    let o = book
        .order(cid)
        .ok_or_else(|| ExecError::UnknownClientId(cid.into()))?;
    if let Some(vid) = o.venue_order_id.clone()
        && (o.fill_record_count() < o.venue_fill_count || o.status == OrderStatus::Resting)
    {
        for f in venue.fills_for_order(&vid).map_err(ExecError::Read)? {
            apply(book, cid, now, OrderEvent::Fill(f))?;
        }
    }
    outcome(
        sink,
        book,
        cid,
        "RECONCILE",
        json!(book.order(cid).map(|o| &o.status)),
    );
    Ok(())
}

/// When the create was first sent (0 if never).
pub fn sent_at_of(o: &OrderRecord) -> i64 {
    o.history
        .iter()
        .find(|t| t.to == "SENDING")
        .map_or(0, |t| t.at)
}

/// Restart / periodic pass over every order that is not settled, plus
/// recently declared-absent orders (ghost watch).
pub fn reconcile_book<T: KalshiTransport>(
    book: &mut GameBook,
    venue: &mut NbaVenue<T>,
    now: i64,
    sink: &mut Sink<'_>,
) -> Vec<(String, ExecError)> {
    let ids: Vec<(String, i64)> = book
        .orders
        .iter()
        .filter(|o| {
            let ghost = matches!(&o.status, OrderStatus::Rejected { code, .. } if code == "NOT_FOUND_ON_VENUE");
            (!o.is_settled() && !ghost) || (ghost && now - sent_at_of(o) <= GHOST_WATCH_S)
        })
        .map(|o| (o.spec.client_order_id.clone(), sent_at_of(o)))
        .collect();
    let mut errors = Vec::new();
    for (cid, at) in ids {
        if let Err(e) = reconcile_order(book, venue, &cid, at, now, sink) {
            errors.push((cid, e));
        }
    }
    errors
}
