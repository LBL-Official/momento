use serde::{Deserialize, Serialize};

use crate::error::ConfigError;
use crate::money::{Bps, Money, Price};

pub const LIVE_CONFIRMATION: &str = "ENABLE_LIVE_TRADING";
pub const MIN_ALLOCATION_BPS: u32 = 1;
pub const MAX_ALLOCATION_BPS: u32 = 10_000;

/// How Risk derives `max_position_budget` from the weekly snapshot.
///
/// `PCT_WEEKLY` and `PCT_CURRENT` use `bankroll × allocation_bps`.
/// `FIXED_CENTS` sets the budget directly. The 80–83 maker band is independent.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PositionSizingMode {
    #[default]
    PctWeekly,
    PctCurrent,
    FixedCents,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TradingMode {
    Replay,
    Paper,
    Live,
    Demo,
}

impl TradingMode {
    pub const fn is_live(self) -> bool {
        matches!(self, Self::Live)
    }

    pub const fn is_demo(self) -> bool {
        matches!(self, Self::Demo)
    }
}

/// Which strategy machine this unit loads. Live MLB stays `mlb_factory`.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StrategyProfile {
    #[default]
    MlbFactory,
    ResearchIti,
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct LiveGate {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default)]
    pub confirmation: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct TradingConfig {
    pub mode: TradingMode,
    #[serde(default)]
    pub timezone: String,
    pub allocation_bps: u32,
    pub max_entry_price_cents: u16,
    pub preferred_entry_price_cents: u16,
    pub min_entry_price_cents: u16,
    pub initial_bankroll_cents: i64,
    #[serde(default)]
    pub sizing_mode: PositionSizingMode,
    /// Required when `sizing_mode = FIXED_CENTS`. Integer cents. Not a float.
    #[serde(default)]
    pub max_position_budget_cents: Option<i64>,
    #[serde(default)]
    pub max_daily_entries: Option<u32>,
    #[serde(default)]
    pub max_daily_wins: Option<u32>,
    #[serde(default)]
    pub max_daily_losses: Option<u32>,
    #[serde(default)]
    pub max_daily_win_cents: Option<i64>,
    #[serde(default)]
    pub max_daily_loss_cents: Option<i64>,
    #[serde(default)]
    pub live: LiveGate,
    #[serde(default)]
    pub strategy_profile: StrategyProfile,
    #[serde(default)]
    pub iti_entry_cents: Option<u16>,
    #[serde(default)]
    pub iti_win_cents: Option<u16>,
    #[serde(default)]
    pub iti_loss_cents: Option<u16>,
    /// Isolated demo unit sport slug: mlb / nba / ncaab / atp / wta.
    #[serde(default)]
    pub sport: Option<String>,
}

impl TradingConfig {
    pub fn from_toml_str(s: &str) -> Result<Self, ConfigError> {
        toml::from_str(s).map_err(|e| ConfigError::Parse(e.to_string()))
    }

    pub fn is_live_armed(&self) -> bool {
        self.mode == TradingMode::Live
            && self.live.enabled
            && self.live.confirmation == LIVE_CONFIRMATION
    }

