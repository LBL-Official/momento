//! Opponent-team YES complement hedge. Pair verified before entry.
//! 68 prepares locally only; no exchange order before the ≤67 close.

use momento_core::Contracts;
use serde::{Deserialize, Serialize};

use crate::{LADDER_CAP_CENTS, MARKET_DUMP_BELOW_CENTS, PREPARE_CENTS, STOP_CENTS};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventDescriptor {
    pub event_ticker: String,
    pub series_ticker: Option<String>,
    pub mutually_exclusive: Option<bool>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MarketDescriptor {
    pub ticker: String,
    pub event_ticker: String,
    pub status: Option<String>,
    pub yes_sub_title: Option<String>,
    pub rules_primary: Option<String>,
    pub rules_secondary: Option<String>,
    pub close_time: Option<String>,
    pub expected_expiration_time: Option<String>,
    pub settlement_timer_seconds: Option<i64>,
    pub exchange_index: Option<i64>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComplementPair {
    pub event_ticker: String,
    pub original: String,
    pub opponent: String,
    pub exchange_index: Option<i64>,
}

fn primary_remainder(m: &MarketDescriptor) -> Result<String, String> {
    let team = m
        .yes_sub_title
        .as_deref()
        .filter(|t| !t.trim().is_empty())
        .ok_or_else(|| format!("{}: yes_sub_title missing", m.ticker))?;
    let rules = m
        .rules_primary
        .as_deref()
        .ok_or_else(|| format!("{}: rules_primary missing", m.ticker))?;
    let prefix = format!("If {team} wins ");
    rules
        .strip_prefix(&prefix)
        .map(str::to_string)
        .ok_or_else(|| format!("{}: rules_primary does not start with '{prefix}'", m.ticker))
}

/// Exact complement checks from `execution_contract.json` `hedge_instrument`.
pub fn verify_complement(
    event: &EventDescriptor,
    markets: &[MarketDescriptor],
    original_ticker: &str,
) -> Result<ComplementPair, String> {
    if event.mutually_exclusive != Some(true) {
        return Err("event is not mutually_exclusive".into());
    }
    if markets.len() != 2 {
        return Err(format!("event has {} markets, expected 2", markets.len()));
    }
    if markets.iter().any(|m| m.event_ticker != event.event_ticker) {
        return Err("market event_ticker differs from event".into());
    }
    let (a, b) = (&markets[0], &markets[1]);
    let (original, opponent) = if a.ticker == original_ticker {
        (a, b)
    } else if b.ticker == original_ticker {
        (b, a)
    } else {
        return Err("original ticker is not in the event".into());
    };
    if original.ticker == opponent.ticker {
        return Err("duplicate market ticker".into());
    }
    for m in [original, opponent] {
        match m.status.as_deref() {
            Some("active") | Some("open") => {}
            other => return Err(format!("{} status {:?}", m.ticker, other)),
        }
    }
    if original.yes_sub_title == opponent.yes_sub_title {
        return Err("both markets name the same YES team".into());
    }
    if primary_remainder(original)? != primary_remainder(opponent)? {
        return Err("rules_primary differs beyond the YES team".into());
    }
    if original.rules_secondary.is_none() || original.rules_secondary != opponent.rules_secondary {
        return Err("rules_secondary differs or is missing".into());
    }
    if original.close_time != opponent.close_time
        || original.expected_expiration_time != opponent.expected_expiration_time
        || original.settlement_timer_seconds != opponent.settlement_timer_seconds
    {
        return Err("close, expiration, or settlement timer differs".into());
    }
    if original.exchange_index.is_none() || original.exchange_index != opponent.exchange_index {
        return Err("exchange_index differs or is missing".into());
    }
    Ok(ComplementPair {
        event_ticker: event.event_ticker.clone(),
        original: original.ticker.clone(),
        opponent: opponent.ticker.clone(),
        exchange_index: original.exchange_index,
    })
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "zone", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PathZone {
    AbovePrepare,
    /// 68: prepare-only limit 32. No order.
    PrepareOnly {
        limit_cents: u16,
    },
    /// 55..=67: opponent limit 33..45.
    Ladder {
        limit_cents: u16,
    },
    /// Below 55: Market Dump (emergency action unresolved).
    MarketDump,
}

pub fn path_zone(original_yes_close: u16) -> PathZone {
    if original_yes_close > PREPARE_CENTS {
        PathZone::AbovePrepare
    } else if original_yes_close == PREPARE_CENTS {
        PathZone::PrepareOnly {
            limit_cents: 100 - PREPARE_CENTS,
        }
    } else if original_yes_close >= MARKET_DUMP_BELOW_CENTS {
        PathZone::Ladder {
            limit_cents: 100 - original_yes_close,
        }
    } else {
        PathZone::MarketDump
    }
}

/// `limit = 100 − path`, clamped to the submittable ladder 33..45.
pub fn opponent_limit_for_path(original_yes_close: u16) -> Option<u16> {
    match path_zone(original_yes_close) {
        PathZone::Ladder { limit_cents } => Some(limit_cents),
        _ => None,
    }
}

/// Reconciled filled original YES minus already-filled opponent YES.
/// `Err` means over-hedged: reconciliation hold, never a negative order.
pub fn hedge_quantity(
    filled_original: Contracts,
    filled_opponent: Contracts,
) -> Result<Contracts, Contracts> {
    filled_original
        .checked_sub(filled_opponent)
        .map_err(|_| Contracts::from_u32(filled_opponent.get() - filled_original.get()))
}

/// Settlement payout (cents, before fees) of held YES on a verified
/// two-market mutually exclusive pair: exactly one side pays 100¢.
pub fn complement_settlement_cents(
    original_yes: Contracts,
    opponent_yes: Contracts,
    original_wins: bool,
) -> i64 {
    let winning = if original_wins {
        original_yes
    } else {
        opponent_yes
    };
    i64::from(winning.get()) * 100
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "action", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum HedgeAction {
    None,
    /// Local intent only. Nothing is sent.
    LocalPrepared {
        limit_cents: u16,
        qty: u32,
    },
    /// Official ≤67 trigger. A proposal; cadence unresolved.
    TriggerProposal {
        limit_cents: u16,
        qty: u32,
    },
    /// Ascending ladder proposal after the trigger.
    LadderProposal {
        limit_cents: u16,
        qty: u32,
    },
    /// Below 55 after or at the trigger. Emergency unresolved.
    MarketDumpUnresolved {
        qty: u32,
    },
    Complete,
}

/// Proposes hedge limits from closes. Ascending only. Never submits.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct HedgePlanner {
    triggered: bool,
    proposed_limit: Option<u16>,
}

impl HedgePlanner {
    pub fn proposed_limit(&self) -> Option<u16> {
        self.proposed_limit
    }

    pub fn triggered(&self) -> bool {
        self.triggered
    }

    pub fn on_close(&mut self, original_yes_close: u16, remaining_qty: Contracts) -> HedgeAction {
        let qty = remaining_qty.get();
        if qty == 0 {
            return if self.triggered {
                HedgeAction::Complete
            } else {
                HedgeAction::None
            };
        }
        if !self.triggered {
            if original_yes_close > STOP_CENTS {
                return match path_zone(original_yes_close) {
                    PathZone::PrepareOnly { limit_cents } => {
                        HedgeAction::LocalPrepared { limit_cents, qty }
                    }
                    _ => HedgeAction::None,
                };
            }
            self.triggered = true;
        }
        match path_zone(original_yes_close) {
            PathZone::MarketDump => HedgeAction::MarketDumpUnresolved { qty },
            zone => {
                let fresh = match zone {
                    PathZone::Ladder { limit_cents } => limit_cents,
                    _ => 100 - STOP_CENTS,
                };
                let first = self.proposed_limit.is_none();
                let limit = self
                    .proposed_limit
                    .map_or(fresh, |prev| prev.max(fresh))
                    .min(LADDER_CAP_CENTS);
                self.proposed_limit = Some(limit);
                if first {
                    HedgeAction::TriggerProposal {
                        limit_cents: limit,
                        qty,
                    }
                } else {
                    HedgeAction::LadderProposal {
                        limit_cents: limit,
                        qty,
                    }
                }
            }
        }
    }
}
