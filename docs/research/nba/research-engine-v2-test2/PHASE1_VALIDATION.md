# PHASE 1 VALIDATION — Test 2

Written `2026-09-01T19:09:05.947195+00:00`

## Frozen labels

- first80: 1230 (expected 1230)
- Y_40_CLOSE: 320 (expected 320)
- baseline_ok: **True**

## Possessions

- n_possessions: 224957
- games_built: 1223
- unmatched observations: 7
- no PBP: 0
- duplicate ids: 0
- impossible score jumps (flagged, not dropped): 50751
- nonmonotonic clocks (flagged): 0
- unmapped action types: {'ejection': 66}

## Alignment (MODELED walls; per-play timeActual unavailable)

Confidence counts: {'HIGH': 955, 'MEDIUM': 214, 'UNUSABLE': 51, 'LOW': 3}

- Primary HIGH+MEDIUM n=1169 q=0.2643284858853721
- Excluded n=54 q=0.14814814814814814
- |q_primary − 26.02%| = 0.004165884259355823
- Leakage post-entry in Z: **False**

## Overlay quality

{'EXACT_ALIGNMENT': 19191, 'MULTI_POSSESSION_CANDLE': 145013, 'MULTI_CANDLE_POSSESSION': 57527, 'PARTIAL_ALIGNMENT': 3226}

## Gate

- PASS: **True**
- Material exclusion bias (>3pp): **False**
