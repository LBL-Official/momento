# 2026-09-04 — FIRST80 research day summary

Research only. **Live trading, FIRST01, Risk, and Execution were not changed.**

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY
LIVE DEPLOYMENT: NOT AUTHORIZED
```

Dynamic Risk Engine (DRE) work was set aside and is not part of this day.

Two research tracks ran on 2026-09-04:

1. **NBA FIRST80 alpha decomposition** — is the historical First80 result mostly terminal calibration, or an independent path-survival effect?
2. **WNBA FIRST80 80→40** — same observational rule on Kalshi `KXWNBAGAME`, after pulling historic 1-minute candles.

---

## Frozen FIRST80 identity (not redefined)

Canonical source: `apps/nba-data/scripts/nba_80_40_execution_audit.py`.

- **FIRST80** = first tradable `yes_bid_close ≥ 80¢` after a prior tradable close `< 80¢`, two-sided uncrossed spread `≤ 10¢`, one per event. Same-minute ties excluded.
- **T40 (primary)** = later tradable `yes_bid_close ≤ 40¢` (`stop_close_triggered`). Wick (`yes_bid_low`) is secondary.
- **W** = official expiration / `result` on that ticker.
- Gross candle economics used for the path study: **+20¢** if W and never T40; **−40¢** if T40 (assumed 40¢ exit, not a fill).

NBA frozen audit counts (unchanged): 1,362 games; 1,230 settled FIRST80; 1,019 wins (82.85%); WIN∧¬T40 = 910; WIN∧T40 = 109; LOSS∧¬T40 = 0; LOSS∧T40 = 211; T40 = 320.

---

## 1. NBA — FIRST80 alpha decomposition v1

**Question:** is the ~83% First80 win rate an 80¢-specific path effect, or mostly terminal miscalibration vs 80%?

**Classification (locked rule):** `A_TERMINAL_CALIBRATION_ONLY`

Independent path-survival required an **OOS interval on FIRST80 − FIRST75 that excludes 0**. A raw ~4pp gap with a CI that includes 0 is not path evidence. That interval included 0.

### Terminal calibration

| Sample | P(W \| FIRST80) | vs 80% |
|---|---:|---|
| FULL | 1,019 / 1,230 = **82.85%**, Wilson [80.64%, 84.85%] | one-sided p = 0.0062 |
| TRAIN | **80.75%** | p = 0.36 — does **not** reject 80% |
| OOS | **86.01%** (n = 243) | p = 0.0097 |

FirstReach(q) − q is a **broad ~2–3pp positive bias** across 70–95¢, not a unique 80¢ spike.

### Path survival (among winners)

- P(¬T40 \| W, FIRST80) = 910 / 1,019 = **89.30%**
- FIRST75 winners: 781 / 915 = **85.36%**
- OOS difference **+3.97pp**, approx 95% **[−2.89pp, +10.83pp] includes 0**
- NON_FIRST80 winners 94.79% are comeback-selected, not a FIRST80 control
- Matched OOS adequate strata = 4 (too thin)

### Joint / hedge / persistence

- Joint P(W ∩ ¬T40) = 910 / 1,230 = **73.98%** = 0.8285 × 0.8930
- If P(W) were 80% and path held: **71.44%** (sensitivity only)
- LOSS ∧ ¬T40 = 0 on minute closes (phi ≈ 0.767; odds ratio undefined)
- Opponent `yes_bid_close ≤ 20¢` at FIRST80 ≈ **98.5%**, median delay **1 minute** — complementarity at the FIRST80 candle, not a later hedge lock-in. Not fills.
- Walk-forward α̂ = F̂ − K (TRAIN buckets only): OOS ≈ **−0.0062**. F is not observed.

**Useful claim from this day:** the historical 74% “survive to settlement without a 40 close” number is mostly `0.80 × P(¬T40|W)` plus a small terminal-calibration bump. It is **not** established as an independent First80 path edge.

### What was created (NBA)

| Path | Role |
|---|---|
| `research/first80_alpha_decomposition_v1/` | Experiment code, locks, results, figures |
| `research/first80_alpha_decomposition_v1/FINAL_RESEARCH_REPORT.md` | Canonical write-up |
| `docs/research/first80_alpha_decomposition_v1/` | Docs copy of reports |
| `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/first80_alpha_decomposition_v1/` | Warehouse copy of run manifest |

Regenerate reports without a candle rescan:

```bash
/tmp/momento-first80-decomp/bin/python research/first80_alpha_decomposition_v1/src/run_experiment.py --from-artifacts
```

---

## 2. WNBA — data, then 80→40 backtest

### What we learned about the data first

- `Backtesting Suite/Data/WNBA` **manifests are a DEMO FIXTURE** (Sheets e2e). They are not real games and were not used as candles.
- `Backtesting Suite/Data-Real/WNBA/2025-2026/` is a collector lake: RestCandlestick **close only**, no bid high/low, no candle volume. Usable coverage was only **2026-06-18 … 2026-06-30** (~33 settled games). All 2025 dates and most early-June 2026 dates had 0 candle rows.
- Kalshi historical ingest had been blocked on this laptop earlier; on 2026-09-04 `https://external-api.kalshi.com` answered.

### What we built to ingest Kalshi

