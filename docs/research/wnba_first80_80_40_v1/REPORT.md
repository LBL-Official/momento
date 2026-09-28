# WNBA FIRST80 80→40 — observational backtest

Research only. Does not change live trading. Does not invent L2.

Same FIRST80 / close-40 rule as `apps/nba-data/scripts/nba_80_40_execution_audit.py`
on Kalshi `KXWNBAGAME`. Definition is imported, not rewritten.

Kalshi KXWNBAGAME warehouse: 612 games / 1224 markets with 1-minute yes_bid OHLC + trades. Earliest candle 2025-05-22; latest 2026-08-31. Historical cutoff 2026-07-06; later settled games used the live candlestick endpoint with window splits. Historical L2 unavailable.

Collector demo manifests under `Backtesting Suite/Data/WNBA/manifests` were not used as candles.

**Candle path ≠ fill. Historical stop quotes ≠ executable profit.**

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
```

---

## 0. Coverage

- Source: `Kalshi historical+live 1-minute candlesticks (warehouse)`
- Games: **612**
- Tickers: **1224**
- Candle span: 2025-05-22 .. 2026-08-31
- Volume gate: **NBA_quality_volume_or_prior**
- Bid OHLC high/low: **available** — wick-stop is independent of close-stop

Kalshi `historical/cutoff` at ingest: market_settled_ts 2026-07-06. Earlier games used `/historical/markets/{ticker}/candlesticks`. Later settled games used the live candlestick endpoint with ≤5000-bar splits. Open September 2026 markets: 0 at ingest time. Historical L2 is unavailable.

## 1. Observed FIRST-80 / close-40 path

| | N |
|---|---:|
| Games | 612 |
| First tradable 80 cross (settled) | 589 |
| WIN ∧ ¬T40 | 436 |
| WIN ∧ T40 | 56 |
| LOSS ∧ ¬T40 | 0 |
| LOSS ∧ T40 | 97 |
| Later `yes_bid_close ≤ 40¢` | 153 |
| No tradable 80 | 23 |
| Same-minute FIRST80 tie | 0 |

Strategy win rate (hold unless close-stop): **74.0238%**  
95% Wilson CI: **70.3348% – 77.4014%** (n = 589)

| Quantity | Estimate |
|---|---:|
| P(Kalshi yes \| first 80) | 83.5314% |
| P(WIN ∧ ¬T40 \| first 80) | 74.0238% |
| Gross EV / trade (+1R/−2R) | 0.2207 R |
| +1R/−2R breakeven | 66.67% |

Gross: +20¢ if win and never close-stop; −40¢ if close-stop (assumed 40¢ exit, not a fill); 0 if LOSS_NO_STOP (measurement gap on minute closes).

## 2. Execution-realism models

HIGH/MEDIUM confidence uses last-print through 80 on the crossing candle. Wick-stop uses yes_bid_low. These are not fills.

| Model | Trades | Win rate | Gross EV R |
|---|---:|---:|---:|
| original (close-stop, all fills) | 589 | 74.0238% | 0.2207 |
| require last-print through 80 | 392 | 75.2551% | 0.2577 |
| HIGH + wick-stop | 333 | 65.7658% | -0.027 |
| HIGH + close-stop | 333 | 73.2733% | 0.1982 |
| all fills + wick-stop | 589 | 63.6672% | -0.09 |

## 3. Chronological splits (a priori WNBA cuts; not retuned)

IN_SAMPLE `game_date <= 2025-10-31`; VALIDATION through 2026-07-15; OOS after. Cuts were locked before this warehouse run and were not retuned.

- **IN_SAMPLE**: n=284 win=73.2394% CI [67.8054, 78.0531] EV_R=0.1972
- **VALIDATION**: n=187 win=73.262% CI [66.4969, 79.0907] EV_R=0.1979
- **OOS**: n=118 win=77.1186% CI [68.7558, 83.7714] EV_R=0.3136

## 4. What this is not

- Not a live order, fill, or realized P&L.
- Not MLB FIRST01 / 80/81/83/89.
- Not a production WNBA strategy.
- Not proof of a tradable inefficiency.
- Fees are a labeled published-schedule estimate. `KXWNBAGAME` is documented as quadratic / M=1; live `fee_type` is taker-quadratic, not a proven maker rebate.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

