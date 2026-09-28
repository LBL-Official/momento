//! B1 must not invent L2, fills, live orders, or production strategy changes.

pub const B1_FORBIDDEN_CONCEPTS: &[&str] = &[
    "ORDER_FILLED",
    "FILLED_ENTRY",
    "POSITION_OPEN",
    "yes_bid",
    "yes_ask",
    "mid_price",
    "microprice",
    "order_flow_imbalance",
    "maker_fill_probability",
    "xgboost",
    "live_order_submit",
];
