//! Risk reservations: approved-but-unfilled exposure that still consumes budget.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use momento_core::{ClientOrderId, GameId, Money, PositionId};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Reservation {
    pub client_order_id: ClientOrderId,
    pub position_id: PositionId,
    pub game_id: GameId,
    pub remaining: Money,
    pub unknown: bool,
}

#[derive(Clone, Debug, Default)]
pub struct ReservationBook {
    by_order: HashMap<u128, Reservation>,
}

impl ReservationBook {
    pub(crate) fn reserved_for_position(&self, position_id: PositionId) -> Money {
        let mut total = Money::ZERO;
        for r in self.by_order.values() {
            if r.position_id == position_id {
                total = total.saturating_add_lossy(r.remaining);
            }
        }
        total
    }

    pub fn has_unknown_for_position(&self, position_id: PositionId) -> bool {
        self.by_order
            .values()
            .any(|r| r.position_id == position_id && r.unknown)
    }

    pub fn insert(&mut self, reservation: Reservation) {
        self.by_order
            .insert(reservation.client_order_id.raw(), reservation);
    }

    /// Reduce reservation by fill economics. Does not mutate the position.
    pub fn apply_fill(&mut self, order: ClientOrderId, economic: Money) {
        if let Some(r) = self.by_order.get_mut(&order.raw()) {
            r.remaining = r.remaining.saturating_sub(economic);
            if r.remaining.cents() <= 0 && !r.unknown {
                self.by_order.remove(&order.raw());
            }
        }
    }

    /// Release unused reservation. UNKNOWN orders are not released.
    pub fn cancel(&mut self, order: ClientOrderId) -> bool {
        match self.by_order.get(&order.raw()) {
            Some(r) if r.unknown => false,
            Some(_) => {
                self.by_order.remove(&order.raw());
                true
            }
            None => false,
        }
    }

    pub(crate) fn known_order_ids_for_position(
        &self,
        position_id: PositionId,
    ) -> Vec<ClientOrderId> {
        self.by_order
            .values()
            .filter(|r| r.position_id == position_id && !r.unknown)
            .map(|r| r.client_order_id)
            .collect()
    }

    pub fn mark_unknown(&mut self, order: ClientOrderId) -> bool {
        if let Some(r) = self.by_order.get_mut(&order.raw()) {
            r.unknown = true;
            true
        } else {
            false
        }
    }

    pub fn clear_unknown(&mut self, order: ClientOrderId) {
        if let Some(r) = self.by_order.get_mut(&order.raw()) {
            r.unknown = false;
        }
    }

    pub fn has_any_unknown(&self) -> bool {
        self.by_order.values().any(|r| r.unknown)
    }

    pub fn has_for_position(&self, position_id: PositionId) -> bool {
        self.by_order.values().any(|r| r.position_id == position_id)
    }

    pub fn position_id_for(&self, order: ClientOrderId) -> Option<PositionId> {
        self.by_order.get(&order.raw()).map(|r| r.position_id)
    }

    pub fn snapshot(&self) -> Vec<Reservation> {
        self.by_order.values().cloned().collect()
    }

    pub fn restore(reservations: Vec<Reservation>) -> Self {
        let mut book = Self::default();
        for reservation in reservations {
            book.insert(reservation);
        }
        book
    }
}

trait SaturatingMoney {
    fn saturating_add_lossy(self, other: Money) -> Money;
}

impl SaturatingMoney for Money {
    fn saturating_add_lossy(self, other: Money) -> Money {
        self.checked_add(other)
            .unwrap_or(Money::from_cents(i64::MAX))
    }
}