    pub fn validate(&self) -> Result<(), ConfigError> {
        if self.timezone.is_empty() {
            return Err(ConfigError::Invalid("timezone required".into()));
        }
        if self.allocation_bps < MIN_ALLOCATION_BPS || self.allocation_bps > MAX_ALLOCATION_BPS {
            return Err(ConfigError::Invalid(
                "allocation_bps must be 1..=10000".into(),
            ));
        }
        if self.sizing_mode == PositionSizingMode::FixedCents {
            match self.max_position_budget_cents {
                Some(cents) if cents > 0 => {}
                _ => {
                    return Err(ConfigError::Invalid(
                        "FIXED_CENTS requires max_position_budget_cents > 0".into(),
                    ));
                }
            }
        }
        optional_positive_u32("max_daily_entries", self.max_daily_entries)?;
        optional_positive_u32("max_daily_wins", self.max_daily_wins)?;
        optional_positive_u32("max_daily_losses", self.max_daily_losses)?;
        optional_positive_i64("max_daily_win_cents", self.max_daily_win_cents)?;
        optional_positive_i64("max_daily_loss_cents", self.max_daily_loss_cents)?;
        match self.mode {
            TradingMode::Paper | TradingMode::Replay => {
                self.validate_factory_entry_band()?;
                if self.strategy_profile != StrategyProfile::MlbFactory {
                    return Err(ConfigError::Invalid(
                        "paper/replay cannot load research_iti".into(),
                    ));
                }
                if self.live.enabled || self.live.confirmation == LIVE_CONFIRMATION {
                    return Err(ConfigError::LiveGateIncomplete);
                }
                Ok(())
            }
            TradingMode::Live => {
                if self.strategy_profile == StrategyProfile::ResearchIti {
                    return self.validate_live_iti();
                }
                self.validate_factory_entry_band()?;
                if self.is_live_armed() {
                    if self.initial_bankroll_cents <= 0 {
                        return Err(ConfigError::Invalid(
                            "live initial bankroll must be a positive integer of cents".into(),
                        ));
                    }
                    Ok(())
                } else {
                    Err(ConfigError::LiveGateIncomplete)
                }
            }
            TradingMode::Demo => self.validate_demo_iti(),
        }
    }

    fn validate_factory_entry_band(&self) -> Result<(), ConfigError> {
        if self.max_entry_price_cents != 83 {
            return Err(ConfigError::Invalid(
                "max_entry_price_cents must remain 83".into(),
            ));
        }
        if self.min_entry_price_cents != 80 || self.preferred_entry_price_cents != 80 {
            return Err(ConfigError::Invalid(
                "entry band must remain 80–83 cents".into(),
            ));
        }
        Ok(())
    }

    fn validate_iti_prices(&self) -> Result<(u16, u16, u16), ConfigError> {
        if self.strategy_profile != StrategyProfile::ResearchIti {
            return Err(ConfigError::Invalid(
                "research_iti prices require strategy_profile = research_iti".into(),
            ));
        }
        let entry = self
            .iti_entry_cents
            .ok_or_else(|| ConfigError::Invalid("research_iti requires iti_entry_cents".into()))?;
        let win = self
            .iti_win_cents
            .ok_or_else(|| ConfigError::Invalid("research_iti requires iti_win_cents".into()))?;
        let loss = self
            .iti_loss_cents
            .ok_or_else(|| ConfigError::Invalid("research_iti requires iti_loss_cents".into()))?;
        for (name, cents) in [
            ("iti_entry_cents", entry),
            ("iti_win_cents", win),
            ("iti_loss_cents", loss),
        ] {
            if !(1..=99).contains(&cents) {
                return Err(ConfigError::Invalid(format!("{name} must be 1..=99")));
            }
        }
        if !(loss < entry && entry < win) {
            return Err(ConfigError::Invalid(
                "iti prices must satisfy loss < entry < win".into(),
            ));
        }
        if self.min_entry_price_cents != entry || self.preferred_entry_price_cents != entry {
            return Err(ConfigError::Invalid(
                "min/preferred entry must equal iti_entry_cents".into(),
            ));
        }
        let max = win.saturating_sub(1);
        if self.max_entry_price_cents != max {
            return Err(ConfigError::Invalid(
                "max_entry_price_cents must be iti_win_cents - 1".into(),
            ));
        }
        if self.min_entry_price_cents == 80 && self.max_entry_price_cents == 83 {
            return Err(ConfigError::Invalid(
                "research_iti cannot use the factory 80–83 band".into(),
            ));
        }
        Ok((entry, win, loss))
    }

    fn validate_iti_sport(&self) -> Result<(), ConfigError> {
        let sport = self
            .sport
            .as_deref()
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .ok_or_else(|| ConfigError::Invalid("research_iti requires sport".into()))?;
        if !matches!(
            sport.to_ascii_lowercase().as_str(),
            "mlb" | "nba" | "ncaab" | "wnba" | "atp" | "wta"
        ) {
            return Err(ConfigError::Invalid(
                "sport must be mlb, nba, ncaab, wnba, atp, or wta".into(),
            ));
        }
        Ok(())
    }

