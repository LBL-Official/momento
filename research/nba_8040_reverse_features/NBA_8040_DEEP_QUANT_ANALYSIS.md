# NBA 80→40 deep quant analysis

Research only. Candle path ≠ fill. Association, not causation.
No trading filter. The Choosin Texas 2026–27 book is unchanged.

Generated: `2026-09-18T00:59:28.682826+00:00`

## 1. Executive Summary

Locked population N=604 (Q2=314, Q3=290, Q2 regular season=280).
Primary PCA uses the complete-column representation: N=604, p=77.
Q2 vs Q3 PCA composition: **COMPOSITIONALLY PARTIAL**.
Distance support: **partially_separated**.
Structural labels: **COMPOSITIONAL, STATE_DIFFERENTIAL, UNSTABLE**.

If a Q2 instance and a Q3 instance look similar on the non-time pre-80 columns, the matched T40 difference is -0.08375796178343942. On the full space the Q2→Q3 matched T40 difference is -0.08535031847133756. Period still carries a residual T40 difference after conditioning on the available non-time state, or the residual is too unstable to treat as composition. OBSERVED DIFFERENCE NOT EXPLAINED BY CURRENT FEATURE SET remains live for the outcome gap.

`RESEARCH ONLY — NO TRADING FILTER CREATED.`

## 2. Research Question

Why does NBA Q2 FIRST80 80→40 behave differently from Q3 on candle path?
Not: which filter raises a ledger number.

## 3. Population Lock

| lock | N |
| --- | ---: |
| Q2∪Q3 | 604 |
| Q2 all-phase | 314 |
| Q3 all-phase | 290 |
| Q2 regular season | 280 |

Instance = one FIRST80 trigger per event. `instance_id` is unique on all 604.

## 4. Instance Definition

First tradable `yes_bid_close ≥ 80` after a prior close `< 80`, spread ≤ 10¢.
Not a later 80 reprint. Not a game-level collapse.

## 5. Feature Inventory

See `reports/FEATURE_INVENTORY.md`. Every store column is listed.
Labels remain in `labels/outcomes.parquet`.

## 6. Data Availability

Observable: quote-at-entry, pre-80 TRADABLE_YES_BID path, modeled clock, score snapshot, pre-tip open.
Unavailable: historical L2, fills, possession/fouls/timeouts at the candle, PBP↔candle PIT, opposite ticker.

## 7. Missingness

Complete columns p=77 N=604. Complete-case N=601 p=78. Missing-indicator N=604 p=79. Zero-coverage excluded from numeric PCA: ['accel_1m', 'std_1m', 'direction_changes_1m', 'accel_3m']. Missing residuals in the indicator representation are set to the observed mean after z-score, never to an economic zero.

## 8. Analytical Matrix

`features/pre80_matrix.parquet` holds instance keys, every predictive column, and `miss_*` indicators.
Manifest: `reports/PCA_FEATURE_MANIFEST.json`.

## 9. Correlation Structure

See `reports/FEATURE_CORRELATION.md`. Correlated columns are retained.

## 10. PCA Method

`numpy.linalg.svd` on z-scored complete columns. No sklearn. No labels in the fit.

## 11. PCA Results

Dimensions for 50/75/90/95% variance: {'dims_for_50pct': 3, 'dims_for_75pct': 8, 'dims_for_90pct': 15, 'dims_for_95pct': 20}.
See `reports/PCA_REPORT.md`.

## 12. Feature-Class PCA

See the class sections of `PCA_REPORT.md`. PERIOD one-hot is class-only and is not in ALL_PRE80.

## 13. Q2/Q3 State Composition

COMPOSITIONALLY PARTIAL

| pc | q2_mean | q3_mean | smd | overlap |
| --- | --- | --- | --- | --- |
| 1 | -1.3575 | 1.4699 | -0.6223 | 0.7248 |
| 2 | -0.2785 | 0.3015 | -0.2074 | 0.8482 |
| 3 | 0.2288 | -0.2478 | 0.1905 | 0.8865 |
| 4 | -0.4220 | 0.4569 | -0.4378 | 0.7949 |
| 5 | 0.2411 | -0.2611 | 0.2531 | 0.8246 |
| 6 | -0.0803 | 0.0869 | -0.0861 | 0.8406 |


## 14. Outcome Overlay

Predetermined quintiles on PCs fitted without T40. See PCA report.

## 15. KNN Method

Euclidean on the same z-matrix. k ∈ {5,10,20,30}. Distances do not use labels.

## 16. KNN Results

