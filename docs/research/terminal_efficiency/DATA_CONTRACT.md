# Base Terminal Efficiency — Data Contract

**Semantics version:** 1.0.0  
**Schema version:** 1.0.0  
**Code version:** `base_te_v1.0.0`  
**Binding PIT rule:** `available_at < observation_ts` (half-open; equality excluded)  
**Object:** empirical observation. Not a prediction. Not XIB.

Statuses used on fields: `OBSERVED` · `DERIVED` · `UNAVAILABLE` · `AMBIGUOUS`.  
Not used: `PREDICTED` · `ALPHA` · `EDGE`.

---

## Clocks

| Name | Rule |
|------|------|
| `available_at` | When the row could have been known. I(t) filter uses **only** this. |
| `observation_ts` | Candle close of the tradable bar (`available_at` of that bar). |
| `event_timestamp` | When the PBP event happened. Used by `snap_events` **after** I(t). |

```text
visible(row, t)  iff  row.available_at < t
snap: last I(t)-visible PBP with event_timestamp <= observation_ts
```

Do not use `available_at <= observation_ts`. Informal `<=` in other drafts is rejected.

Terminal settlement is post-entry. It must not enter any entry-state field.

---

## Identity

| Field | Type | Unit | Source | Kind | PIT | Missing |
|-------|------|------|--------|------|-----|---------|
| `observation_id` | str | — | `BTE_{game}_{ticker}_{compact}_V{schema}` | DERIVED | n/a | never empty |
| `game_id` | str | — | candle `internal_game_id` | OBSERVED | identity | drop row |
| `ticker` | str | — | candle `ticker` | OBSERVED | identity | drop row |
| `league` | str | — | games / universe | OBSERVED | identity | UNAVAILABLE |
| `season` | str | — | games / universe | OBSERVED | identity | UNAVAILABLE |
| `team_side` | str | home\|away | candle `team_side` | OBSERVED | identity | UNAVAILABLE |
| `opponent` | str | team id | games home/away vs `team_side` | DERIVED | identity | UNAVAILABLE |
| `team` | str | team id | games vs `team_side` | DERIVED | identity | UNAVAILABLE |
| `observation_ts` | UTC ISO | — | candle `available_at` | OBSERVED | is t | drop row |

`make_observation_id` in ROLLER is game+time only. Two YES tickers share a close. Base TE ids **include ticker**. The existing helper is not modified.

---

## Game time

| Field | Type | Unit | Source | Kind | PIT | Missing |
|-------|------|------|--------|------|-----|---------|
| `period` | str/int | — | snapped PBP | OBSERVED | I(t) then snap | UNAVAILABLE / UNALIGNED |
| `game_clock` | str | remaining | snapped PBP `clock` | OBSERVED | same | UNAVAILABLE |
| `remaining_game_time` | int | seconds | `clock_remaining` + period | DERIVED | same | UNAVAILABLE |
| `elapsed_game_time` | int | seconds | `elapsed_game_seconds` | DERIVED | same | UNAVAILABLE |
| `alignment_status` | str | — | snap status | OBSERVED | same | `UNALIGNED` |

---

## Game state (level)

Team YES: `team_side=home` → team=`home_score`, opponent=`away_score`. Away reversed.

| Field | Type | Unit | Source | Kind | PIT | Missing |
|-------|------|------|--------|------|-----|---------|
| `team_points` | int | points e0 | PBP score | OBSERVED | I(t)+snap | UNAVAILABLE (not 0) |
| `opponent_points` | int | points e0 | PBP score | OBSERVED | same | UNAVAILABLE |
| `total_points` | int | points e0 | team+opponent at same snap | DERIVED | same | UNAVAILABLE if either missing |
| `point_differential` | int | points e0 | team−opponent | DERIVED | same | UNAVAILABLE |
| `point_differential_abs_e0` | int | points e0 | abs(diff) | DERIVED | same | UNAVAILABLE |
| `point_differential_sign` | int | −1/0/+1 | sign(diff) | DERIVED | same | UNAVAILABLE |
| `score_status` | str | — | — | — | — | `OBSERVED` / `UNAVAILABLE` / `UNALIGNED` |

