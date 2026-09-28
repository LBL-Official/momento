# DISCOVERY INTERPRETATION AUDIT · NCAAB_H1_2_AUSTIN_TRANSFER_V1

slice=H1_2 locked N=193 cohort=DISCOVERY
POLICY STATUS = UNFROZEN
CONFIRMATION = NOT RUN
No feature / PCA / K / EV / policy / schedule / cohort change.

## 1. Coverage

trades=96 primary=1345 valid_states=1167 per_trade=12.16
complete/partial/unavailable=22/74/0
PRIMARY PRE_80=178 POST_80=1167
PRE_80 wall_before_entry=178 when-entry median_sec=-1692.0
reasons={'NO_ENTRY_IN_FITTED_SPACE': 178, '': 1167}
PRIMARY_GRID clock-eligible rows reconstructed as PRE_80 because PBP/bar timestamp < asked-six entry_timestamp. Warehouse price/score are present. KNN is not missing; NO_ENTRY_IN_FITTED_SPACE is the PRE_80 gate. This is clock-vs-wall alignment, not an absent parquet tree.

## 2. Warning denominators

Discovery report median_minutes is median_first_negative_to_settlement over AVAILABLE+TOO_LATE. It is not median_warning_available. If AVAILABLE=0 the reported median is a TOO_LATE-only figure.
AVAILABLE=5 TOO_LATE=62 NONE=29 PATH_UNAVAILABLE=0
median_warning_available n=5 median=20.0
median_warning_too_late n=62 median=20.0
median_first_negative_to_T40 n=67 median=0.0
median_first_negative_to_worst_price n=67 median=0.0
median_first_negative_to_settlement n=67 median=20.0
Missing is not converted to zero.

## 3–4. Game-clustered ordering

EV ordering observed Δ=2.753161731885136 CI=[-8.267520449127913, 13.641564628672574] excludes_zero=False status=MIXED
  n_pos=650 n_neg=517 n_games=96
deterioration ordering observed Δ=2.8734672677017827 CI=[-9.970154236180266, 15.533124453339425] excludes_zero=False status=MIXED
  n_pos=714 n_neg=453 n_games=96
trade first-valid checkpoint MIXED Δ=8.193277310924369 CI=[-7.621602426289926, 24.958802816901407]
trade ever-negative vs settlement hold SUPPORTED Δ=17.44724652599074 CI=[5.604395604395604, 29.6339593114241]

## 5. Scoring — not a single accuracy

Austin outputs a continuous conditional EV, not a binary winner/loser call. MAE/RMSE/sign/rank are the proper scores. The ever-EV<0 final-loss table is a crude classifier and is not Austin accuracy. A dumb always-win rule already equals the discovery win rate.
n_valid_states=1167 n_trades_scored=96 missing_valid_state=0
MAE ¢ observed=28.14146085795147 CI=[23.50361003675476, 33.50004880894671] n_games=96
RMSE ¢ observed=39.60257149298472
sign accuracy (EV>0 vs hold>0, zeros excluded) observed=0.5526992287917738 CI=[0.46986852332931045, 0.6335793802333322] zeros_excluded=0
Spearman EV vs hold observed=0.054731082227841454 CI=[-0.07903068670122355, 0.22521236716982146] excludes_zero=False
state loss-detection precision=0.172147001934236 recall=0.48633879781420764 specificity=0.5650406504065041
crude ever-EV<0 final-loss classifier (NOT Austin accuracy): TP=14 FP=53 FN=1 TN=28
  precision=0.208955223880597 CI=[0.11591233071988596, 0.3188405797101449] recall=0.9333333333333333 specificity=0.345679012345679
  classification_accuracy=0.4375 naive_always_win=0.84375 minus_naive=-0.40625
warning-before-damage precision=0.0 recall_among_losses=0.0

## 6. Calibration

