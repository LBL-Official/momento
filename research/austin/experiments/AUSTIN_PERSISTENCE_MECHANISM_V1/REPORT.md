AUSTIN DRE
PHASE 2 — PERSISTENCE MECHANISM

DISCOVERY ONLY

MODEL FROZEN
POLICY UNFROZEN
CONFIRMATION UNTOUCHED

LIVE FEED UNAVAILABLE
EXECUTION DISABLED

# 1. EXECUTIVE RESEARCH SUMMARY

Phase 2 asks whether persistence of a negative Austin EV contains incremental information
beyond EV < 0, whether that distinction is visible at t0/t1/t2, and whether it appears
while meaningful adverse movement still remains.

Gate A persistence economics: MIXED
Gate B PIT distinguishability: SUPPORTED
Gate C timing: MIXED
Gate D H2_1 alignment: EXPECTED_FROM_CANONICAL_TIMING
Earliest predetermined checkpoint with any PIT separation: t1
Phase 3 justified: False
Acceptance reading: valid state diagnosis — not an actionable risk mechanism

Some adverse cents remain after t0/t1 on persistent paths, but Discovery AVAILABLE warning among eventual losses remains 0. Hindsight persistence is not the same as a before-damage signal.

Temporary / persistent labels are future-derived descriptive outcomes. They are not PIT features.

# 2. PHASE IDENTITY

phase PHASE_2
phase_name PERSISTENCE MECHANISM
audit_id AUSTIN_PERSISTENCE_MECHANISM_V1
source_suite AUSTIN_NCAAB_TRANSFER_V1
source_experiment_A NCAAB_H1_2_AUSTIN_TRANSFER_V1
source_experiment_B NCAAB_H2_1_AUSTIN_TRANSFER_V1
observation_schedule EVERY_2_GAME_CLOCK_MINUTES
EV_definition hold_80_to_settlement
confirmation_accessed False
policy_status UNFROZEN
policy_selected NONE
execution_enabled False
submits False

# 3. MODEL / COHORT LOCKS

model_version austin_v2
dataset_version choosin_nba_2q3q_604
model_manifest_hash 4a47bf9ad3a2fcd4bb092a77cf93d534e308423deec29e33b6e6bad85c76431c
feature_schema_hash ebd49948320720f7f8acb15ae46a03d5fc703c8c0f29a6be9e52f3d4442031ab
pca_version austin_pca_v1
K 25
A discovery hash f7bc6280913c63a2a50cb5181b0c523c5492bbdb47da167d9639e2f867a87e36
A confirmation hash 4bc027bddba0f723b914b2d80e0ff49ae0eb0bff94711860e310737941e0f0e4
B discovery hash 699e6bb65fe4fa3dffc566b352f089c109ffadfb501b830e2c129f2e66450840
B confirmation hash 1ce8a0b2f3d3ee88d34cb0e4833cf3369aa776fc75bff912d7e2f3b2a4173c51
git_commit UNAVAILABLE reason=not_a_git_repo
NCAAB is query-only. It does not enter scaler, PCA, or KNN.

# 4. WHY PHASE 2 EXISTS

Phase 1 showed Austin can mark worse states. EV < 0 is not 'this trade will lose.'
H1_2 discovery first-negative (timestamp-order interpretation) was 67 / 47 temporary /
15 persistent / 5 unresolved. H2_1 was 22 / 5 / 5 / 12. Phase 1 AVAILABLE warning
among eventual losses remains A 0/15 and B 0/12. Phase 2 does not rerun Phase 1
and does not redefine that warning.

# 5. FIRST-NEGATIVE POPULATIONS

t0 is the earliest valid PRIMARY_GRID Austin state with conditional_EV < 0.
Diagnostic 42/41/40/T40/ENTRY rows do not define t0 unless they are PRIMARY_GRID.

A N first-negative 67 temporary 51 persistent 15 unresolved 1
B N first-negative 22 temporary 5 persistent 6 unresolved 11

Later is PRIMARY_GRID clock order. Discovery interpretation used timestamp order,
so class counts can differ without changing Phase 1 files.

# 6. TEMPORARY VS PERSISTENT NEGATIVE EV

TEMPORARY_NEGATIVE_EV = later valid PRIMARY EV >= 0 exists.
PERSISTENT_NEGATIVE_EV = later valid PRIMARY EV exists and all stay < 0.
UNRESOLVED_NO_LATER_VALID_EV = no later valid PRIMARY EV.
Missing later observations never imply persistent.

