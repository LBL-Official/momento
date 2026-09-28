# W4 coverage measurement

Measure, do not manufacture:

```text
reconstructed tickers
paths by completeness
coupled episodes with both YES contracts
mapped paths vs unmatched paths vs ambiguous
starting_price verified vs unverified
lifetime OPEN_TO_SETTLEMENT vs SETTLEMENT_DAY_ONLY vs UNKNOWN
BLOCKED_ON_INGEST_OBSERVATIONS ticker count
PIT snapshots excluded from t_game
```

First fixture window: **2026-06-18** (ingest landing already has TRADES_ONLY
envelopes). Then 2026-06-18..30. Batch plan for 4,754 mapped pairs is declared
in the W4 summary after those windows; it is not executed in A5-S1.

Identity histograms are **consumed counts**. W4 does not rewrite pairs.