status=SEPARATED
[{'band': '< -10¢', 'n': 298, 'mean_predicted_ev': -31.693107946189883, 'mean_realized_hold': -3.1543624161073827, 'median_realized_hold': 20.0}, {'band': '-10 to 0¢', 'n': 219, 'mean_predicted_ev': -5.001567630423115, 'mean_realized_hold': 10.867579908675799, 'median_realized_hold': 20.0}, {'band': '0 to +5¢', 'n': 109, 'mean_predicted_ev': 2.8211809300697746, 'mean_realized_hold': 2.5688073394495414, 'median_realized_hold': 20.0}, {'band': '+5 to +10¢', 'n': 75, 'mean_predicted_ev': 8.069284025035993, 'mean_realized_hold': 5.333333333333333, 'median_realized_hold': 20.0}, {'band': '> +10¢', 'n': 466, 'mean_predicted_ev': 16.263689150337544, 'mean_realized_hold': 6.266094420600858, 'median_realized_hold': 20.0}]

## 7–8. First-negative trades (descriptive, not a policy)

{'n_first_negative_trades': 67, 'n_eventually_win': 53, 'n_eventually_lose': 14, 'win_share': 0.7910447761194029, 'settlement_hold': {'n': 67, 'mean': -0.8955223880597015, 'median': 20.0, 'ev_cents': -0.8955223880597015, 'std': 40.963078101212155, 'p10': -80.0, 'p25': 20.0, 'p75': 20.0, 'p90': 20.0, 'min': -80.0, 'max': 20.0, 'total': -60.0}, 'hold_after_first_negative': {'n': 67, 'mean': -0.8955223880597015, 'median': 20.0, 'ev_cents': -0.8955223880597015, 'std': 40.963078101212155, 'p10': -80.0, 'p25': 20.0, 'p75': 20.0, 'p90': 20.0, 'min': -80.0, 'max': 20.0, 'total': -60.0}, 'subsequent_mae': {'n': 62, 'mean': 9.516129032258064, 'median': 0.0, 'ev_cents': 9.516129032258064, 'std': 27.79830277605054, 'p10': -18.0, 'p25': -7.5, 'p75': 15.5, 'p90': 59.49999999999999, 'min': -31.0, 'max': 84.0, 'total': 590.0}, 'subsequent_mfe': {'n': 62, 'mean': 12.548387096774194, 'median': 12.5, 'ev_cents': 12.548387096774194, 'std': 18.468118225702348, 'p10': -1.8999999999999995, 'p25': 5.25, 'p75': 20.0, 'p90': 34.0, 'min': -65.0, 'max': 56.0, 'total': 778.0}, 'recovered_to_60': {'n': 54, 'n_known': 67, 'share': 0.8059701492537313}, 'recovered_to_70': {'n': 51, 'n_known': 67, 'share': 0.7611940298507462}, 'recovered_to_80': {'n': 48, 'n_known': 67, 'share': 0.7164179104477612}, 'later_hit_t40': {'n': 66, 'n_known': 67, 'share': 0.9850746268656716}, 'deterioration_class': {'TEMPORARY_DETERIORATION': 47, 'PERSISTENT_DETERIORATION': 15, 'UNRESOLVED_NO_LATER_VALID_EV': 5, 'definition': 'TEMPORARY = later valid PRIMARY EV >= 0 exists. PERSISTENT = later valid PRIMARY EV exists and all stay < 0. UNRESOLVED = no later valid PRIMARY EV. Descriptive only. Not a policy.'}, 'temporary_win_lose': {'n': 47, 'win': 43, 'lose': 4}, 'persistent_win_lose': {'n': 15, 'win': 7, 'lose': 8}}

TEMPORARY vs PERSISTENT is a description of later Austin EV sign. It is not a freeze candidate.

CONFIRMATION NOT RUN. POLICY UNFROZEN. No winner.

## Phase 2 research object

Discovery-only persistence mechanism continues at `research/austin/experiments/AUSTIN_PERSISTENCE_MECHANISM_V1/`.
This file remains the Phase 1 discovery interpretation. Confirmation remains NOT RUN. Policy remains UNFROZEN.
