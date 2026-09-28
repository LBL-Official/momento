//! Compile-time firewall: W4 must not grow sync/theta types.

/// Intentionally absent from this crate.
pub const W4_FORBIDDEN_CONCEPTS: &[&str] = &[
    "SynchronizedState",
    "theta_value",
    "event_theta",
    "market_theta",
    "implied_probability",
];
