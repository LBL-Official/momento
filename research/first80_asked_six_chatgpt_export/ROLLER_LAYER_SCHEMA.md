# Asked-six FIRST80 → ROLLER layers

The frozen ledger is **untouched**. This document is the KEEP / REMOVE / ADD
schema. It does not retune splits, FIRST80, or live 80/81/83/89.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
FIRST80 STAYS OFF O_t
LEDGER = L_{τ→} BENCHMARK
DO NOT FABRICATE POSSESSION / FOULS / TIMEOUTS / TRADE COUNTS
```

The 1,182-row CSV is the **outcome / ledger layer** at one timestamp
(the FIRST80 trigger). It is not the state layer. Do not widen it into a
giant point-in-time table.

ROLLER already has the three-layer split ChatGPT described. Do not build a
second prediction database beside it.

```
GAME  (identity)
  ├── FUNDAMENTAL / PREGAME     F_t + pre-tip market   db.fundamental()
  ├── POINT-IN-TIME GAME STATE  G_t                    db.game_state() / clock_snap()
  └── POINT-IN-TIME MARKET STATE M_{≤t}                observation MARKET_STATE
          │
          ▼
      OBSERVATION O_t          assemble_observation()
                               NO first80 / T40 / W / P&L
          │
          ▼
      FUTURE PATH / OUTCOME    L_{t→}                  db.labels()
                               frozen asked-six CSV    (this file)
                               db.first80()            off O_t
