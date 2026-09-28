# Cursor prompt — NCAAB `KXNCAAMBGAME` warehouse (2025–2026)

Paste-ready agent prompt. Copy everything under **Prompt** into a **Cursor Cloud Agent** (or any agent on a non-trading cloud host that can reach Kalshi).

This is the same Momento backtest ingest logic as [`docs/research/NBA_KXNBAGAME_MARKET_DATA.md`](../NBA_KXNBAGAME_MARKET_DATA.md), applied to all men’s NCAAB game markets for 2025–2026. Kalshi HTTP must not run from the operator laptop (public wifi blocks Kalshi) and must not run on live trading EC2 `i-0f0849d5829476c31`.

---

## Prompt

# CURSOR AGENT — BUILD COMPLETE KALSHI NCAAB HISTORICAL MARKET DATA WAREHOUSE
# Same Momento backtest logic as KXNBAGAME, applied to 2025–2026 NCAAB game markets

You are working inside the existing Momento Systems algorithmic trading/research codebase.

Your task is to clone the EXISTING NBA Kalshi game-market warehouse — not the MLB date-partitioned collector — onto ALL historically available Kalshi MEN'S college basketball game markets for the 2025–2026 season.

This is research-only market-data ingestion. It does not change live trading.

The operator's current laptop is on public wifi that BLOCKS Kalshi. You MUST run every Kalshi HTTP call from a cloud host.

Do not build a toy scraper.
Do not start from MLB.
Do not invent L2.
Do not invent a Kalshi series ticker.

---

# 0. HARD CONSTRAINTS

## Network (hard)

Kalshi is blocked on the operator laptop / public wifi.

You MUST NOT run Kalshi HTTP from that laptop.

Execute all Kalshi API calls from a cloud host that can reach:

https://external-api.kalshi.com/trade-api/v2

Allowed hosts:
- This Cursor Cloud Agent VM
- A Momento AWS research/ingest EC2 that is NOT the live trading box

Forbidden hosts:
- The operator laptop / public wifi
- Live trading EC2 i-0f0849d5829476c31
- Any host running momento-live.service or momento-paper.service

