# W1 Coverage Specification

v1 `completeness_status=COMPLETE` is **not** lifetime-complete, L2-complete, or PBP-complete.

## PartitionCoverage (W1)

| Value | Meaning |
|-------|---------|
| `PARTITION_COMPLETE_V1` | All discovered close/settled PT-day markets collected |
| `PROBE_EMPTY` | Attempted; 0 markets (e.g. 2025 probes, 2026-06-01..17) |
| `PARTIAL` / `INVALID` / `MISSING` | v1 remaining states |
| `NOT_ATTEMPTED` | No manifest in this lake |
| `HISTORICAL_API_UNAVAILABLE` | Reserved for documented API cutoff |

## Dimensions

`COMPLETE_FOR_WINDOW` applies only to the v1 PT close/settled day.

Always for this lake:

- `l2` → UNAVAILABLE (`L2_HISTORICAL_UNAVAILABLE`)
- `pbp` → UNAVAILABLE
- `starting_price` → UNAVAILABLE / `STARTING_PRICE_UNVERIFIED`
- `synchronized_state` → UNAVAILABLE
- `lifetime_path` → UNAVAILABLE (`LIFETIME_UNVERIFIED` is this dimension, not a redefinition of v1 COMPLETE)
