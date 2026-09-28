# V4A capability matrix

| Object | Current data capability | V4A status | Reason |
|--------|-------------------------|------------|--------|
| Period | REAL | used in `core_v1` | PBP `period` |
| Clock | REAL (remaining ISO → elapsed) | used in `core_v1` | width-60 elapsed buckets |
| Score differential | REAL (home − away) | used in `core_v1` | `score_differential_home` |
| Home/Away | REAL | not a default dimension | subject is always home |
| Terminal winner | REAL (NBA ~1352/1362) | Y for F_t | `home_win` + `result_available_at` |
| Possession | NBA REAL; WNBA/NCAAB PARTIAL | off F_t conditioner | grammar when team present |
| Pre-game strength | PARTIAL (`*_pre`) | off | not F_t |
| Market `yes_bid_close` | REAL integer E4 | excluded | K ≠ F |
| PBP alignment | REAL | corpus source | `available_at < cutoff` |
| F_t empirical v1 | implemented NBA / WNBA / NCAAB P5 | REAL when support passes | prior-only wins/n; sport clocks; NCAAB corpus is P5 vs P5 |
| Basis / L2 / Greeks of F_t | SCHEMA_ONLY / out of scope | not in V4A | later phases only |
| WNBA / NCAAB F_t | implemented; terminals may be sparse | INSUFFICIENT_SUPPORT when floors fail | never 0.50 or K |

Surface occupancy on NBA 2025-2026: **ROBUST** under the configured floors. See [`reports/ROLLER_V4A_FUNDAMENTAL_SURFACE_AUDIT.md`](../reports/ROLLER_V4A_FUNDAMENTAL_SURFACE_AUDIT.md).
