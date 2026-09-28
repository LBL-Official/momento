# V3 data lineage

```text
V1 source (warehouse, immutable)
    →
V1 canonical games / pbp / integer E4 candles
    →
V2 state tables and observation O_t  (available_at < cutoff)
    →
V3 backward measurements M_{≤t} on O_t
    →
explicit future boundary
    →
V3 response Y_{t→t+h}   (db.response; response_available_at)
    →
PIT-safe baseline E[Y|C]  (both clocks)
    →
residual R_t             (or INSUFFICIENT_SUPPORT)
```

Labels remain on `db.labels()` and are not used as V3 market responses.

Optional `derived/v3_response_corpus.csv` is a sampled first/mid/last-candle corpus for baseline grouping. It is not a public `dataset()` table.

1-second / L2 families are schema-only and are not computed from OHLC.