    fn validate_demo_iti(&self) -> Result<(), ConfigError> {
        if self.live.enabled || self.live.confirmation == LIVE_CONFIRMATION {
            return Err(ConfigError::Invalid(
                "demo mode forbids ENABLE_LIVE_TRADING".into(),
            ));
        }
        self.validate_iti_prices()?;
        if self.initial_bankroll_cents <= 0 {
            return Err(ConfigError::Invalid(
                "demo initial bankroll must be a positive integer of cents".into(),
            ));
        }
        self.validate_iti_sport()
    }

    fn validate_live_iti(&self) -> Result<(), ConfigError> {
        if !self.is_live_armed() {
            return Err(ConfigError::LiveGateIncomplete);
        }
        self.validate_iti_prices()?;
        if self.initial_bankroll_cents <= 0 {
            return Err(ConfigError::Invalid(
                "live ITI initial bankroll must be a positive integer of cents".into(),
            ));
        }
        self.validate_iti_sport()
    }

    pub fn is_research_iti(&self) -> bool {
        self.strategy_profile == StrategyProfile::ResearchIti
    }

    pub fn allocation(&self) -> Bps {
        Bps::from_bps(self.allocation_bps)
    }

    pub fn max_entry_price(&self) -> Result<Price, ConfigError> {
        Price::from_cents(self.max_entry_price_cents)
            .map_err(|e| ConfigError::Invalid(e.to_string()))
    }

    pub fn initial_bankroll(&self) -> Money {
        Money::from_cents(self.initial_bankroll_cents)
    }
}

fn optional_positive_u32(name: &str, value: Option<u32>) -> Result<(), ConfigError> {
    if let Some(n) = value {
        if n == 0 {
            return Err(ConfigError::Invalid(format!("{name} must be > 0 when set")));
        }
    }
    Ok(())
}

