AUSTIN DRE
PHASE 5A — PRE-REGISTERED DRE POLICY V2

DISCOVERY ONLY

PHASE 2 FINALIZED
PHASE 3 COMPLETE
PHASE 4 COMPLETE

AUSTIN FROZEN
STATE MODEL FROZEN
HAZARD MODEL FROZEN

POLICY UNFROZEN
CONFIRMATION UNTOUCHED

EXECUTION DISABLED

# 1. EXECUTIVE RESEARCH SUMMARY

Phase 4 handoff: PHASE 5 NOT JUSTIFIED. Classification MIXED. This is a preregistration exercise, not a freeze.
PROPOSED_POLICY NONE. HUMAN_FREEZE_JUSTIFIED NOT_SUPPORTED.
POLICY_A…F remain historical discovery objects and were not selected.
Phase 4 classification is MIXED and its decision text is PHASE 5 NOT JUSTIFIED. This exercise is preregistration only. POLICY_A–F are historical.

# 2. WATERFALL STATUS

Phase 2 FINALIZED / actionability NOT MET. Phase 3 COMPLETE / MIXED. Phase 4 COMPLETE. Phase 6 not started.

# 3. PHASE 4 HANDOFF

Hazard schema `b16bf075c323c926497beeba9bf6d51496eb348d40b306a8a99bfb8e9932c72e`. Gates A–F from Phase 4 remain MIXED except validity PASS.

# 4. POLICY DESIGN PRINCIPLES

Distress states only. H1 only. Frozen 0.2 calibration-bin edge. Support N>=10. Missing hazard → NONE.
T40 already: allow trigger and classify TOO_LATE. First-fire only. No EV / price / clock cuts. No PNL sweep.

# 5. CANDIDATE REGISTRY

Registry hash `e9816a29be6b24550e2712e7b81d9003be3ff518f60e237ad422ecfd9903f276`. Written before economics. Immutable after.

- `DRE_C1_WATCH_LOSS_GE_0P2` states=['WATCH_NEGATIVE'] Phase 4 WATCH vs HEALTHY p_loss is the only directionally consistent loss contrast. 0.2 is the frozen second calibration-bin edge. A WATCH mean 0.213 and B WATCH 0.543 sit at/above it.
- `DRE_C2_P2PLUS_RECOVERY_LT_0P2` states=['PERSISTENCE_2', 'PERSISTENCE_3PLUS'] Phase 4 A recovery t1 drops into the first calibration bin at P2/P3PLUS (0.069 / 0.051). B recovery is expected thin; support rule will fail-close those cells.
- `DRE_C3_DISTRESS_TWO_SIDED` states=['WATCH_NEGATIVE', 'PERSISTENCE_2', 'PERSISTENCE_3PLUS'] Two-sided Phase 4 language: elevated loss-bin and impaired recovery-bin on any distress state.
- `DRE_C4_WATCH_TWO_SIDED` states=['WATCH_NEGATIVE'] Same two-sided bins restricted to WATCH_NEGATIVE, the only B distress state that still had adverse cents remaining in Phase 4 timing.

# 6. CANDIDATE PIT DEFINITIONS

See POLICY_CANDIDATES.json. INTERVENE or NONE only.

# 7. CANDIDATE SUPPORT

support_n >= 10 on every required probability. LOW_HISTORICAL_SUPPORT → NONE.

# 8. DISCOVERY A ECONOMICS

| Candidate | Trigger N | Rate | Losses intervened | Winners intervened | Scenario-B EV | Δ vs hold | 95% CI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DRE_C1_WATCH_LOSS_GE_0P2 | 67 | 0.6979 | 14 | 53 | 2.3646 | -2.0104 | [-8.302604166666667, 4.594531249999999] |
| DRE_C2_P2PLUS_RECOVERY_LT_0P2 | 50 | 0.5208 | 8 | 42 | 1.7292 | -2.6458 | [-7.313802083333333, 2.323177083333333] |
| DRE_C3_DISTRESS_TWO_SIDED | 0 | 0.0000 | 0 | 0 | 4.3750 | 0.0000 | [0.0, 0.0] |
| DRE_C4_WATCH_TWO_SIDED | 0 | 0.0000 | 0 | 0 | 4.3750 | 0.0000 | [0.0, 0.0] |

# 9. DISCOVERY B ECONOMICS

| Candidate | Trigger N | Rate | Losses intervened | Winners intervened | Scenario-B EV | Δ vs hold | 95% CI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DRE_C1_WATCH_LOSS_GE_0P2 | 22 | 0.3188 | 12 | 10 | 4.3623 | 1.7536 | [-2.464855072463768, 6.565579710144927] |
| DRE_C2_P2PLUS_RECOVERY_LT_0P2 | 0 | 0.0000 | 0 | 0 | 2.6087 | 0.0000 | [0.0, 0.0] |
| DRE_C3_DISTRESS_TWO_SIDED | 0 | 0.0000 | 0 | 0 | 2.6087 | 0.0000 | [0.0, 0.0] |
| DRE_C4_WATCH_TWO_SIDED | 0 | 0.0000 | 0 | 0 | 2.6087 | 0.0000 | [0.0, 0.0] |

# 10. LOSS AVOIDANCE

