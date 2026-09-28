# ROLLER V1 build report

**Date:** 2026-09-06  
**Pipeline:** 1.0.0  
**Contract:** the warehouse knows what data exists; ROLLER knows what could have been known at a particular time.

```text
I(t) = { x | available_at(x) < t }
```

This report uses IMPLEMENTED / PARTIALLY IMPLEMENTED / NOT YET IMPLEMENTED. It does not claim live-trading readiness. Candidates are not production.

## Operational rebuild (2026-09-06)

Offline `update_roller.py` against the existing warehouse. Integrity PASS and leakage PASS for each sport after the fixes below.

| Sport / season | Identity | MAPPED | Games | Scored | PBP rows | Candle rows | Feature rows | D2D rows |
|----------------|----------|--------|-------|--------|----------|-------------|--------------|----------|
| NBA 2025-2026 | 1,362 | 1,352 | 1,362 | 1,352 | 780,137 | 6,165,183 | 2,724 | 6,665 |
| WNBA 2025 | 303 | 302 | 303 | 302 | 120,618 | 501,214 | 606 | 2,034 |
| WNBA 2026 | 309 | 308 | 309 | 307 | 132,002 | 940,373 | 618 | 1,944 |
| NCAAB 2025-2026 | 5,280 | 849 | 5,280 | 847 | ~387k–399k | 2,674,280 (MAPPED only) | 1,698 (P5 vs P5) | 8,260 (70 P5 teams) |

`game_identity.csv`: 7,254 rows, 0 duplicate IDs.

NCAAB candle export is smaller than the warehouse’s ~13.4M rows because research joins drop anything that is not `MAPPED` (849 P5 vs P5 games). That is required, not a shortfall.

Tests: `pytest` **25 passed** without needing the 4 GB warehouse. One optional `@pytest.mark.integration` reads the live catalog when present.

## IMPLEMENTED

### Architecture

- `ROLLER/` tree, `roller.json` map v1.0.0, metadata-driven sports/seasons
- Config: `sports.json`, `seasons.json`, `schemas.json`, `sources.json`, `features.json`, `conferences.json`, `team_aliases.json`
- Dataset registry with required-path validation (empty outputs stay `pending`)
- Python package `roller` (3.11+; pandas, pyarrow, pydantic, pytest)
- Three timestamps: `event_timestamp`, `available_at`, `ingested_at`
- Availability quality: `OBSERVED`, `CONSERVATIVE_PROXY`
- Row lineage: `source_dataset`, `source_file_hash`, `pipeline_version`, `derived_at`

### Identity

- Deterministic `internal_game_id` = `{SPORT}_{YYYYMMDD}_{AWAY}_{HOME}` from stable codes
- Same-day rematch suffix `_2`, `_3`, … after sort by `scheduled_start`
- Hyphen preserved in codes (`L-MD` ≠ `LMD`)
- Spaces stripped from display-name leftovers (`Nigeria National Team` → `NigeriaNationalTeam`)
- Persisted aliases: `warehouse_game_id`, `event_ticker`, `source_game_id`
- Mapping: `MAPPED` / `UNMAPPED` / `REVIEW_REQUIRED` — no silent guesses
- Home/away Kalshi tickers inferred from `market_tickers` when the warehouse leaves them null (WNBA 2026)
- WNBA city-name canonicalization (`Dallas→DAL`, `LAS→LA`, `LVA→LV`)
- NCAAB conference metadata (70 P5 codes; aliases `OU→OKLA`, `SC→SCAR`, `TA&M→TXAM`)

### Ingest and canonical layer

- Warehouse is read-only. Raw pointer + sha256 + `ingested_at` manifests
- `games.csv` scores from box / PBP terminal; null if unknown
- Monthly PBP: NBA `pbp_live.timeActual`; WNBA/NCAAB normalized `wallclock`
- Canonical PBP sorted by `available_at` (source `actionNumber` is not always clock-monotonic)
- Monthly candles: integer E4 bid/ask, `available_at` = candle close, observation not fill
- Never invent wall clocks from tip + clock

### Features and D2D

