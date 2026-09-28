//! W5 must not grow W6 matrices, Greeks, or FIRST01 replay.

pub const W5_FORBIDDEN_CONCEPTS: &[&str] = &[
    "TransitionMatrix",
    "theta_value",
    "event_theta",
    "market_theta",
    "implied_probability",
    "GameMarketEpisode",
];
