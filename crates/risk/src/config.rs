//! Risk configuration. Unresolved aggregate policies stay optional.

use momento_core::{Bps, Money, PositionSizingMode, Price, StrategyId, TradingConfig};

/// Limits injected into the risk engine. Do not hide unresolved policy as constants.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RiskConfig {
    pub max_entry_price: Price,
    pub min_entry_price: Price,
    /// MLB percent-of-bankroll when the snapshot was captured as a percent mode.
    /// `decide_entry` sizes MLB from `snapshot.max_position_budget()`, not this field.
    pub per_game_allocation: Bps,
    /// WNBA per-game maximum: 8.33% = 833 bps. See [`Bps::PCT_8_33`].
    pub wnba_per_game_allocation: Bps,
    /// Desk-wide cap: at most five simultaneously open PositionIds across
    /// every strategy (MLB + WNBA combined). Not five per league.
    pub max_open_positions: u32,
    /// Unresolved weekly MLB aggregate. `None` = not enforced.
    pub weekly_sport_max: Option<Money>,
    /// Unresolved concurrent-game cap distinct from open-position occupancy.
    /// `None` = not enforced.
    pub max_concurrent_games: Option<u32>,
    /// Pacific-day new-entry cap. `None` = not enforced.
    pub max_daily_entries: Option<u32>,
    pub max_daily_wins: Option<u32>,
    pub max_daily_losses: Option<u32>,
    pub max_daily_win_cents: Option<Money>,
    pub max_daily_loss_cents: Option<Money>,
    pub sizing_mode: PositionSizingMode,
}

impl RiskConfig {
    pub fn mlb_paper_experimental() -> Result<Self, momento_core::error::PriceError> {
        Ok(Self {
            max_entry_price: Price::from_cents(83)?,
            min_entry_price: Price::from_cents(80)?,
            per_game_allocation: Bps::PCT_12_5,
            wnba_per_game_allocation: Bps::PCT_8_33,
            max_open_positions: 5,
            weekly_sport_max: None,
            max_concurrent_games: None,
            max_daily_entries: None,
            max_daily_wins: None,
            max_daily_losses: None,
            max_daily_win_cents: None,
            max_daily_loss_cents: None,
            sizing_mode: PositionSizingMode::PctWeekly,
        })
    }

    /// Host path: take confirmed sizing + session limits from `TradingConfig`.
    /// Live factory stays 80–83. Demo `research_iti` uses that unit's ITI band.
    pub fn from_trading_config(
        cfg: &TradingConfig,
    ) -> Result<Self, momento_core::error::PriceError> {
        let mut out = Self::mlb_paper_experimental()?;
        out.max_entry_price = Price::from_cents(cfg.max_entry_price_cents)?;
        out.min_entry_price = Price::from_cents(cfg.min_entry_price_cents)?;
        out.per_game_allocation = cfg.allocation();
        out.sizing_mode = cfg.sizing_mode;
        out.max_daily_entries = cfg.max_daily_entries;
        out.max_daily_wins = cfg.max_daily_wins;
        out.max_daily_losses = cfg.max_daily_losses;
        out.max_daily_win_cents = cfg.max_daily_win_cents.map(Money::from_cents);
        out.max_daily_loss_cents = cfg.max_daily_loss_cents.map(Money::from_cents);
        Ok(out)
    }

    /// Per-game allocation for the strategy that proposed the intent.
    /// Unknown strategies yield `None` (fail closed).
    pub fn allocation_for(&self, strategy_id: StrategyId) -> Option<Bps> {
        if strategy_id == StrategyId::MLB || strategy_id == StrategyId::RESEARCH_ITI {
            Some(self.per_game_allocation)
        } else if strategy_id == StrategyId::WNBA {
            Some(self.wnba_per_game_allocation)
        } else {
            None
        }
    }

    pub fn win_loss_limits_set(&self) -> bool {
        self.max_daily_wins.is_some()
            || self.max_daily_losses.is_some()
            || self.max_daily_win_cents.is_some()
            || self.max_daily_loss_cents.is_some()
    }
}