Do not fabricate 0–0. Do not use `games.final_*` for entry state.

---

## Score path

Scoring **increments** = PBP events that change team or opponent score. Not every PBP row. No interpolation.

| Field | Type | Unit | Source | Kind | PIT | Missing |
|-------|------|------|--------|------|-----|---------|
| `score_path_team` | list[int] | e0 | scores after each increment ≤ t | OBSERVED | I(t) events only | `[]` + UNAVAILABLE path status |
| `score_path_opponent` | list[int] | e0 | same | OBSERVED | same | same |
| `score_change_from_start` | int | e0 | last team − first team (0 if empty) | DERIVED | same | UNAVAILABLE if no path |
| `opponent_score_change_from_start` | int | e0 | same opponent | DERIVED | same | UNAVAILABLE |
| `total_score_change_from_start` | int | e0 | sum of changes | DERIVED | same | UNAVAILABLE |
| `differential_change_from_start` | int | e0 | last diff − first diff | DERIVED | same | UNAVAILABLE |

`0→10→20` and `0→5→20` must remain distinguishable via the path lists.

---

## SCORE_PATH_VOLATILITY_V1

| Item | Definition |
|------|------------|
| Variable | scoring increments (Δscore on events that change score) |
| Basis | I(t)-visible PBP through entry, not every event |
| Estimator | sample standard deviation, **ddof = 1** |
| Minimum | **3 increments** |
| Missing | `UNAVAILABLE` — never 0 |
| Version | `1.0.0` / `SCORE_PATH_VOLATILITY_V1` |

Fields (each Optional[float], plus `*_status`):

- `team_score_volatility`
- `opponent_score_volatility`
- `total_score_volatility` (increments of total points)
- `differential_volatility` (increments of team−opponent)

`points_scored` volatility aliases the same estimators (`team_points_volatility` = `team_score_volatility`). They are not substituted for market volatility.

---

## Market state (level)

| Field | Type | Unit | Source | Kind | PIT | Missing |
|-------|------|------|--------|------|-----|---------|
| `entry_price_e4` | int | E4 | tradable `yes_bid_close` | OBSERVED | bar at t | drop (no observation) |
| `entry_price_cents` | int | cents | `e4 // 100` | DERIVED | same | — |
| `entry_price_ts` | UTC ISO | — | bar ts | OBSERVED | is t | — |
| `entry_price_source` | str | — | `kalshi_candles` | OBSERVED | — | — |
| `entry_price_definition` | str | — | `tradable_yes_bid_close` | — | — | — |
| `market_status` | str | — | — | — | — | `OBSERVED` |

Not a probability. Not a fill. Not midpoint unless a later contract says so.

---

## Market path (to entry, inclusive)

`K_0` = first **tradable** `yes_bid_close` of that ticker. Series = tradable bars with `ts <= observation_ts`.

| Field | Type | Unit | Kind | Definition |
|-------|------|------|------|------------|
| `initial_market_price_e4` | int | E4 | OBSERVED | K_0 |
| `signed_price_displacement_e4` | int | E4 | DERIVED | K_t − K_0 |
| `absolute_price_displacement_e4` | int | E4 | DERIVED | \|K_t − K_0\| |
| `cumulative_price_travel_e4` | int | E4 | DERIVED | Σ \|K_j − K_{j−1}\| |
| `max_price_pre_entry_e4` | int | E4 | OBSERVED | max(K) through entry |
| `min_price_pre_entry_e4` | int | E4 | OBSERVED | min(K) through entry |
| `price_path_range_e4` | int | E4 | DERIVED | max − min |

Fixture: `50→60→50` → displacement `0`, travel `20`. These names are not interchangeable.

Optional crossing counts (`n_up_crossings`, `n_down_crossings`) are not required in v1 schema.

---

## MARKET_PRICE_VOLATILITY_V1

