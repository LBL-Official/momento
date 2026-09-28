# Phase 14 — Edge / failure suite

Measured: **2026-09-13**. Adversarial tests only. No new engine features beyond identity uniqueness (duplicate `internal_game_id` must not emit two rows).

Fixtures are in-memory under `ROLLER/tests/`. The canonical warehouse was not written.

Module under test: `ROLLER/roller/warehouse/conditional_backtest.py`.
Suite: `ROLLER/tests/test_conditional_backtest_edge_cases.py`.

---

## Matrix

| Case | Expected | Actual |
| --- | --- | --- |
| No market | no fabricated ticker; empty population | PASS — links empty → population 0 |
| No PBP (not required) | execution proceeds | PASS — CROSS without period → population 1 |
| No PBP (required) | explicit missing/unaligned, no invented clock | PASS — Q2 without PBP → population 0 + exclusions |
| Missing settlement | `MISSING_SETTLEMENT`, not LOSS | PASS |
| Invalid settlement | `INVALID_SETTLEMENT`, not NO/LOSS | PASS |
| Missing minute | no forward-fill / interpolate | PASS — 10-minute gap still crosses on next real bar |
| Missing `available_at` | reject; no `event_timestamp` substitute | PASS — entity construction raises `ValueError` |
| Same-minute duplicate | warehouse order; no arbitrary pick | PASS — 6200 then 6300 at same minute; entry 6300 |
| Multiple entry / ordinal | first / second / third exact | PASS |
| Repeated touch | exact ordinal; one row | PASS |
| Repeated exit | one terminal observation | PASS — first REACH 87, later 88 ignored |
| Same-observation tie | `SAME_BAR_TIE`; no invented order | PASS — WIN and LOSS at `01:02:00Z` |
| Jump-through | candle-path REACH/DROP; no fill fields | PASS — 6300→3700 is LOSS; no `fill_price` |
| Boundary equality | CROSS already-at-P not a cross; ABOVE `>`; BELOW `<`; REACH already-at-P not a new reach | PASS |
| Period boundary | Q1↛Q2, Q2↛Q3, Q3↛Q4, Q4↛OT | PASS |
| OT | OT ≠ Q4 | PASS |
| Clock boundary | 12:00 / 11:59 / 10:00 inclusive on [600,720]; 09:59 / 00:01 / 00:00 excluded; 00:00 excluded from 6–8 min window | PASS |
| Missing next observation | `NO_TERMINAL_RESULT`; no fabricated candle | PASS |
| Date boundary | inverted range `DATA_REQUIRED`; live 2025-10-10 context dates ⊆ {2025-10-10} | PASS |
| DST | UTC `available_at` unchanged; not local | PASS — entry `2025-11-02T06:00:00Z` |
| Duplicate game date | identity, not date+teams | PASS — BOS_TOR and ORL_PHI both appear |
| Duplicate records | no duplicate result rows | PASS — duplicate games/links/obs/PBP/settlements → population 1 |
| Malformed record | explicit failure / exclusion | PASS — empty ticker rejected; period `xx` → no Q2 entry |
| Empty population | `ZERO_RESULTS`, not `DATA_REQUIRED` / LOSS | PASS |
| Historical L2 | `DATA_REQUIRED`, no scan | PASS |
| Historical tick | `DATA_REQUIRED` | PASS |
| ORDERBOOK / TRADE_TAPE | `DATA_REQUIRED` | PASS |
| PBP/candle PIT | `OPERATION_REQUIRED`, no scan | PASS |
| No inferred execution | no fill/slippage/queue fields | PASS |
| No inferred settlement | last candle 0 or 100 is not YES/NO | PASS — still `MISSING_SETTLEMENT` |

---

## Notes

- Clock remaining is inclusive (`lo <= remaining_s <= hi`) via existing `ClockWindow.contains`. Clock is PBP game clock only.
- Jump-through and `SAME_BAR_TIE` are observation-path classifications. They are not fills.
- Duplicate `Game` rows in a synthetic bag are collapsed by `internal_game_id` so reference and optimized stay at one row.

Phase 14 complete. Next authorized phase is **15**. Do not start it from this report.