```

`P(W | I_t)` is estimated from `O_t` only.

`P(W | I_t, FIRST80)` and `P(T40 < T | I_t, FIRST80)` condition on a
**selection label**. That is the ledger join, not a new feature inside `O_t`.

---

## Constitutional map

| Layer | ROLLER object | May contain FIRST80 / T40 / W / hyp_pnl? |
|---|---|---|
| Identity | `internal_game_id`, games | No |
| `F_t` | `db.fundamental()` | No. Prior-only empirical home-win rate. Not a pregame model. Not edge. |
| `G_t` | `GAME_STATE`, `clock_snap` | No |
| `M_t` | `MARKET_STATE` (E4 candles) | No |
| `O_t` | `db.observation()` | **No. Hard rule.** |
| `L_{t→}` | `db.labels()`, this CSV, `db.first80()` | Yes |

`as_of` is always `available_at < t`. Candle `available_at` is the minute
**close**. The FIRST80 observation cutoff is the trigger candle close, not
the printed last-trade time.

---

## Frozen ledger — KEEP / REMOVE / ADD

**REMOVE** means: do not copy into `O_t` / do not treat as a state feature.
The column **stays on the frozen CSV**.

**ADD** means: exist on a *new* observation-side object, or already exist in
ROLLER. Do not add them onto `first80_asked_six.csv`.

### KEEP on the ledger (outcome benchmark)

These are `L_{τ→}` plus the join keys that identify τ.

| Column | Role |
|---|---|
| `sport`, `slice`, `slice_label` | Population membership (asked-six). Label, not a feature to retune. |
| `game_id`, `event_id`, `ticker` | Join keys. ROLLER also has `internal_game_id`. |
| `game_date`, `calendar_month`, `dataset_split`, `season_phase` | Frozen splits. Do not retune. |
| `timestamp`, `timestamp_utc` | τ = FIRST80 trigger (candle close). |
| `bought_team`, `side`, `opponent_team` | Which YES contract was selected. |
| `W` | Kalshi expiration on that ticker. |
| `T40`, `T40_wick` | Close-path vs wick. Wick is not an exit. |
| `would_have_exited_at_40`, `held_to_expiration` | Same fact as T40 / ¬T40. |
| `exit_kind`, `exit_price_cents`, `exit_timestamp`, `exit_timestamp_utc` | Where the 80/40 rule got out, including never-T40 → settlement. |
| `exit_period`, `exit_game_clock`, `exit_score_home`, `exit_score_away` | State **at exit**, which is future of τ. |
| `post_entry_min_yes_bid_cents`, `post_entry_min_yes_bid_timestamp` | Future path diagnostic. |
| `last_tradable_yes_bid_cents`, `last_tradable_timestamp` | Future path diagnostic. |
| `final_winner`, `final_score`, `final_score_home`, `final_score_away` | Terminal. Future of τ. |
| `outcome_80_40`, `hyp_pnl_cents_80_40` | Gross candle 80/40 / hold. Zero fee. Not a fill. |
| `candle_path_not_fill`, `live_execution` | Provenance locks. |

### REMOVE from `O_t` (keep on ledger only)

| Column | Why it cannot enter the information set |
|---|---|
| `W`, `final_*` | Future. |
| `T40`, `T40_wick`, all `exit_*`, `held_to_expiration`, `would_have_exited_at_40` | Future path. |
| `post_entry_*`, `last_tradable_*` | After τ. |
| `outcome_80_40`, `hyp_pnl_cents_80_40` | Constructed from future + assumed 40 fill. |
| `first80_rule_implied_prob` | Always 0.80. Rule constant, not a measured state. |
| `slice`, `slice_label` | Derived from clock at τ **and** used to *select* the book. Membership is a label. Clock itself belongs in `G_t`. |
| `possession_team`, `possession_id` | Empty. Status `UNAVAILABLE`. Do not backfill. |
| `home_fouls`, `away_fouls`, `home_timeouts`, `away_timeouts` | Empty. Status `UNAVAILABLE` at entry. |
| `market_trades` | Empty. `trade_count_available=false`. |

### KEEP as *copies of* `O_τ` (re-assemble from warehouse, do not trust the flatten)

These CSV columns are a snapshot of state **at τ**. For the prediction
database, re-assemble them through `db.observation(gid, as_of=τ)` so
`available_at` is enforced. The CSV values are a convenience check, not
the source of truth.

| Column | ROLLER home |
|---|---|
| `period`, `game_clock`, `period_remaining_s`, `game_seconds_remaining`, `entry_phase` | `GAME_STATE` / `clock_snap` |
| `alignment_confidence` | Clock-snap quality, not a feature to optimize |
| `home_team`, `away_team`, `*_code` | Game identity |
| `score_home`, `score_away`, `score_diff`, `bought_team_margin` | `GAME_STATE.score` |
| `event_type`, `event_description` | Latest PBP ≤ τ |
| `market_yes_bid`, `market_yes_ask`, `market_last_price` | `MARKET_STATE` (last is candle `price_close`, not a fill) |
| `market_volume` | **Entry-candle volume only**, not cumulative. Re-derive if needed. |
| `entry_implied_prob` | `yes_bid / 100` at τ |
| `pregame_home_win_prob`, `pregame_away_win_prob` | Not `F_t`. Kalshi last **pre-tip** yes bid. 140 / 1182 missing. |

### ADD on a new observation-side object (not on this CSV)

| Field | Status now | Notes |
|---|---|---|
| `internal_game_id` | ADD (ROLLER identity) | `{SPORT}_{YYYYMMDD}_{AWAY}_{HOME}` |
| `observation_id` | ADD | `assemble_observation` id at cutoff = τ |
| `available_at` / `observation_time` | ADD | Candle close. Half-open I(t). |
| `F_t` (`db.fundamental()`) | ADD via API | Empirical `P(home wins \| period, clock bucket, margin bucket)` from **other** settled games. `F_t ≠ K_t ≠ EDGE`. |
| `team_features` / D2D | ADD via API | Prior-only team strength. Already in ROLLER `TEAM_STATE`. |
| `yes_bid_e4`, `yes_ask_e4`, `spread_e4` | ADD (integer E4) | Prefer E4 over float cents for money-adjacent fields. |
| `n_pbp_available`, `n_candles_available` | ADD | Observability, not alpha. |
| `possession_team` at τ | **DO NOT ADD** until a validated contract | NBA: reconstructed possessions exist (`capability=REAL`) but `possession_delta` is **not authorized**. NCAAB/WNBA: `PARTIAL`. CSV was correct to leave blank. |
| `shot_clock` | **DO NOT ADD** | Not in stored PBP. |
| `home_fouls` / `away_fouls` / `timeouts_remaining` at τ | **DO NOT ADD** | Not in stored action stream. NBA box timeouts are **end of game**. |
| `trade_count` | **DO NOT ADD** | Warehouse flag is false. Prints exist as `kalshi_trades` (not fills) and can be counted later under I(t) if a contract is written. |
| `pregame_model_probability` | **DO NOT ADD a fake model** | Pre-tip Kalshi bid is market, not a model. `F_t` is in-game empirical, not pregame. |
| `future_market_path` | ADD only under `L_{t→}` | Minute path after τ. Never in `O_t`. |
| `T40_timestamp` / `T40_flag` | Already on ledger + `db.labels()` | Stay on `L`. |

---

## ChatGPT wishlist vs warehouse truth

| Requested | Verdict |
|---|---|
| `game_id`, `timestamp`, `period`, `game_clock` | Observed at τ. Re-assemble in `G_t`. |
| `home_score`, `away_score`, `score_diff` | Observed at τ (1182 / 1182 on the ledger check). |
| `home_away` | Observed (`side`). |
| `yes_bid`, `yes_ask`, `last_trade`, `spread` | Bid/ask observed. Last = candle last. Spread = ask−bid. Not L2. |
| `volume` | Entry candle only. |
| `future_winner`, `future_score` | Ledger `L`. |
| `T40_timestamp`, `T40_flag` | Ledger `L`. Close-path. |
| `future_market_path` | Not on this CSV except min-bid / last-bid after entry. Build as a label series. |
| `pregame_model_probability` | **Unavailable as a model.** Pre-tip Kalshi bid on 1042 / 1182. |
| `team_strength_features` | Not on this CSV. Use ROLLER `team_features` / D2D under I(t). |
| `possession_team` | **Unavailable as an observed field on this ledger.** Do not infer from last shooter. |
| `shot_clock` | Unavailable. |
| `home_fouls`, `away_fouls`, `timeouts_remaining` | Unavailable at τ. |
| `trade_count` | Unavailable. |

---

## What to build next (not a rewrite)

One join, two objects:

```
frozen first80_asked_six.csv          # L_{τ→}  DO NOT EDIT
        │  keys: sport, event_id, ticker, timestamp
        ▼
