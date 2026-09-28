# DISCOVERY INTERPRETATION AUDIT · SUITE

Suite `AUSTIN_NCAAB_TRANSFER_V1`. POLICY STATUS = UNFROZEN. CONFIRMATION A = NOT RUN. CONFIRMATION B = NOT RUN.
No freeze. No policy selection. No confirmation spend.

## Answers

### 1. Why H2_1 has 117 valid states and 0 complete paths

PRIMARY_GRID clock-eligible rows reconstructed as PRE_80 because PBP/bar timestamp < asked-six entry_timestamp. Warehouse price/score are present. KNN is not missing; NO_ENTRY_IN_FITTED_SPACE is the PRE_80 gate. This is clock-vs-wall alignment, not an absent parquet tree.
A: valid=1167 per_trade=12.16 complete=22 PRE_80_primary=178
B: valid=117 per_trade=1.70 complete=0 PRE_80_primary=429
H2_1 starts later, so fewer PRIMARY clocks remain, and a much larger share of those clocks have PBP wall time still before asked-six entry. That is alignment, not a missing warehouse.

### 2. Warning median when AVAILABLE=0

Discovery report median_minutes is median_first_negative_to_settlement over AVAILABLE+TOO_LATE. It is not median_warning_available. If AVAILABLE=0 the reported median is a TOO_LATE-only figure.
B median_warning_available n=0 median=None
B median_warning_too_late n=22 median=3.0
B median_first_negative_to_settlement n=22 median=3.0

### 3–4. Clustered ordering

A EV MIXED Δ=2.753161731885136 CI=[-8.267520449127913, 13.641564628672574]
A deterioration MIXED Δ=2.8734672677017827 CI=[-9.970154236180266, 15.533124453339425]
B EV SUPPORTED Δ=55.128205128205124 CI=[30.153476206107786, 77.40345018905144]
B deterioration MIXED Δ=45.959595959595966 CI=[-4.753797208538587, 72.82827183518263]

### 5. Scoring — not one Austin accuracy

Austin outputs a continuous conditional EV, not a binary winner/loser call. MAE/RMSE/sign/rank are the proper scores. The ever-EV<0 final-loss table is a crude classifier and is not Austin accuracy. A dumb always-win rule already equals the discovery win rate.
A MAE=28.14146085795147 CI=[23.50361003675476, 33.50004880894671] RMSE=39.60257149298472 sign=0.5526992287917738 Spearman=0.054731082227841454
A crude ever-EV<0 acc=0.4375 naive_always_win=0.84375 minus_naive=-0.40625 prec=0.208955223880597 rec=0.9333333333333333
B MAE=18.958544069489918 CI=[11.366336632064344, 26.53003096045958] RMSE=33.44167221958777 sign=0.8376068376068376 Spearman=0.3902201441652055
B crude ever-EV<0 acc=0.8412698412698413 naive_always_win=0.8095238095238095 minus_naive=0.031746031746031744 prec=0.5454545454545454 rec=1.0
A warning-before-damage recall_losses=0.0 B=0.0

### 6. H2_1 calibration

status=SEPARATED
[{'band': '< -10¢', 'n': 34, 'mean_predicted_ev': -50.46210422220223, 'mean_realized_hold': -41.76470588235294, 'median_realized_hold': -80.0}, {'band': '-10 to 0¢', 'n': 5, 'mean_predicted_ev': -3.3003749890203893, 'mean_realized_hold': -20.0, 'median_realized_hold': 20.0}, {'band': '0 to +5¢', 'n': 9, 'mean_predicted_ev': 1.755475208375199, 'mean_realized_hold': 8.88888888888889, 'median_realized_hold': 20.0}, {'band': '+5 to +10¢', 'n': 8, 'mean_predicted_ev': 6.631936280609974, 'mean_realized_hold': -5.0, 'median_realized_hold': 20.0}, {'band': '> +10¢', 'n': 61, 'mean_predicted_ev': 18.717488094844832, 'mean_realized_hold': 20.0, 'median_realized_hold': 20.0}]

### 6–7. First-negative persistence (descriptive)

A first-neg n=67 win=53 lose=14 classes={'TEMPORARY_DETERIORATION': 47, 'PERSISTENT_DETERIORATION': 15, 'UNRESOLVED_NO_LATER_VALID_EV': 5, 'definition': 'TEMPORARY = later valid PRIMARY EV >= 0 exists. PERSISTENT = later valid PRIMARY EV exists and all stay < 0. UNRESOLVED = no later valid PRIMARY EV. Descriptive only. Not a policy.'}
B first-neg n=22 win=10 lose=12 classes={'TEMPORARY_DETERIORATION': 5, 'PERSISTENT_DETERIORATION': 5, 'UNRESOLVED_NO_LATER_VALID_EV': 12, 'definition': 'TEMPORARY = later valid PRIMARY EV >= 0 exists. PERSISTENT = later valid PRIMARY EV exists and all stay < 0. UNRESOLVED = no later valid PRIMARY EV. Descriptive only. Not a policy.'}

Austin can mark a worse state. It does not yet separate transient from terminal deterioration well enough for an exit rule.

DISCOVERY INTERPRETATION COMPLETE
POLICY STATUS = UNFROZEN
CONFIRMATION A = NOT RUN
CONFIRMATION B = NOT RUN
NEXT REQUIRED ACTION = HUMAN SELECTS EXACTLY ONE PRE-REGISTERED POLICY OR NONE