| member | candidate | losses avoided | cents saved |
| --- | --- | --- | --- |
| A | DRE_C1_WATCH_LOSS_GE_0P2 | 14 | 804.0000 |
| A | DRE_C2_P2PLUS_RECOVERY_LT_0P2 | 8 | 413.0000 |
| A | DRE_C3_DISTRESS_TWO_SIDED | 0 | 0 |
| A | DRE_C4_WATCH_TWO_SIDED | 0 | 0 |
| B | DRE_C1_WATCH_LOSS_GE_0P2 | 12 | 308.0000 |
| B | DRE_C2_P2PLUS_RECOVERY_LT_0P2 | 0 | 0 |
| B | DRE_C3_DISTRESS_TWO_SIDED | 0 | 0 |
| B | DRE_C4_WATCH_TWO_SIDED | 0 | 0 |

# 11. WINNER SACRIFICE

| member | candidate | winners abandoned | winner cents sacrificed |
| --- | --- | --- | --- |
| A | DRE_C1_WATCH_LOSS_GE_0P2 | 53 | 997.0000 |
| A | DRE_C2_P2PLUS_RECOVERY_LT_0P2 | 42 | 667.0000 |
| A | DRE_C3_DISTRESS_TWO_SIDED | 0 | 0 |
| A | DRE_C4_WATCH_TWO_SIDED | 0 | 0 |
| B | DRE_C1_WATCH_LOSS_GE_0P2 | 10 | 187.0000 |
| B | DRE_C2_P2PLUS_RECOVERY_LT_0P2 | 0 | 0 |
| B | DRE_C3_DISTRESS_TWO_SIDED | 0 | 0 |
| B | DRE_C4_WATCH_TWO_SIDED | 0 | 0 |

# 12. DRE VALUE ADDED

losses_saved − winner_upside_sacrificed − declared_zero_execution_cost. Hypothetical only.

| member | candidate | DRE value added |
| --- | --- | --- |
| A | DRE_C1_WATCH_LOSS_GE_0P2 | -193.0000 |
| A | DRE_C2_P2PLUS_RECOVERY_LT_0P2 | -254.0000 |
| A | DRE_C3_DISTRESS_TWO_SIDED | 0 |
| A | DRE_C4_WATCH_TWO_SIDED | 0 |
| B | DRE_C1_WATCH_LOSS_GE_0P2 | 121.0000 |
| B | DRE_C2_P2PLUS_RECOVERY_LT_0P2 | 0 |
| B | DRE_C3_DISTRESS_TWO_SIDED | 0 |
| B | DRE_C4_WATCH_TWO_SIDED | 0 |

# 13. TIMING / BEFORE-DAMAGE ANALYSIS

| member | candidate | median price | median adverse ¢ | median minutes to worst | TOO_LATE N |
| --- | --- | --- | --- | --- | --- |
| A | DRE_C1_WATCH_LOSS_GE_0P2 | 79.0000 | 0.0000 | 0.0000 | 62 |
| A | DRE_C2_P2PLUS_RECOVERY_LT_0P2 | 81.0000 | 0.0000 | 0.0000 | 47 |
| A | DRE_C3_DISTRESS_TWO_SIDED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | 0 |
| A | DRE_C4_WATCH_TWO_SIDED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | 0 |
| B | DRE_C1_WATCH_LOSS_GE_0P2 | 66.5000 | 11.5000 | 0.0000 | 22 |
| B | DRE_C2_P2PLUS_RECOVERY_LT_0P2 | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | 0 |
| B | DRE_C3_DISTRESS_TWO_SIDED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | 0 |
| B | DRE_C4_WATCH_TWO_SIDED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | 0 |

# 14. SCENARIO A

Observed yes_bid / current price at the first-fire checkpoint. SCENARIO — NOT OBSERVED FILL.

# 15. SCENARIO B

Next available 1-minute close from discovery PRIMARY. Primary comparison. SCENARIO — NOT OBSERVED FILL.

# 16. STATISTICAL UNCERTAINTY

Game-clustered bootstrap. cluster=internal_game_id. seed=80. B=1000.

# 17. CROSS-MEMBER CONSISTENCY

A and B are never pooled. B recovery / P2 / P3PLUS cells remain thin. That counts against freeze.

# 18. LEAKAGE / INTEGRITY

Leakage PASS. Confirmation accessed=false. POLICY_FREEZE.json not written.

# 19. WHAT THE DATA SHOWS

Candidate classes: {'DRE_C1_WATCH_LOSS_GE_0P2': {'A': 'MIXED', 'B': 'MIXED'}, 'DRE_C2_P2PLUS_RECOVERY_LT_0P2': {'A': 'MIXED', 'B': 'INSUFFICIENT_SAMPLE'}, 'DRE_C3_DISTRESS_TWO_SIDED': {'A': 'INSUFFICIENT_SAMPLE', 'B': 'INSUFFICIENT_SAMPLE'}, 'DRE_C4_WATCH_TWO_SIDED': {'A': 'INSUFFICIENT_SAMPLE', 'B': 'INSUFFICIENT_SAMPLE'}}.

# 20. WHAT THE POLICY WOULD DO

INTERVENE is a hypothetical defensive-action branch on the later validation ledger. It is not a fill.

# 21. WHAT HAS NOT BEEN PROVEN

No confirmation. No freeze. No live EV. No execution. Candle path is not a fill. POLICY_A–F were not revived.

# 22. PROPOSED POLICY OR NONE

PROPOSED_POLICY NONE
POLICY_STATUS AWAITING_HUMAN_FREEZE

# 23. WHETHER HUMAN FREEZE IS JUSTIFIED

HUMAN_FREEZE_JUSTIFIED NOT_SUPPORTED

PHASE 6 — NOT STARTED