| Piece | Purpose |
|---|---|
| `crates/research-data` WNBA identity | Parse `KXWNBAGAME-` date tokens; folder `2025-2026` holds **both** 2025 and 2026 campaigns; do not reuse NBA October preseason rules |
| `WarehouseConfig::wnba_season_2025_26()` | Series `KXWNBAGAME` |
| Event synthesis from markets | `/events` can be truncated vs historical markets |
| `apps/wnba-data` (`wnba-data` CLI) | `discover` / `download-all` / `validate` |
| Candle window split | Live candlestick API rejects windows that would return **>5,000** bars; split before request (needed after Kalshi cutoff **2026-07-06**) |
| `crates/research-data/tests/wnba_warehouse.rs` | No live HTTP |

Ingest (resumable):

```bash
cargo run -p momento-wnba-data --release -- download-all \
  --data-dir "Backtesting Suite/Data" --max-workers 1 --rps 1.5
```

### Kalshi warehouse that actually landed

| | |
|---|---|
| Path | `Backtesting Suite/Data/WNBA/2025-2026/warehouse/` |
| Games / markets | **612 / 1,224** (all finalized; 298 events in 2025, 314 in 2026) |
| Candles | **1,443,201** one-minute yes-bid **OHLC** |
| Trades | **6,730,186** |
| Span | **2025-05-22 → 2026-08-31** |
| Markets with candles + trades | **1,224 / 1,224** after retry |
| Open Sep 2026 markets at ingest | **0** |
| Historical L2 | **Unavailable** (not invented) |
| First-pass failures | 29 tickers (HTTP 429 and/or >5,000-bar windows); all recovered on retry |

Coverage ratio ~0.40 is expected minutes in the Kalshi open→close window vs published 1-minute bars, not 29 missing markets.

An intermediate **June-only** collector scan (n = 32 FIRST80, 71.9% hold-unless-stop, CI including 66.67%) was a coverage-limited preview. **Do not treat that slice as the WNBA result.** The warehouse numbers below replace it.

### WNBA FIRST80 80→40 (full Kalshi catalog)

Same imported rule. Game window = Kalshi market open/close. Volume gate = NBA `quality()` (volume or prior tradable bar). Wick-stop is independent because bid high/low exist.

| | N |
|---|---:|
| Games | 612 |
| FIRST80 settled | 589 |
| WIN ∧ ¬T40 | 436 |
| WIN ∧ T40 | 56 |
| LOSS ∧ ¬T40 | 0 |
| LOSS ∧ T40 | 97 |
| T40 close | 153 |
| No tradable 80 | 23 |

- P(W \| FIRST80) = **492 / 589 = 83.53%**
- Hold unless close-stop = **436 / 589 = 74.02%** (Wilson **70.3–77.4%**)
- Assumed +1R / −2R candle EV = **+0.22 R / trade** (breakeven 66.67%)
- That Wilson interval is **above** 66.67% on this sample. It is still not a fill and not a live authorization.

Locked splits (not retuned after PnL):

| Split | n | Win rate | EV R |
|---|---:|---:|---:|
| IN_SAMPLE (`≤ 2025-10-31`) | 284 | 73.24% | 0.20 |
| VALIDATION (through 2026-07-15) | 187 | 73.26% | 0.20 |
| OOS (after 2026-07-15) | 118 | 77.12% | 0.31 |

Execution-realism (still not fills):

| Model | n | Win rate | EV R |
|---|---:|---:|---:|
| Close-stop, all FIRST80 | 589 | 74.02% | +0.22 |
| Require last-print through 80 | 392 | 75.26% | +0.26 |
| HIGH + close-stop | 333 | 73.27% | +0.20 |
| HIGH + wick-stop | 333 | 65.77% | **−0.03** |
| All fills + wick-stop | 589 | 63.67% | **−0.09** |

Wick-stop turns the path **negative**. Close-stop and wick-stop are not the same object on this warehouse.

LOSS ∧ ¬T40 = 0 again (same minute-close measurement gap as NBA).

### What was created (WNBA)

| Path | Role |
|---|---|
| `apps/wnba-data/` | Kalshi warehouse CLI |
| `apps/wnba-data/scripts/wnba_80_40_execution_audit.py` | Observational 80→40 audit |
| `apps/wnba-data/scripts/wnba_collector_quotes.py` | Data-Real close-only loader (June fallback) |
| `research/wnba_first80_80_40_v1/` | REPORT, summary, ledgers, candidates, tests |
| `docs/research/wnba_first80_80_40_v1/` | Docs copy |
| `…/warehouse/derived/wnba/first80_execution_audit/` | Warehouse copy of the same artifacts |

```bash
/tmp/momento-first80-decomp/bin/python apps/wnba-data/scripts/wnba_80_40_execution_audit.py
```

---

## What this day does **not** authorize

- No live order, no paper-to-live promotion, no FIRST01 / 80/81/83/89 change.
- No production WNBA strategy.
- No claim that a maker 80 or a taker 40 would have filled at the candle print.
- No L2, queue, or production fee model. `KXWNBAGAME` is documented quadratic / M=1; live `fee_type` is taker-quadratic, not a proven maker rebate.
- NBA path-survival is **not** an independent edge under the locked OOS-CI rule.
- WNBA +0.22 R is **assumed candle economics** on settled Kalshi games through 2026-08-31 only.

---

## One-line takeaways

1. **NBA:** First80 looks like **terminal calibration (broad yes-bid bias)**, not a proven independent 80→40 path effect. Letter **A**.
2. **WNBA:** Kalshi historic 1-minute books for **612** settled games now live in the warehouse. Observational 80→40 close-stop is **74%** (n = 589); **wick-stop is not profitable** on the same sample.
3. **Live deployment remains not authorized.**
