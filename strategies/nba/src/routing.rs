//! Routing. The market/event `exchange_index` is authoritative for that
//! market; the series `exchange_index` only names the shard where *new*
//! events are created (docs.kalshi.com/getting_started/exchange_sharding,
//! read 2026-09-27: "no plan to migrate any live market"; "all child markets
//! of an event will live on the same exchange instance"). A series/market
//! difference is therefore expected for events created before a series move
//! and is not a conflict. Legs on different shards are a data error.

use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "route", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Route {
    Verified {
        exchange_index: i64,
        /// Series index for new events. Informational only.
        #[serde(default)]
        series_index: Option<i64>,
    },
    /// The two legs of the hedge pair report different shards.
    PairMismatch {
        a_index: Option<i64>,
        b_index: Option<i64>,
    },
    Unread,
}

impl Route {
    pub fn verified_index(&self) -> Option<i64> {
        match self {
            Route::Verified { exchange_index, .. } => Some(*exchange_index),
            _ => None,
        }
    }

    /// The shard both legs trade on. Collateral must be on this shard.
    pub fn market_index(&self) -> Option<i64> {
        self.verified_index()
    }
}

pub fn route_for_pair(series: Option<i64>, a: Option<i64>, b: Option<i64>) -> Route {
    match (a, b) {
        (Some(x), Some(y)) if x == y => Route::Verified {
            exchange_index: x,
            series_index: series,
        },
        (None, None) => Route::Unread,
        _ => Route::PairMismatch {
            a_index: a,
            b_index: b,
        },
    }
}
