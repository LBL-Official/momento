# e

Research only. **LIVE EXECUTION CHANGED: FALSE.**

Written before A1 engine code. Does not change FIRST01, Risk, or Execution.

---

## WHERE IS THE FIRST80 UNIVERSE?


| Sport                  | Path                                                                                                 | Frozen n |
| ---------------------- | ---------------------------------------------------------------------------------------------------- | -------- |
| NBA                    | `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/first80_execution_audit/candidates.json` | 1,230    |
| NCAAB (warehouse)      | `.../NCAAB/.../derived/ncaab/first80_execution_audit/candidates.json`                                | 4,099    |
| **NCAAB working (A1)** | same candidates ∩ P5 vs P5 on `ncaab_games.parquet`                                                  | **721**  |


V4 ledger (hold / 80→40 / V1 hedge P&L):  
`.../derived/{nba,ncaab}/first80_opponent_hedge_optimal_v4/trade_ledger.parquet`

V3 per-H opportunity (H=10..60):  
`.../derived/{nba,ncaab}/first80_opponent_hedge_execution_model_v3/opportunity_dataset.parquet`

---



## WHAT EXACTLY DEFINES A FIRST80 EVENT?

`apps/nba-data/scripts/nba_80_40_execution_audit.py` (NCAAB clones this):

```text
FIRST-80 ⇔ first tradable 1-minute bar in the game-day window
  with yes_bid_close ≥ 80¢
  after a prior tradable yes_bid_close < 80¢
```

Tradable: `is_valid`, bid≤ask, spread ≤ 10¢, volume or quality latch,  
`end_period_ts ∈ [game_window_start, min(close_ts, game_window_end)]`.

Nominal book entry = **80¢**. Candle close may be 81. Maker fill at 80 is **unobserved**.

---



## HOW ARE A1 AND A2 IDENTIFIED?

A1 = `ticker` on the FIRST-80 candidate (favorite YES).  
A2 = other YES on the same `event_id`:

```text
home_market_ticker / away_market_ticker
or market_tickers list
```

`first80_opponent_40_hedge_v1.opponent_of`. Missing opponent = 0 in frozen V1
(`missing_opponent = 0`).

Do not infer the pair from prices.

---



## WHAT PRICE FIELDS ARE AVAILABLE?

1-minute candles (`candles_1m/{ticker}.parquet`), e4 integer cents:

- `yes_bid_{open,high,low,close}_e4`
- `yes_ask_{open,high,low,close}_e4`
- `price_{open,high,low,close}_e4` (last trade)
- `volume_hundredths`, `is_valid`

No L2, no queue, no historical maker-fill flag. Mid is not a first-class field.

---



## WHAT IS THE TIME RESOLUTION?

One minute (`end_period_ts`). Same-candle A1 entry vs A2 hedge is ambiguous.  
V2/V3 already use **strict next-bar**: opponent quotes with `t <= first_80_timestamp`
are dropped (`t <= ts0` excluded). A1 default = that conservative convention.

---



## HOW IS 80 → 40 BACKTESTED?

```text
stop_close_triggered ⇔ later tradable A1 yes_bid_close ≤ 40¢
pnl = −40 if stopped, else +20 if won, else 0 (leak)
```

This is **Model A** (fill at exactly 40). Liquidation V1 also has Model B
(stop-minute close) and C (stop-minute low). Model A EV: NBA +4.3902,  
full NCAAB +3.9034, P5 +4.3551. Zero-EV fill ~23¢ NBA / ~25¢ NCAAB.

---



## WHAT EXISTING EXECUTION-AUDIT CODE EXISTS?


| Program                           | What it is                                    |
| --------------------------------- | --------------------------------------------- |
| V1 `first80_opponent_40_hedge_v1` | A2 close≥40 ⇒ lock −20 (fictional fill)       |
| V2 `..._frontier_v2`              | H=20..60 surface, VAL H* NBA 28 / NCAAB 20    |
| V3 `..._execution_model_v3`       | A/B/C/E/D classes, p_fill **scenarios**       |
| V4 `..._optimal_v4`               | HYBRID / REPLACE / ORACLE vs 80→40            |
| V5 `..._causal_timeline_audit_v5` | Wait persist, pay T2 bid — **loses** to 80→40 |
| Liquidation V1                    | 40 is a trigger                               |
| Entry quality V1                  | jump-through on the **80** entry              |
| `first80_hybrid_modfill_h37_42`   | A/B⇒−20 else 80→40 (lookahead persist)        |


A1 must **not** treat V1/V4 lock-at-H as executable EV.

---



## WHAT DATA LIMITATIONS EXIST?

- No historical L2 / actual maker fills (`ACTUAL_FILL = UNOBSERVED`).
- Fees not in warehouse config (gross ¢ only).
- 1-minute bars cannot prove a print inside a gap (23→75).
- Full NCAAB 4,099 is mid-major heavy; **A1 NCAAB = P5 vs P5 only**.
- NCAAB OOS n is small on full warehouse (84); P5 OOS is smaller still.
- Live FIRST01 cannot book A2 (one market per game).
- Post-only A2@40 rejects while ask ~21.

---



## SPLITS (reuse, do not invent)

```text
TRAIN      game_date ≤ 2025-12-31
VALIDATION game_date ≤ 2026-03-15
OOS        after
```

---



## REUSE DECISION

A1 loads frozen V3 opportunity rows + V4 ledger. It does not rescan raw
candles. Band occupancy uses the **first close ≥ band_lo** and the
**observed close** on that bar (not H). Persist comes from V3
`persist_subsequent_min` (bars still ≥ band_lo — not a perfect in-band
clock; labeled).

---



## UNIVERSE_VERSION (frozen for A1)

```text
A1_UNIVERSE_V1
  NBA_FIRST80_2025_2026_N1230
  NCAAB_P5VP5_2025_2026_N721
```

