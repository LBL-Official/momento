# Model gates

TRAIN: estimate mean curves, medoids, SVD, functionals.
VALIDATION: choose among {H0, HS, H2, H3, H4, H5}.
OOS: one pass.

A **path** model may replace H0 for a research entry discussion only if VAL:

1. Brier on Y_40_CLOSE ≤ 0.95 × Model 0 Brier
2. Brier ≤ HS (state-at-80) Brier − 0.001  (sequence must beat the endpoint)
3. ECE ≤ Model 0 ECE + 0.005
4. A predicted-q or prototype bucket with n ≥ 40 separates by ≥8pp or
   non-overlapping Wilson CIs
5. Optional reject rule (VAL q̂ thresholds {0.30, 0.333, 0.40}) has
   EV ≥ hold EV at remaining n ≥ 40

If (2) fails, the path is not adding information beyond Z_τ80.

OOS: freeze the winner. If it fails, **NO PRODUCTION CHANGE**.

Negative mean-curve / permutation results are reported as science,
not “fixed” by adding features.

Production line is never “production ready.”
