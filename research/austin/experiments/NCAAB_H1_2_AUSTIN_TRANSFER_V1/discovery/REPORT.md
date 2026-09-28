# AUSTIN · CONDITIONAL RISK VALIDATION

CROSS-DOMAIN TRANSFER TEST

**Suite:** `AUSTIN_NCAAB_TRANSFER_V1`
**Experiment:** `NCAAB_H1_2_AUSTIN_TRANSFER_V1`
**TRAINING:** NBA Choosin N=604
**TEST:** NCAAB H1_2 N=193
**Cohort:** `DISCOVERY`
**Observation:** EVERY 2 GAME-CLOCK MINUTES
**LIVE FEED:** UNAVAILABLE
**EXECUTION:** DISABLED
**FILL:** FILL_UNAVAILABLE
**POLICY STATUS:** UNFROZEN
**CONFIRMATION RESULT:** NOT RUN

# 1. EXECUTIVE RESEARCH SUMMARY

Does frozen Austin conditional EV contain forward-looking information about
remaining hold-to-settlement economics at predetermined 2-minute checkpoints?

| Measure | DISCOVERY |
| --- | ---: |
| Games | 96 |
| Trades | 96 |
| State observations | 2444 |
| BASELINE_HOLD EV ¢ | 4.375 |
| Path complete / partial / unavailable | 22 / 74 / 0 |
| EV ordering vs subsequent hold | SUPPORTED |
| Median warning minutes | 20.0 |

No overall winner. No holy grail claim.

# 2. EXPERIMENT IDENTITY

Suite `AUSTIN_NCAAB_TRANSFER_V1`. Member `NCAAB_H1_2_AUSTIN_TRANSFER_V1`. Slice `H1_2` locked N=193.
H2_2 is forbidden. Page 3 N=280 is display-only.

# 3. MODEL LOCK

austin_v2 · choosin_nba_2q3q_604 · K=25 · hold_80_to_settlement · NCAAB did not fit.

# 4. COHORT LOCK

Role `DISCOVERY`. Games 96. Trades 96.
Split is temporal floor(G/2) unique games written before inference.

# 5. DATA / PATH COVERAGE

{'N_trades': 96, 'N_path_complete': 22, 'N_path_partial': 74, 'N_path_unavailable': 0, 'N_primary_grid_rows': 1345, 'N_valid_Austin_rows': 1453, 'N_knn_observations': 48752, 'N_games': 96, 'N_state_observations': 2444}

# 6. AUSTIN CONDITIONAL EV VS SUBSEQUENT PNL

Negative EV states n=517 mean hold=2.7852998065764023
Non-negative EV states n=650 mean hold=5.538461538461538
Ordering claim: SUPPORTED

# 7. EV TRAJECTORY / DETERIORATION

EV_NOW − EV_entry ≤ −8¢ n=453 mean hold=2.5607064017660046
Otherwise n=714 mean hold=5.434173669467787

# 8. WARNING TIME

AVAILABLE=5 TOO_LATE=62 NONE=29 PATH_UNAVAILABLE=0
median=20.0 P25=18.0 P75=20.0 losers_median=None
mean adverse cents remaining=13.373134328358208
Missing warning is not converted to zero.

# 9. CALIBRATION

Status: SEPARATED
[{'band': '< -10¢', 'n': 298, 'mean_predicted_ev': -31.693107946189883, 'mean_realized_hold': -3.1543624161073827, 'median_realized_hold': 20.0}, {'band': '-10 to 0¢', 'n': 219, 'mean_predicted_ev': -5.001567630423115, 'mean_realized_hold': 10.867579908675799, 'median_realized_hold': 20.0}, {'band': '0 to +5¢', 'n': 109, 'mean_predicted_ev': 2.8211809300697746, 'mean_realized_hold': 2.5688073394495414, 'median_realized_hold': 20.0}, {'band': '+5 to +10¢', 'n': 75, 'mean_predicted_ev': 8.069284025035993, 'mean_realized_hold': 5.333333333333333, 'median_realized_hold': 20.0}, {'band': '> +10¢', 'n': 466, 'mean_predicted_ev': 16.263689150337544, 'mean_realized_hold': 6.266094420600858, 'median_realized_hold': 20.0}]

# 10. DISCOVERY POLICY TABLE

