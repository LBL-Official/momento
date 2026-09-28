//! Canonical B1 entry snapshot. Prices are TRADE cents. L2 is unavailable.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::availability::FeatureAvailability;
use crate::versions::{EXECUTION_STATUS, OBSERVABILITY, PRICE_KIND};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MoveDirection {
    Up,
    Down,
    Flat,
}

impl MoveDirection {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Up => "UP",
            Self::Down => "DOWN",
            Self::Flat => "FLAT",
        }
    }

    pub fn from_delta(cents: i32) -> Self {
        match cents.cmp(&0) {
            std::cmp::Ordering::Greater => Self::Up,
            std::cmp::Ordering::Less => Self::Down,
            std::cmp::Ordering::Equal => Self::Flat,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum BaseballRegime {
    EarlyClose,
    EarlyLead,
    EarlyTrail,
    MidClose,
    MidLead,
    MidTrail,
    LateClose,
    LateLead,
    LateTrail,
    NinthClose,
    NinthLead,
    NinthTrail,
    ExtraInnings,
    NoState,
}

impl BaseballRegime {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::EarlyClose => "EARLY_CLOSE",
            Self::EarlyLead => "EARLY_LEAD",
            Self::EarlyTrail => "EARLY_TRAIL",
            Self::MidClose => "MID_CLOSE",
            Self::MidLead => "MID_LEAD",
            Self::MidTrail => "MID_TRAIL",
            Self::LateClose => "LATE_CLOSE",
            Self::LateLead => "LATE_LEAD",
            Self::LateTrail => "LATE_TRAIL",
            Self::NinthClose => "NINTH_CLOSE",
            Self::NinthLead => "NINTH_LEAD",
            Self::NinthTrail => "NINTH_TRAIL",
            Self::ExtraInnings => "EXTRA_INNINGS",
            Self::NoState => "NO_STATE",
        }
    }
}