### A · H1_2 · TEMPORARY VS PERSISTENT

N first-negative 67
N temporary 51
N persistent 15
N unresolved 1

| Metric | Temporary | Persistent | Difference | 95% CI |
| --- | --- | --- | --- | --- |
| N | 51 | 15 | UNAVAILABLE |  |
| Win rate | 0.8627 | 0.6000 | UNAVAILABLE |  |
| Loss rate | 0.1373 | 0.4000 | 0.2627 | 0.2627 CI=[-0.0001, 0.5270] MIXED |
| Mean subsequent PNL | 6.2745 | -20.0000 | -26.2745 | -26.2745 CI=[-52.7017, 0.0146] MIXED |
| Median subsequent PNL | 20.0000 | 20.0000 | UNAVAILABLE |  |
| T40 rate | 1.0000 | 1.0000 | 0.0000 | 0.0000 CI=[0.0000, 0.0000] MIXED |
| Future MAE | 9.2157 | 20.0667 | 10.8510 | 10.8510 CI=[-5.0758, 28.3390] MIXED |
| Future MFE | 19.2941 | 1.6667 | -17.6275 | -17.6275 CI=[-23.0373, -12.4129] SUPPORTED |
| Recover ≥50 | 1.0000 | 1.0000 | UNAVAILABLE |  |
| Recover ≥60 | 1.0000 | 0.8000 | UNAVAILABLE |  |
| Recover ≥70 | 0.9804 | 0.5333 | UNAVAILABLE |  |
| Recover ≥80 | 0.9020 | 0.4000 | UNAVAILABLE |  |
| First-negative EV | -27.3321 | -33.5601 | UNAVAILABLE |  |
| EV change from entry | -12.1724 | -11.1221 | UNAVAILABLE |  |
| Price at t0 | 75.6078 | 72.7333 | UNAVAILABLE |  |
| Price travel | -6.3922 | -8.9333 | UNAVAILABLE |  |
| Game time remaining | 1117.6471 | 972.0000 | UNAVAILABLE |  |

### B · H2_1 · TEMPORARY VS PERSISTENT

N first-negative 22
N temporary 5
N persistent 6
N unresolved 11

| Metric | Temporary | Persistent | Difference | 95% CI |
| --- | --- | --- | --- | --- |
| N | 5 | 6 | UNAVAILABLE |  |
| Win rate | 1.0000 | 0.3333 | UNAVAILABLE |  |
| Loss rate | 0.0000 | 0.6667 | 0.6667 | 0.6667 CI=[0.2500, 1.0000] SUPPORTED |
| Mean subsequent PNL | 20.0000 | -46.6667 | -66.6667 | -66.6667 CI=[-100.0000, -25.0000] SUPPORTED |
| Median subsequent PNL | 20.0000 | -80.0000 | UNAVAILABLE |  |
| T40 rate | 1.0000 | 1.0000 | 0.0000 | 0.0000 CI=[0.0000, 0.0000] MIXED |
| Future MAE | 17.2000 | 18.8333 | 1.6333 | 1.6333 CI=[-25.5083, 29.5733] MIXED |
| Future MFE | 21.0000 | -5.1667 | -26.1667 | -26.1667 CI=[-38.8982, -11.5233] SUPPORTED |
| Recover ≥50 | 1.0000 | 0.3333 | UNAVAILABLE |  |
| Recover ≥60 | 1.0000 | 0.1667 | UNAVAILABLE |  |
| Recover ≥70 | 1.0000 | 0.1667 | UNAVAILABLE |  |
| Recover ≥80 | 1.0000 | 0.0000 | UNAVAILABLE |  |
| First-negative EV | -20.5831 | -43.7343 | UNAVAILABLE |  |
| EV change from entry | -8.7174 | -8.7338 | UNAVAILABLE |  |
| Price at t0 | 78.0000 | 52.6667 | UNAVAILABLE |  |
| Price travel | -5.4000 | -29.5000 | UNAVAILABLE |  |
| Game time remaining | 456.0000 | 160.0000 | UNAVAILABLE |  |

# 7. ECONOMIC SEPARATION

A Δ PNL -26.2745 CI=[-52.7017, 0.0146] MIXED
A Δ loss rate 0.2627 CI=[-0.0001, 0.5270] MIXED
B Δ PNL -66.6667 CI=[-100.0000, -25.0000] SUPPORTED
B Δ loss rate 0.6667 CI=[0.2500, 1.0000] SUPPORTED

A and B are never pooled as the headline. Appendix A+B is descriptive only.

