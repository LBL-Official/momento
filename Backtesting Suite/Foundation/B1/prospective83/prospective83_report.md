# Prospective validation of frozen 83¢ entry states

## DOES ANY FROZEN 83¢ STATE SURVIVE PROSPECTIVE VALIDATION?

**INSUFFICIENT DATA**

W6 has post-cutoff games, but W7 TRADE paths do not (or none printed 83¢). No first-exact-83 prospective observation exists. NO ROBUST 83¢ ENTRY EDGE FOUND — holdout not yet evaluable.

PRODUCTION_COUNT = 0

Fill = `TRADE_PRINT_MODELED`. L2 = `UNAVAILABLE_SOURCE`.

## Coverage

| Field | Value |
|---|---:|
| existing locked TEST cutoff | 2026-06-27 |
| prospective start | 2026-06-28 |
| prospective end (W6 observed) | 2026-08-26 |
| W6 eligible games after cutoff | 757 |
| W7 reconstructed games (all time) | 3384 |
| W7 ∩ post-cutoff W6 | 0 |
| first-exact-83 in holdout | 0 |
| excluded (no W7 path) | 757 |

W6 games exist after cutoff but W7 EventMarketPath / TRADE prints were not reconstructed for those games. First-exact-83 requires a W7 TRADE at 83¢. Do not invent prints from W6 state alone.

## Executive table

| Candidate | Historical TEST EV | Prospective N | Prospective EV | 95% CI | Cost survival | Classification |
|---|---:|---:|---:|---|---|---|
| Candidate A | +2.41¢ | 0 | — | — | — | INSUFFICIENT_DATA |
| Candidate B | +12.12¢ | 0 | — | — | — | INSUFFICIENT_DATA |
| Candidate C | +3.96¢ | 0 | — | — | — | INSUFFICIENT_DATA |
| Candidate D | +3.96¢ | 0 | — | — | — | INSUFFICIENT_DATA |
| Candidate E | +4.25¢ | 0 | — | — | — | INSUFFICIENT_DATA |
| Candidate F | +2.42¢ | 0 | — | — | — | INSUFFICIENT_DATA |
| ALL_FIRST83 | +1.43¢ | 0 | — | — | — | INSUFFICIENT_DATA |
| do nothing | +0.00¢ | 0 | +0.00¢ | — | — | INSUFFICIENT_DATA |

## Distinctions

| Layer | Status |
|---|---|
| historical backtest (TRAIN/VAL) | frozen; not re-selected |
| locked TEST through 2026-06-27 | CONSUMED; not used to pick winners |
| prospective evidence | **not yet available** |
| production evidence | none; PRODUCTION_COUNT=0 |

## Why the holdout is empty

W6 canonical state includes games 2026-06-28 through 2026-08-26. W7 EventMarketPath and W8 replay stop at 2026-06-27. A first-exact-83 snapshot requires a W7 TRADE print at 83¢. Using W6 scores/innings without a TRADE print would invent the research unit. That is forbidden.

## Frozen definitions (do not edit to improve a score)

See `prospective83_candidates.json`. Historical TEST is locked/consumed.

| ID | Condition | Why frozen | Hist TEST |
|---|---|---|---:|
| CAND_A_40_49 | `start_price_band=40_49` | simplest +EV 1-way; discovery q=0.173 | +2.41¢ |
| CAND_B_MOVE30_OUTS0_VOL1M_LOW | `start_move_gt30=YES&outs=0&vol_1m_tertile=LOW` | predeclared priority 3-way | +12.12¢ |
| CAND_C_LEAD2_MOVE30_VOL1M_LOW | `lead_signed=LEAD_2&start_move_gt30=YES&vol_1m_tertile=LOW` | predeclared | +3.96¢ |
| CAND_D_TWORUN_MOVE30_VOL1M_LOW | `score_bucket=TWO_RUN&start_move_gt30=YES&vol_1m_tertile=LOW` | predeclared (near-dup C) | +3.96¢ |
| CAND_E_MOVEFINE_VOL_LOW | `move_fine=30_35&vol_1m_tertile=LOW&vol_15m_tertile=LOW` | predeclared | +4.25¢ |
| CAND_F_INNING7_PEAK_AT | `inning_grp=7&p_max_vs_83=PEAK_AT` | VAL-selected; less weight | +2.42¢ |

No prospective EV, CI, cost, or threshold result exists for any of these.

## Secondary analyses

Bootstrap, permutation, cost grid, threshold sensitivity, and new discovery were **not run**. They must not replace a missing primary holdout.

## Reproducibility

```text
./target/release/momento-research-b1 --validate-83-prospective
```

Research only. No live FIRST01 / 80/81/83/89 / stop / risk / W9 / L2 / orders.