Forbidden actions:
- systemctl start/restart momento-live or momento-paper
- Deploy DATA-INGEST CloudFormation (cloud is LOCAL_CRON_ONLY / IMPLEMENTED_NOT_DEPLOYED)
- Use live trading API keys or submit orders
- Write into Backtesting Suite/Data/NBA/**
- Write into Data-Real, Foundation/W1, Foundation/W2/raw
- Change FIRST01 / 80 / 81 / 83 / 89 / live Risk / live Execution
- Start W9
- Download women's series KXNCAAWBGAME

First command on the chosen cloud host:

curl -sS -o /dev/null -w "%{http_code}\n" \
  https://external-api.kalshi.com/trade-api/v2/historical/cutoff

If that is not HTTP 200, STOP. Switch hosts. Do not invent data.

Public historical endpoints do not require live credentials. Do not hard-code secrets.

## Financial / research safety (hard)

- Never fabricate historical L2 from 1-minute candles
- Never use f64 as the stored price representation (integer E4, same as NBA)
- Never silently drop anomalies
- Never use future information in derived features
- Never enable live trading
- Never add NCAAB to CollectorConfig::default_sports()

---

# 1. FIRST: INSPECT THE EXISTING NBA WAREHOUSE (NOT MLB)

Read and reuse:

- docs/research/NBA_KXNBAGAME_MARKET_DATA.md
- apps/nba-data/src/main.rs
- crates/research-data/src/warehouse/**
- crates/research-data/src/sport.rs
- crates/research-data/tests/nba_warehouse.rs

The NBA system already does the job:

- Discover events + markets for series KXNBAGAME
- Download 1-minute yes_bid/yes_ask candles
- Download public trades
- Preserve raw JSONL.gz
- Normalize to parquet
- Map game ↔ two team YES markets
- Integer E4 prices
- Resume manifest (PENDING/DOWNLOADING/COMPLETE/FAILED/RETRY)
- Dry-run, validate, rebuild-derived
- Query API: get_games / get_markets / get_candles / get_trades / get_game_market_data / aligned_two_sided
- market_data_type = CANDLESTICK_TOP_OF_BOOK
- orderbook_depth_available = false

NCAAB must become the same first-class warehouse for a different series.

Do NOT copy MLB orderbook.parquet / CANDLESTICK_ONLY behavior.

Before coding, write this assessment:

EXISTING NBA WAREHOUSE
        ↓
GENERALIZABLE COMPONENTS (http, catalog, ingest, parquet, resume, validate, query)
        ↓
NBA-SPECIFIC (KXNBAGAME prefix, October season, Play-In/Playoffs/Finals, paths hard-coded to NBA)
        ↓
NCAAB-SPECIFIC (series, identity, season calendar, phases, paths, CLI, docs)

Then implement.

---

# 2. DATA SOURCE

Kalshi production API:

https://external-api.kalshi.com/trade-api/v2

Primary series — DISCOVER, do not invent:

Expected men's college basketball game series:

KXNCAAMBGAME

Observed event shape:

KXNCAAMBGAME-26JAN18TLSAUAB

Do NOT assume the series ticker is KXNCAABGAME. That string is not the Kalshi series.

Required discovery step:

1. GET /historical/cutoff — record cutoff
2. GET /series or events/markets search to confirm the men's college game series ticker
3. If the live catalog is not KXNCAAMBGAME, use the confirmed ticker and document it
4. If you cannot confirm a men's college GAME series, STOP

Then use the confirmed ticker everywhere:

GET /events?series_ticker={SERIES}
GET /historical/markets?series_ticker={SERIES}
GET /markets?series_ticker={SERIES}
GET /historical/markets/{ticker}/candlesticks?period_interval=1
GET /historical/trades?ticker={ticker}

Traverse every cursor page. Do not hard-code the number of games.

Women's KXNCAAWBGAME is out of scope.

---

# 3. DATASET SCOPE

Digest ALL historically available men's NCAAB game markets for:

season: 2025-2026
sport: ncaab
series: confirmed KXNCAAMBGAME (or discovered equivalent)
include_exhibition: true if present
include_regular_season: true
include_conference_tournament: true
include_ncaa_tournament: true
include_other_postseason: true only if Kalshi titles actually have them

Typical calendar (do not treat as a hard filter):

November 2025 → April 2026

Exhibition/early games may appear in October. Include them if they belong to this season in Kalshi metadata.

Support --season 2024-2025 and future seasons without architectural change.
Default run is 2025-2026.

Do NOT classify games by month alone.

---

# 4. HISTORICAL DATA IS TOP-OF-BOOK, NOT L2

Same rule as NBA.

Historical Kalshi data does NOT provide historical L2 order books.

market_data_type = CANDLESTICK_TOP_OF_BOOK
orderbook_depth_available = false

Never fabricate bid_size, ask_size, depth, queue_position, L2 levels, or maker inventory.

Candles are never written as orderbook.parquet.

---

# 5. STORE BOTH SIDES OF EVERY GAME

Every game event should have two team YES markets.

GAME
 ├── TEAM A YES
 └── TEAM B YES

Explicit relationship:

event_id
game_id
market_id
market_ticker
team
opponent

Flag, do not silently drop:

missing market
duplicate market
unexpected market count
team mismatch
event mismatch

---

# 6. REUSE / GENERALIZE — DO NOT FORK A SECOND UNIVERSE

Preferred implementation:

1. Add ResearchSport::Ncaab and SERIES_NCAAB in crates/research-data/src/sport.rs
2. Parameterize WarehousePaths (today hard-codes ResearchSport::Nba and raw/kalshi/nba)
3. Parameterize identity prefix (today strip_prefix("KXNBAGAME-"))
4. NCAAB season_for_date: college season, not NBA October-start, unless metadata says otherwise
5. NCAAB phase classifier from event title/subtitle
6. Keep NBA behavior and NBA tests green
7. Add apps/ncaab-data CLI (bin ncaab-data) mirroring nba-data
8. Add crates/research-data/tests/ncaab_warehouse.rs (offline, no live Kalshi)

Do not introduce a new database.
Do not add a new crate family unless generalization is genuinely blocked.
Do not rename NbaWarehouse in a huge mechanical rewrite if a thin NcaabWarehouse / shared warehouse parameterized by sport is cleaner.

---

# 7. DIRECTORY LAYOUT

Backtesting Suite/Data/NCAAB/{season}/warehouse/
  raw/kalshi/ncaab/{events,markets,candlesticks,trades}/
  normalized/ncaab/{events,markets,games,candles_1m,trades}/
  derived/ncaab/{causal_features,complementarity,trade_minute,coverage}/
  manifests/ncaab/

Season folder: 2025-2026 (canonicalize 2025-26 → 2025-2026, same helper as NBA).

Raw: JSONL.gz, partitioned, not one giant JSON.
Normalized timeseries: parquet, month partitions, not one file per candle.

---

# 8. NORMALIZED TABLES

Same conceptual schemas as NBA:

Events, markets, ncaab_games, kalshi_ncaab_candles_1m, kalshi_ncaab_trades.

Prices: integer E4 (0.7100 → 7100). Document conversion.
Timestamps: UTC, timezone-aware.
schema_version = ncaab_market_data_schema_v1

Preserve every economically useful API field. Store null when missing. Never manufacture.

Game table must include:

game_id
event_id
event_ticker
season
season_phase
game_date
scheduled_start
home_team
away_team
home_market_ticker
away_market_ticker
event_status
settlement_status
source

Identity: prefer Kalshi event/market metadata. Ticker parse is fallback only.
GameId remains the existing Kalshi GameId hash of event_ticker if that is what NBA does.

---

# 9. NCAAB PHASES (DO NOT COPY NBA PHASES BLINDLY)

season_phase values:

EXHIBITION
PRESEASON
REGULAR_SEASON
CONFERENCE_TOURNAMENT
NCAA_TOURNAMENT
OTHER_POSTSEASON
UNKNOWN

Use event title/subtitle first.

Examples of title signals (only if present):
- Exhibition / preseason / friendly
- Conference tournament / championship week
- First Four / Round of 64 / Round of 32 / Sweet 16 / Elite 8 / Final Four / National Championship
- NIT / CBI / other postseason

Do NOT label NCAAB games PLAY_IN / NBA PLAYOFFS / NBA FINALS unless the title actually says that.

Do NOT invent March Madness labels from calendar month alone.

---

# 10. DERIVED LAYER (SAME AS NBA)

Where both bid and ask exist:

mid_e4 = (bid_e4 + ask_e4) / 2
spread = ask - bid

No mid if either side is missing.

Complementarity diagnostic:

complementarity_error = (a_mid + b_mid) - 1

This is NOT an arb signal.

Causal features only (look_ahead = false):

return_1m / return_5m / return_15m
trade_count / trade_volume / trade intensity
unknown side stays unknown

Tests must catch look-ahead.

---

# 11. INGEST BEHAVIOR (SAME AS NBA)

- Idempotent. Re-run must not duplicate. COMPLETE ticker jobs are skipped.
- Resumable. Survive timeout, 429, crash, partial completion.
- Manifest: ticker, dataset_type, status, attempts, timestamps, row_count, error, checksum
- Rate limit: bounded concurrency, backoff, Retry-After, jitter
- Default: --max-workers 4 --rps 4
- Pagination: traverse next_cursor fully
- Record /historical/cutoff in metadata
- NCAAB is large (possibly thousands of games). Correctness over speed. Do not fire thousands of requests at once.

---

# 12. CLI

ncaab-data discover
ncaab-data download-all --season 2025-2026
ncaab-data download-all --season 2025-2026 --dry-run
ncaab-data download-all --event KXNCAAMBGAME-...
ncaab-data download-all --ticker KXNCAAMBGAME-...
ncaab-data validate
ncaab-data coverage
ncaab-data rebuild-derived

Dry-run reports events, markets, games, estimated requests, already downloaded, pending. No download.

---

# 13. QUERY API

Research code must be able to:

get_games(season, phase)
get_markets(game_id)
get_candles(ticker, start, end)
get_trades(ticker, start, end)
get_game_market_data(game_id, start, end)
get_season_market_data(season, phase)
aligned_two_sided(game_id)

NCAAB GAME
    ↓
TEAM A MARKET + TEAM B MARKET
    ↓
1M TOP OF BOOK
    ↓
TRADES

---

# 14. VALIDATION REPORT

After full ingest, write human + JSON reports under manifests/ncaab/:

NCAAB KXNCAAMBGAME DATASET VALIDATION
Season
Events / markets / games
Games with 2 markets
Games missing a market
Candles / trades
Markets with/without candles
Markets with/without trades
Earliest / latest candle UTC
Duplicates
Failed requests
Coverage
Anomalies
Historical cutoff
schema_version
code_version
checksum

Also write dataset_manifest.json.

---

# 15. TESTS

Offline tests only for CI (no live Kalshi in cargo test):

- series mapping ResearchSport::Ncaab ↔ KXNCAAMBGAME
- season canonicalize 2025-26 → 2025-2026
- ticker/event date parse for KXNCAAMBGAME-YYMONDD...
- two-market game mapping
- phase classification from titles (regular / conference tourney / NCAA tournament / unknown)
- E4 price conversion
- dedup keys
- no look-ahead on derived features
- NBA warehouse tests still pass
- paths do not write under Data/NBA

Then, ON THE CLOUD HOST ONLY, run live ingest tests:

1. dry-run 2025-2026
2. one regular-season event
3. one conference-tournament event if present
4. one NCAA-tournament event if present
5. full download-all --season 2025-2026
6. validate
7. spot-check both sides + candles + trades for sampled games

---

# 16. IMPLEMENTATION ORDER

Phase 1 — Prove Kalshi reachability from the cloud host. Record cutoff.
Phase 2 — Confirm series ticker from the live catalog.
Phase 3 — Inspect NBA warehouse; write the architecture assessment.
Phase 4 — Generalize sport/paths/identity; add ncaab-data CLI; offline tests.
Phase 5 — cargo fmt, check, test, clippy for touched crates. NBA stays green.
Phase 6 — Cloud dry-run for 2025-2026. Print event/market/game counts.
Phase 7 — Sample-game ingest (regular + tourney + NCAA if present).
Phase 8 — Full 2025-2026 download-all. Resume if interrupted.
Phase 9 — validate + documentation docs/research/NCAAB_KXNCAAMBGAME_MARKET_DATA.md
Phase 10 — Implementation report.

Do not declare complete after writing code. Actually download. Actually validate.

---

# 17. DOCUMENTATION

Create docs/research/NCAAB_KXNCAAMBGAME_MARKET_DATA.md modeled on docs/research/NBA_KXNBAGAME_MARKET_DATA.md:

- What data exists
- What data does not exist (historical L2)
- Confirmed series ticker
- How NCAAB phases differ from NBA
- How to query
- How to rerun
- Cloud-host requirement (Kalshi blocked on some public wifi)

Explicit sentence:

Historical KXNCAAMBGAME data is 1-minute top-of-book/candlestick data plus public trades; it is not historical L2 order-book reconstruction.

---

# 18. ACCEPTANCE

Do not declare complete until:

1. Cloud host can reach Kalshi historical cutoff
2. Series ticker is confirmed from the live catalog (expected KXNCAAMBGAME)
3. All discoverable 2025-2026 men's NCAAB game events are enumerated
4. Both markets mapped per game (anomalies flagged, not dropped)
5. Candles downloaded for every available market
6. Trades downloaded for every available market
7. Raw + normalized + derived + manifests exist under Data/NCAAB/2025-2026/warehouse
8. Deduped, UTC, E4 prices
9. Validation report + dataset manifest exist
10. CLI dry-run / download-all / validate work
11. Query helpers work
12. Pipeline is resumable and idempotent
13. Offline tests pass; NBA warehouse tests still pass
14. No historical L2 fabricated
15. Derived features are point-in-time safe
16. Live trading, NBA warehouse, MLB collector, and W9 untouched

---

# 19. FINAL REPORT

FILES CREATED
FILES MODIFIED

CLOUD HOST USED
KALSHI REACHABILITY PROOF

CONFIRMED SERIES TICKER

DATASET LOCATION

EVENT COUNT
GAME COUNT
MARKET COUNT
CANDLE COUNT
TRADE COUNT

EARLIEST DATA
LATEST DATA

FAILED REQUESTS
MISSING MARKETS
MISSING CANDLES
MISSING TRADES

SCHEMA VERSION
VALIDATION STATUS
CLI EXAMPLES
KNOWN LIMITATIONS

Historical data available:
1-minute top-of-book + trades

Historical L2:
NOT AVAILABLE

Future live L2:
ARCHITECTURE READY

Sample at least one regular-season game, one conference-tournament game if present, and one NCAA-tournament game if present. Verify both team markets, candles, and trades.

The final standard:

Momento should have a clean, queryable, reproducible historical KXNCAAMBGAME market-data warehouse for 2025–2026, built with the same backtest logic as KXNBAGAME, downloaded from a cloud host because Kalshi is blocked on the operator's public wifi.