# 8. PIT DIFFERENCES AT t0

Question: before seeing the future Austin path, were persistent-negative trades already different at t0?
Differences are not a rule.

### A · t0 PIT

| Feature | Temporary | Persistent | Difference | 95% CI | Effect size |
| --- | --- | --- | --- | --- | --- |
| EV | -27.3321 | -33.5601 | -6.2279 | [-20.7854, 10.0348] | -0.2410 |
| EV depth | 27.3321 | 33.5601 | 6.2279 | [-10.0348, 20.7854] | 0.2410 |
| ΔEV from entry | -12.1724 | -11.1221 | 1.0502 | [-12.6859, 12.6001] | 0.0447 |
| ΔEV from previous | -43.7998 | -35.9662 | 7.8336 | [-20.7625, 32.6905] | 0.3205 |
| EV slope | -9.0698 | -4.7061 | 4.3637 | [-1.7289, 10.0575] | 0.6238 |
| CI lower | -43.4529 | -49.8667 | -6.4137 | [-18.9810, 7.9572] | -0.2948 |
| CI upper | -11.9922 | -17.0667 | -5.0745 | [-21.4284, 11.8535] | -0.1748 |
| CI width | 31.4608 | 32.8000 | 1.3392 | [-3.7928, 6.1249] | 0.1230 |
| Price travel | -6.3922 | -8.9333 | -2.5412 | [-10.9519, 6.0700] | -0.1528 |
| Score diff travel | -1.1373 | -3.2000 | -2.0627 | [-4.9263, 1.0576] | -0.3675 |
| Time since entry | 364.2549 | 584.2000 | 219.9451 | [-44.3659, 502.9105] | 0.6461 |
| Time remaining | 1117.6471 | 972.0000 | -145.6471 | [-399.6573, 89.4982] | -0.4687 |
| ESS | 24.7563 | 24.5715 | -0.1848 | [-0.5433, 0.1230] | -0.4521 |
| Median distance | 1.1908 | 1.0619 | -0.1289 | [-0.3223, 0.1046] | -0.2631 |

### B · t0 PIT

| Feature | Temporary | Persistent | Difference | 95% CI | Effect size |
| --- | --- | --- | --- | --- | --- |
| EV | -20.5831 | -43.7343 | -23.1513 | [-41.9341, -2.3650] | -1.2577 |
| EV depth | 20.5831 | 43.7343 | 23.1513 | [2.3650, 41.9341] | 1.2577 |
| ΔEV from entry | -8.7174 | -8.7338 | -0.0164 | [-20.4526, 15.9291] | -0.0009 |
| ΔEV from previous | -21.7935 | -44.8196 | -23.0261 | [-24.6989, -21.3533] | UNAVAILABLE |
| EV slope | -8.3817 | -3.7431 | 4.6386 | [1.2871, 7.9901] | UNAVAILABLE |
| CI lower | -38.4000 | -59.3333 | -20.9333 | [-38.5194, -1.8376] | -1.2904 |
| CI upper | -3.1600 | -26.6667 | -23.5067 | [-42.4830, -2.6600] | -1.2461 |
| CI width | 35.2400 | 32.6667 | -2.5733 | [-9.3502, 3.7669] | -0.4157 |
| Price travel | -5.4000 | -29.5000 | -24.1000 | [-41.2712, -8.2458] | -1.6824 |
| Score diff travel | -1.6000 | -7.6667 | -6.0667 | [-9.8350, -2.1655] | -1.7974 |
| Time since entry | 335.8000 | 679.5000 | 343.7000 | [113.9458, 525.4500] | 1.7204 |
| Time remaining | 456.0000 | 160.0000 | -296.0000 | [-531.4571, 34.5714] | -1.0895 |
| ESS | 23.7956 | 22.5789 | -1.2167 | [-2.5984, 0.3235] | -0.8963 |
| Median distance | 0.9527 | 0.8212 | -0.1315 | [-0.6434, 0.3299] | -0.2939 |

t0 status A/B features SUPPORTED: [] / ['first_negative_EV', 'EV_DEPTH_BELOW_ZERO', 'CI_LOWER', 'CI_UPPER', 'PRICE', 'PRICE_TRAVEL', 'SCORE_TRAVEL', 'SCORE_DIFF_TRAVEL', 'TIME_SINCE_ENTRY']

# 9. t1 TRAJECTORY

t1 is the next valid PRIMARY_GRID state only. No interpolation.
Question: does one additional predetermined checkpoint materially improve separation?

