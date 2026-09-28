# ROLLER V4A fundamental surface audit

**Date:** 2026-09-06  
**Script:** `scripts/audit_fundamental_surface.py`  
**Corpus:** `pbp_last_per_clock_bucket_v1` on NBA 2025-2026  
**Estimator:** `fundamental_win_probability_empirical_v1` / `core_v1`  
**This is a support-architecture rating, not a trading-quality rating.**

```text
F_t ≠ TRUTH    MORE CELLS ≠ MORE INFORMATION    n_obs ≠ n_independent_games
```

## Classification

**ROBUST** under the configured floors (`minimum_observations=3`, `minimum_unique_games=2`, `minimum_unique_dates=1`, `minimum_unique_seasons=1`).

The question this gate answers:

> Does the current NBA corpus support a reproducible, prior-only empirical fundamental probability surface?

**Yes, with documented limits:** one season, last-PBP-per-clock-bucket sampling, home-oriented Y, and rare extreme cells that still refuse.

## Corpus

| Quantity | Value |
|----------|-------|
| State rows | 70,730 |
| Unique games with terminal Y | 1,352 |
| Late information cutoff used for occupancy | `2026-06-14T03:29:27Z` (max `result_available_at` + 1s) |

Rows are the last visible PBP event in each `(game, period, clock_bucket)`. That is why `n_observations` ≈ `n_unique_games` inside a cell.

## End-of-sample occupancy (`core_v1`)

| Surface | Cells | Supported | Null rate | Median unique games | Min unique games |
|---------|-------|-----------|-----------|---------------------|------------------|
| period | 6 | 6 | 0.0 | 1,352 | 9 |
| period + clock | 64 | 64 | 0.0 | 1,352 | 9 |
| period + clock + score (`core_v1`) | 352 | 336 | 0.045 | 209 | 1 |

16 of 352 full cells fail the floors (extreme margin × rare clock/OT). Those cells return `null` + `INSUFFICIENT_SUPPORT`. They are not filled with 0.50 or K.

## Prior-only occupancy at earlier cutoffs

Same corpus, same floors, eligibility still `result_available_at < cutoff` and `state_available_at < cutoff`:

| Cutoff | Cells | Supported | Null rate | Median unique games | Class |
|--------|-------|-----------|-----------|---------------------|-------|
| 2025-11-15Z | 330 | 307 | 0.070 | 36 | ROBUST |
| 2026-01-01Z | 341 | 325 | 0.047 | 90 | ROBUST |
| 2026-06-14Z | 352 | 336 | 0.045 | 209 | ROBUST |

Early-season queries have fewer priors. The class stays ROBUST because the floors are deliberately low and most regulation cells still clear them. Min unique games remains 1 in the tail — those cells refuse.

## Fragmentation

Adding clock to period does not explode the cell count the way an independent minute grid would: elapsed seconds already encode period, so `period + clock` is 64 cells, all supported.

Adding score margin is the real split: 64 → 352 cells, null rate 0 → 4.5%, median unique games 1,352 → 209. That is expected. It is not a reason to auto-change `core_v1`.

## What this does not say

- F_t is not the true probability.
- ROBUST is not a claim that the market is inefficient.
- ROBUST is not authorization for Greeks, basis, or live trading.
- One NBA season cannot satisfy a two-season floor; the configured season floor is 1 for that reason.
