# DISCOVERY INTERPRETATION AUDIT · NCAAB_H2_1_AUSTIN_TRANSFER_V1

slice=H2_1 locked N=139 cohort=DISCOVERY
POLICY STATUS = UNFROZEN
CONFIRMATION = NOT RUN
No feature / PCA / K / EV / policy / schedule / cohort change.

## 1. Coverage

trades=69 primary=546 valid_states=117 per_trade=1.70
complete/partial/unavailable=0/63/6
PRIMARY PRE_80=429 POST_80=117
PRE_80 wall_before_entry=429 when-entry median_sec=-798.0
reasons={'NO_ENTRY_IN_FITTED_SPACE': 429, '': 117}
PRIMARY_GRID clock-eligible rows reconstructed as PRE_80 because PBP/bar timestamp < asked-six entry_timestamp. Warehouse price/score are present. KNN is not missing; NO_ENTRY_IN_FITTED_SPACE is the PRE_80 gate. This is clock-vs-wall alignment, not an absent parquet tree.

## 2. Warning denominators

Discovery report median_minutes is median_first_negative_to_settlement over AVAILABLE+TOO_LATE. It is not median_warning_available. If AVAILABLE=0 the reported median is a TOO_LATE-only figure.
AVAILABLE=0 TOO_LATE=22 NONE=47 PATH_UNAVAILABLE=0
median_warning_available n=0 median=None
median_warning_too_late n=22 median=3.0
median_first_negative_to_T40 n=22 median=0.0
median_first_negative_to_worst_price n=22 median=0.0
median_first_negative_to_settlement n=22 median=3.0
Missing is not converted to zero.

## 3–4. Game-clustered ordering

EV ordering observed Δ=55.128205128205124 CI=[30.153476206107786, 77.40345018905144] excludes_zero=True status=SUPPORTED
  n_pos=78 n_neg=39 n_games=63
deterioration ordering observed Δ=45.959595959595966 CI=[-4.753797208538587, 72.82827183518263] excludes_zero=False status=MIXED
  n_pos=99 n_neg=18 n_games=63
trade first-valid checkpoint SUPPORTED Δ=62.5 CI=[35.833333333333336, 87.74591503267975]
trade ever-negative vs settlement hold SUPPORTED Δ=54.54545454545455 CI=[33.333333333333336, 75.0]

## 5. Scoring — not a single accuracy

Austin outputs a continuous conditional EV, not a binary winner/loser call. MAE/RMSE/sign/rank are the proper scores. The ever-EV<0 final-loss table is a crude classifier and is not Austin accuracy. A dumb always-win rule already equals the discovery win rate.
n_valid_states=117 n_trades_scored=63 missing_valid_state=6
MAE ¢ observed=18.958544069489918 CI=[11.366336632064344, 26.53003096045958] n_games=63
RMSE ¢ observed=33.44167221958777
sign accuracy (EV>0 vs hold>0, zeros excluded) observed=0.8376068376068376 CI=[0.7478953743659627, 0.923845126835781] zeros_excluded=0
Spearman EV vs hold observed=0.3902201441652055 CI=[0.1305547257668842, 0.651646477229198] excludes_zero=True
state loss-detection precision=0.5897435897435898 recall=0.8846153846153846 specificity=0.8241758241758241
crude ever-EV<0 final-loss classifier (NOT Austin accuracy): TP=12 FP=10 FN=0 TN=41
  precision=0.5454545454545454 CI=[0.3333333333333333, 0.7647058823529411] recall=1.0 specificity=0.803921568627451
  classification_accuracy=0.8412698412698413 naive_always_win=0.8095238095238095 minus_naive=0.031746031746031744
warning-before-damage precision=None recall_among_losses=0.0

## 6. Calibration