### A · t1

| Feature | Temporary | Persistent | Difference | 95% CI | Effect size |
| --- | --- | --- | --- | --- | --- |
| EV | -5.3850 | -27.8777 | -22.4927 | [-32.4541, -12.3851] | -1.4150 |
| ΔEV from t0 | 21.9471 | 5.6823 | -16.2648 | [-29.0752, -1.6113] | -0.5834 |
| EV velocity | 7.1163 | -2.6670 | -9.7833 | [-17.3799, -3.6311] | -0.7567 |
| CI lower | -21.6510 | -46.1333 | -24.4824 | [-34.9891, -13.7359] | -1.3247 |
| CI upper | 8.8686 | -9.6000 | -18.4686 | [-27.2706, -9.6028] | -1.4689 |
| CI width | 30.5196 | 36.5333 | 6.0137 | [3.2940, 8.9088] | 0.7379 |
| Price change | 3.9412 | 0.1333 | -3.8078 | [-8.6706, 0.2725] | -0.3170 |
| Score diff change | 0.4902 | 0.0000 | -0.4902 | [-1.7709, 0.4546] | -0.1429 |
| ESS | 24.8609 | 24.6798 | -0.1811 | [-0.5339, 0.0774] | -0.4677 |
| Median distance | 1.5496 | 1.3759 | -0.1736 | [-0.4037, 0.0458] | -0.4508 |

### B · t1

| Feature | Temporary | Persistent | Difference | 95% CI | Effect size |
| --- | --- | --- | --- | --- | --- |
| EV | 3.9043 | -54.9628 | -58.8670 | [-79.1589, -32.0074] | -2.6440 |
| ΔEV from t0 | 24.4873 | -11.2284 | -35.7158 | [-69.8177, -2.2907] | -1.1531 |
| EV velocity | 4.6408 | 0.4789 | -4.1618 | [-18.1455, 16.5922] | -0.3766 |
| CI lower | -9.6000 | -66.0000 | -56.4000 | [-79.2233, -29.3024] | -2.5615 |
| CI upper | 15.2000 | -42.6667 | -57.8667 | [-81.6833, -32.1333] | -2.5135 |
| CI width | 24.8000 | 23.3333 | -1.4667 | [-17.4371, 14.0000] | -0.1102 |
| Price change | 14.0000 | -18.1667 | -32.1667 | [-55.4200, -14.3183] | -1.6776 |
| Score diff change | 1.4000 | 2.0000 | 0.6000 | [-6.2542, 7.3929] | 0.1037 |
| ESS | 24.5878 | 23.5118 | -1.0760 | [-1.9022, -0.3431] | -1.4176 |
| Median distance | 0.8063 | 1.0880 | 0.2817 | [-0.0379, 0.6310] | 0.8769 |

t1 status: SUPPORTED

# 10. t2 TRAJECTORY

Question: by two subsequent 2-minute checkpoints, is persistent deterioration clearly distinguishable?
Descriptive only. No optimal checkpoint search.

### A · t2

| Feature | Temporary | Persistent | Difference | 95% CI | Effect size |
| --- | --- | --- | --- | --- | --- |
| EV | -6.9390 | -27.9528 | -21.0138 | [-30.7226, -9.9924] | -1.1802 |
| ΔEV from t0 | 20.3931 | 6.3390 | -14.0542 | [-28.4153, 1.5310] | -0.4733 |
| EV velocity | -1.0431 | 0.1254 | 1.1685 | [-0.6755, 3.4717] | 0.1811 |
| CI lower | -23.1412 | -46.0000 | -22.8588 | [-32.7609, -11.1898] | -1.1339 |
| CI upper | 7.3000 | -9.4286 | -16.7286 | [-25.6753, -6.3650] | -1.1315 |
| CI width | 30.4412 | 36.5714 | 6.1303 | [3.2203, 9.0780] | 0.7375 |
| Price change | 4.1765 | 0.1429 | -4.0336 | [-9.0117, 0.9133] | -0.2896 |
| Score diff change | 0.2745 | 0.0000 | -0.2745 | [-1.3965, 0.6810] | -0.0788 |
| ESS | 24.8309 | 24.6967 | -0.1342 | [-0.4781, 0.1102] | -0.3780 |
| Median distance | 1.4817 | 1.4199 | -0.0618 | [-0.2807, 0.1359] | -0.1714 |

### B · t2

