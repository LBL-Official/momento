# NCAAB FIRST-80 / close-40 observational audit (2025–2026)

Research only. Same candle-path rule as
[`apps/nba-data/scripts/nba_80_40_execution_audit.py`](../../../apps/nba-data/scripts/nba_80_40_execution_audit.py).

**LIVE EXECUTION CHANGED: FALSE.** Not MLB FIRST01. Not W9. Not a fill.

Script: `apps/ncaab-data/scripts/ncaab_80_40_execution_audit.py`  
Artifacts: `Backtesting Suite/Data/NCAAB/2025-2026/warehouse/derived/ncaab/first80_execution_audit/`

## Rule (copied, not retuned)

1. Game-day window: 16h–52h from `game_date` UTC (same as NBA audit).
2. FIRST-80: first tradable `yes_bid_close ≥ 80¢` after a prior tradable close `< 80¢`.
3. One entry per game (earliest 80). Later 80s are not re-entries.
4. Close-stop: later tradable `yes_bid_close ≤ 40¢` → STOP (−2R).
5. Else hold to settlement: YES → +1R, else `LOSS_NO_STOP`.
6. Fill confidence uses **only the crossing candle**. Not a historical fill.
7. Calendar splits frozen a priori (same NBA cuts): IS ≤ 2025-12-31, VAL ≤ 2026-03-15, OOS after.

## First measurement

| | N |
|---|---:|
| Games | 5,280 |
| Settled FIRST-80 | 4,099 |
| Survivors (no close-40 and won) | 2,998 |
| Close-40 stops | 1,099 |
| No tradable 80 | 1,179 |
| Close-stop win rate | 73.14% (CI 71.76–74.47) |
| Gross EV (+1R/−2R) | +0.195 R |
| HIGH / MEDIUM / LOW fill confidence | 2,575 / 405 / 1,119 |

NBA frozen reference (not a target): 1,230 / 910 / 320 at 73.98%.

Conservative HIGH + wick-stop on this NCAAB set: **65.48% / −0.036 R** (below 66.67% breakeven). That is an estimated candle path, not a fill.

OOS n=84 is small (late season / tournament). Do not over-read it.

## Variant: first-exit 90 or 40 (no expiration hold)

Script: `apps/ncaab-data/scripts/ncaab_80_90_40_execution_audit.py`  
Artifacts: `.../derived/ncaab/first80_90_40_exit_audit/`

Same FIRST-80 entry. Exit is the first later `yes_bid_close ≥ 90¢` or `≤ 40¢`. Settlement is **not** used as P&L. One path never printed either barrier.

Payoff: **+10¢** at 90, **−40¢** at 40. Breakeven **80%** (vs 66.67% hold-to-100).

| Close-path | N / value |
|---|---:|
| Decided | 4,098 |
| Hit 90 first | 3,370 |
| Hit 40 first | 728 |
| P(90 \| decided) | 82.24% (CI 81.04–83.38) |
| Gross EV | +1.12¢ / trade (+0.056 R vs 20¢ unit) |

Wick path (`bid_high ≥ 90` vs `bid_low ≤ 40`): 77.78% (CI 76.48–79.03), **−1.11¢**. 20 same-minute ties excluded — intra-minute order unknown.

The close-path CI sits just above 80%. Fees and fills would erase that. Wick fails the hurdle.

### Stop moved to 50¢ (first-exit 90 or 50)

Same script with `--stop 50`. Artifacts: `.../derived/ncaab/first80_90_50_exit_audit/`

Payoff: **+10¢** at 90, **−30¢** at 50. Breakeven **75%**.

| Close-path | N / value |
|---|---:|
| Decided | 4,099 (none missed both barriers) |
| Hit 90 first | 3,217 |
| Hit 50 first | 882 |
| P(90 \| decided) | 78.48% (CI 77.20–79.71) |
| Gross EV | +1.39¢ / trade (+0.070 R vs 20¢ unit) |

Wick path: 71.74% (CI 70.33–73.10), **−1.31¢**. 23 same-minute ties excluded.

Tighter stop vs 40: more stops (882 vs 728), lower P(90) (78.5% vs 82.2%), but the hurdle falls from 80% to 75%, so close-path EV is slightly higher (+1.39¢ vs +1.12¢). Wick still fails.

## Stop-candle inspection (close-40 minutes)

On the **1,099** baseline stop minutes (`yes_bid_close ≤ 40¢`):

- Bid range > 10¢: **861 (78.3%)**. Median bid range **18¢** (p90 38¢, max 93¢).
- Last-trade range > 10¢: **775 (70.5%)**.
- Close finished more than 10¢ through 40 (close ≤ 30¢): **227**.
- Bid high/low straddled 40 that minute: **1,036 (94.3%)** — the bid *passed* 40; that is not a fill.
- Entire minute already below 40 (high < 40): **63 (5.7%)**.
- Prior close > 50¢ then this close ≤ 40¢: **326**. Prior close > 55¢: **163**.

A 40.00 stop fill is an assumption. Wide/gapped minutes make −2R optimistic. See `first80_execution_audit/stop_candle_inspect/REPORT.md`.

## Liquidation model v1 (40¢ is a trigger, not a fill)

`FIRST80_LIQUIDATION_MODEL_V1` re-prices only the stop leg. Wins stay +20¢.
Gross EV is zero at average stop fill **25.44¢ (NCAAB)** / **23.13¢ (NBA)** before fees.

| Model | NCAAB E[P_fill] / EV | NBA E[P_fill] / EV |
|---|---:|---:|
| A ideal 40 | 40.00 / +3.90¢ | 40.00 / +4.39¢ |
| B stop-minute bid close | 33.15 / +2.07¢ | 34.13 / +2.86¢ |
| C stop-minute bid low | 28.68 / +0.87¢ | 30.60 / +1.94¢ |
| D gap-aware | 31.70 / +1.68¢ | 32.60 / +2.46¢ |

Candle proxies, not fills. L2 UNAVAILABLE. Spec:
[`FIRST80_LIQUIDATION_MODEL_V1.md`](FIRST80_LIQUIDATION_MODEL_V1.md).

## Opponent-40 hedge (not a stop)

Rest a 40¢ maker bid on the **other** YES after FIRST-80. If both fill:
locked **−20¢**. If the bid never fills: +20 / **−80**.

Close-path (ESTIMATED): NCAAB **+4.89¢** / contract vs 80/40 **+3.90¢**;
NBA **+5.17¢** vs **+4.39¢**. Missed-hedge −80 is almost absent (1 and 0).
The cost is earlier hedges: 842 NCAAB / 245 NBA locks later settled YES.

On a reserved $6.25 budget (5×120¢ vs 7×80¢) the dollar ranking flips
back to 80/40. Spec:
[`FIRST80_OPPONENT_40_HEDGE_V1.md`](FIRST80_OPPONENT_40_HEDGE_V1.md).

## Historical data used

1-minute top-of-book + last-trade OHLC. **L2 NOT AVAILABLE.**
