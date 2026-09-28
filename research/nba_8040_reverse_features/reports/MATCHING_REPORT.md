# Matching report

Descriptive only. Q2 instances are placed next to nearest Q3 states and conversely.
Same-instance matching is impossible because periods differ.

| source_period | match_period | k | n | source_t40 | matched_t40 | difference | source_s | matched_s | median_nearest_distance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q2 | Q3 | 10 | 314 | 0.2389 | 0.3242 | -0.0854 | 0.7611 | 0.6758 | 5.4762 |
| Q3 | Q2 | 10 | 290 | 0.2724 | 0.2341 | 0.0383 | 0.7276 | 0.7659 | 5.8424 |

## Distance-quantile thresholds (pre-specified, not outcome-tuned)

| direction | quantile | distance_cutoff | n | source_t40 | matched_t40 | difference | source_s | matched_s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q2_to_Q3 | 0.2500 | 4.9838 | 79 | 0.1899 | 0.3038 | -0.1139 | 0.8101 | 0.6962 |
| Q2_to_Q3 | 0.5000 | 5.4762 | 157 | 0.1975 | 0.3376 | -0.1401 | 0.8025 | 0.6624 |
| Q2_to_Q3 | 0.7500 | 6.0681 | 235 | 0.2340 | 0.3489 | -0.1149 | 0.7660 | 0.6511 |
| Q3_to_Q2 | 0.2500 | 5.0541 | 73 | 0.2329 | 0.2329 | 0.0000 | 0.7671 | 0.7671 |
| Q3_to_Q2 | 0.5000 | 5.8424 | 145 | 0.2897 | 0.2690 | 0.0207 | 0.7103 | 0.7310 |
| Q3_to_Q2 | 0.7500 | 7.0547 | 217 | 0.2857 | 0.2673 | 0.0184 | 0.7143 | 0.7327 |

## Propensity (linear probability of Q2 from pre-80 state)

Full-space linear probability of period is degenerate when clock is included (period is a near-linear function of game time). Matching below uses the non-time state only.

| direction | n | source_t40 | matched_t40 | difference | median_propensity_gap |
| --- | --- | --- | --- | --- | --- |
| Q2_to_Q3 | 314 | 0.2389 | 0.3631 | -0.1242 | 0.0023 |
| Q3_to_Q2 | 290 | 0.2724 | 0.2034 | 0.0690 | 0.0023 |

