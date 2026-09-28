# Asked-six FIRST80 ledger (ChatGPT export)

Research only. **Not a fill. Not live. Not a strategy authorization.**

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
POSSESSION / FOULS / TIMEOUTS / TRADE COUNTS = UNAVAILABLE
```

## Universe

Frozen FIRST80, then the published asked-six mid-game windows only:

| Sport | Window | Expected N |
|---|---|---:|
| NBA | 2Q ∪ 3Q | 604 |
| WNBA | 2Q ∪ 3Q | 246 |
| NCAAB P5 vs P5 | 1H second 10 ∪ 2H first 10 | 332 |
| **Total** | | **1182** |

This is **not** 3,000 games. Do not invent extra rows.

**All 1,182 rows use the 80/40 stop rule.** Do not report `W` / `terminal_yes` as the strategy win rate.

| Headline | Column | Count | Rate |
|---|---|---:|---:|
| **80/40 win** | `win_80_40=True` | 883 | **74.70%** |
| 80/40 stop | `stopped_40=True` | 299 | 25.30% |
| Terminal YES (ignore stop) | `W` / `terminal_yes` | 991 | 83.84% |

`W` includes 108 trades that hit the 40 close and later settled YES. Those are **stops**, not 80/40 wins.

FIRST80 = first tradable `yes_bid_close ≥ 80¢` after a prior tradable close `< 80`, uncrossed spread ≤ 10¢, one per event. Same-minute ties excluded.

## Exit when the tape never printed 40

`would_have_exited_at_40` is the close-path T40 (`yes_bid_close ≤ 40` after entry).

| `exit_kind` | meaning | `exit_price_cents` | `hyp_pnl_cents_80_40` |
|---|---|---:|---:|
| `T40_CLOSE` | first later tradable close ≤ 40 | 40 | −40 |
| `SETTLEMENT_YES` | never T40, YES expires | 100 | +20 |
| `SETTLEMENT_NO` | never T40, NO expires | 0 | −80 |

If T40 never printed, use `exit_kind`, `exit_price_cents`, `exit_timestamp`, `exit_period`, `exit_game_clock`, `exit_score_*`, plus `post_entry_min_yes_bid_cents` (closest close-path bid after entry) and `T40_wick` (wick touched 40 even if close did not).

Wick-only 40 is **not** an exit. Close-path is the frozen rule.

## Do not treat these as observed strategy inputs

| Column | Status |
|---|---|
| `possession_team`, `possession_id` | UNAVAILABLE — not invented |
| `home_fouls`, `away_fouls`, `home_timeouts`, `away_timeouts` | UNAVAILABLE at entry |
| `market_trades` | UNAVAILABLE (`trade_count_available=false`) |
| `pregame_*_win_prob` | Kalshi last tradable yes bid **before tip**, not a model. Missing → blank, `pregame_source=UNAVAILABLE` |
| `market_volume` | volume on the **entry candle only**, not cumulative tape |
| `hyp_pnl_cents_80_40` | gross candle-path 80/40 / hold. Zero fee. Not a fill |

`first80_rule_implied_prob` is always 0.80. `entry_implied_prob` is the actual entry bid / 100 (can be > 0.80).

## Splits (frozen, do not retune)

`dataset_split`: IN_SAMPLE `game_date ≤ 2025-12-31`; VALIDATION `≤ 2026-03-15`; else OOS.

NCAAB OOS is small (conference tournament / March). Do not use the full 1,182 rows both to “prove” a win rate and to fit a risk model. Split first.

## What ChatGPT should not do

- Do not treat this as executable edge.
- Do not hunt a profitable subset and promote it.
- Do not assume a 40 exit was fillable.
- Do not fill UNAVAILABLE columns from box-score intuition.
- Do not change live FIRST01 / 80/81/83/89.
- Do not use `W` as the 80/40 win rate.

## Next object (do not reshape this ledger into O_t)

KEEP / REMOVE / ADD for a ROLLER observation layer is in
`ROLLER_LAYER_SCHEMA.md` and `column_layer_map.json`. FIRST80 stays off `O_t`.
