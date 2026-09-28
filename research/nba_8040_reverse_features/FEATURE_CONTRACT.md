# NBA 80→40 reverse-features contract

Research only. Candle path ≠ fill. Do not change live FIRST01 / 80/81/83/89.
Do not edit `first80.py`. Do not start W9 or warehouse Phase 21.
The Choosin Texas 2026–27 book is out of scope.

Authority lives in `ROLLER/roller/nba_8040_reverse_features/`. This file is the
human-readable copy of that contract.

## Question

Why does NBA Q2 FIRST80 80→40 behave differently from Q3?

Two questions stay separate:

- **A.** Unconditional Q2 vs Q3 composition
- **B.** Survive vs T40 inside each period

If Q2 and Q3 occupy the same pre-80 region but keep different outcomes, the
honest result is `OBSERVED DIFFERENCE NOT EXPLAINED BY CURRENT FEATURE SET`.

## Universe

If and only if the locked contract independently reproduces NBA Q2∪Q3 **N=604**,
that 604 is the feature-store universe.

| lock | N | S | W∩T40 | L∩T40 | EV | book |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| NBA Q2∪Q3 | 604 | 450 | 55 | 99 | +4.7020¢ | 2840¢ |
| Q2 all-phase | 314 | slice | slice | slice | computed | computed |
| Q3 all-phase | 290 | slice | slice | slice | computed | computed |
| Q2 regular season | 280 | 218 | 22 | 40 | +6.7143¢ | 1880¢ |

280 / 314 / 290 / regular-season / IN / VAL / OOS are **analytical slices** of
the same 604-row store. They are not separate stores.

Any mismatch **stops the run** (`LOCK_MISMATCH`).

EV uses `roller.choosin_texas.ev` only:

```text
EV = 20S − 40(1−S)
S  = ¬T40
```

Q1 / Q4 exist on warehouse full-sport FIRST80 (TABLES.md 1,230) but not on
asked-six. v1 does not rescan them (`DATA_REQUIRED`).

## Instance

The locked FIRST80 contract is **one trigger per event**: first tradable
`yes_bid_close ≥ 80` after a prior close `< 80`, spread ≤ 10¢.

`nba_8040_instance` = that trigger. Not every later 80 reprint. Not a
game-level collapse.

```text
instance_id = sha256(event_id + "|" + ticker + "|" + timestamp_utc + "|FIRST80")[:16]
```

One row per 604 instance. Collision or two triggers per `event_id` is
`LOCK_MISMATCH`.

## Data plane

```text
asked-six CSV  →  who / when / labels / score+clock at 80 / pregame
warehouse parquet (read-only)  →  pre-80 1m TRADABLE_YES_BID path
warehouse PBP  →  sequence-only; no candle PIT
L2 / last-trade / fills  →  SOURCE_UNAVAILABLE / DATA_REQUIRED
```

- Population authority: `research/first80_asked_six_chatgpt_export/first80_asked_six.csv`
- Pre-80 bars: `ROLLER/data/nba/2025_2026/derived/warehouse/observations/basis=tradable_yes_bid/`
  via `available_at < timestamp_utc`. Windows are `[entry − w, entry)`.
  `yes_bid_*` e4 / 100 = cents.
  `TRADABLE_YES_BID ≠ LAST_TRADE_PRINT`.
- Post-80 bars and `time_to_40` / min / max / 90 live in **labels / event_path only**.
- Score/clock at 80: CSV snapshots. Clock model is
  `PERIOD_BOUNDED_LINEAR_GAME_CLOCK`, not warehouse PIT.
- Possession / fouls / timeouts: CSV already `UNAVAILABLE`. Class I =
  `SOURCE_UNAVAILABLE`. Do not invent from PBP timestamps.
- Time-windowed PBP (`score_change_1m`, …): `OPERATION_REQUIRED` until a named
  PBP↔candle PIT op exists. Do not interpolate.
- Historical L2: `SOURCE_UNAVAILABLE`. Entry bid/ask may be recorded as
  **quote-at-entry**, not L2.

## Namespaces

```text
asked-six population
        ↓
nba_8040_instance          (N=604 if lock holds)
        ↓
pre-80 feature store ───────────────┐
        ↓                           │
Q2/Q3 composition                   │
        ↓                           │
within-period S vs T40              │
        ↓                           │
temporal normalization              │
        ↓                           │
class ablation                      │
        ↓                           │
   PCA → KNN/matching → null → stability
                                    │
event_path.parquet ── inspection only
                                    │
labels/targets ────── outcome only
```

