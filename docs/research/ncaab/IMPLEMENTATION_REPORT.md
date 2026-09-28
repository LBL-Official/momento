# NCAAB `KXNCAAMBGAME` warehouse — implementation report

Research-only. Live trading, FIRST01, MLB collector, NBA warehouse data, and W9 were not changed.

Live 2025–2026 digest completed 2026-09-02 on the operator MacBook (Kalshi reachable from work network). `download-all` included candles, trades, normalize, derive, and validate.

## Architecture

```text
EXISTING NBA WAREHOUSE
        ↓
GENERALIZABLE COMPONENTS (http, catalog, ingest, parquet, resume, validate, query)
        ↓
NBA-SPECIFIC (KXNBAGAME prefix, October season, Play-In/Playoffs/Finals)
        ↓
NCAAB-SPECIFIC (KXNCAAMBGAME, college phases, NCAAB paths, ncaab-data CLI)
```

## FILES CREATED

- `apps/ncaab-data/Cargo.toml`
- `apps/ncaab-data/src/main.rs`
- `crates/research-data/tests/ncaab_warehouse.rs`
- `docs/research/ncaab/ARCHITECTURE_ASSESSMENT.md`
- `docs/research/ncaab/IMPLEMENTATION_REPORT.md`
- `docs/research/NCAAB_KXNCAAMBGAME_MARKET_DATA.md`

## FILES MODIFIED

- `Cargo.toml` (workspace member `apps/ncaab-data`)
- `crates/research-data/src/sport.rs`
- `crates/research-data/src/lib.rs`
- `crates/research-data/src/warehouse/{mod,config,types,identity,paths,catalog,ingest,normalize,validate,runner,query}.rs`

NBA CLI and NBA tests were kept. `CollectorConfig::default_sports()` remains MLB + WNBA.

## HOST USED

Operator MacBook, work network, `caffeinate -dimsu`. Not live trading EC2 `i-0f0849d5829476c31`.

## KALSHI REACHABILITY PROOF

```text
curl https://external-api.kalshi.com/trade-api/v2/historical/cutoff
http_code=200
market_settled_ts=2026-07-03T00:00:00Z
```

Cutoff file: `Backtesting Suite/Data/NCAAB/2025-2026/warehouse/raw/kalshi/ncaab/cutoff.json`

## CONFIRMED SERIES TICKER

**`KXNCAAMBGAME`** from the live catalog (5,280 events / 10,566 markets discovered). Do not treat `KXNCAABGAME` as the series.

## DATASET LOCATION

```text
Backtesting Suite/Data/NCAAB/2025-2026/warehouse/
```

## COUNTS

| Metric | Value |
| --- | --- |
| EVENT COUNT | 5280 |
| GAME COUNT | 5280 |
| MARKET COUNT | 10560 |
| CANDLE COUNT | 13429581 |
| TRADE COUNT | 32139837 |
| GAMES WITH 2 MARKETS | 5280 |
| GAMES MISSING MARKET | 0 |
| MARKETS WITH CANDLES | 10560 |
| MARKETS WITH TRADES | 10560 |
| EARLIEST DATA | 2025-10-28T23:49:00+00:00 |
| LATEST DATA | 2026-04-05T03:36:00+00:00 |
| FAILED REQUESTS | 0 |
| DUPLICATE CANDLES | 9 |
| DUPLICATE TRADES | 0 |
| COVERAGE | 0.3922 |
| VALIDATION STATUS | PASS |

## SCHEMA VERSION

`ncaab_market_data_schema_v1`

## VALIDATION STATUS

`PASS`

Human report: `Backtesting Suite/Data/NCAAB/2025-2026/warehouse/manifests/ncaab/validation.txt`

## SAMPLE GAMES