| Feature | Temporary | Persistent | Difference | 95% CI | Effect size |
| --- | --- | --- | --- | --- | --- |
| EV | 20.0000 | -54.6499 | -74.6499 | [-94.5841, -44.2253] | UNAVAILABLE |
| ΔEV from t0 | 54.0308 | -7.5891 | -61.6199 | [-97.6024, -25.7779] | UNAVAILABLE |
| EV velocity | 4.8737 | 0.0000 | -4.8737 | [-4.8737, -4.8737] | UNAVAILABLE |
| CI lower | 20.0000 | -64.8000 | -84.8000 | [-99.4400, -59.7600] | UNAVAILABLE |
| CI upper | 20.0000 | -43.2000 | -63.2000 | [-88.2400, -30.4000] | UNAVAILABLE |
| CI width | 0.0000 | 21.6000 | 21.6000 | [10.0000, 30.0000] | UNAVAILABLE |
| Price change | 33.0000 | -19.8000 | -52.8000 | [-77.4600, -37.0000] | UNAVAILABLE |
| Score diff change | -4.0000 | 1.4000 | 5.4000 | [4.0000, 8.2000] | UNAVAILABLE |
| ESS | 24.9700 | 23.6834 | -1.2866 | [-2.3306, -0.3068] | UNAVAILABLE |
| Median distance | 0.8907 | 0.9546 | 0.0639 | [-0.1265, 0.3065] | UNAVAILABLE |

t2 status: MIXED

# 11. t3 / LONGER PERSISTENCE

### A · H1_2 · PERSISTENCE LANDMARKS

Nested descriptive groups. No best row. Missing later states do not imply persistence.

| State | N | Loss rate | Mean future PNL | T40 rate | Future MAE | Future MFE |
| --- | --- | --- | --- | --- | --- | --- |
| NEGATIVE_AT_T0 | 67 | 0.2090 | -0.8955 | 1.0000 | 11.6818 | 15.2879 |
| NEGATIVE_AT_T0_T1 | 48 | 0.1667 | 3.3333 | 1.0000 | 12.1667 | 13.0833 |
| NEGATIVE_AT_T0_T1_T2 | 44 | 0.1818 | 1.8182 | 1.0000 | 13.2045 | 12.9545 |
| NEGATIVE_AT_T0_T1_T2_T3 | 41 | 0.1463 | 5.3659 | 1.0000 | 12.3415 | 13.5854 |

### B · H2_1 · PERSISTENCE LANDMARKS

Nested descriptive groups. No best row. Missing later states do not imply persistence.

| State | N | Loss rate | Mean future PNL | T40 rate | Future MAE | Future MFE |
| --- | --- | --- | --- | --- | --- | --- |
| NEGATIVE_AT_T0 | 22 | 0.5455 | -34.5455 | 1.0000 | 17.7143 | 1.7857 |
| NEGATIVE_AT_T0_T1 | 7 | 0.5714 | -37.1429 | 1.0000 | 17.0000 | 0.2857 |
| NEGATIVE_AT_T0_T1_T2 | 5 | 0.6000 | -40.0000 | 1.0000 | 19.8000 | -3.4000 |
| NEGATIVE_AT_T0_T1_T2_T3 | 3 | 0.6667 | -46.6667 | 1.0000 | 27.6667 | -0.3333 |

A availability {'N_with_t0': 67, 'N_with_t1': 66, 'N_with_t2': 65, 'N_with_t3': 63}
B availability {'N_with_t0': 22, 'N_with_t1': 11, 'N_with_t2': 6, 'N_with_t3': 3}

# 12. EV DEPTH / VELOCITY / ACCELERATION

Derivatives use game-clock minutes between valid PRIMARY points. Missing stays UNAVAILABLE.
No smoothing. No cutoff search.

