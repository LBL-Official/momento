# Asked-six 80/40 path distribution

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
NOT 3,000 GAMES — N = 1,182
HEADLINE WIN = win_80_40 = 74.70%  (NOT terminal W = 83.84%)
RISK MODEL FIT ON IN_SAMPLE ONLY
LIVE EXECUTION = FALSE
```

Buy 80 / close-path stop 40. +20¢ / −40¢. Zero fee. Integer contracts.
Stake = 5% of **week-start** bankroll. 10 trades / week. 22 weeks.
Start $20,000. Seed 20260910.

## Edge (do not use FULL to both prove and size)

| Split | N | 80/40 wins | Rate | Wilson 95% | vs 66.67% |
|---|---:|---:|---:|---:|---:|
| IN_SAMPLE | 418 | 310 | 74.1627% | 69.7595–78.1257 | 7.496 pp |
| VALIDATION | 582 | 438 | 75.2577% | 71.5939–78.5903 | 8.591 pp |
| OOS | 182 | 135 | 74.1758% | 67.3637–79.9885 | 7.5091 pp |
| FULL | 1182 | 883 | 74.7039% | 72.1483–77.0994 | 8.0372 pp |

IN_SAMPLE is the locked risk-model population. FULL is descriptive.

## 10-trade week (IID IN_SAMPLE, 200,000 paths, 5%)

Median return **5.0%**. 5th **-6.25%**. 95th **12.5%**.
P(lose week) 24.291%. P(≤−5%) 8.8975%. P(≤−10%) 2.332%. P(≥+10%) 5.2005%.
Check: 7/3 → 1.25% ; 5/5 → -6.25%.

P(≥3-loss streak in the week) 10.5175%. ≥4 2.417%. ≥5 0.5525%. ≥6 0.113%.

## 22-week bankroll at 5% (IN_SAMPLE risk model)

| Method | P5 | P50 | P95 | P(lose) | P(≤−20%) | Median DD |
|---|---:|---:|---:|---:|---:|---:|
| IID IN_SAMPLE | $23,874 | $35,786 | $52,906 | 0.943% | 0.067% | 7.6772% |
| Permutation | $27,329 | $35,731 | $46,598 | 0.025% | 0.0% | 7.622% |
| Block 10 | $25,575 | $36,022 | $51,511 | 0.328% | 0.006% | 6.0482% |
| IID VALIDATION | $26,349 | $39,472 | $57,224 | 0.305% | 0.02% | 6.3162% |
| IID OOS | $23,905 | $35,790 | $52,921 | 0.9975% | 0.085% | 7.7036% |
| IID FULL (contaminated) | $25,167 | $37,356 | $55,084 | 0.5825% | 0.0325% | 7.1233% |

## True-p model risk (Bernoulli, 5%, 22 weeks)

| Assumed p | P50 end | P5 end | P(lose) | P(≤−20%) |
|---:|---:|---:|---:|---:|
| 66.7% | $19,517 | $12,488 | 54.105% | 22.8275% |
| 68.0% | $21,684 | $13,942 | 38.06% | 12.48% |
| 70.0% | $25,512 | $16,701 | 17.26% | 3.5775% |
| 72.0% | $29,945 | $19,704 | 5.52% | 0.685% |
| 74.7% | $37,454 | $25,036 | 0.515% | 0.0375% |
| 76.0% | $41,607 | $28,316 | 0.1075% | 0.0% |

## Position size (IID IN_SAMPLE, 22 weeks)

| f | P50 end | P5 end | Median DD | P(≤−20%) | P(ruin) |
|---:|---:|---:|---:|---:|---:|
| 2% | $25,421 | $21,593 | 3.4785% | 0.0% | 0.0% |
| 3% | $28,566 | $22,362 | 5.09% | 0.0125% | 0.0% |
| 4% | $32,026 | $23,144 | 6.447% | 0.025% | 0.0% |
| 5% | $35,875 | $24,005 | 7.6704% | 0.08% | 0.0% |
| 6% | $39,933 | $24,513 | 8.8007% | 0.1225% | 0.0% |
| 7% | $44,264 | $25,236 | 10.0183% | 0.165% | 0.0% |
| 8% | $49,542 | $25,833 | 10.7254% | 0.295% | 0.0% |
| 10% | $60,480 | $26,840 | 12.4999% | 0.385% | 0.0% |

## Realized chronological book (not a sim)

118 complete 10-trade blocks, 2 leftover trades. End $576,772. Min $20,000. Max DD 8.48%.

## What this is not

- Not a live authorization.
- Not a fill. 40 exits are assumed.
- Not 3,000 games.
- Not terminal 83.84% as the strategy win rate.
- FULL IID is contaminated if you also used FULL to quote the edge.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

