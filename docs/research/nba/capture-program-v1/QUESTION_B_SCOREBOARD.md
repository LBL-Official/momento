# Question B scoreboard

Candle-only execution facts. **Copied from the frozen audit.** This file
does not relabel FIRST-80, does not invent fills, and does not claim
“the strategy makes 74%.”

Source (do not modify):

```text
Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/first80_execution_audit/summary.json
```

Script: `apps/nba-data/scripts/capture_program_v1/build_scoreboard.py`

Generated warehouse copy:
`.../momento_capture_program_v1/scoreboard.json`

---

## This report does not conclude the strategy makes 74%

`yes_bid_close ≥ 80` is not a maker fill.
`yes_bid_close ≤ 40` is not a 40.00 IOC fill.
Production `KalshiFeeModel` is UNRESOLVED.

---

## Close-path baseline (Question A labels)

| Quantity | Value |
| --- | ---: |
| Games | 1,362 |
| FIRST-80 settled | 1,230 |
| Survivors (no close-path 40 and won) | 910 |
| Close-path 40 | 320 |
| Survival | 73.98% (CI 71.46–76.36) |
| Gross EV (+1R / −2R) | +0.2195 R |
| Net EV (research taker stop fee, maker fee off) | +0.1977 R |

P(Kalshi YES | first 80) = **82.85%**. Do not mix with strategy survival.

P(eventual YES | 80 then close-40) = **34.06%** (109 / 320).

---

## Fill at 80 (estimated, not observed)

`historical_fill_unknown = true`
`orderbook_depth_available = false`
Fill confidence uses **only the crossing candle** (a priori; not fit on OOS).

| Confidence | n | Rule |
| --- | ---: | --- |
| HIGH | 1,071 | last-trade through 80, volume > 0, spread ≤ 5¢, bid still ≥ 80, bid range ≤ 15¢ |
| MEDIUM | 75 | last-trade through 80, volume > 0, bid ≥ 80 |
| LOW | 84 | tradable bid ≥ 80 without last-trade evidence |

Fill filter only (HIGH, still close-stop): **73.30%**, n=1,071, gross EV **+0.1989 R**.
That drop is noise relative to the stop-path drop.

---

## Stop at 40 (largest EV uncertainty)

Do not mix fill filters with stop path.

| Model | n | Win rate | Gross EV |
| --- | ---: | ---: | ---: |
| Original / close-stop | 1,230 | 73.98% | +0.2195 R |
| HIGH fill, close-stop | 1,071 | 73.30% | +0.1989 R |
| All fills, wick-stop (`bid_low ≤ 40`) | 1,230 | 69.02% | +0.0707 R |
| Conservative (HIGH + wick) | 1,071 | 69.28% | +0.0784 R |

Conservative 95% CI **66.45–71.97% includes 66.67% breakeven**.

Wick-stop eventual-win given 40-low: **44.62%** (170 / 381). Close-stop
eventual-win given 40-close: **34.06%** (109 / 320). A wick is a different
object than a close-path stop.

---

## Fees (research estimate only)

Label: `RESEARCH_PUBLISHED_SCHEDULE_ESTIMATE`.
`kxnbagame_maker_multiplier`: UNKNOWN_NOT_IN_WAREHOUSE.

Quadratic `ceil_6dp(coef × C × P × (1−P))`, M=1:

| Leg | Coef | Per contract |
| --- | ---: | ---: |
| Maker entry 80¢ | 0.0175 | $0.002800 |
| Taker entry 80¢ | 0.07 | $0.011200 |
| Taker stop 40¢ | 0.07 | $0.016801 |

Maker fee off, taker stop on: baseline net **+0.1977 R** (gross +0.2195 R).
Maker fee on: baseline net **+0.1837 R**; conservative net **+0.0386 R**.

Fees nibble EV. They are not the 74% → 69% gap.

---

## Persistence (close-stop vs conservative)

| Split | Baseline n / WR | Conservative n / WR |
| --- | --- | --- |
| IN_SAMPLE | 504 / 71.83% | 415 / **66.27%** |
| VALIDATION | 483 / 75.57% | 429 / 70.63% |
| OOS | 243 / **75.31%** | 227 / **72.25%** |

Close-stop OOS is 75%. Conservative early (IN_SAMPLE) is **below**
breakeven. Thresholds were not fit on OOS.

---

## Concurrent exposure (gross path sim, not fills)

Unlimited baseline: **max 8** concurrent first-80s.
Cap=1: 505 accepted / 725 skipped.
Cap=5: 1,192 accepted / 38 skipped.

Overlap caps booked N. It does not invent the path edge.

---

## What would close Question B

Observed maker fills at 80, observed stop fills at/through 40, observed
fees, and fillable weekly N. Not more 1-minute feature mining.