| Item | Definition |
|------|------------|
| Variable | first differences of tradable `yes_bid_close` (E4) |
| Window (cumulative) | ticker start through entry inclusive |
| Estimator | sample stdev, **ddof = 1** |
| Minimum | **3 bars** (2 differences) |
| Missing | `UNAVAILABLE` — never 0 |
| `recent_entry_price_volatility` | last **5** differences; requires **≥ 3** differences else UNAVAILABLE |

Stored as float of E4-difference units, or null + `UNAVAILABLE`. Not money equality. Not a fill.

---

## Exit fields (query-time; not baked into the warehouse)

Exit books are parameters. Observation rows do not store a single WIN 90 / LOSS 40 outcome.

When a book is evaluated:

| Field | Meaning |
|-------|---------|
| `win_exit_type` / `loss_exit_type` | path op or `HOLD_EXPIRATION` |
| `win_exit_ts` / `loss_exit_ts` | first later bar that completes that book |
| `win_exit_price_e4` / `loss_exit_price_e4` | that bar’s `yes_bid_close` |
| `exit_outcome` | `WIN` / `LOSS` / `AMBIGUOUS` / null |
| `exit_ts` / `exit_price_e4` | first-exit bar |
| `exclusion_reason` | `TIE_EXACT_TIMESTAMP` or empty |

`exit_ts > entry_ts` always. Exact timestamp tie → `AMBIGUOUS`, excluded from mutually exclusive first-exit denominators.

Invalid WIN below entry or LOSS above entry → `INVALID_SEMANTICS` (compile-time / call-time). Not flipped.

Game-clock legs require PBP snap. Missing PBP → do not evaluate Reach-only as the full book (`DATA_REQUIRED`).

---

## Terminal (post-entry)

| Field | Type | Source | Kind | Missing |
|-------|------|--------|------|---------|
| `terminal_outcome` | YES / NO / MISSING | `settled_yes` on `kalshi_markets` | OBSERVED | `TERMINAL_MISSING` |

Reuse `roller.research.first80.settled_yes` (import only). Do not infer from box score, PBP, last candle, or `games.home_win`. Current NBA `kalshi_markets.csv` is absent → all missing.

---

## Provenance / quality

| Field | Meaning |
|-------|---------|
| `feature_status` | worst of score/market/alignment for entry-state completeness |
| `source_dataset` | `kalshi_candles` + `pbp` |
| `source_version` | warehouse fingerprint |
| `semantics_version` | `1.0.0` |
| `schema_version` | `1.0.0` |
| `code_version` | `base_te_v1.0.0` |

---

## Path store

Per ticker, compact series (not one hardcoded book):

`ts`, `yes_bid_close`, `available_at`, `game_id`, optional snapped scores.

Supports later WIN 85/LOSS 60, WIN 90/LOSS 40, … without rescanning monthly CSVs.

---

## Manifest

`schema_version`, `semantics_version`, `code_version`, `dataset_version`, `git_sha`, `build_timestamp_utc`, `league`, `season`, `source_paths`, `source_checksums`, counts, `coverage_start`, `coverage_end`.

Mismatch / corrupt → `DATA_REQUIRED`.

---

## Failure states

| Situation | Status |
|-----------|--------|
| Missing candles/PBP warehouse | `DATA_REQUIRED` |
| No I(t) PBP at t | `UNALIGNED` / `UNAVAILABLE` |
| Vol n too small | `UNAVAILABLE` |
| No Kalshi result | `TERMINAL_MISSING` |
| Exact WIN/LOSS ts | `AMBIGUOUS` |
| Bad WIN/LOSS side | `INVALID_SEMANTICS` |
| Game clock, no PBP | `DATA_REQUIRED` |
| Stale derived tree | `DATA_REQUIRED` |

Never convert missing → 0 / false / NO / empty population.

---

## Future market types

Spread, O/U, team total, Polymarket TOB, L2, ticks: **DATA_REQUIRED**. Same architecture when ingested. Not fabricated in 1.0.0.