| k | mean_agreement | mean_entropy | mean_cross_period_share |
| --- | --- | --- | --- |
| 5 | 0.6202 | 0.6648 | 0.2477 |
| 10 | 0.6225 | 0.7507 | 0.2820 |
| 20 | 0.6188 | 0.7873 | 0.3105 |
| 30 | 0.6181 | 0.7982 | 0.3330 |


## 17. Cross-Period Matching

| source_period | n | source_t40 | matched_t40 | difference |
| --- | --- | --- | --- | --- |
| Q2 | 314 | 0.2389 | 0.3242 | -0.0854 |
| Q3 | 290 | 0.2724 | 0.2341 | 0.0383 |


## 18. Distance Geometry

Support **partially_separated**. Median cross/within = 1.1502.

## 19. Local Outcome Homogeneity

Neighborhood T40 entropy and agreement are in `KNN_REPORT.md`.

## 20. Permutation Null

| k | observed_agreement | null_mean | null_p025 | null_p975 | percentile_of_observed |
| --- | --- | --- | --- | --- | --- |
| 5 | 0.6202 | 0.6197 | 0.5996 | 0.6365 | 0.5300 |
| 10 | 0.6225 | 0.6192 | 0.6036 | 0.6349 | 0.6900 |
| 20 | 0.6188 | 0.6193 | 0.6084 | 0.6335 | 0.5100 |
| 30 | 0.6181 | 0.6192 | 0.6091 | 0.6315 | 0.4800 |


## 21. Conditional Q2/Q3 Analysis

Pre-specified nearest-neighbor distance quantiles 0.25 / 0.50 / 0.75.

| direction | quantile | n | source_t40 | matched_t40 | difference |
| --- | --- | --- | --- | --- | --- |
| Q2_to_Q3 | 0.2500 | 79 | 0.1899 | 0.3038 | -0.1139 |
| Q2_to_Q3 | 0.5000 | 157 | 0.1975 | 0.3376 | -0.1401 |
| Q2_to_Q3 | 0.7500 | 235 | 0.2340 | 0.3489 | -0.1149 |
| Q3_to_Q2 | 0.2500 | 73 | 0.2329 | 0.2329 | 0.0000 |
| Q3_to_Q2 | 0.5000 | 145 | 0.2897 | 0.2690 | 0.0207 |
| Q3_to_Q2 | 0.7500 | 217 | 0.2857 | 0.2673 | 0.0184 |


## 22. State Balancing

Linear probability of Q2 membership from pre-80 state (not T40).
Full-space AUC=1.0, R²=1.0.
Non-time AUC=0.8476718647045903.

| direction | n | source_t40 | matched_t40 | difference |
| --- | --- | --- | --- | --- |
| Q2_to_Q3 | 314 | 0.2389 | 0.3631 | -0.1242 |
| Q3_to_Q2 | 290 | 0.2724 | 0.2034 | 0.0690 |


## 23. Feature-Class Ablation

| set | key | p | pc1_smd_q2_q3 | knn_k10_agreement | q2_to_q3_t40_diff | distance_support |
| --- | --- | --- | --- | --- | --- | --- |
| A_PRICE | PRICE | 17 | -0.6110 | 0.6119 | -0.0548 | largely_overlapping |
| B_TIME | TIME | 4 | -1.0605 | 0.6146 | -0.1379 | strongly_separated |
| C_SCORE | SCORE | 5 | 0.0753 | 0.6373 | -0.1217 | largely_overlapping |
| D_OPEN | OPEN | 2 | -0.3704 | 0.6189 | -0.0398 | largely_overlapping |
| E_MARKET_PATH | MARKET_PATH | 28 | -0.5956 | 0.6123 | -0.0710 | largely_overlapping |
| F_VOLATILITY | VOLATILITY | 14 | 0.3911 | 0.6045 | -0.0710 | largely_overlapping |
| G_PERIOD | PERIOD | 2 | 0.0000 | 0.7063 | -0.2611 | strongly_separated |
| H_PRICE_TIME | PRICE_TIME | 21 | -0.8055 | 0.6204 | -0.0548 | partially_separated |
| I_PRICE_SCORE | PRICE_SCORE | 22 | -0.6003 | 0.6199 | -0.0455 | largely_overlapping |
| J_TIME_SCORE | TIME_SCORE | 9 | -0.3370 | 0.6257 | -0.0395 | strongly_separated |
| K_ALL_PRE80 | ALL_PRE80 | 77 | -0.6223 | 0.6225 | -0.0854 | partially_separated |


## 24. Interaction Structure

Predetermined tertiles only. See `STATE_SPACE_REPORT.md`.

## 25. Temporal Normalization

