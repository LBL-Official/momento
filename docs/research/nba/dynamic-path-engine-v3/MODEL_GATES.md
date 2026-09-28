# Model gates

TRAIN: fit. VALIDATION: choose. OOS: one pass.

Model 2/3/4 may replace Model 0 for **research warning** only if VAL:

1. Clustered Brier on H_40_5M ≤ 0.95 × Model 0 Brier
2. ECE ≤ Model 0 ECE + 0.005
3. Usable predicted-hazard buckets (n_trades ≥ 30) separate by ≥8pp or
   non-overlapping Wilson CIs on realized 5m event rate
4. Early-warning policy (pre-registered thresholds) has VAL EV ≥ hold EV
   **or** max DD materially lower without destroying survival EV, using
   conservative simulated exit quotes

OOS: freeze the winner. If it fails, **NO PRODUCTION CHANGE**.

Policy thresholds (VAL only): 5m hazard ∈ {0.05, 0.10, 0.15, 0.20, 0.25};
persistence N ∈ {1, 2, 3}.

Exit quote: next completed candle `yes_bid_close` after warning.
Labeled **SIMULATED**; not a fill. Same-bar 1m order unknown.

Production line is never “production ready”.
