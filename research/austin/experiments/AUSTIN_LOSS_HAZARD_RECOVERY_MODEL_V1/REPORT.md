AUSTIN DRE
PHASE 4 — LOSS HAZARD / RECOVERY MODEL

DISCOVERY ONLY

PHASE 2 FINALIZED
PHASE 3 COMPLETE

AUSTIN MODEL FROZEN
DOWNFALL STATE SCHEMA FROZEN

POLICY UNFROZEN
CONFIRMATION UNTOUCHED

EXECUTION DISABLED

# 1. EXECUTIVE RESEARCH SUMMARY

Phase 4 fits a frozen Jeffreys Beta-Binomial leave-one-game-out layer on Phase 3 first-entry states.
These are terminal-loss / recovery / next-deterioration estimates only. They are not an action rule.
Phase 5 decision: PHASE 5 NOT JUSTIFIED.
The PIT → LOGO improvement → recovery → update → early-enough → support chain does not hold.
A and B are never pooled as a headline.

# 2. WATERFALL / PRIOR-PHASE FINALIZATION

Phase 2 FINALIZED. Actionability NOT MET. Historical Phase 2 artifacts were not rewritten.
Phase 3 COMPLETE / MIXED. Historical Phase 3 artifacts were not rewritten.
Phase 2 REPORT hash `152bf411e3182568a44ea512c14b08c00e7d17cc0f176ccfcfaf043d27bc3177`.
Phase 3 REPORT hash `44473f2d47c1b1766020124d807952ad022a53b5592e1cf69bed8bbc8af4b37e`.

# 3. PHASE 4 IDENTITY

MODEL_ID `AUSTIN_LOSS_HAZARD_RECOVERY_MODEL_V1`. Schema `loss_hazard_recovery_v1`. Families H0 member / H1 core_state / H2 core_state×CI_state.
No extra families. No price/score/time/EV buckets. No classifier. No DRE score.

# 4. MODEL / COHORT LOCKS

Austin model `austin_v2` hash `4a47bf9ad3a2fcd4bb092a77cf93d534e308423deec29e33b6e6bad85c76431c`.
Training N=604. K=25. State schema downfall_state_v1 hash `96018aec5e8d3da8374632ae139b0a25761b4d485da394a46b0f5e3159079307`.
Hazard schema hash `b16bf075c323c926497beeba9bf6d51496eb348d40b306a8a99bfb8e9932c72e`.
A discovery `f7bc6280913c63a2a50cb5181b0c523c5492bbdb47da167d9639e2f867a87e36`. B discovery `699e6bb65fe4fa3dffc566b352f089c109ffadfb501b830e2c129f2e66450840`.

# 5. PHASE 3 HANDOFF

Evaluation unit is Phase 3 first trade×core_state entries. Timeline rows are not independent N.
Phase 3 result remains MIXED. Phase 4 does not upgrade Phase 3 into a useful path model by assertion.

# 6. HAZARD SCHEMA

Jeffreys prior 0.5/0.5. `p_hat=(y+0.5)/(n+1)`. n=0 → UNAVAILABLE. H2 never falls back to H1.
LOGO drops `internal_game_id`. Gap / UNRESOLVED breaks recovery continuity. No interpolation.

# 7. TARGET DEFINITIONS

TARGET_terminal_loss = 1 if FIRST80 settles LOSS.
TARGET_recovery_t1/t2/t3 = next 1/2/3 adjacent valid PRIMARY rows with EV present.
TARGET_deeper_distress_next uses STATE_DEPTH only. Recovery states are not depths.
TARGET_T40_before_recovery is secondary. T40 already at entry is NOT_APPLICABLE.

# 8. CROSS-FIT METHODOLOGY

Every scoring p_hat rebuilds the Beta table after dropping that row's internal_game_id.
same_game_present_in_training=false on 8025 predictions.

# 9. MEMBER BASE RATES

H0 is member-only. A and B have separate base rates. Do not pool.

# 10. TERMINAL LOSS RISK — H0/H1/H2

## A

