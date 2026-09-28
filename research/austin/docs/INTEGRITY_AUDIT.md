# Austin integrity audit

Measured from `python -m roller.austin` on 2026-09-18T04:22:23+00:00.
Artifact: `research/austin/artifacts/integrity_audit.json`.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
MODEL UNIVERSE    choosin_nba_2q3q_604
QUERY UNIVERSE    nba_warehouse_games
KNN target        pnl_hold_after_t
EV definition     hold_80_to_settlement = 20S − 80(1−S)
```

Identity lock: **PASS**. `N_trades = 604`.

## Path coverage

Definition: favorite 1m path after entry, opponent joined, PBP present,
no gap > 300s.

| class | N |
|---|---|
| PATH_COMPLETE | 520 |
| PATH_PARTIAL | 84 |
| PATH_UNAVAILABLE | 0 |
| N_trades | 604 |
| N_knn_observations | 48752 |
| N_entry_snapshots | 604 |

The previous boolean (`bool(post)`) counted every trade with ≥1
post-entry bar as complete. That is retired.

## 41 vs 42 (`TRIGGER_RESOLUTION = 1m_close`)

| count | N |
|---|---|
| n_first_le_42 | 443 |
| n_first_le_41 | 443 |
| n_42_without_41 | 18 |
| n_same_bar_42_and_41 | 425 |

18 first ≤42 closes land in (41, 42]. 425 first ≤42 and ≤41 prints are
the same 1m bar. Do not invent fully separated hedge economics. Wick
stays WORSE SCENARIO / DIAGNOSTIC. `FILL_UNAVAILABLE`.

## price_travel

`price_travel = current_price_cents − entry_price_cents`.

Path-snapshot Pearson vs `pnl_hold_after_t`: **0.496** (n=48148,
status=VALUE). Entry-only travel is identically 0. That case is
`ZERO_VARIANCE`, not `UNAVAILABLE`.

## Mid-path recognition (ladder)

Stored snapshots converted to QueryState, self `trade_id` +
`snapshot_id` excluded. Neighbor median current price is near the
query, not ~80, except the first entry row (an 81¢ FIRST80 print,
travel 0).

| query ¢ | n_source | query current | query travel | neighbor median current | neighbor median travel | weighted EV ¢ |
|---|---|---|---|---|---|---|
| 80 | 604 | 81 | 0 | 81 | 0 | +6.63 |
| 70 | 463 | 70 | −10 | 72 | −8 | +5.28 |
| 60 | 242 | 60 | −23 | 60 | −22 | −41.47 |
| 50 | 115 | 50 | −33 | 52 | −31 | −39.54 |
| 42 | 96 | 42 | −38 | 41 | −39 | −53.41 |
| 41 | 125 | 41 | −39 | 54 | −26 | −60.32 |
| 40 | 163 | 40 | −43 | 42 | −41 | −36.16 |

The 41¢ fixture's first source row is a sparse neighborhood
(median neighbor 54¢, median d=1.33). Status remains OBSERVED.
Candle path ≠ fill.

## Snapshot-level OOS (paper query)

Beside the locked entry walk-forward (TRAIN 351 / VAL 182 / OOS 71):

```
snapshot_oos n              6040
mean abs error              20.61 ¢
actual = pnl_hold_after_t
neighbors = earlier dates only
```

## Calibration

OOS n=71. Top / mid / bot realized hold PNL: **20.000 / −15.714 / 0.000**.
Status: **INSUFFICIENT_SAMPLE**. Default band **3%**.
`ENTRY_SIZING_REFERENCE` on POST-80. Decile table is persisted and
rendered. Small n stays visible.

## Data limits

- PBP is `PBP_SEQUENCE_NOT_PIT`. Candle-PBP PIT is `OPERATION_REQUIRED`.
- L2 / fills: `SOURCE_UNAVAILABLE` / `FILL_UNAVAILABLE`.
- LIVE FEED UNAVAILABLE. Query games ≠ training N.
- PRE-80 cannot enter the fitted 604 KNN without fabricating entry
  features (`NO_ENTRY_IN_FITTED_SPACE`).