status=SEPARATED
[{'band': '< -10¢', 'n': 34, 'mean_predicted_ev': -50.46210422220223, 'mean_realized_hold': -41.76470588235294, 'median_realized_hold': -80.0}, {'band': '-10 to 0¢', 'n': 5, 'mean_predicted_ev': -3.3003749890203893, 'mean_realized_hold': -20.0, 'median_realized_hold': 20.0}, {'band': '0 to +5¢', 'n': 9, 'mean_predicted_ev': 1.755475208375199, 'mean_realized_hold': 8.88888888888889, 'median_realized_hold': 20.0}, {'band': '+5 to +10¢', 'n': 8, 'mean_predicted_ev': 6.631936280609974, 'mean_realized_hold': -5.0, 'median_realized_hold': 20.0}, {'band': '> +10¢', 'n': 61, 'mean_predicted_ev': 18.717488094844832, 'mean_realized_hold': 20.0, 'median_realized_hold': 20.0}]

## 7–8. First-negative trades (descriptive, not a policy)

{'n_first_negative_trades': 22, 'n_eventually_win': 10, 'n_eventually_lose': 12, 'win_share': 0.45454545454545453, 'settlement_hold': {'n': 22, 'mean': -34.54545454545455, 'median': -80.0, 'ev_cents': -34.54545454545455, 'std': 50.96471914376255, 'p10': -80.0, 'p25': -80.0, 'p75': 20.0, 'p90': 20.0, 'min': -80.0, 'max': 20.0, 'total': -760.0}, 'hold_after_first_negative': {'n': 22, 'mean': -34.54545454545455, 'median': -80.0, 'ev_cents': -34.54545454545455, 'std': 50.96471914376255, 'p10': -80.0, 'p25': -80.0, 'p75': 20.0, 'p90': 20.0, 'min': -80.0, 'max': 20.0, 'total': -760.0}, 'subsequent_mae': {'n': 10, 'mean': 4.3, 'median': 5.0, 'ev_cents': 4.3, 'std': 27.072125886232136, 'p10': -21.2, 'p25': -15.0, 'p75': 12.75, 'p90': 20.999999999999982, 'min': -32.0, 'max': 66.0, 'total': 43.0}, 'subsequent_mfe': {'n': 10, 'mean': 0.3, 'median': -0.5, 'ev_cents': 0.3, 'std': 28.460694143170702, 'p10': -20.599999999999998, 'p25': -12.75, 'p75': 20.0, 'p90': 32.1, 'min': -62.0, 'max': 33.0, 'total': 3.0}, 'recovered_to_60': {'n': 5, 'n_known': 22, 'share': 0.22727272727272727}, 'recovered_to_70': {'n': 5, 'n_known': 22, 'share': 0.22727272727272727}, 'recovered_to_80': {'n': 5, 'n_known': 22, 'share': 0.22727272727272727}, 'later_hit_t40': {'n': 22, 'n_known': 22, 'share': 1.0}, 'deterioration_class': {'TEMPORARY_DETERIORATION': 5, 'PERSISTENT_DETERIORATION': 5, 'UNRESOLVED_NO_LATER_VALID_EV': 12, 'definition': 'TEMPORARY = later valid PRIMARY EV >= 0 exists. PERSISTENT = later valid PRIMARY EV exists and all stay < 0. UNRESOLVED = no later valid PRIMARY EV. Descriptive only. Not a policy.'}, 'temporary_win_lose': {'n': 5, 'win': 5, 'lose': 0}, 'persistent_win_lose': {'n': 5, 'win': 1, 'lose': 4}}

TEMPORARY vs PERSISTENT is a description of later Austin EV sign. It is not a freeze candidate.

CONFIRMATION NOT RUN. POLICY UNFROZEN. No winner.

## Phase 2 research object

Discovery-only persistence mechanism continues at `research/austin/experiments/AUSTIN_PERSISTENCE_MECHANISM_V1/`.
This file remains the Phase 1 discovery interpretation. Confirmation remains NOT RUN. Policy remains UNFROZEN.