| Model | Eligible N | Losses | Unavailable | Brier | BSS vs H0 | Log loss | Δ log loss | ROC AUC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H0 | 382 | 62 | 0 | 0.1392 | UNAVAILABLE | 0.4557 | UNAVAILABLE | 0.0000 |
| H1 | 382 | 62 | 0 | 0.1401 | -0.0060 | 0.4582 | 0.0025 | 0.3835 |
| H2 | 382 | 62 | 0 | 0.1388 | 0.0034 | 0.4550 | -0.0007 | 0.5075 |

H1 BSS CI [-0.02307817875827836, 0.004922855315867471]. H2 BSS CI [-0.08543703920762592, 0.06917032926316098].

## B

| Model | Eligible N | Losses | Unavailable | Brier | BSS vs H0 | Log loss | Δ log loss | ROC AUC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H0 | 153 | 33 | 0 | 0.1759 | UNAVAILABLE | 0.5416 | UNAVAILABLE | 0.0000 |
| H1 | 153 | 33 | 0 | 0.1419 | 0.1929 | 0.4445 | -0.0971 | 0.6672 |
| H2 | 151 | 33 | 0 | 0.1360 | 0.2268 | 0.4258 | -0.1158 | 0.6664 |

H1 BSS CI [-0.032420048868787535, 0.32626735714201466]. H2 BSS CI [-0.020495818180831685, 0.3257364192673164].

# 11. TERMINAL LOSS CALIBRATION

Fixed bins [0,0.2), [0.2,0.4), [0.4,0.6), [0.6,0.8), [0.8,1]. N<10 is not strong evidence.

## A

| bin | N | mean p | observed | strong |
| --- | --- | --- | --- | --- |
| 0.0-0.2 | 294 | 0.1522 | 0.1463 | true |
| 0.2-0.4 | 88 | 0.2222 | 0.2159 | true |
| 0.4-0.6 | 0 | UNAVAILABLE | UNAVAILABLE | false |
| 0.6-0.8 | 0 | UNAVAILABLE | UNAVAILABLE | false |
| 0.8-1.0 | 0 | UNAVAILABLE | UNAVAILABLE | false |

## B

| bin | N | mean p | observed | strong |
| --- | --- | --- | --- | --- |
| 0.0-0.2 | 120 | 0.1232 | 0.1167 | true |
| 0.2-0.4 | 0 | UNAVAILABLE | UNAVAILABLE | false |
| 0.4-0.6 | 29 | 0.5444 | 0.6552 | true |
| 0.6-0.8 | 4 | 0.7250 | 0.0000 | false |
| 0.8-1.0 | 0 | UNAVAILABLE | UNAVAILABLE | false |

# 12. RECOVERY T1 MODEL

## A

| Model | Eligible N | Recovery N | Unavailable N | Brier | BSS | Log loss |
| --- | --- | --- | --- | --- | --- | --- |
| H0 | 163 | 23 | 5 | 0.1228 | UNAVAILABLE | 0.4137 |
| H1 | 163 | 23 | 5 | 0.1126 | 0.0830 | 0.3752 |
| H2 | 163 | 23 | 5 | 0.1093 | 0.1100 | 0.3719 |

## B

| Model | Eligible N | Recovery N | Unavailable N | Brier | BSS | Log loss |
| --- | --- | --- | --- | --- | --- | --- |
| H0 | 12 | 0 | 21 | 0.0022 | UNAVAILABLE | 0.0482 |
| H1 | 12 | 0 | 21 | 0.0188 | -7.4154 | 0.1357 |
| H2 | 11 | 0 | 21 | 0.0216 | -8.6905 | 0.1488 |

# 13. RECOVERY T2 MODEL

## A

| Model | Eligible N | Recovery N | Unavailable N | Brier | BSS | Log loss |
| --- | --- | --- | --- | --- | --- | --- |
| H0 | 158 | 31 | 10 | 0.1605 | UNAVAILABLE | 0.5040 |
| H1 | 158 | 31 | 10 | 0.1511 | 0.0585 | 0.4773 |
| H2 | 158 | 31 | 10 | 0.1501 | 0.0646 | 0.4853 |

## B