A dynamics {'temporary': {'mean_EV_depth': {'n': 51, 'mean': 11.66742553683331}, 'mean_EV_velocity': {'n': 51, 'mean': 1.300219709142564}, 'mean_EV_acceleration': {'n': 51, 'mean': -0.5585680588868257}, 'EV_velocity_t0_to_t1': {'n': 31, 'mean': 7.116347480268466}, 'EV_acceleration_t0_t2': {'n': 28, 'mean': -3.834800130573496}}, 'persistent': {'mean_EV_depth': {'n': 15, 'mean': 28.46683870650651}, 'mean_EV_velocity': {'n': 15, 'mean': -0.47966978240598707}, 'mean_EV_acceleration': {'n': 14, 'mean': 0.5455635355359019}, 'EV_velocity_t0_to_t1': {'n': 6, 'mean': -2.666972046802097}, 'EV_acceleration_t0_t2': {'n': 5, 'mean': 1.6001832280812582}}, 'note': 'Descriptive only. Missing derivatives stay UNAVAILABLE. No cutoff search.'}
B dynamics {'temporary': {'mean_EV_depth': {'n': 5, 'mean': 9.77332716032738}, 'mean_EV_velocity': {'n': 5, 'mean': 4.508431345139265}, 'mean_EV_acceleration': {'n': 1, 'mean': -0.22056190546162466}, 'EV_velocity_t0_to_t1': {'n': 5, 'mean': 4.6407684884162395}, 'EV_acceleration_t0_t2': {'n': 1, 'mean': -0.22056190546162466}}, 'persistent': {'mean_EV_depth': {'n': 6, 'mean': 48.642765686836434}, 'mean_EV_velocity': {'n': 6, 'mean': -0.046392788596858615}, 'mean_EV_acceleration': {'n': 5, 'mean': -2.2187427552466983}, 'EV_velocity_t0_to_t1': {'n': 4, 'mean': 0.4789281296653549}, 'EV_acceleration_t0_t2': {'n': 3, 'mean': -2.771354503849217}}, 'note': 'Descriptive only. Missing derivatives stay UNAVAILABLE. No cutoff search.'}

# 13. RECOVERY BEHAVIOR

A recovery {'temporary': {'n': 51, 'EV_recovery_rate': 1.0, 'recover_ge_50': 1.0, 'recover_ge_60': 1.0, 'recover_ge_70': 0.9803921568627451, 'recover_ge_80': 0.9019607843137255, 'mean_time_to_EV_recovery': 10.666666666666666, 'mean_future_MFE': 19.294117647058822}, 'persistent': {'n': 15, 'EV_recovery_rate': 0.0, 'recover_ge_50': 1.0, 'recover_ge_60': 0.8, 'recover_ge_70': 0.5333333333333333, 'recover_ge_80': 0.4, 'mean_time_to_EV_recovery': None, 'mean_future_MFE': 1.6666666666666667}}
B recovery {'temporary': {'n': 5, 'EV_recovery_rate': 1.0, 'recover_ge_50': 1.0, 'recover_ge_60': 1.0, 'recover_ge_70': 1.0, 'recover_ge_80': 1.0, 'mean_time_to_EV_recovery': 7.6, 'mean_future_MFE': 21.0}, 'persistent': {'n': 6, 'EV_recovery_rate': 0.0, 'recover_ge_50': 0.3333333333333333, 'recover_ge_60': 0.16666666666666666, 'recover_ge_70': 0.16666666666666666, 'recover_ge_80': 0.0, 'mean_time_to_EV_recovery': None, 'mean_future_MFE': -5.166666666666667}}

# 14. DOWNFALL BEHAVIOR

A downfall {'temporary': {'n': 51, 'loss_rate': 0.13725490196078433, 'T40_rate': 1.0, 'mean_future_MAE': 9.215686274509803, 'mean_future_min_price': 66.3921568627451, 'mean_time_to_T40': 0.0784313725490196, 'mean_time_to_worst_price': 4.392156862745098}, 'persistent': {'n': 15, 'loss_rate': 0.4, 'T40_rate': 1.0, 'mean_future_MAE': 20.066666666666666, 'mean_future_min_price': 52.666666666666664, 'mean_time_to_T40': 0.13333333333333333, 'mean_time_to_worst_price': 7.466666666666667}}
B downfall {'temporary': {'n': 5, 'loss_rate': 0.0, 'T40_rate': 1.0, 'mean_future_MAE': 17.2, 'mean_future_min_price': 60.8, 'mean_time_to_T40': 0.0, 'mean_time_to_worst_price': 1.6}, 'persistent': {'n': 6, 'loss_rate': 0.6666666666666666, 'T40_rate': 1.0, 'mean_future_MAE': 18.833333333333332, 'mean_future_min_price': 33.833333333333336, 'mean_time_to_T40': 0.0, 'mean_time_to_worst_price': 2.6666666666666665}}

# 15. T40 / MAE / MFE

A T40 temporary 1.0000 persistent 1.0000
B T40 temporary 1.0000 persistent 1.0000
A MAE temporary 9.2157 persistent 20.0667
B MAE temporary 17.2000 persistent 18.8333
A MFE temporary 19.2941 persistent 1.6667
B MFE temporary 21.0000 persistent -5.1667

# 16. INTERVENTION WINDOW REMAINING

