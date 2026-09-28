# W4 completion report (bounded window)

**Run:** `w4-20260826T184707Z`  
**Window:** 2026-06-18 only  
**CTO ACCEPTED:** no (acceptance pack only)

## Measured

| Metric | Value |
|--------|------:|
| Committed envelopes | 18 |
| Reconstructed | 18 |
| Failed | 0 |
| Completeness | TRADES_ONLY × 18 |
| Coupled episodes (both YES) | 9 / 9 |
| Identity mapped / unmatched / ambiguous | 0 / 18 / 0 |
| Starting price | UNVERIFIED × 18 |
| Lifetime | UNKNOWN × 18 (no open/settlement on envelopes) |
| PIT snapshots excluded from t_game | 8 |
| BLOCKED_ON_INGEST_OBSERVATIONS | 0 (this day has trades) |
| L2_COMPLETE / FULL_L2 | not claimed |
| 2024 Kalshi | not claimed |

`completeness_claimed=true` means reconstruction **invariants** passed for this
window, not that the book is complete.

## Batch plan (not executed)

1. Prove 2026-06-18 (this report).
2. Next grant: 2026-06-18..30 (Data-Real COMPLETE + ingest trades).
3. Only then batch the 4,754 mapped pairs by date, skipping
   `MARKET_METADATA_ONLY` into a blocker list rather than fabricating points.

## Not done (as of 2026-06-18 window)

W5 sync, Greeks, FIRST01 replay, AWS ingest, Data-Real writes, production trees.

---

## Price-path foundation (W4-PRICE-PATH-S1)

**Status:** COMPLETE (engineering). See [W4/RECONSTRUCTION.md](W4/RECONSTRUCTION.md).

| Metric | Value |
|--------|------:|
| Inventoried | 8,428 |
| Reconstructed TRADES_ONLY | 238 |
| L2 paths | 0 |
| Excluded (METADATA_ONLY) | 8,190 |
| 80% print (reconstructed) | 137 / 238 |
| GameId-linked 80% denominator | 0 / 2,377 MATCHED games |

W5 was not started.