| variant | pc1_smd | support | k10_agreement |
| --- | --- | --- | --- |
| all_pre80 | -0.6223 | partially_separated | 0.6225 |
| ex_time | -0.5655 | largely_overlapping | 0.6149 |
| time_frac_plus_nontime | -0.5929 | largely_overlapping | 0.6214 |
| time_raw_plus_nontime | -0.5929 | largely_overlapping | 0.6214 |


## 26. Season Stability

| split | n | q2_n | q3_n | pc1_smd | raw_t40_diff | knn_k10_agreement |
| --- | --- | --- | --- | --- | --- | --- |
| IN_SAMPLE | 236 | 125 | 111 | -0.7781 | -0.0663 | 0.6072 |
| VALIDATION | 248 | 119 | 129 | -0.6755 | 0.0040 | 0.6371 |
| OOS | 120 | 70 | 50 | -0.2958 | -0.0457 | 0.6225 |


## 27. Bootstrap Uncertainty

{'seed': 8040, 'n_boot': 200, 'raw_t40_diff': {'observed': -0.03356028991873489, 'boot_p025': -0.10671214529612626, 'boot_p50': -0.02957496192691983, 'boot_p975': 0.034648371039886605}, 'pc1_smd': {'boot_p025': -0.7989176952430607, 'boot_p50': -0.6216229532197581, 'boot_p975': -0.46466682712215795}, 'matched_q50_reference': {'direction': 'Q2_to_Q3', 'quantile': 0.5, 'distance_cutoff': 5.476218834446315, 'n': 157, 'source_t40': 0.19745222929936307, 'matched_t40': 0.3375796178343949, 'difference': -0.14012738853503182, 'source_s': 0.802547770700637, 'matched_s': 0.6624203821656051, 'source_t40_wilson': [0.14273446406922466, 0.2666223192505136], 'matched_t40_wilson': [0.26827380211481894, 0.4146440499831458], 'source_period': 'Q2', 'match_period': 'Q3'}}

## 28. Information Gap

OBSERVABLE: market at 80, pre-80 path, modeled clock, score snapshot, pre-tip open, quote-at-entry, window volatility.
UNAVAILABLE: L2, fills, possession/fouls/timeouts, PBP↔candle PIT, hidden order flow.

## 29. H1–H8 Assessment

- **H1 TIME** — PARTIALLY_SUPPORTED. TIME-only PC1 |SMD|=1.061; ALL PC1 |SMD|=0.622; EX_TIME PC1 |SMD|=0.566. Clock separates periods. Removing time does not absorb the T40 residual.
- **H2 SCORE** — NOT_SUPPORTED. SCORE ablation PC1 SMD=0.07528295836983148. Score-at-80 stays similar.
- **H3 OPEN** — PARTIALLY_SUPPORTED. OPEN PC1 SMD=-0.37038955903014914. Composition only unless matching absorbs T40.
- **H4 PRE-80 PATH** — PARTIALLY_SUPPORTED. PRICE PC1 SMD=-0.6109803368608127.
- **H5 GAME STATE** — UNAVAILABLE. Possession / fouls / timeouts remain SOURCE_UNAVAILABLE.
- **H6 L2** — UNAVAILABLE. Historical L2 remains SOURCE_UNAVAILABLE.
- **H7 JOINT STATE** — NOT_SUPPORTED. |KNN agreement − null| at k=10 is 0.0033.
- **H8 RESIDUAL** — UNEXPLAINED. Q2→Q3 matched T40 difference=-0.08535031847133756. Split T40 diffs=[-0.0663063063063063, 0.004038824832258481, -0.045714285714285735].

## 30. Final Structural Conclusion

**COMPOSITIONAL, STATE_DIFFERENTIAL, UNSTABLE**

Q2 and Q3 occupy different clock regions by construction. Removing time shrinks PC1 |SMD| from 0.622 to 0.566. Neighborhood T40 agreement stays near the permutation baseline. Cross-period matching does not convert Q2 outcomes into Q3 outcomes in a stable way. IN/VAL/OOS raw T40 differences are [-0.0663063063063063, 0.004038824832258481, -0.045714285714285735]. Multiple descriptive labels may coexist; none is a trading instruction.

## 31. Research Limitations

N=604 is the asked-six lock, not a resample. Clock is `PERIOD_BOUNDED_LINEAR_GAME_CLOCK`, not warehouse PIT.
Complete-column PCA drops zero-coverage window summaries (`std_1m`, `accel_1m`, …) rather than filling them.
IN/VAL/OOS cells are modest. Candle path is not a fill.

## 32. Explicit Non-Trading Conclusion

This study does not produce a rule, a book edit, a live signal, or a claimed edge.
`RESEARCH ONLY — NO TRADING FILTER CREATED.`
