# ROBUSTNESS

| Check | Behavior |
|-------|----------|
| Cost sensitivity | net = gross EV − c for c ∈ {0, 0.25, 0.5, 1, 2, 3, 5}¢ |
| Adjacent entry buckets | 5¢ bands on observed `entry_close`; not ranked as an edge |
| Season groups | from `entry_ts` month (Oct–Sep NBA season); not silently pooled |
| Train / validation / OOS | only if `sample_partition` is on the row; no invented median split |
| Cluster count | always disclosed |
| Cross-venue | not forced; Kalshi vs Polymarket stays OPERATION_REQUIRED at compile |
