//! Compile-time firewall: W3 must not grow market/theta types.

/// Intentionally absent from this crate: MarketState, MarketPath, theta estimates.
pub const W3_FORBIDDEN_CONCEPTS: &[&str] = &[
    "MarketState",
    "MarketPath",
    "theta_value",
    "implied_probability",
    "orderbook",
    "SynchronizedState",
    "GameMarketEpisode",
];