| Model | Eligible N | Recovery N | Unavailable N | Brier | BSS | Log loss |
| --- | --- | --- | --- | --- | --- | --- |
| H0 | 7 | 0 | 26 | 0.0077 | UNAVAILABLE | 0.0912 |
| H1 | 6 | 0 | 26 | 0.0312 | -3.0440 | 0.1849 |
| H2 | 6 | 0 | 26 | 0.0312 | -3.0440 | 0.1849 |

# 14. RECOVERY T3 MODEL

## A

| Model | Eligible N | Recovery N | Unavailable N | Brier | BSS | Log loss |
| --- | --- | --- | --- | --- | --- | --- |
| H0 | 154 | 36 | 14 | 0.1834 | UNAVAILABLE | 0.5557 |
| H1 | 154 | 36 | 14 | 0.1729 | 0.0574 | 0.5283 |
| H2 | 154 | 36 | 14 | 0.1760 | 0.0401 | 0.5433 |

## B

| Model | Eligible N | Recovery N | Unavailable N | Brier | BSS | Log loss |
| --- | --- | --- | --- | --- | --- | --- |
| H0 | 4 | 0 | 29 | 0.0508 | UNAVAILABLE | 0.2491 |
| H1 | 2 | 0 | 29 | 0.0625 | -0.2308 | 0.2877 |
| H2 | 2 | 0 | 29 | 0.0625 | -0.2308 | 0.2877 |

# 15. DEEPER-DISTRESS MODEL

Next adjacent valid core_state has greater STATE_DEPTH. Recovery destinations are not depths.

## A

| Model | Eligible N | Event N | Unavailable N | Brier | BSS |
| --- | --- | --- | --- | --- | --- |
| H0 | 163 | 94 | 5 | 0.2450 | UNAVAILABLE |
| H1 | 163 | 94 | 5 | 0.1004 | 0.5903 |
| H2 | 163 | 94 | 5 | 0.0971 | 0.6038 |

## B

| Model | Eligible N | Event N | Unavailable N | Brier | BSS |
| --- | --- | --- | --- | --- | --- |
| H0 | 12 | 10 | 21 | 0.1524 | UNAVAILABLE |
| H1 | 12 | 10 | 21 | 0.0187 | 0.8769 |
| H2 | 11 | 10 | 21 | 0.0216 | 0.8583 |

# 16. STATE-CONDITIONAL HAZARDS

## A

| State | N | p(loss) | p(recovery t1) | p(recovery by t2) | p(recovery by t3) |
| --- | --- | --- | --- | --- | --- |
| HEALTHY | 68 | 0.1377 | N/A | N/A | N/A |
| WATCH_NEGATIVE | 67 | 0.2132 | 0.2803 | 0.3308 | 0.3672 |
| PERSISTENCE_2 | 52 | 0.1792 | 0.0686 | 0.1100 | 0.1809 |
| PERSISTENCE_3PLUS | 49 | 0.1700 | 0.0510 | 0.1196 | 0.1196 |
| RECOVERING | 51 | 0.1442 | N/A | N/A | N/A |
| HEALTHY_AFTER_RECOVERY | 21 | 0.2500 | N/A | N/A | N/A |

## B

| State | N | p(loss) | p(recovery t1) | p(recovery by t2) | p(recovery by t3) |
| --- | --- | --- | --- | --- | --- |
| HEALTHY | 51 | 0.0481 | N/A | N/A | N/A |
| WATCH_NEGATIVE | 22 | 0.5435 | 0.0833 | 0.1000 | 0.1667 |
| PERSISTENCE_2 | 6 | 0.6429 | 0.0833 | 0.1667 | 0.2500 |
| PERSISTENCE_3PLUS | 5 | 0.5833 | 0.1667 | 0.2500 | 0.2500 |
| RECOVERING | 0 | UNAVAILABLE | N/A | N/A | N/A |
| HEALTHY_AFTER_RECOVERY | 0 | UNAVAILABLE | N/A | N/A | N/A |

# 17. STATE × CI HAZARDS

H2 cells with n=0 stay UNAVAILABLE. No H2→H1 fallback.