Descriptive object only. Not a trading instruction. Phase 5+ would simulate an intervention.

A window {'t0': {'n': 67, 'n_persistent': 15, 'mean_price_at_landmark': 72.73333333333333, 'mean_future_minimum_price': 52.666666666666664, 'mean_adverse_cents_remaining': 20.066666666666666, 'mean_minutes_to_worst_price': 7.866666666666666, 'mean_minutes_to_T40': 0.8}, 't1': {'n': 48, 'n_persistent': 15, 'mean_price_at_landmark': 72.86666666666666, 'mean_future_minimum_price': 51.642857142857146, 'mean_adverse_cents_remaining': 21.642857142857142, 'mean_minutes_to_worst_price': 8.571428571428571, 'mean_minutes_to_T40': 1.8666666666666667}, 't2': {'n': 47, 'n_persistent': 14, 'mean_price_at_landmark': 73.28571428571429, 'mean_future_minimum_price': 50.84615384615385, 'mean_adverse_cents_remaining': 23.307692307692307, 'mean_minutes_to_worst_price': 8.0, 'mean_minutes_to_T40': 1.8571428571428572}, 't3': {'n': 44, 'n_persistent': 13, 'mean_price_at_landmark': 74.15384615384616, 'mean_future_minimum_price': 50.833333333333336, 'mean_adverse_cents_remaining': 25.25, 'mean_minutes_to_worst_price': 7.5, 'mean_minutes_to_T40': 1.8461538461538463}}
B window {'t0': {'n': 22, 'n_persistent': 6, 'mean_price_at_landmark': 52.666666666666664, 'mean_future_minimum_price': 33.833333333333336, 'mean_adverse_cents_remaining': 18.833333333333332, 'mean_minutes_to_worst_price': 3.0, 'mean_minutes_to_T40': 2.6666666666666665}, 't1': {'n': 7, 'n_persistent': 6, 'mean_price_at_landmark': 34.5, 'mean_future_minimum_price': 37.6, 'mean_adverse_cents_remaining': 0.8, 'mean_minutes_to_worst_price': 2.0, 'mean_minutes_to_T40': 1.6666666666666667}, 't2': {'n': 5, 'n_persistent': 5, 'mean_price_at_landmark': 37.6, 'mean_future_minimum_price': 29.666666666666668, 'mean_adverse_cents_remaining': 0.0, 'mean_minutes_to_worst_price': 2.0, 'mean_minutes_to_T40': 1.2}, 't3': {'n': 3, 'n_persistent': 3, 'mean_price_at_landmark': 29.666666666666668, 'mean_future_minimum_price': 48.0, 'mean_adverse_cents_remaining': -7.0, 'mean_minutes_to_worst_price': 3.0, 'mean_minutes_to_T40': 1.0}}

# 17. WARNING-TIME INTERPRETATION

Discovery warning definition is preserved. It is not redefined to look better.
A AVAILABLE=5 TOO_LATE=62 NONE=29
B AVAILABLE=0 TOO_LATE=22 NONE=47
A warning-before-damage among losses {'n': 0, 'n_losses': 15, 'note': 'preserved Discovery definition; not redefined'}
B warning-before-damage among losses {'n': 0, 'n_losses': 12, 'note': 'preserved Discovery definition; not redefined'}
A Phase 2 timing {'n_rows': 67, 'n_losses': 14, 'losses_t0_to_T40_before_damage': {'n': 14, 'n_label': 0, 'rate': 0.0}, 'losses_t1_to_T40_before_damage': {'n': 14, 'n_label': 0, 'rate': 0.0}, 'losses_t2_to_T40_before_damage': {'n': 14, 'n_label': 0, 'rate': 0.0}, 'losses_t0_to_worst_before_damage': {'n': 14, 'n_label': 11, 'rate': 0.7857142857142857}, 'persistent_t0_to_T40_before_damage': {'n': 15, 'n_label': 1, 'rate': 0.06666666666666667}, 'persistent_t1_to_T40_before_damage': {'n': 15, 'n_label': 0, 'rate': 0.0}, 'persistent_t2_to_T40_before_damage': {'n': 15, 'n_label': 0, 'rate': 0.0}, 'note': 'Phase 2 mechanism timing. Does not replace Discovery AVAILABLE warning among losses.'}
B Phase 2 timing {'n_rows': 22, 'n_losses': 12, 'losses_t0_to_T40_before_damage': {'n': 12, 'n_label': 0, 'rate': 0.0}, 'losses_t1_to_T40_before_damage': {'n': 12, 'n_label': 0, 'rate': 0.0}, 'losses_t2_to_T40_before_damage': {'n': 12, 'n_label': 0, 'rate': 0.0}, 'losses_t0_to_worst_before_damage': {'n': 12, 'n_label': 5, 'rate': 0.4166666666666667}, 'persistent_t0_to_T40_before_damage': {'n': 6, 'n_label': 0, 'rate': 0.0}, 'persistent_t1_to_T40_before_damage': {'n': 6, 'n_label': 0, 'rate': 0.0}, 'persistent_t2_to_T40_before_damage': {'n': 6, 'n_label': 0, 'rate': 0.0}, 'note': 'Phase 2 mechanism timing. Does not replace Discovery AVAILABLE warning among losses.'}