Scenario B = next 1m close. SCENARIO — NOT OBSERVED FILL. No winner is marked.

- `POLICY_A` rate=0.6979166666666666 baseline=4.375 policyB=2.3645833333333335 Δ=-2.0104166666666665 CI=[-8.302604166666667, 4.594531249999999] DD=-175.0 P10=-23.5 worst=-80.0 avoided=14 saved=804.0 abandoned=53 sacrificed=997.0 warn_med=20.0
- `POLICY_B` rate=0.7291666666666666 baseline=4.375 policyB=1.875 Δ=-2.5 CI=[-8.70859375, 4.105989583333332] DD=-200.0 P10=-23.5 worst=-80.0 avoided=14 saved=804.0 abandoned=56 sacrificed=1044.0 warn_med=20.0
- `POLICY_C` rate=0.78125 baseline=4.375 policyB=2.0104166666666665 Δ=-2.3645833333333335 CI=[-8.74140625, 4.542447916666666] DD=-201.0 P10=-23.5 worst=-80.0 avoided=14 saved=827.0 abandoned=61 sacrificed=1054.0 warn_med=20.0
- `POLICY_D` rate=0.625 baseline=4.375 policyB=2.15625 Δ=-2.21875 CI=[-7.1156250000000005, 2.9593749999999988] DD=-201.0 P10=-48.5 worst=-80.0 avoided=14 saved=512.0 abandoned=46 sacrificed=725.0 warn_med=20.0
- `POLICY_E` rate=0.4375 baseline=4.375 policyB=2.4270833333333335 Δ=-1.9479166666666665 CI=[-7.291927083333333, 3.6994791666666655] DD=-167.0 P10=-28.5 worst=-80.0 avoided=12 saved=591.0 abandoned=30 sacrificed=778.0 warn_med=20.0
- `POLICY_F` rate=0.4479166666666667 baseline=4.375 policyB=1.5625 Δ=-2.8125 CI=[-7.439322916666666, 2.1984374999999994] DD=-222.0 P10=-53.5 worst=-80.0 avoided=6 saved=367.0 abandoned=37 sacrificed=637.0 warn_med=20.0

# 11. FALSE INTERVENTIONS

Winners abandoned and cents sacrificed are in the policy table. Not a count-only ratio.

# 12. LOSSES AVOIDED / CENTS SAVED

Avoided losers report cents saved, not only a count.

# 13. EXECUTION SCENARIOS

HYPOTHETICAL_INTERVENTION is SCENARIO — NOT OBSERVED FILL. FILL_UNAVAILABLE. FEE_MODEL=UNAVAILABLE.

# 14. EQUITY / DRAWDOWN

Equity curves are chronological by entry_timestamp. Discovery is not combined with confirmation.

# 15. CLUSTERED STATISTICS

Cluster = internal_game_id. seed=80. B=1000. Checkpoints are not independent bets.

# 16. LOW-SUPPORT / OFF-MANIFOLD ANALYSIS

LOW_HISTORICAL_SUPPORT rows remain in the experiment. Distance is not confidence.

# 17. LEAKAGE / SELF-NEIGHBOR / INTEGRITY

See leakage_audit.json and self_neighbor_audit.json. submits=false.

# 18. DISCOVERY RESULT

Family POLICY_A–F evaluated. Policy remains UNFROZEN. No automatic selection.

# 19. CONFIRMATION RESULT

NOT RUN

# 20. LIVE APPLICABILITY

RESEARCH REPLAY VALIDATED · LIVE FEED UNAVAILABLE · EXECUTION DISABLED · FILL_UNAVAILABLE

# WHAT THE DATA SHOWS

Locked H1_2 N=193. Cohort DISCOVERY. Hold EV 4.375. Ordering SUPPORTED.

# WHAT AUSTIN ADDS

Frozen NBA-neighbor conditional EV and EV trajectory at 2-minute game-clock checkpoints after entry.

# WHAT HAS NOT BEEN PROVEN

Fills, live feed, 2026–27 NBA prospective validation, NCAAB-native model, confirmation generalization.

# WHETHER THE EVIDENCE JUSTIFIES THE NEXT VALIDATION STAGE

Discovery evidence alone cannot establish generalization. Human must select one POLICY_A…F, then freeze, then run confirmation once per member.