/// Inning bands: 1–3 EARLY, 4–6 MID, 7–8 LATE, 9 NINTH, ≥10 EXTRA.
pub fn baseball_regime(inning: Option<u8>, bound_lead: Option<i32>) -> BaseballRegime {
    let Some(inn) = inning else {
        return BaseballRegime::NoState;
    };
    if inn >= 10 {
        return BaseballRegime::ExtraInnings;
    }
    let Some(lead) = bound_lead else {
        return BaseballRegime::NoState;
    };
    let (close, lead_v, trail_v) = if inn <= 3 {
        (
            BaseballRegime::EarlyClose,
            BaseballRegime::EarlyLead,
            BaseballRegime::EarlyTrail,
        )
    } else if inn <= 6 {
        (
            BaseballRegime::MidClose,
            BaseballRegime::MidLead,
            BaseballRegime::MidTrail,
        )
    } else if inn <= 8 {
        (
            BaseballRegime::LateClose,
            BaseballRegime::LateLead,
            BaseballRegime::LateTrail,
        )
    } else {
        (
            BaseballRegime::NinthClose,
            BaseballRegime::NinthLead,
            BaseballRegime::NinthTrail,
        )
    };
    if lead >= 2 {
        lead_v
    } else if lead <= -2 {
        trail_v
    } else {
        close
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ScoreBucket {
    Tied,
    OneRun,
    TwoRun,
    MultiRun,
    Unavailable,
}

impl ScoreBucket {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Tied => "TIED",
            Self::OneRun => "ONE_RUN",
            Self::TwoRun => "TWO_RUN",
            Self::MultiRun => "MULTI_RUN",
            Self::Unavailable => "UNAVAILABLE",
        }
    }

    pub fn from_abs_lead(abs_lead: Option<i32>) -> Self {
        match abs_lead {
            None => Self::Unavailable,
            Some(0) => Self::Tied,
            Some(1) => Self::OneRun,
            Some(2) => Self::TwoRun,
            Some(_) => Self::MultiRun,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum BaseClass {
    BasesEmpty,
    RunnerOn,
    Risp,
    Loaded,
    Unavailable,
}

impl BaseClass {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::BasesEmpty => "BASES_EMPTY",
            Self::RunnerOn => "RUNNER_ON",
            Self::Risp => "RISP",
            Self::Loaded => "LOADED",
            Self::Unavailable => "UNAVAILABLE",
        }
    }

    pub fn from_mask(mask: Option<u8>) -> Self {
        let Some(m) = mask else {
            return Self::Unavailable;
        };
        if m == 0 {
            Self::BasesEmpty
        } else if m == 7 {
            Self::Loaded
        } else if m & 6 != 0 {
            Self::Risp
        } else {
            Self::RunnerOn
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MarketPersonality {
    Trending,
    MeanReverting,
    Choppy,
    Accelerating,
    Decelerating,
    Reversing,
    Stable,
    Unclassified,
}

impl MarketPersonality {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Trending => "TRENDING",
            Self::MeanReverting => "MEAN_REVERTING",
            Self::Choppy => "CHOPPY",
            Self::Accelerating => "ACCELERATING",
            Self::Decelerating => "DECELERATING",
            Self::Reversing => "REVERSING",
            Self::Stable => "STABLE",
            Self::Unclassified => "UNCLASSIFIED",
        }
    }
}

/// Starting-belief buckets. Raw `p_start_cents` is always retained.
///
/// Cuts are on P_start cents: &lt;40, 40–46, 47–53, 54–59, ≥60.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum StartSentiment {
    StrongUnderdog,
    Underdog,
    Neutral,
    Favorite,
    StrongFavorite,
    Unavailable,
}

impl StartSentiment {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::StrongUnderdog => "STRONG_UNDERDOG",
            Self::Underdog => "UNDERDOG",
            Self::Neutral => "NEUTRAL",
            Self::Favorite => "FAVORITE",
            Self::StrongFavorite => "STRONG_FAVORITE",
            Self::Unavailable => "UNAVAILABLE",
        }
    }

    pub fn from_p_start_cents(cents: Option<i32>) -> Self {
        match cents {
            None => Self::Unavailable,
            Some(p) if p < 40 => Self::StrongUnderdog,
            Some(p) if p < 47 => Self::Underdog,
            Some(p) if p <= 53 => Self::Neutral,
            Some(p) if p < 60 => Self::Favorite,
            Some(_) => Self::StrongFavorite,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SettlementOutcome {
    Win,
    Loss,
    FinalTie,
    SettlementUnavailable,
}

impl SettlementOutcome {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Win => "WIN",
            Self::Loss => "LOSS",
            Self::FinalTie => "FINAL_TIE",
            Self::SettlementUnavailable => "SETTLEMENT_UNAVAILABLE",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SplitGroup {
    Train,
    Test,
}

impl SplitGroup {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Train => "TRAIN",
            Self::Test => "TEST",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SampleSizeFlag {
    VerySmall,
    Small,
    Moderate,
    Researchable,
}

impl SampleSizeFlag {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::VerySmall => "VERY_SMALL",
            Self::Small => "SMALL",
            Self::Moderate => "MODERATE",
            Self::Researchable => "RESEARCHABLE",
        }
    }

    pub fn from_unique_games(n: usize) -> Self {
        if n < 20 {
            Self::VerySmall
        } else if n < 50 {
            Self::Small
        } else if n < 100 {
            Self::Moderate
        } else {
            Self::Researchable
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct TradeLookback {
    pub requested_horizon_secs: i64,
    pub availability: FeatureAvailability,
    pub price_cents: Option<i32>,
    pub feature_timestamp: Option<DateTime<Utc>>,
    pub source_observation_id: Option<String>,
    pub lookback_actual_seconds: Option<i64>,
    pub delta_cents: Option<i32>,
    pub velocity_cents_per_sec_e6: Option<i64>,
}

impl TradeLookback {
    pub fn missing(horizon: i64, avail: FeatureAvailability) -> Self {
        Self {
            requested_horizon_secs: horizon,
            availability: avail,
            price_cents: None,
            feature_timestamp: None,
            source_observation_id: None,
            lookback_actual_seconds: None,
            delta_cents: None,
            velocity_cents_per_sec_e6: None,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct BaseballStateFeatures {
    pub availability: FeatureAvailability,
    pub state_id: Option<String>,
    pub state_seq: Option<u32>,
    pub state_timestamp: Option<DateTime<Utc>>,
    pub inning: Option<u8>,
    pub half_inning: Option<String>,
    pub outs: Option<u8>,
    pub score_home: Option<u16>,
    pub score_away: Option<u16>,
    pub home_run_differential: Option<i32>,
    pub bound_team_score: Option<u16>,
    pub opponent_score: Option<u16>,
    pub bound_team_lead: Option<i32>,
    pub score_diff: Option<i32>,
    pub abs_score_diff: Option<i32>,
    pub leading_flag: Option<bool>,
    pub trailing_flag: Option<bool>,
    pub tied_flag: Option<bool>,
    pub score_bucket: ScoreBucket,
    pub bases_bitmask: Option<u8>,
    pub base_state: Option<String>,
    pub base_class: BaseClass,
    pub base_out_state: Option<String>,
    pub balls: Option<u8>,
    pub strikes: Option<u8>,
    pub batter_id: Option<String>,
    pub pitcher_id: Option<String>,
    pub batter_available: FeatureAvailability,
    pub pitcher_available: FeatureAvailability,
    pub regime: BaseballRegime,
    pub home_abbr: Option<String>,
    pub away_abbr: Option<String>,
    pub identity_source: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct StartingMarketFeatures {
    pub availability: FeatureAvailability,
    pub p_start_cents: Option<i32>,
    pub starting_price_source: String,
    pub start_observation_id: Option<String>,
    pub start_timestamp: Option<DateTime<Utc>>,
    pub start_bias_cents: Option<i32>,
    pub start_bucket: Option<String>,
    pub start_sentiment: StartSentiment,
    pub starting_bid: FeatureAvailability,
    pub starting_ask: FeatureAvailability,
    pub starting_mid: FeatureAvailability,
    pub starting_spread: FeatureAvailability,
}

/// Current quoted market at entry. Mid/spread require L2.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct CurrentMarketFeatures {
    pub bid: FeatureAvailability,
    pub ask: FeatureAvailability,
    pub mid: FeatureAvailability,
    pub spread: FeatureAvailability,
    /// Mid − 80. UNAVAILABLE until a historical mid exists.
    pub d80_mid: FeatureAvailability,
    /// Entry TRADE − 80. Available; not a mid distance.
    pub d80_trade_cents: i32,
    pub price_kind: String,
}

impl CurrentMarketFeatures {
    pub fn from_entry_trade(entry_cents: i32) -> Self {
        Self {
            bid: FeatureAvailability::UnavailableSource,
            ask: FeatureAvailability::UnavailableSource,
            mid: FeatureAvailability::UnavailableSource,
            spread: FeatureAvailability::UnavailableSource,
            d80_mid: FeatureAvailability::UnavailableSource,
            d80_trade_cents: entry_cents - 80,
            price_kind: PRICE_KIND.to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MarketHistoryFeatures {
    pub start_to_entry_move_cents: Option<i32>,
    pub start_to_entry_magnitude_cents: Option<i32>,
    pub start_to_entry_direction: Option<MoveDirection>,
    pub start_to_entry_move_bucket: Option<String>,
    pub p_max_cents: Option<i32>,
    pub p_min_cents: Option<i32>,
    pub path_distance_cents: Option<i32>,
    pub path_efficiency_bps: Option<i32>,
    pub reversal_count: Option<u32>,
    pub max_run_up_cents: Option<i32>,
    pub max_drawdown_cents: Option<i32>,
    pub volatility_1m_cents: Option<i32>,
    pub volatility_5m_cents: Option<i32>,
    pub volatility_15m_cents: Option<i32>,
    pub volatility_30m_cents: Option<i32>,
    /// TRAIN-regime z × 1000. None until batch attach.
    pub volatility_5m_z_e3: Option<i32>,
    pub volatility_z_availability: FeatureAvailability,
    pub start_to_entry_move_z_e3: Option<i32>,
    pub start_to_entry_move_z_availability: FeatureAvailability,
    pub personality: MarketPersonality,
    pub price_kind: String,
}

impl Default for MarketHistoryFeatures {
    fn default() -> Self {
        Self {
            start_to_entry_move_cents: None,
            start_to_entry_magnitude_cents: None,
            start_to_entry_direction: None,
            start_to_entry_move_bucket: None,
            p_max_cents: None,
            p_min_cents: None,
            path_distance_cents: None,
            path_efficiency_bps: None,
            reversal_count: None,
            max_run_up_cents: None,
            max_drawdown_cents: None,
            volatility_1m_cents: None,
            volatility_5m_cents: None,
            volatility_15m_cents: None,
            volatility_30m_cents: None,
            volatility_5m_z_e3: None,
            volatility_z_availability: FeatureAvailability::InsufficientHistory,
            start_to_entry_move_z_e3: None,
            start_to_entry_move_z_availability: FeatureAvailability::InsufficientHistory,
            personality: MarketPersonality::Unclassified,
            price_kind: PRICE_KIND.to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PriceDynamicsFeatures {
    pub p_1m: TradeLookback,
    pub p_5m: TradeLookback,
    pub p_15m: TradeLookback,
    pub p_30m: TradeLookback,
    pub acceleration_1m_vs_5m_e6: Option<i64>,
    pub acceleration_availability: FeatureAvailability,
    pub price_kind: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventClassResponse {
    pub event_class: String,
    pub n_events: u32,
    pub n_with_price_response: u32,
    pub last_delta_cents: Option<i32>,
    pub last_event_id: Option<String>,
    pub last_event_timestamp: Option<DateTime<Utc>>,
}

/// Observed (event, TRADE before, TRADE after) step. Not causal.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventPathPoint {
    pub event_id: String,
    pub event_class: String,
    pub event_type: String,
    pub event_timestamp: DateTime<Utc>,
    pub p_before_cents: Option<i32>,
    pub p_after_cents: Option<i32>,
    pub delta_cents: Option<i32>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventResponseFeatures {
    pub availability: FeatureAvailability,
    pub note: String,
    pub responses: Vec<EventClassResponse>,
    pub event_history: Vec<EventPathPoint>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MicrostructureFeatures {
    pub bid: FeatureAvailability,
    pub ask: FeatureAvailability,
    pub mid: FeatureAvailability,
    pub spread: FeatureAvailability,
    pub delta_spread: FeatureAvailability,
    pub spread_velocity: FeatureAvailability,
    pub spread_state: FeatureAvailability,
    pub obi_1: FeatureAvailability,
    pub obi_3: FeatureAvailability,
    pub obi_5: FeatureAvailability,
    pub obi_10: FeatureAvailability,
    pub delta_obi_1m: FeatureAvailability,
    pub delta_obi_5m: FeatureAvailability,
    pub delta_obi_15m: FeatureAvailability,
    pub obi_z: FeatureAvailability,
    pub delta_obi_z: FeatureAvailability,
    pub microprice: FeatureAvailability,
    pub microprice_deviation: FeatureAvailability,
    pub micro_deviation_z: FeatureAvailability,
    pub bid_depth_1: FeatureAvailability,
    pub bid_depth_3: FeatureAvailability,
    pub bid_depth_5: FeatureAvailability,
    pub bid_depth_10: FeatureAvailability,
    pub ask_depth_1: FeatureAvailability,
    pub ask_depth_3: FeatureAvailability,
    pub ask_depth_5: FeatureAvailability,
    pub ask_depth_10: FeatureAvailability,
    pub depth_imbalance: FeatureAvailability,
    pub delta_bid_depth: FeatureAvailability,
    pub delta_ask_depth: FeatureAvailability,
    pub bid_liquidity_velocity: FeatureAvailability,
    pub ask_liquidity_velocity: FeatureAvailability,
    pub liquidity_state: FeatureAvailability,
    pub ofi_1m: FeatureAvailability,
    pub ofi_5m: FeatureAvailability,
    pub ofi_15m: FeatureAvailability,
    pub ofi_z: FeatureAvailability,
    pub price_book_divergence: FeatureAvailability,
    pub price_flow_divergence: FeatureAvailability,
    pub absorption: FeatureAvailability,
    pub replenishment: FeatureAvailability,
    pub ask_depletion_rate: FeatureAvailability,
    pub bid_depletion_rate: FeatureAvailability,
    pub ask_replenishment_rate: FeatureAvailability,
    pub bid_replenishment_rate: FeatureAvailability,
    pub price_impact_per_unit_volume: FeatureAvailability,
    pub cancellation_behavior: FeatureAvailability,
    pub liquidity_migration: FeatureAvailability,
    pub queue_position: FeatureAvailability,
    pub maker_fill_probability: FeatureAvailability,
    pub historical_fill: FeatureAvailability,
    pub microstructure_residual: FeatureAvailability,
    pub provider: String,
}

impl MicrostructureFeatures {
    pub fn trade_only() -> Self {
        let u = FeatureAvailability::UnavailableSource;
        Self {
            bid: u,
            ask: u,
            mid: u,
            spread: u,
            delta_spread: u,
            spread_velocity: u,
            spread_state: u,
            obi_1: u,
            obi_3: u,
            obi_5: u,
            obi_10: u,
            delta_obi_1m: u,
            delta_obi_5m: u,
            delta_obi_15m: u,
            obi_z: u,
            delta_obi_z: u,
            microprice: u,
            microprice_deviation: u,
            micro_deviation_z: u,
            bid_depth_1: u,
            bid_depth_3: u,
            bid_depth_5: u,
            bid_depth_10: u,
            ask_depth_1: u,
            ask_depth_3: u,
            ask_depth_5: u,
            ask_depth_10: u,
            depth_imbalance: u,
            delta_bid_depth: u,
            delta_ask_depth: u,
            bid_liquidity_velocity: u,
            ask_liquidity_velocity: u,
            liquidity_state: u,
            ofi_1m: u,
            ofi_5m: u,
            ofi_15m: u,
            ofi_z: u,
            price_book_divergence: u,
            price_flow_divergence: u,
            absorption: u,
            replenishment: u,
            ask_depletion_rate: u,
            bid_depletion_rate: u,
            ask_replenishment_rate: u,
            bid_replenishment_rate: u,
            price_impact_per_unit_volume: u,
            cancellation_behavior: u,
            liquidity_migration: u,
            queue_position: u,
            maker_fill_probability: u,
            historical_fill: u,
            microstructure_residual: u,
            provider: "TRADE_ONLY".to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct FairValueFeatures {
    pub fair_value_cents: Option<i32>,
    pub fair_value_model_version: Option<String>,
    pub fair_value_available: FeatureAvailability,
    pub edge_cents: Option<i32>,
    pub note: String,
}

impl FairValueFeatures {
    pub fn reserved() -> Self {
        Self {
            fair_value_cents: None,
            fair_value_model_version: None,
            fair_value_available: FeatureAvailability::UnavailableSource,
            edge_cents: None,
            note: "Reserved. Not estimated from settlement (would leak the label).".to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct FutureReturn {
    pub horizon_secs: i64,
    pub availability: FeatureAvailability,
    pub price_cents: Option<i32>,
    pub return_cents: Option<i32>,
    pub outcome_timestamp: Option<DateTime<Utc>>,
    pub source_observation_id: Option<String>,
}

impl FutureReturn {
    pub fn missing(horizon: i64, avail: FeatureAvailability) -> Self {
        Self {
            horizon_secs: horizon,
            availability: avail,
            price_cents: None,
            return_cents: None,
            outcome_timestamp: None,
            source_observation_id: None,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ForwardOutcomes {
    pub future_1m: FutureReturn,
    pub future_5m: FutureReturn,
    pub future_15m: FutureReturn,
    pub future_30m: FutureReturn,
    pub future_max_cents: Option<i32>,
    pub future_min_cents: Option<i32>,
    pub mfe_cents: Option<i32>,
    pub mae_cents: Option<i32>,
    pub time_to_profit_secs: Option<i64>,
    pub time_to_loss_secs: Option<i64>,
    pub settlement: SettlementOutcome,
    pub settlement_home: Option<u16>,
    pub settlement_away: Option<u16>,
}

/// A1 research entry bucket. Raw entry cents are always retained.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum A1EntryTarget {
    Entry80,
    Entry81,
    Entry82,
    Entry83,
    EntryOutOfBand,
}

impl A1EntryTarget {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Entry80 => "ENTRY_80",
            Self::Entry81 => "ENTRY_81",
            Self::Entry82 => "ENTRY_82",
            Self::Entry83 => "ENTRY_83",
            Self::EntryOutOfBand => "ENTRY_OUT_OF_BAND",
        }
    }

    pub fn from_entry_cents(cents: i32) -> Self {
        match cents {
            80 => Self::Entry80,
            81 => Self::Entry81,
            82 => Self::Entry82,
            83 => Self::Entry83,
            _ => Self::EntryOutOfBand,
        }
    }

    pub fn in_default_band(self) -> bool {
        !matches!(self, Self::EntryOutOfBand)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum A1ExitKind {
    Settlement,
    ModeledStop,
    ModeledHorizon,
}

impl A1ExitKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Settlement => "SETTLEMENT",
            Self::ModeledStop => "MODELED_STOP",
            Self::ModeledHorizon => "MODELED_HORIZON",
        }
    }
}

/// Observational P&L under one A1 exit. TRADE print, not a fill.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct A1ExitOutcome {
    pub exit_target: String,
    pub kind: A1ExitKind,
    pub availability: FeatureAvailability,
    pub triggered: bool,
    pub exit_price_cents: Option<i32>,
    pub return_cents: Option<i32>,
    pub exit_timestamp: Option<DateTime<Utc>>,
    pub source_observation_id: Option<String>,
    pub note: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct A1TargetFeatures {
    pub entry_target: A1EntryTarget,
    pub entry_band: String,
    pub in_default_band: bool,
    pub exits: Vec<A1ExitOutcome>,
}

impl A1TargetFeatures {
    pub fn outcome(&self, exit_target: &str) -> Option<&A1ExitOutcome> {
        self.exits.iter().find(|e| e.exit_target == exit_target)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct InteractionFlags {
    pub start_move_x_regime: String,
    pub start_bias_x_regime: String,
    pub start_move_x_velocity: String,
    pub velocity_x_volatility: String,
    pub score_diff_x_inning: String,
    pub base_out_x_inning: String,
    pub start_bias_x_score_diff: String,
    pub start_move_x_score_diff: String,
    pub sentiment_x_regime: String,
    pub sentiment_x_start_move: String,
    pub personality_x_regime: String,
    pub a1_entry_x_regime: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct B1EntrySnapshot {
    pub snapshot_id: String,
    pub game_id: String,
    pub market_id: String,
    pub ticker: Option<String>,
    pub contract_side: String,
    pub entry_timestamp: DateTime<Utc>,
    pub entry_signal_price_cents: i32,
    pub entry_trade_price_cents: i32,
    pub execution_status: String,
    pub observability: String,
    pub entry_state_id: Option<String>,
    pub entry_state_seq: Option<u32>,
    pub w5_observation_id: String,
    pub w5_prior_event_id: Option<String>,
    pub w7_path_id: Option<String>,
    pub w8_opportunity_id: String,
    pub first80_observation_id: Option<String>,
    pub first80_timestamp: Option<DateTime<Utc>>,
    pub confirm_observation_id: Option<String>,
    pub official_date: Option<String>,
    pub split_group: SplitGroup,
    pub baseball: BaseballStateFeatures,
    pub starting_market: StartingMarketFeatures,
    pub current_market: CurrentMarketFeatures,
    pub market_history: MarketHistoryFeatures,
    pub price_dynamics: PriceDynamicsFeatures,
    pub event_response: EventResponseFeatures,
    pub microstructure: MicrostructureFeatures,
    pub fair_value: FairValueFeatures,
    pub a1_targets: A1TargetFeatures,
    pub outcomes: ForwardOutcomes,
    pub interactions: InteractionFlags,
    pub feature_schema_version: String,
}

impl B1EntrySnapshot {
    pub fn observational_defaults() -> (&'static str, &'static str) {
        (EXECUTION_STATUS, OBSERVABILITY)
    }
}