observation_at_first80                # O_τ     NEW, query-time or derived
        = db.observation(internal_game_id, as_of=τ)
        + pre-tip Kalshi bids (if available_at < tip)
        + F_t (query-time)
```

Invariants:

1. The 1,182-row identity stays 604 / 246 / 332.
2. `dataset_split` cuts stay `≤ 2025-12-31` / `≤ 2026-03-15`.
3. `O_τ` contains no `W`, `T40`, exit, or P&L.
4. Missing possession / fouls / timeouts / trades stay missing.
5. `F_t` never consumes the current game’s result.
6. No live FIRST01 change. No W9. No invented L2.

That is enough to measure, on this frozen population only:

```
P̂(W | O_τ)           vs   historical P(W | FIRST80, asked-six)
P̂(T40 | O_τ)         vs   historical P(T40 | FIRST80, asked-six)
```

Those are **calibration / residual** questions. They are not an entry rule.

---

## Explicitly not next

- Do not reshape `first80_asked_six.csv`.
- Do not hunt a profitable subset.
- Do not authorize `possession_delta`.
- Do not treat `hyp_pnl_cents_80_40` as realized P&L.
- Do not use the same 1,182 rows to fit `O_τ` and to certify the 80/40 book.
  Fit on `IN_SAMPLE`, confirm on `VALIDATION`, leave `OOS` last.