{
  "REGULAR_SEASON": {
    "event_ticker": "KXNCAAMBGAME-26APR04MICHARIZ",
    "phase": "REGULAR_SEASON",
    "market_tickers": [
      "KXNCAAMBGAME-26APR04MICHARIZ-ARIZ",
      "KXNCAAMBGAME-26APR04MICHARIZ-MICH"
    ],
    "candles_present": [
      true,
      true
    ],
    "trades_present": [
      true,
      true
    ]
  },
  "NCAA_TOURNAMENT": {
    "event_ticker": "KXNCAAMBGAME-26MAR18PVLEH",
    "phase": "NCAA_TOURNAMENT",
    "market_tickers": [
      "KXNCAAMBGAME-26MAR18PVLEH-LEH",
      "KXNCAAMBGAME-26MAR18PVLEH-PV"
    ],
    "candles_present": [
      true,
      true
    ],
    "trades_present": [
      true,
      true
    ]
  }
}

Missing phases (not present in catalog or not yet classified): ['CONFERENCE_TOURNAMENT']

## CLI EXAMPLES

```bash
cargo run -p momento-ncaab-data -- discover --season 2025-2026
cargo run -p momento-ncaab-data -- download-all --season 2025-2026 --dry-run
cargo run -p momento-ncaab-data -- download-all --season 2025-2026 --max-workers 4 --rps 4
cargo run -p momento-ncaab-data -- download-all --event KXNCAAMBGAME-26JAN18TLSAUAB
cargo run -p momento-ncaab-data -- validate
```

## KNOWN LIMITATIONS

1. Historical L2 is not available and was not fabricated.
2. NCAAB season labeling is exhibition-inclusive (October–April).
3. Shared type names remain `NbaWarehouse` / `NbaQuery` (parameterized by `WarehouseConfig.sport`).
4. Women’s `KXNCAAWBGAME` is out of scope.

## FIRST-80 / close-40 observational backtest

Same NBA candle-path rule. First measurement (not the NBA 1,230 freeze).

| | N / value |
|---|---:|
| Settled FIRST-80 | 4,099 |
| Survivors / close-40 | 2,998 / 1,099 |
| Close-stop win rate | 73.14% (CI 71.76–74.47) |
| Gross EV (+1R/−2R) | +0.195 R |

Details: [`FIRST80_EXECUTION_AUDIT.md`](FIRST80_EXECUTION_AUDIT.md). Candle path ≠ fill. L2 not invented.

First-exit 90 or 40 (no expiration): 3,370 hit 90 / 728 hit 40 / 1 neither. Close-path **82.24%** (CI 81.04–83.38) vs **80%** breakeven; **+1.12¢** / trade. Wick path 77.78% / **−1.11¢**.

First-exit 90 or 50: 3,217 / 882. Close-path **78.48%** (CI 77.20–79.71) vs **75%** breakeven; **+1.39¢** / trade. Wick 71.74% / **−1.31¢**.

`FIRST80_LIQUIDATION_MODEL_V1`: 40¢ is a liquidation trigger, not a fill.
NCAAB Model B (stop-minute bid close) average exit **33.15¢**, EV **+2.07¢**
vs Model A +3.90¢. Model C (bid low) **28.68¢ / +0.87¢**. Zero-EV fill
**25.44¢** NCAAB / **23.13¢** NBA before fees.
Details: [`FIRST80_LIQUIDATION_MODEL_V1.md`](FIRST80_LIQUIDATION_MODEL_V1.md).

Opponent-40 hedge (other-side 40¢ bid, lock −20 if filled): NCAAB close-path
**+4.89¢** / contract vs 80/40 +3.90¢; NBA **+5.17¢** vs +4.39¢. Candle
proxy only. Reserved-capital sizing can reverse dollar EV.
[`FIRST80_OPPONENT_40_HEDGE_V1.md`](FIRST80_OPPONENT_40_HEDGE_V1.md).

## Historical data available

1-minute top-of-book + trades (same contract as NBA).

## Historical L2

NOT AVAILABLE. Never fabricated.

## Future live L2

ARCHITECTURE READY (`market_data_type`)