## A

| state | CI | N | p_loss H2 | label |
| --- | --- | --- | --- | --- |
| WATCH_NEGATIVE | CI_NEGATIVE | 32 | 0.2879 | OBSERVED |
| WATCH_NEGATIVE | CI_CROSSES_ZERO | 35 | 0.1528 | OBSERVED |
| PERSISTENCE_2 | CI_NEGATIVE | 16 | 0.3824 | OBSERVED |
| PERSISTENCE_2 | CI_CROSSES_ZERO | 36 | 0.0946 | OBSERVED |
| PERSISTENCE_3PLUS | CI_NEGATIVE | 13 | 0.3929 | OBSERVED |
| PERSISTENCE_3PLUS | CI_CROSSES_ZERO | 36 | 0.0946 | OBSERVED |

## B

| state | CI | N | p_loss H2 | label |
| --- | --- | --- | --- | --- |
| WATCH_NEGATIVE | CI_NEGATIVE | 16 | 0.6765 | OBSERVED |
| WATCH_NEGATIVE | CI_CROSSES_ZERO | 6 | 0.2143 | LOW_SAMPLE |
| PERSISTENCE_2 | CI_NEGATIVE | 5 | 0.5833 | LOW_SAMPLE |
| PERSISTENCE_2 | CI_CROSSES_ZERO | 1 | 0.7500 | LOW_SAMPLE |
| PERSISTENCE_3PLUS | CI_NEGATIVE | 4 | 0.5000 | LOW_SAMPLE |
| PERSISTENCE_3PLUS | CI_CROSSES_ZERO | 1 | 0.7500 | LOW_SAMPLE |

# 18. DYNAMIC RISK CONTRAST

Do not force monotonicity.

## A

| from | to | N | Δ p_loss H1 | Δ p_recovery t1 H1 |
| --- | --- | --- | --- | --- |
| WATCH_NEGATIVE | PERSISTENCE_2 | 52 | -0.0345 | -0.2149 |
| PERSISTENCE_2 | PERSISTENCE_3PLUS | 49 | -0.0094 | -0.0180 |
| PERSISTENCE_2 | RECOVERING | 37 | -0.0357 | UNAVAILABLE |

## B

| from | to | N | Δ p_loss H1 | Δ p_recovery t1 H1 |
| --- | --- | --- | --- | --- |
| WATCH_NEGATIVE | PERSISTENCE_2 | 6 | 0.1010 | 0.0000 |
| PERSISTENCE_2 | PERSISTENCE_3PLUS | 5 | -0.0700 | 0.1500 |
| PERSISTENCE_2 | RECOVERING | 0 | UNAVAILABLE | UNAVAILABLE |

# 19. HAZARD TRAJECTORIES

First downside-state sequence per trade. Δ p_loss / Δ p_recovery are descriptive.

# 20. TRANSITION-RISK ANALYSIS

H1/H2 probabilities are taken at the FROM state only. Destination is evaluation.

## A

| from | to | N | mean p_loss H1 at FROM |
| --- | --- | --- | --- |
| WATCH_NEGATIVE | PERSISTENCE_2 | 52 | 0.2138 |
| PERSISTENCE_2 | PERSISTENCE_3PLUS | 49 | 0.1796 |
| WATCH_NEGATIVE | RECOVERING | 20 | 0.2127 |
| PERSISTENCE_2 | RECOVERING | 5 | 0.1827 |

## B

| from | to | N | mean p_loss H1 at FROM |
| --- | --- | --- | --- |
| WATCH_NEGATIVE | PERSISTENCE_2 | 6 | 0.5379 |
| PERSISTENCE_2 | PERSISTENCE_3PLUS | 5 | 0.6500 |

# 21. AUSTIN EV VS HAZARD

## A

| contrast | N | Spearman | CI lo | CI hi |
| --- | --- | --- | --- | --- |
| EV vs p_loss | 308 | -0.6294 | -0.6841 | -0.5707 |
| EV vs p_recovery_t1 | 163 | -0.1682 | -0.2858 | -0.0528 |

## B

