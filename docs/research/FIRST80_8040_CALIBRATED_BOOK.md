# 80→40 calibrated book — jump≥20 excluded

Research only. **LIVE EXECUTION CHANGED: FALSE.**

This is the working FIRST-80 universe after last night’s volatility freeze.
Jump ≥20¢ one-minute entries are **out of the book**. They are not listed below.

```text
FILTER             entry-minute yes_bid jump ≥ 20¢ (FIRST80_ENTRY_QUALITY_AUDIT_V1)
CANDLE PATH        ≠ actual 80¢ maker fill
MODEL A            +20 survive / −40 close-40 stop / 0 leak
A1_UNIVERSE_V1     unchanged (still 1,230 / 721 unfiltered)
```

Does not modify FIRST01, Risk, Execution, or live MLB 80/81/83/89.

---

## Universes (volatility games excluded)

| Universe | Warehouse games | FIRST-80 | Never printed tradable 80 | Dates |
|---|---:|---:|---:|---|
| NBA `KXNBAGAME` | 1,340 | **1,208** | 132 | 2025-10-10 → 2026-06-13 |
| NCAAB all `KXNCAAMBGAME` | 5,171 | **3,990** settled | 1,179 | 2025-11-03 → 2026-04-04 |
| NCAAB P5 vs P5 | 834 | **706** | 128 | same season |

P5 vs mid = 680 games. Mid vs mid = 3,657. Those stay in the warehouse book only.

Raw NCAAB candidates still have 2 unsettled FIRST-80 rows (`25DEC21 PEAY-UMKC`, `26JAN25 WAG-LIU`). They were already out of the settled book. They are not volatility exclusions.

Excluded jump ≥20¢ (not in this book): NBA 22 · NCAAB warehouse 109 · P5 15.

---

## 80→40 calibrated book

| Universe | n | Survivors (+20) | Close-40 stops (−40) | Leak (lost, never 40) | Survival | Model A EV |
|---|---:|---:|---:|---:|---:|---:|
| NBA | 1,208 | 889 | 319 | 0 | 73.59% | +4.1556¢ |
| NCAAB warehouse | 3,990 | 2,909 | 1,080 | 1 | 72.91% | +3.7544¢ |
| NCAAB P5 vs P5 | 706 | 522 | 184 | 0 | 73.94% | +4.3626¢ |

NBA + P5 working total = **1,914**.

Remaining warehouse leak is mid-major, not P5: `26JAN27 ARPB-GRAM` GRAM (entry jump 15¢, kept). The other historical leak (`26JAN17 TXSO-ALCN` ALCN, jump 77¢, entry close 99¢) is a volatility exclusion and is not in this book.

Splits (filtered):

| | TRAIN | VAL | OOS |
|---|---:|---:|---:|
| NBA | 493 | 477 | 238 |
| NCAAB P5 | 134 | 544 | 28 (INSUFFICIENT_SAMPLE) |
| NCAAB warehouse | 916 | 2,992 | 82 |

P5 OOS n=28 is too small to lock a rule.

---

## What this is not

- Not a new FIRST-80 definition.
- Not a live retune.
- Not A1_UNIVERSE_V1 / EIE (those still use the unfiltered 1,230 / 721 freeze).
- Not an 80¢ maker-fill claim. Jump <20¢ is a candle-access proxy.
