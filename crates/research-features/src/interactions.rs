//! Enumerated, versioned interactions. No combinatorial explosion.

use crate::types::{
    A1EntryTarget, BaseballStateFeatures, InteractionFlags, MarketHistoryFeatures,
    PriceDynamicsFeatures, StartSentiment,
};

fn vel_bucket(v: Option<i64>) -> &'static str {
    match v {
        None => "NA",
        Some(x) if x > 0 => "UP",
        Some(x) if x < 0 => "DOWN",
        Some(_) => "FLAT",
    }
}

fn vol_bucket(v: Option<i32>) -> &'static str {
    match v {
        None => "NA",
        Some(x) if x <= 1 => "LOW",
        Some(x) if x <= 4 => "MED",
        Some(_) => "HIGH",
    }
}

fn bias_bucket(cents: Option<i32>) -> &'static str {
    match cents {
        None => "NA",
        Some(x) if x < 0 => "UNDER",
        Some(0) => "EVEN",
        Some(_) => "OVER",
    }
}

pub fn interactions(
    baseball: &BaseballStateFeatures,
    start_bias: Option<i32>,
    start_sentiment: StartSentiment,
    entry_target: A1EntryTarget,
    hist: &MarketHistoryFeatures,
    dyns: &PriceDynamicsFeatures,
) -> InteractionFlags {
    let inn = baseball
        .inning
        .map(|i| i.to_string())
        .unwrap_or_else(|| "NA".into());
    let lead = baseball
        .bound_team_lead
        .map(|l| l.to_string())
        .unwrap_or_else(|| "NA".into());
    let move_b = hist
        .start_to_entry_move_bucket
        .clone()
        .unwrap_or_else(|| "NA".into());
    let vel = vel_bucket(dyns.p_1m.velocity_cents_per_sec_e6);
    InteractionFlags {
        start_move_x_regime: format!("{}|{}", move_b, baseball.regime.as_str()),
        start_bias_x_regime: format!("{}|{}", bias_bucket(start_bias), baseball.regime.as_str()),
        start_move_x_velocity: format!("{move_b}|{vel}"),
        velocity_x_volatility: format!("{}|{}", vel, vol_bucket(hist.volatility_5m_cents)),
        score_diff_x_inning: format!("{lead}|{inn}"),
        base_out_x_inning: format!(
            "{}|{inn}",
            baseball.base_out_state.as_deref().unwrap_or("NA")
        ),
        start_bias_x_score_diff: format!("{}|{lead}", bias_bucket(start_bias)),
        start_move_x_score_diff: format!("{move_b}|{lead}"),
        sentiment_x_regime: format!("{}|{}", start_sentiment.as_str(), baseball.regime.as_str()),
        sentiment_x_start_move: format!("{}|{move_b}", start_sentiment.as_str()),
        personality_x_regime: format!("{}|{}", hist.personality.as_str(), baseball.regime.as_str()),
        a1_entry_x_regime: format!("{}|{}", entry_target.as_str(), baseball.regime.as_str()),
    }
}