| contrast | N | Spearman | CI lo | CI hi |
| --- | --- | --- | --- | --- |
| EV vs p_loss | 84 | -0.7874 | -0.8296 | -0.7064 |
| EV vs p_recovery_t1 | 12 | -0.3256 | -0.5230 | 0.1240 |

# 22. CI INFORMATION VALUE

A H2 vs H1 terminal-loss class: MIXED. B: MIXED.
H2 is not declared a winner.

# 23. SUPPORT / MANIFOLD

## A

| state | N | mean ESS | mean median distance | low cell N |
| --- | --- | --- | --- | --- |
| WATCH_NEGATIVE | 67 | 24.7178 | 1.1718 | 0 |
| PERSISTENCE_2 | 52 | 24.7998 | 1.4811 | 0 |
| PERSISTENCE_3PLUS | 49 | 24.8229 | 1.5153 | 0 |
| HEALTHY | 68 | 24.8086 | 1.0024 | 0 |

## B

| state | N | mean ESS | mean median distance | low cell N |
| --- | --- | --- | --- | --- |
| WATCH_NEGATIVE | 22 | 23.5505 | 1.0526 | 0 |
| PERSISTENCE_2 | 6 | 23.6824 | 1.0811 | 6 |
| PERSISTENCE_3PLUS | 5 | 23.6853 | 0.9485 | 5 |
| HEALTHY | 51 | 24.2336 | 0.7899 | 0 |

# 24. T40-BEFORE-RECOVERY DIAGNOSTIC

A: negative=168 observable=10 T40-before-recovery=10 N/A=157 unavailable=1
B: negative=33 observable=0 T40-before-recovery=0 N/A=33 unavailable=0

# 25. TIMING / REMAINING DAMAGE

Phase 1 warning remains 0/15 and 0/12. This is not validated early warning.

## A

| state | N | mean adverse ¢ remaining | mean minutes to worst | mean p_loss H1 |
| --- | --- | --- | --- | --- |
| WATCH_NEGATIVE | 67 | 11.6818 | 5.0149 | 0.2133 |
| PERSISTENCE_2 | 52 | 11.5800 | 4.2308 | 0.1794 |
| PERSISTENCE_3PLUS | 49 | 11.2917 | 3.5918 | 0.1701 |

## B

| state | N | mean adverse ¢ remaining | mean minutes to worst | mean p_loss H1 |
| --- | --- | --- | --- | --- |
| WATCH_NEGATIVE | 22 | 17.7143 | 1.3636 | 0.5434 |
| PERSISTENCE_2 | 6 | 0.0000 | 0.0000 | 0.6389 |
| PERSISTENCE_3PLUS | 5 | 0.0000 | 0.0000 | 0.5800 |

# 26. CALIBRATION / DISCRIMINATION

Brier and log loss are primary. ROC/PR AUC only when both classes are present. No thresholded accuracy headline.

# 27. STATISTICAL UNCERTAINTY

Game-clustered bootstrap. cluster=internal_game_id. seed=80. B=1000.

# 28. LEAKAGE / INTEGRITY

Leakage PASS. Crossfit PASS. Confirmation accessed=false.
Phase 2 finalization PASS. Phase 3 finalization PASS.

# 29. WHAT THE DATA SHOWS

Gate B terminal-loss information: MIXED.
Gate C recovery information: MIXED.
WATCH vs HEALTHY p_loss can agree, but B recovery is thin or missing and counts against transfer.

# 30. WHAT AUSTIN ADDS

Austin contributes the frozen first-entry state keys and hold-80-to-settlement EV used as a covariate, not a policy.

# 31. WHAT HAS NOT BEEN PROVEN

No fill. No live EV. No exit rule. No confirmation. No Phase 5 policy. Candle path is not a fill.

# 32. WHETHER PHASE 5 IS JUSTIFIED

PHASE 5 NOT JUSTIFIED
The PIT → LOGO improvement → recovery → update → early-enough → support chain does not hold.

PHASE 5 — NOT STARTED

POLICY UNFROZEN
CONFIRMATION UNTOUCHED
EXECUTION DISABLED

