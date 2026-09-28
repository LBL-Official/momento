//! W8 must not grow fills, P&L, Greeks, L2 invention, or live order submission.

pub const W8_FORBIDDEN_CONCEPTS: &[&str] = &[
    "realized_pnl",
    "unrealized_pnl",
    "ORDER_FILLED",
    "POSITION_OPEN",
    "yes_bid",
    "yes_ask",
    "mid_price",
    "xgboost",
    "monte_carlo",
    "theta_value",
    "maker_fill",
    "settlement_pnl",
];
