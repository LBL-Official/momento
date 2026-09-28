# FIRST80 alpha decomposition v1 — methodology

**RESEARCH ONLY. LIVE EXECUTION = FALSE.**

```
OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY
TERMINAL ALPHA ≠ PATH ALPHA
PATH SURVIVAL ≠ INDEPENDENT EDGE
CONDITIONAL INFORMATION ≠ EXECUTABLE PROFIT
HISTORICAL CANDLE PATH ≠ ACTUAL FILL
HEDGE OPPORTUNITY ≠ LOCKED-IN ALPHA
```

## Definitions (imported, not forked)

FIRST80 and primary T40 are exactly the frozen NBA execution-audit objects:

- `apps/nba-data/scripts/nba_80_40_execution_audit.py`
- `warehouse/derived/nba/first80_execution_audit/candidates.json`

Identity gate: 1230 / 910 / 320 / 0 and 1019 wins.

Wick T40 is not the primary object.

## Decomposition

\[
P(W\cap\neg T_{40}\mid FIRST80)=P(W\mid FIRST80)\times P(\neg T_{40}\mid W,FIRST80)
\]

These terms are not independent edges.

## Modules

- A: exact binomial vs 80%; threshold FirstReach(q) surface with the same tradable-cross rule.
- B: P(¬T40|W) vs FIRST75, NON_FIRST80, coarsened strata. Bins locked a priori.
- C: four-cell tree, phi / OR / MI, sensitivity surface labeled hypothetical.
- D: opponent candle bid_close grid. Quoted state ≠ fill.
- Persistence: TRAIN-only F̂(S); VAL/OOS evaluate α̂=F̂−K. F is not observed.

## Splits

Frozen audit cuts. Not retuned on OOS.

## Clustering

Game / team / date bootstrap. n=1230 is not treated as i.i.d. without that check.

## Classification (locked)

- **Terminal distinguishable:** one-sided exact binomial p vs 0.80 < 0.05 on FULL, **and** OOS point estimate > 0.80.
- **Independent path:** among winners, OOS interval on P(¬T40|W, FIRST80) − P(¬T40|W, FIRST75) excludes 0. If FIRST75 is nearly identical to FIRST80, the path test is inconclusive.

A 4pp OOS point gap with overlapping intervals is **not** an independent path effect.