- `X_pre(i,g) = f(G_1…G_{g-1})` ordered by `result_available_at`
- Unresolved games use `scheduled_start` / `game_date` as cutoff — they do **not** absorb later results
- `win_pct_pre` integer E4
- L1 `d2d_daily.csv`, L2 `team_game_features.csv`, L3 `Roller.game_state`
- Terminal labels isolated as `*_terminal`
- NCAAB research features default to `P5_vs_P5`; identity still stores non-P5 games

### Point-in-time API

- Public `dataset` / `get_team_state` / `game_state` / `as_of` require `as_of` or `full_history=True`
- Half-open UTC cutoffs; date → UTC start; `end_of_day=True` → next midnight
- Naive vs aware comparison raises
- Backward-only PBP↔candle alignment (`merge_asof` backward, `allow_exact_matches=False`)

### Validation and maintenance

- Integrity + leakage fail the pipeline
- Required tests plus rematch stability, half-open equality, conservative-proxy label, registry missing-path, source-hash columns, unresolved-game cutoff
- `scripts/update_roller.py` offline by default; `--fetch` optional
- Append-only `meta/update_log.csv` with `prior_source_hash` / `new_source_hash`
- Incremental sport updates do not demote already-required rows
- Missing warehouse seasons are skipped so an NBA-only rebuild can run

## PARTIALLY IMPLEMENTED

### Schedule publication time

V1 warehouse catalogs do not carry a true schedule-publication timestamp. Game identity `available_at` is `scheduled_start` when present, otherwise `game_dateT00:00:00Z`, always labeled `CONSERVATIVE_PROXY`. PBP wall clocks are `OBSERVED` when `timeActual` / `wallclock` exists.

### NCAAB tip times

All 5,280 NCAAB warehouse `scheduled_start` values are null. `scheduled_start` stays empty. Identity availability uses the game-date UTC start proxy.

### WNBA team codes

Warehouse codes are mixed abbreviations and city names. ROLLER canonicalizes via `config/team_aliases.json` seeded from the existing ESPN ingest map. Exhibition / national-team tokens without an alias are stored as sanitized tokens, not invented league codes.

### Candle coverage

Candles are exported only for `MAPPED` games. NBA 10 UNMAPPED and NCAAB 4,431 UNMAPPED warehouse games have no research candle CSV. That matches the mapping contract.

### Generated artifacts

Monthly PBP/candle CSVs are gitignored. Rebuild with `scripts/update_roller.py`.

## NOT YET IMPLEMENTED

| Item | Notes |
|------|--------|
| Full source time travel | V2. V1 logs revisions; it does not replay a prior canonical version |
| Observed schedule publication time | Not in the warehouse catalog |
| L2 order book | Not invented. Candles remain top-of-book observations |
| W9 / Greeks / live P&L / strategy retune | Out of scope |
| FIRST75 / FIRST80 / DRE / Lebronner ingest | Explicitly excluded |
| New Kalshi HTTP downloader | Reuse existing Rust CLIs via `--fetch` only |
| DuckDB query layer | Not required for V1 |
| NBA 2024-2025 | PBP-only; not an operational V1 season |

## Fixes found during the first operational run

1. Identity rebuild of all configured sports crashed NBA-only fixtures when WNBA warehouse files were absent. Rebuild is now per-sport and skips missing warehouses.
2. NBA `timeActual` is not always monotonic in `actionNumber`. Canonical PBP is sorted by `available_at`.
3. Games with no `result_available_at` used a missing-first sort key, so later results leaked into `*_pre`. Priors now use an explicit cutoff.
4. WNBA 2026 leaves `home_market_ticker` null and stores both markets on `market_tickers`. Tickers are inferred from that list.
5. `id_token` stripped hyphens, colliding `L-MD` with `LMD`. Hyphens are kept.
6. Registry no longer marks empty candle directories `required`.

## Non-goals (unchanged)

No live trading, no FIRST75/80 logic, no W9, no strategy signals, no dashboards, no float money types.

## How to rebuild

```bash
cd ROLLER
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python scripts/update_roller.py --sport NBA --season 2025-2026
.venv/bin/python scripts/update_roller.py --sport WNBA --season 2025
.venv/bin/python scripts/update_roller.py --sport WNBA --season 2026
.venv/bin/python scripts/update_roller.py --sport NCAAB --season 2025-2026
.venv/bin/python -m pytest -q
```
