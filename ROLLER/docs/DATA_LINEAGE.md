# Data lineage

```text
warehouse evidence (read-only)
  → raw pointer + sha256 + ingested_at
  → canonical CSV
  → derived features / D2D
  → public I(t)
  → later research (not in ROLLER)
```

## Identity

`internal_game_id` format:

```text
{SPORT}_{YYYYMMDD}_{AWAY}_{HOME}
```

Stable team codes only. Same-day rematch suffix `_2`, `_3`, … after sorting that date/pair by `scheduled_start`. Suffixes are deterministic across rebuilds.

Persisted aliases on `meta/game_identity.csv`:

- `warehouse_game_id` (hex)
- `event_ticker`
- `source_game_id` (NBA Stats / ESPN)

Polymarket moneyline tokens live on `meta/polymarket_game_map.csv` and
`canonical/polymarket_markets.csv`. They join Kalshi candles and PBP through
the same `internal_game_id`. They do not mint a second game id.

Never equal a Kalshi ticker. Do not mint IDs from display names.

Mapping:

| Condition | Status |
|-----------|--------|
| `MATCHED` + unique date/pair + both tickers | `MAPPED` / `HIGH` |
| `UNMATCHED` or missing tickers | `UNMAPPED` |
| Otherwise | `REVIEW_REQUIRED` |

Research candle joins drop anything that is not `MAPPED`.

WNBA warehouse codes are mixed (`Dallas` vs `DAL`, `LAS` vs `LA`). Canonical codes live in `config/team_aliases.json`, seeded from `wnba_pbp_espn_ingest.py`.

NCAAB P5 membership is metadata in `config/conferences.json` (70 codes, aliases `OU→OKLA`, `SC→SCAR`, `TA&M→TXAM`).

## Row-level lineage

Derived rows carry:

- `source_dataset`
- `source_file_hash`
- `pipeline_version`
- `derived_at`

plus `internal_game_id` when the row is game-scoped.

## Source revision policy

Canonical datasets may be rebuilt when upstream evidence changes.

Every rebuild appends to `meta/update_log.csv`:

- `prior_source_hash`
- `new_source_hash`
- `timestamp`
- `dataset`
- `records_before` / `records_added` / `records_updated` / `records_after`
- `pipeline_version`

V1 is auditable. V1 is not full source time travel. Point-in-time integrity (`available_at`) is not the same as historical source-version reproducibility.

## Added research objects (4.1.0-R)

Kalshi markets (expiration W), trades tape as prints, forward-only orderbook snapshots, candle `quality()` flags, game windows, FIRST80/T40 derived table. FIRST80 stays off `O_t`.

Live orderbook collector: `scripts/ingest_orderbook_snapshots.py` (NBA + NCAAB P5 vs P5). No historical L2 backfill.

Polymarket 1-minute last-trade history: `scripts/ingest_polymarket.py`. Official
Gamma `/events` + CLOB `/prices-history?fidelity=1`. Stored as
`PRICE_HISTORY_LAST` (`last_*_e4`). Bid/ask are not invented. Tradable
`yes_bid_close` research stays Kalshi-only.

### Observation bases

A research question resolves to exactly one **observation basis**, which pairs
a price field with what that price means. The two are not interchangeable and
are never mixed in one population.

| Basis | Venue | Price field | Event definitions | Meaning |
|-------|-------|-------------|-------------------|---------|
| `TRADABLE_YES_BID` | Kalshi | `yes_bid_close` | `TRADABLE_CLOSE_*` | quote you could have hit; `quality()` applies |
| `LAST_TRADE_PRINT` | Polymarket | `last_close_e4` | `LAST_TRADE_CLOSE_*` | transaction that already printed; not executable |

`LAST_TRADE_PRINT` rules:

- No `quality()` spread gate, because no quote exists to be crossed or wide.
- A minute with no print is **absent**, never forward-filled. An absent trade
  is not evidence the price held.
- No P&L, EV, drawdown, or risk-of-ruin is reported. A print was not offered
  to you, so print-to-print difference is not a return.
- Terminal outcome comes from **Kalshi settlement**, joined on
  `internal_game_id` via the `kalshi_ticker` carried on each Polymarket candle
  row. Settlement is a game result, not a price, so this is a join and not a
  substitution. When `kalshi_markets` is absent the terminal measurement
  reports `ABSENT`, exactly as it does for a Kalshi question. Missing
  settlement is never inferred from price.
- Never eligible for a frozen FIRST80 reference, and never served from the
  Kalshi tradable observation index.
- Selecting Kalshi and Polymarket together is `OPERATION_REQUIRED`: joint
  cross-venue semantics are not defined.

Behavioral change (was: every Polymarket question returned
`OPERATION_REQUIRED`, so linked data was unreadable). Polymarket questions now
compile and execute on `LAST_TRADE_PRINT`. The tradable invariant is unchanged:
Polymarket can still never satisfy a `yes_bid_close` requirement, and research
first_touch on a *tradable* basis remains Kalshi-only.

## What is not ingested

FIRST75 / DRE / Lebronner packages, live trading crates, MLB research-engine W0–W8. Do not start W9 from ROLLER. Do not invent historical L2 or fills from OHLC.