# 18. SUPPORT / MANIFOLD ANALYSIS

Low-support states are retained. The question is whether persistence is only off-manifold.

A support {'temporary': {'n': 51, 'LOW_HISTORICAL_SUPPORT_rate': 0.0, 'mean_ESS': 24.756320285020447, 'mean_median_distance': 1.1908159253256312, 'mean_feature_coverage': 0.9565217391304347}, 'persistent': {'n': 15, 'LOW_HISTORICAL_SUPPORT_rate': 0.0, 'mean_ESS': 24.571549235192364, 'mean_median_distance': 1.0618697351208664, 'mean_feature_coverage': 0.9555555555555556}, 'question': 'Is apparent persistence merely an artifact of Austin being off-manifold?'}
B support {'temporary': {'n': 5, 'LOW_HISTORICAL_SUPPORT_rate': 0.0, 'mean_ESS': 23.79563981905295, 'mean_median_distance': 0.9527016260689407, 'mean_feature_coverage': 0.982608695652174}, 'persistent': {'n': 6, 'LOW_HISTORICAL_SUPPORT_rate': 0.0, 'mean_ESS': 22.57893876885697, 'mean_median_distance': 0.8211627066497845, 'mean_feature_coverage': 0.9951690821256038}, 'question': 'Is apparent persistence merely an artifact of Austin being off-manifold?'}

# 19. H2_1 ALIGNMENT AUDIT

status=EXPECTED_FROM_CANONICAL_TIMING
potential_data_alignment_defect=False
n_clock_wall_mismatch=61 n_aligned=8
median_pbp_minus_entry_seconds=-18.0000
median_wall_minus_entry_seconds=-827.0000
Alignment is observed, not repaired. A reconstruction change would require a new experiment version.
Phase 2 does not repair timestamps. A reconstruction change would need a new version.

# 20. STATISTICAL UNCERTAINTY

cluster=internal_game_id seed=80 B=1000. A and B never pooled as the headline.
Appendix A+B is labeled POOLED DESCRIPTIVE — NOT CONFIRMATION.

# 21. LEAKAGE / INTEGRITY

model hash PASS
leakage PASS
confirmation protection PASS
PIT vectors at t0/t1/t2 exclude future labels, future T40, future MAE/MFE, and eventual outcome.
Mutating bars/PBP after a checkpoint must leave that checkpoint's descriptor unchanged.

# 22. WHAT THE DATA SHOWS

A Δ PNL -26.2745 CI=[-52.7017, 0.0146] MIXED
B Δ PNL -66.6667 CI=[-100.0000, -25.0000] SUPPORTED
Gate A MIXED
Gate B SUPPORTED earliest=t1
Gate C MIXED

# 23. WHAT AUSTIN MAY BE MEASURING

A first negative EV is a distress mark. Persistence of that mark is a later Austin-state
description. It is not automatically terminal economic decline, and it is not a live signal.

# 24. WHAT HAS NOT BEEN PROVEN

No live rule. No fill. No executable exit. No new policy. No confirmation. No Austin V3.
No threshold search. No Phase 3 downfall-state model.

# 25. WHETHER PHASE 3 IS JUSTIFIED

False
valid state diagnosis — not an actionable risk mechanism
If later work preregisters a delay-based persistence rule, it must be a new Phase 5 object. Phase 2 does not create a policy and does not freeze one.

Phase 3 is not started automatically.

## Appendix · POOLED DESCRIPTIVE — NOT CONFIRMATION

pooled first-negative N=89
Not a headline. Not confirmation.

POLICY STATUS = UNFROZEN
CONFIRMATION A = NOT RUN
CONFIRMATION B = NOT RUN
EXECUTION = DISABLED
NEXT PHASE = PHASE 3 — NOT STARTED