fn optional_positive_i64(name: &str, value: Option<i64>) -> Result<(), ConfigError> {
    if let Some(n) = value {
        if n <= 0 {
            return Err(ConfigError::Invalid(format!("{name} must be > 0 when set")));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn live_mode_requires_all_three_gates() {
        let toml = r#"
mode = "live"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 83
preferred_entry_price_cents = 80
min_entry_price_cents = 80
initial_bankroll_cents = 5000
[live]
enabled = true
confirmation = "ENABLE_LIVE_TRADING"
"#;
        let cfg = TradingConfig::from_toml_str(toml).unwrap();
        cfg.validate().unwrap();
        assert!(cfg.is_live_armed());
    }

    #[test]
    fn live_without_confirmation_cannot_arm() {
        let toml = r#"
mode = "live"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 83
preferred_entry_price_cents = 80
min_entry_price_cents = 80
initial_bankroll_cents = 5000
[live]
enabled = true
confirmation = ""
"#;
        let cfg = TradingConfig::from_toml_str(toml).unwrap();
        assert!(matches!(
            cfg.validate(),
            Err(ConfigError::LiveGateIncomplete)
        ));
    }

    #[test]
    fn paper_cannot_carry_live_confirmation() {
        let toml = r#"
mode = "paper"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 83
preferred_entry_price_cents = 80
min_entry_price_cents = 80
initial_bankroll_cents = 5000
[live]
enabled = false
confirmation = "ENABLE_LIVE_TRADING"
"#;
        let cfg = TradingConfig::from_toml_str(toml).unwrap();
        assert!(matches!(
            cfg.validate(),
            Err(ConfigError::LiveGateIncomplete)
        ));
    }

    #[test]
    fn paper_mode_loads() {
        let cfg = TradingConfig::from_toml_str(include_str!("../../../config/paper.toml")).unwrap();
        cfg.validate().unwrap();
        assert_eq!(cfg.mode, TradingMode::Paper);
        assert!(!cfg.is_live_armed());
    }

    #[test]
    fn live_toml_requires_all_three_gates() {
        let cfg = TradingConfig::from_toml_str(include_str!("../../../config/live.toml")).unwrap();
        cfg.validate().unwrap();
        assert!(cfg.is_live_armed());
        assert_eq!(cfg.initial_bankroll_cents, 5000);
        assert_eq!(cfg.max_entry_price_cents, 83);
        assert_eq!(cfg.allocation_bps, 1250);
    }

    #[test]
    fn allocation_bps_1249_1250_1251_are_valid() {
        for bps in [1249_u32, 1250, 1251] {
            let toml = format!(
                r#"
mode = "paper"
timezone = "America/Los_Angeles"
allocation_bps = {bps}
max_entry_price_cents = 83
preferred_entry_price_cents = 80
min_entry_price_cents = 80
initial_bankroll_cents = 5000
"#
            );
            let cfg = TradingConfig::from_toml_str(&toml).unwrap();
            cfg.validate().unwrap();
            assert_eq!(cfg.allocation_bps, bps);
        }
    }

    #[test]
    fn allocation_bps_zero_is_rejected() {
        let toml = r#"
mode = "paper"
timezone = "America/Los_Angeles"
allocation_bps = 0
max_entry_price_cents = 83
preferred_entry_price_cents = 80
min_entry_price_cents = 80
initial_bankroll_cents = 5000
"#;
        let cfg = TradingConfig::from_toml_str(toml).unwrap();
        assert!(cfg.validate().is_err());
    }

    #[test]
    fn fixed_cents_330_331_332() {
        for cents in [330_i64, 331, 332] {
            let toml = format!(
                r#"
mode = "paper"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 83
preferred_entry_price_cents = 80
min_entry_price_cents = 80
initial_bankroll_cents = 3931
sizing_mode = "FIXED_CENTS"
max_position_budget_cents = {cents}
"#
            );
            let cfg = TradingConfig::from_toml_str(&toml).unwrap();
            cfg.validate().unwrap();
            assert_eq!(cfg.sizing_mode, PositionSizingMode::FixedCents);
            assert_eq!(cfg.max_position_budget_cents, Some(cents));
        }
    }

    #[test]
    fn fixed_cents_without_budget_is_rejected() {
        let toml = r#"
mode = "paper"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 83
preferred_entry_price_cents = 80
min_entry_price_cents = 80
initial_bankroll_cents = 5000
sizing_mode = "FIXED_CENTS"
"#;
        let cfg = TradingConfig::from_toml_str(toml).unwrap();
        assert!(cfg.validate().is_err());
    }

    #[test]
    fn live_armed_accepts_non_factory_bankroll() {
        let toml = r#"
mode = "live"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 83
preferred_entry_price_cents = 80
min_entry_price_cents = 80
initial_bankroll_cents = 3931
[live]
enabled = true
confirmation = "ENABLE_LIVE_TRADING"
"#;
        let cfg = TradingConfig::from_toml_str(toml).unwrap();
        cfg.validate().unwrap();
        assert!(cfg.is_live_armed());
        assert_eq!(cfg.initial_bankroll_cents, 3931);
    }

    #[test]
    fn session_limit_zero_is_malformed() {
        let toml = r#"
mode = "paper"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 83
preferred_entry_price_cents = 80
min_entry_price_cents = 80
initial_bankroll_cents = 5000
max_daily_entries = 0
"#;
        let cfg = TradingConfig::from_toml_str(toml).unwrap();
        assert!(cfg.validate().is_err());
    }

    #[test]
    fn entry_band_still_locked() {
        let toml = r#"
mode = "paper"
timezone = "America/Los_Angeles"
allocation_bps = 800
max_entry_price_cents = 84
preferred_entry_price_cents = 80
min_entry_price_cents = 80
initial_bankroll_cents = 5000
"#;
        let cfg = TradingConfig::from_toml_str(toml).unwrap();
        assert!(cfg.validate().is_err());
    }

    fn demo_iti_toml() -> &'static str {
        r#"
mode = "demo"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 59
preferred_entry_price_cents = 20
min_entry_price_cents = 20
initial_bankroll_cents = 5000
sizing_mode = "FIXED_CENTS"
max_position_budget_cents = 625
strategy_profile = "research_iti"
iti_entry_cents = 20
iti_win_cents = 60
iti_loss_cents = 10
sport = "mlb"
[live]
enabled = false
confirmation = ""
"#
    }

    #[test]
    fn demo_iti_20_60_10_is_accepted() {
        let cfg = TradingConfig::from_toml_str(demo_iti_toml()).unwrap();
        cfg.validate().unwrap();
        assert_eq!(cfg.mode, TradingMode::Demo);
        assert!(cfg.is_research_iti());
        assert!(!cfg.is_live_armed());
        assert_eq!(cfg.iti_entry_cents, Some(20));
        assert_eq!(cfg.iti_win_cents, Some(60));
        assert_eq!(cfg.iti_loss_cents, Some(10));
        assert_eq!(cfg.max_entry_price_cents, 59);
    }

    fn live_iti_toml() -> &'static str {
        r#"
mode = "live"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 59
preferred_entry_price_cents = 20
min_entry_price_cents = 20
initial_bankroll_cents = 5000
sizing_mode = "FIXED_CENTS"
max_position_budget_cents = 625
strategy_profile = "research_iti"
iti_entry_cents = 20
iti_win_cents = 60
iti_loss_cents = 10
sport = "mlb"
[live]
enabled = true
confirmation = "ENABLE_LIVE_TRADING"
"#
    }

    #[test]
    fn live_iti_20_60_10_is_accepted() {
        let cfg = TradingConfig::from_toml_str(live_iti_toml()).unwrap();
        cfg.validate().unwrap();
        assert_eq!(cfg.mode, TradingMode::Live);
        assert!(cfg.is_research_iti());
        assert!(cfg.is_live_armed());
        assert_eq!(cfg.iti_entry_cents, Some(20));
        assert_eq!(cfg.max_entry_price_cents, 59);
    }

    #[test]
    fn live_iti_without_confirmation_is_rejected() {
        let toml = r#"
mode = "live"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 59
preferred_entry_price_cents = 20
min_entry_price_cents = 20
initial_bankroll_cents = 5000
sizing_mode = "FIXED_CENTS"
max_position_budget_cents = 625
strategy_profile = "research_iti"
iti_entry_cents = 20
iti_win_cents = 60
iti_loss_cents = 10
sport = "mlb"
[live]
enabled = true
confirmation = ""
"#;
        let cfg = TradingConfig::from_toml_str(toml).unwrap();
        assert!(cfg.validate().is_err());
        assert!(!cfg.is_live_armed());
    }

    #[test]
    fn live_research_iti_cannot_use_factory_80_83() {
        let toml = r#"
mode = "live"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 83
preferred_entry_price_cents = 80
min_entry_price_cents = 80
initial_bankroll_cents = 5000
strategy_profile = "research_iti"
iti_entry_cents = 20
iti_win_cents = 60
iti_loss_cents = 10
sport = "mlb"
[live]
enabled = true
confirmation = "ENABLE_LIVE_TRADING"
"#;
        let cfg = TradingConfig::from_toml_str(toml).unwrap();
        assert!(cfg.validate().is_err());
        assert!(cfg.is_live_armed());
    }

    #[test]
    fn demo_enable_live_trading_is_rejected() {
        let toml = r#"
mode = "demo"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 59
preferred_entry_price_cents = 20
min_entry_price_cents = 20
initial_bankroll_cents = 5000
sizing_mode = "FIXED_CENTS"
max_position_budget_cents = 625
strategy_profile = "research_iti"
iti_entry_cents = 20
iti_win_cents = 60
iti_loss_cents = 10
sport = "mlb"
[live]
enabled = true
confirmation = "ENABLE_LIVE_TRADING"
"#;
        let cfg = TradingConfig::from_toml_str(toml).unwrap();
        assert!(cfg.validate().is_err());
        assert!(!cfg.is_live_armed());
    }

    #[test]
    fn live_80_83_band_is_unchanged() {
        let cfg = TradingConfig::from_toml_str(include_str!("../../../config/live.toml")).unwrap();
        cfg.validate().unwrap();
        assert_eq!(cfg.max_entry_price_cents, 83);
        assert_eq!(cfg.min_entry_price_cents, 80);
        assert_eq!(cfg.preferred_entry_price_cents, 80);
        assert_eq!(cfg.strategy_profile, StrategyProfile::MlbFactory);
    }
}
