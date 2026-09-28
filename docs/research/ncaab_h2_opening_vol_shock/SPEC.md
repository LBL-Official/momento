# H2 OPENING ADVERSE DELTA NORMALIZATION — frozen object

```
RESULT: NEGATIVE
REJECTED MECHANISM
DO NOT OPTIMIZE A PROFITABLE SUBSET
CLOSE_5 = DESCRIPTIVE OBSERVATION
LIVE EXECUTION = FALSE
```

Title: **VOLATILITY NORMALIZATION FAILS AS A RECOVERY MECHANISM**
Short: **QUIET DOES NOT MEAN REVERSION**
Interpretation: **QUIET TAPE = NEW PRICE ACCEPTANCE**

Completely separate from FIRST75 / FIRST80 / Lebronner.
Does not change live FIRST01. P5 vs P5 `KXNCAAMBGAME` 2025-26 only.
Formal freeze: `CONCLUSION.md`.

## One sentence

Within the first five minutes of H2, does an unusually large, bounded
adverse price delta — relative to that game's H1 volatility regime —
subsequently recover when volatility normalizes?

## Universe

- Sport: NCAAB men's
- Filter: both teams in Power-5 codes
- Identity: 849 P5 vs P5 games (warehouse gate)
- Requires: both yes contracts, MATCHED ESPN PBP
- Price: quality `yes_bid_close` (uncrossed, spread ≤ 10¢). Candle path ≠ fill.

## Clock

Regulation 2 × 20:00. ESPN observed wallclock snap.

- t0 conceptual: 20:00 remaining (H2 start)
- H1 baseline: period = 1, phase = IN_PERIOD (halftime INTERMISSION excluded)
- H2 shock window: period = 2, phase = IN_PERIOD, `900 < remaining ≤ 1200`
- Consecutive quality minutes only if wall gap ≤ 90s (halts HT jumps)

## Baseline (stored, not collapsed)

Per damaged contract, and game-pooled:

- n, mean |ΔP|, median |ΔP|, σ(ΔP), σ(|ΔP|)
- p80 / p85 / p90 / p95 of |ΔP|
- Thin H1 (n < 8 diffs) cannot be a primary shock

Continuous shock measures (always stored):

- Z_abs = (|ΔP| − mean_abs) / σ(|ΔP|)
- R_shock = |ΔP| / Q_0.80

Primary *flag* (not the only rows): |ΔP| > H1 p80 and ΔP < 0.

## Score tags (not optimized)

- |ΔM| stored continuously
- bounded_info: |ΔM| ∈ [1, 4]
- pct = |ΔM| / |M_pre| only if |M_pre| ≥ 4 (avoids 2→1 as “50%”)
- prop_band: pct ∈ [25%, 50%]
- CLOSE_5 / 7 / 10 / 12 on |M_pre|
- All bands reported. None selected on recovery.

## Entry object

i* = argmin_i ΔP_i among the two yes contracts that have a quality
ΔP on that minute. Ties discarded.

## Hypothesis

H0: E[R_post | shock] ≤ E[R_post | ordinary adverse control]
H1: E[R_post | shock] > E[R_post | ordinary adverse control]

Control = H2-open minutes with ΔP < 0 and |ΔP| ≤ that contract's H1 p80.

## Objects (tested separately)

- A: does post-entry mean |ΔP| over 5 minutes return to ≤ H1 mean |ΔP|?
- B: R at +1 / +2 / +3 / +5 / +10 minutes (bid close − entry close)
- C: E[R | shock ∧ vol_norm] vs E[R | shock ∧ ¬vol_norm]

## Splits (calendar, frozen before this object)

IN_SAMPLE: game_date ≤ 2025-12-31
VALIDATION: 2026-01-01 … 2026-03-15
OOS: game_date > 2026-03-15

Descriptive only. Close bands are not selected on VAL.

## Archive rule

This object is **closed**. Do not add score bands, close thresholds,
or shock percentiles to rescue R5. CLOSE_5 stays a descriptive
observation and requires independent replication before it can even
be a *hypothesis*, not a condition.

## What this is not

- Not FIRST75 / FIRST80 / T40 / Lebronner
- Not a live fade or other-side rule
- Not L2, mid, fees, or fills
- Not W9
