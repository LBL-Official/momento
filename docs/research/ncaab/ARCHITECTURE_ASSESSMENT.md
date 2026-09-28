# NCAAB warehouse architecture assessment

Written before implementation. NCAAB reuses the NBA event-centric warehouse; it does not copy the MLB date-partitioned collector.

```text
EXISTING NBA WAREHOUSE
        ↓
GENERALIZABLE COMPONENTS (http, catalog, ingest, parquet, resume, validate, query)
        ↓
NBA-SPECIFIC (KXNBAGAME prefix, October season, Play-In/Playoffs/Finals, paths hard-coded to NBA)
        ↓
NCAAB-SPECIFIC (series, identity, season calendar, phases, paths, CLI, docs)
```

## Existing NBA warehouse

- Crate: `crates/research-data/src/warehouse/`
- CLI: `apps/nba-data` (`nba-data`)
- Series: `KXNBAGAME`
- Layout: `Backtesting Suite/Data/NBA/{season}/warehouse/`
- Historical data: 1-minute `yes_bid`/`yes_ask` candles + public trades
- `market_data_type = CANDLESTICK_TOP_OF_BOOK`
- `orderbook_depth_available = false`
- Integer E4 prices
- Resume manifest: PENDING / DOWNLOADING / COMPLETE / FAILED / RETRY

## Generalizable

- Unsigned Kalshi REST client with rate limit, backoff, pagination
- Event/market catalog merge (historical + live)
- Raw JSONL.gz archive
- Parquet normalize + causal derived layer
- Two-sided game map and complementarity diagnostic
- Query API (`get_games`, `get_markets`, `get_candles`, `get_trades`, `aligned_two_sided`)
- Validation report + dataset manifest

## NBA-specific (must not leak into NCAAB)

- Paths hard-coded to `ResearchSport::Nba` and `raw/kalshi/nba`
- Ticker prefix `KXNBAGAME-`
- Phase classifier: Play-In / Playoffs / Finals / October preseason window
- Live candlestick URL hard-coded to series `KXNBAGAME`
- Schema `nba_market_data_schema_v1`
- Report header `NBA KXNBAGAME`

## NCAAB-specific

- `ResearchSport::Ncaab` + expected series `KXNCAAMBGAME` (discover; do not invent `KXNCAABGAME`)
- Prefix `KXNCAAMBGAME-` date parse
- Exhibition-inclusive season (October–April) so October exhibition stays in the upcoming season
- Phases from titles: EXHIBITION / PRESEASON / REGULAR_SEASON / CONFERENCE_TOURNAMENT / NCAA_TOURNAMENT / OTHER_POSTSEASON / UNKNOWN
- Do not label March regular-season games as NCAA tournament from calendar alone
- CLI `ncaab-data`
- Layout: `Backtesting Suite/Data/NCAAB/{season}/warehouse/`
- Schema `ncaab_market_data_schema_v1`
- Women's `KXNCAAWBGAME` is out of scope
