# AUSTIN · CONDITIONAL RISK VALIDATION

CROSS-DOMAIN TRANSFER TEST

**Suite:** `AUSTIN_NCAAB_TRANSFER_V1`
**Experiment:** `NCAAB_H2_1_AUSTIN_TRANSFER_V1`
**TRAINING:** NBA Choosin N=604
**TEST:** NCAAB H2_1 N=139
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
| Games | 69 |
| Trades | 69 |
| State observations | 1738 |
| BASELINE_HOLD EV ¢ | 2.608695652173913 |
| Path complete / partial / unavailable | 0 / 63 / 6 |
| EV ordering vs subsequent hold | SUPPORTED |
| Median warning minutes | 3.0 |

No overall winner. No holy grail claim.

# 2. EXPERIMENT IDENTITY

Suite `AUSTIN_NCAAB_TRANSFER_V1`. Member `NCAAB_H2_1_AUSTIN_TRANSFER_V1`. Slice `H2_1` locked N=139.
H2_2 is forbidden. Page 3 N=280 is display-only.

# 3. MODEL LOCK

austin_v2 · choosin_nba_2q3q_604 · K=25 · hold_80_to_settlement · NCAAB did not fit.

# 4. COHORT LOCK

Role `DISCOVERY`. Games 69. Trades 69.
Split is temporal floor(G/2) unique games written before inference.

# 5. DATA / PATH COVERAGE

{'N_trades': 69, 'N_path_complete': 0, 'N_path_partial': 63, 'N_path_unavailable': 6, 'N_primary_grid_rows': 546, 'N_valid_Austin_rows': 311, 'N_knn_observations': 48752, 'N_games': 69, 'N_state_observations': 1738}

# 6. AUSTIN CONDITIONAL EV VS SUBSEQUENT PNL

Negative EV states n=39 mean hold=-38.97435897435897
Non-negative EV states n=78 mean hold=16.153846153846153
Ordering claim: SUPPORTED

# 7. EV TRAJECTORY / DETERIORATION

EV_NOW − EV_entry ≤ −8¢ n=18 mean hold=-41.111111111111114
Otherwise n=99 mean hold=4.848484848484849

# 8. WARNING TIME

AVAILABLE=0 TOO_LATE=22 NONE=47 PATH_UNAVAILABLE=0
median=3.0 P25=0.0 P75=5.5 losers_median=None
mean adverse cents remaining=5.2272727272727275
Missing warning is not converted to zero.

# 9. CALIBRATION

Status: SEPARATED
[{'band': '< -10¢', 'n': 34, 'mean_predicted_ev': -50.46210422220223, 'mean_realized_hold': -41.76470588235294, 'median_realized_hold': -80.0}, {'band': '-10 to 0¢', 'n': 5, 'mean_predicted_ev': -3.3003749890203893, 'mean_realized_hold': -20.0, 'median_realized_hold': 20.0}, {'band': '0 to +5¢', 'n': 9, 'mean_predicted_ev': 1.755475208375199, 'mean_realized_hold': 8.88888888888889, 'median_realized_hold': 20.0}, {'band': '+5 to +10¢', 'n': 8, 'mean_predicted_ev': 6.631936280609974, 'mean_realized_hold': -5.0, 'median_realized_hold': 20.0}, {'band': '> +10¢', 'n': 61, 'mean_predicted_ev': 18.717488094844832, 'mean_realized_hold': 20.0, 'median_realized_hold': 20.0}]

# 10. DISCOVERY POLICY TABLE

Scenario B = next 1m close. SCENARIO — NOT OBSERVED FILL. No winner is marked.

- `POLICY_A` rate=0.3188405797101449 baseline=2.608695652173913 policyB=4.36231884057971 Δ=1.753623188405797 CI=[-2.4648550724637674, 6.565579710144927] DD=-290.0 P10=-66.0 worst=-79.0 avoided=12 saved=308.0 abandoned=10 sacrificed=187.0 warn_med=3.0
- `POLICY_B` rate=0.36231884057971014 baseline=2.608695652173913 policyB=4.434782608695652 Δ=1.8260869565217392 CI=[-2.4927536231884053, 6.7829710144927535] DD=-291.0 P10=-66.0 worst=-79.0 avoided=12 saved=316.0 abandoned=13 sacrificed=190.0 warn_med=3.0
- `POLICY_C` rate=0.37681159420289856 baseline=2.608695652173913 policyB=4.057971014492754 Δ=1.4492753623188408 CI=[-2.7971014492753623, 6.623550724637681] DD=-291.0 P10=-66.0 worst=-79.0 avoided=12 saved=316.0 abandoned=14 sacrificed=216.0 warn_med=3.0
- `POLICY_D` rate=0.13043478260869565 baseline=2.608695652173913 policyB=3.536231884057971 Δ=0.9275362318840581 CI=[-1.78659420289855, 4.537318840579709] DD=-299.0 P10=-80.0 worst=-80.0 avoided=4 saved=144.0 abandoned=5 sacrificed=80.0 warn_med=3.0
- `POLICY_E` rate=0.2463768115942029 baseline=2.608695652173913 policyB=4.594202898550725 Δ=1.9855072463768115 CI=[-2.2184782608695652, 6.7844202898550705] DD=-290.0 P10=-66.0 worst=-79.0 avoided=12 saved=304.0 abandoned=5 sacrificed=167.0 warn_med=3.0
- `POLICY_F` rate=0.10144927536231885 baseline=2.608695652173913 policyB=3.8840579710144927 Δ=1.2753623188405796 CI=[-0.46449275362318815, 3.695652173913043] DD=-340.0 P10=-80.0 worst=-80.0 avoided=3 saved=107.0 abandoned=4 sacrificed=19.0 warn_med=3.0

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

Locked H2_1 N=139. Cohort DISCOVERY. Hold EV 2.608695652173913. Ordering SUPPORTED.

# WHAT AUSTIN ADDS

Frozen NBA-neighbor conditional EV and EV trajectory at 2-minute game-clock checkpoints after entry.

# WHAT HAS NOT BEEN PROVEN

Fills, live feed, 2026–27 NBA prospective validation, NCAAB-native model, confirmation generalization.

# WHETHER THE EVIDENCE JUSTIFIES THE NEXT VALIDATION STAGE

Discovery evidence alone cannot establish generalization. Human must select one POLICY_A…F, then freeze, then run confirmation once per member.

Do not combine with NCAAB_H1_2_AUSTIN_TRANSFER_V1 as a headline OOS result.
