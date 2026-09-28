# Stability and bootstrap

IN / VAL / OOS are the asked-six splits on the same 604. No 2026–27 rows.

| split | n | q2_n | q3_n | pc1_smd | raw_t40_q2 | raw_t40_q3 | raw_t40_diff | knn_k10_agreement |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IN_SAMPLE | 236 | 125 | 111 | -0.7781 | 0.2400 | 0.3063 | -0.0663 | 0.6072 |
| VALIDATION | 248 | 119 | 129 | -0.6755 | 0.2521 | 0.2481 | 0.0040 | 0.6371 |
| OOS | 120 | 70 | 50 | -0.2958 | 0.2143 | 0.2600 | -0.0457 | 0.6225 |

## Bootstrap (resample rows, 200 draws, seed 8040)

{'seed': 8040, 'n_boot': 200, 'raw_t40_diff': {'observed': -0.03356028991873489, 'boot_p025': -0.10671214529612626, 'boot_p50': -0.02957496192691983, 'boot_p975': 0.034648371039886605}, 'pc1_smd': {'boot_p025': -0.7989176952430607, 'boot_p50': -0.6216229532197581, 'boot_p975': -0.46466682712215795}, 'matched_q50_reference': {'direction': 'Q2_to_Q3', 'quantile': 0.5, 'distance_cutoff': 5.476218834446315, 'n': 157, 'source_t40': 0.19745222929936307, 'matched_t40': 0.3375796178343949, 'difference': -0.14012738853503182, 'source_s': 0.802547770700637, 'matched_s': 0.6624203821656051, 'source_t40_wilson': [0.14273446406922466, 0.2666223192505136], 'matched_t40_wilson': [0.26827380211481894, 0.4146440499831458], 'source_period': 'Q2', 'match_period': 'Q3'}}

