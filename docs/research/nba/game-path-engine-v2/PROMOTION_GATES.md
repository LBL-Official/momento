# Promotion gates and final labels

## Scientific verdict (exactly one)

| Verdict | Meaning |
| --- | --- |
| A | Robust game-path conditional signal: interpretable features + VAL + OOS + meaningful EV + adequate capacity |
| B | Promising but insufficient (n, execution, or OOS confidence) |
| C | Descriptive / weak signal; no economically useful filter |
| D | No robust conditional signal |

## Production status (exactly one, independent of live)

| Status | Meaning |
| --- | --- |
| NO FILTER | Do not change 80/40 selection |
| RESEARCH-ONLY FILTER | Interesting, fails production utility |
| CANDIDATE PRODUCTION FILTER | Passes frozen utility on OOS **in research** |
| PRODUCTION-CANDIDATE PENDING LIVE VALIDATION | Reserved; V2 cannot award this without a separate live charter |

V2 **never** changes live execution.

## Model 3 vs 1

Logistic/elastic-net may replace buckets only if on VALIDATION:

1. Brier ≤ 0.95 × bucket-or-unconditional Brier (vs Model 0)
2. ECE ≤ Model 0 ECE + 0.005
3. Adjacent usable risk-bucket separation (n≥30, non-overlapping Wilson **or** ≥8pp monotone gap)
4. Implied filter acceptance ≥ 50% if a reject-high-q rule is proposed

## Model 4 / 5

Same numeric VAL gate versus the chosen simpler model. Depth-2 leaves are
hypotheses, not rules, until frozen.

## Failed knowledge

Rejected hypotheses remain in `EXPERIMENT_LEDGER` and the dashboard
graveyard with TRAIN / VAL / OOS numbers and the failure reason
(`OVERFIT`, `NON-ROBUST`, `INSUFFICIENT_SAMPLE`, `REJECTED`).
