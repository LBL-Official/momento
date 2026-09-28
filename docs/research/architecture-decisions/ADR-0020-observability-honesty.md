# ADR-0020 — Observability honesty

# Decision

Never fabricate historical data. If it does not exist, document it. If
synchronization cannot be proven, document it. If a Greek cannot be empirically
derived, document it. Completeness is subordinate to accuracy.

# Context

Local lake: 13 MLB days, candles not L2, no PBP, 2025 empty probes, close-day
partitions that may omit starting prices. Kalshi historical discovery returned
0 markets for pre-2026-06-18 windows at collect time 2026-08-25.

# Problem

Filling gaps with mids, interpolated books, or synthetic 2025 days would poison
every later model.

# Alternatives Considered

1. Impute to keep tables dense.
2. Drop incomplete games entirely.
3. Retain incomplete evidence with explicit coverage vocabulary.

# Decision Made

Alternative 3. Coverage must distinguish at least:

```text
NOT_ATTEMPTED | PROBE_EMPTY | PARTITION_COMPLETE | LIFETIME_INCOMPLETE
HISTORICAL_API_UNAVAILABLE | UNAVAILABLE | INVALID
```

Do not redefine v1 `COMPLETE` to mean lifetime-complete.
Do not treat demo `Backtesting Suite/Data` as real MLB.

# Rationale

False precision is worse than a hole.

# Consequences

Waterfall 1 catalog is the honest inventory. Re-query may still return empty;
persist the empty evidence.

# Data/Model Implications

Models must consume coverage flags. Survivorship bias is a W19 concern.

# Testing Implications

no_synthetic_rows; demo ≠ real; catalog does not invent 2025 games.

# Future Compatibility

New sources expand OBSERVED coverage without rewriting UNAVAILABLE history.

# Status

ACCEPTED

# Date

2026-08-26
