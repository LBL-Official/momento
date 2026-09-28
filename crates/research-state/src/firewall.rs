//! W6 must not grow W7 paths, Greeks, FIRST01, or market invention.

pub const W6_FORBIDDEN_CONCEPTS: &[&str] = &[
    "theta_value",
    "event_theta",
    "implied_probability",
    "FIRST01",
    "xgboost",
    "monte_carlo",
    "yes_bid",
    "orderbook",
    "starting_price",
    "MarketPricePath",
];