`event_features(instance)` is the pre-80 row.
`target(instance, stop_cents=40)` is the isolated outcome.
v1 analysis uses stop 40 only. 25–50 can reuse the store later.

## Timing

Every catalog feature carries:

`feature_name`, `feature_class`, `source`, `availability_rule`, `formula`,
`units`, `semantic_basis`, `timing`.

`timing` ∈:

- `AVAILABLE_BEFORE_ENTRY`
- `AVAILABLE_AT_ENTRY`
- `POST_EVENT_DIAGNOSTIC`
- `FUTURE_OUTCOME`

Value + status. Missing stays missing
(`OBSERVATION_UNAVAILABLE` / `SOURCE_UNAVAILABLE` / `OPERATION_REQUIRED`).
Never fill 0 except where the catalog says a **count** of zero is observed
(`n_bars_*m`, `bars_before_n`).

Period, `season_phase`, and `dataset_split` are columns on every instance.
Q2 / Q3 one-hot is a grouping column (`include_in_matrix=False`). It must not
enter PCA / KNN as an “explanation” of Q2 vs Q3.

## Leakage invariant (machine-tested)

```text
PREDICTIVE_FEATURE_MATRIX
    = AVAILABLE_BEFORE_ENTRY
    ∪ AVAILABLE_AT_ENTRY
```

Forbidden in that matrix:

```text
T40
S
W∩T40
L∩T40
terminal_yes
post_entry_min
time_to_40
hit_90
min_after
max_after
any post-entry price
any future score/clock
```

`assert_predictive_columns` fails the run if a forbidden name or a
`FUTURE_OUTCOME` / `POST_EVENT_DIAGNOSTIC` column is requested.
`matrix.py` does not import `labels.py` or `event_path.py`.
PCA, KNN, ablation, and matching call that one builder.

## Implemented now (data exists)

| class | contents |
| --- | --- |
| A identity | ticker, event_id, game_id, date, split, phase, period, side, teams, alignment |
| B market at 80 | bid, ask, last, volume-on-entry-candle |
| C / J / K pre-80 path | 1/3/5/10/15/30m windows: close, delta, velocity, accel, min/max/range/std, direction changes |
| D micro-path | prior close vs entry close; exact 80 vs jump-through; from-below |
| F time | period remaining, game remaining, fraction of period, fraction of game, OT flag |
| G score | home/away, bought margin, abs margin, lead/tie, favorite-leading |
| L quote-at-entry | bid/ask/spread. Not L2 |
| M open | `KALSHI_LAST_PRE_TIP_YES_BID`; distance 80-from-open |
| O period | Q2 / Q3 one-hot. No forced Q1/Q4. Not in the predictive matrix |
| P labels | isolated parquet: T40, S, W∩T40, L∩T40, post_entry_min, time_to_40, hit_90, terminal_yes, EV contribution +20 / −40 |

## Later or unavailable

| class | status |
| --- | --- |
| E post-80 path | event_path + labels only. Leakage audit fails if it enters PCA/KNN |
| H score trajectory | `OPERATION_REQUIRED` (no PBP↔candle PIT) |
| I possession / fouls / timeouts | `SOURCE_UNAVAILABLE` |
| N opposite ticker | skipped unless a complementary `GameMarketLink` row is used with honest timestamps; v1 skips |
| H6 L2 microstructure | `SOURCE_UNAVAILABLE` |

## Analysis sequence

1. Lock 604 / 314 / 290 / 280
2. Build the store on all 604. No outcome-based selection
3. Leakage test
4. Q2 vs Q3 composition (Question A)
5. S vs T40 within Q2 and within Q3 (Question B)
6. Temporal normalization (H1)
7. Class ablation: PRICE, TIME, SCORE, OPEN, PRICE+TIME, PRICE+SCORE, ALL PRE-80
8. PCA (numpy SVD) → fixed-k KNN `{5,10,20,30}` → label-permutation null → IN/VAL/OOS
9. Report one of `COMPOSITIONAL` / `STATE-DIFFERENTIAL` / `TIME-STRUCTURAL` /
   `MARKET-STRUCTURAL` / `JOINT` / `UNEXPLAINED`

PCA / KNN use complete-case rows on features observed on ≥90% of the 604.
No mean-fill. No sklearn. No EV-tuned k.

## What this will not do

- No skip-4–6 / only-56–60 / only-Q2 rule
- No Kelly, no live, no Risk, no FIRST80 retune
- No Choosin Texas book edit
- No treating PCA/KNN as a signal
