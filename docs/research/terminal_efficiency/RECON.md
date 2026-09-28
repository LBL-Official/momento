# Base Terminal Efficiency — Phase 0 Reconnaissance

**Object:** Base Terminal Efficiency (Base TE / Terminal Efficiency Measurement Layer)  
**Status:** PHASE 0 COMPLETE — documentation only  
**Date:** 2026-09-09  
**Semantics target:** 1.0.0  
**First warehouse:** NBA 2025–26 ROLLER canonical  

This document inventories what already exists so Phase 1+ can reuse it. No Python package was created. No existing source, test, frontend, XIB/MCD, research_query, FIRST80, or trading file was modified.

```text
XIB / MCD Terminal Efficiency V1          NEW: Base Terminal Efficiency
apps/terminal-efficiency                  ROLLER/roller/base_terminal_efficiency  (not created yet)
frozen 2024–25 predictive object          empirical observation panel
UNTOUCHED                                 Phase 1+ only
```

XIB/MCD is a separate, legitimate object. It is not a source for Base TE. It is not renamed here.

---

## 1. Files inspected

### Warehouse / config

- `ROLLER/roller.json`
- `ROLLER/config/schemas.json`
- `ROLLER/roller/admin.py`
- `ROLLER/roller/config.py` (path resolution via `dataset_path`)
- `ROLLER/data/nba/2025_2026/canonical/games.csv`
- `ROLLER/data/nba/2025_2026/canonical/pbp/month=*.csv`
- `ROLLER/data/nba/2025_2026/canonical/kalshi_candles/month=*.csv`
- `ROLLER/data/nba/2025_2026/canonical/kalshi_markets.csv` — **absent**
- `ROLLER/meta/game_identity.csv`

### Canonical writers / PIT

- `ROLLER/roller/canonical/candles.py`
- `ROLLER/roller/canonical/pbp.py`
- `ROLLER/roller/canonical/markets.py`
- `ROLLER/roller/canonical/games.py`
- `ROLLER/roller/canonical/events.py` (`events_visible`, `project_events`)
- `ROLLER/docs/POINT_IN_TIME.md`
- `ROLLER/roller/state/clock_snap.py` (`snap_events`, `clock_snap`)
- `ROLLER/roller/state/clock.py` (`clock_remaining_seconds`, `entry_slice`, `elapsed_game_seconds`)
- `ROLLER/roller/state/observation_id.py`

### Market / path / quality (reuse, do not fork)

- `ROLLER/roller/research_query/entry_engine.py` (`tradable_sequence`, `default_snap`, `TradableBar`)
- `ROLLER/roller/research/quality.py` (`quality`)
- `ROLLER/roller/research_query/path_engine.py` (`run_path`, `first_later`)
- `ROLLER/roller/research_query/execute.py` (`_classify_exits`, `_settled_yes`) — **inspect only; do not modify; do not reuse `_classify_exits`**
- `ROLLER/roller/research/first80.py` (`settled_yes`) — **import only; do not modify**
- `ROLLER/roller/ingest/kalshi.py` (`team_side`)
- `ROLLER/roller/research_query/validation.py` (WIN/LOSS price side checks)
- `ROLLER/roller/research_query/hashing.py` (`CODE_VERSION`)
- `ROLLER/roller/research_query/dataset_version.py`
- `ROLLER/roller/research_query/indexes/manifest.py`
- `ROLLER/roller/research_query/indexes/__main__.py`
- `ROLLER/roller/io_csv.py` (`sha256_file`)
- `ROLLER/docs/research_query/INCREMENT2_DESIGN.md`
- `.cursor/rules/12-roller-research-query.mdc`

### Isolation confirmation (read-only)

- `apps/terminal-efficiency/` (exists; XIB/MCD; Phase 7 gated)
- `docs/research/terminal_efficiency/CURRENT_STATE.md`
- `docs/research/terminal_efficiency/TERMINAL_EFFICIENCY_RECON.md` (XIB Phase 0 — **do not overwrite**)
- `docs/research/terminal_efficiency/POINT_IN_TIME_DATA_CONTRACT.md` (XIB clocks — **do not overwrite**)
- `frontend/roller-terminal/` (no Base TE; do not modify in this workstream)
- `ROLLER/docs/FUTURE_LABELS.md` (`game_state_features.csv` is future information)

---

## 2. Canonical sources found

### Binding first implementation

| Dataset | Path (`roller.json` NBA `2025-2026`) | On disk | Role for Base TE |
|---------|--------------------------------------|---------|------------------|
| `games` | `data/nba/2025_2026/canonical/games.csv` | **1,362 rows** | identity, home/away teams, scheduled start. **Not** settlement. **Not** entry score. |
| `pbp` | `data/nba/2025_2026/canonical/pbp/` (monthly CSV) | **780,137 rows** (2025-10 … 2026-06) | PIT game state + score path |
| `kalshi_candles` | `data/nba/2025_2026/canonical/kalshi_candles/` | **6,165,183 rows** | dense grid: tradable `yes_bid_close` |
| `kalshi_markets` | `data/nba/2025_2026/canonical/kalshi_markets.csv` | **ABSENT** (no `kalshi_markets.csv` under `ROLLER/data/**`) | settlement YES/NO — currently `TERMINAL_MISSING` |
| `game_identity` | `meta/game_identity.csv` | 7,254 rows; 1,362 NBA 2025* | `kalshi_market_yes_home` / `_away`, mapping |

`load_dataset(cfg, sport, season, name)` in `ROLLER/roller/admin.py` is the warehouse reader. Season key in config is `2025-2026` (hyphen), path key is `2025_2026` (underscore).

### Candle columns (on disk, Oct–Dec sampled; schema consistent)

```text
internal_game_id, ticker, team_side, candle_timestamp, event_timestamp,
available_at, ingested_at,
yes_bid_open, yes_bid_high, yes_bid_low, yes_bid_close,
yes_ask_open, yes_ask_high, yes_ask_low, yes_ask_close,
volume, market_data_type, source_dataset, source_file_hash,
pipeline_version, derived_at
```

Prices are **integer E4** (`8000` = 80¢). Canonical writer also defines quality flags (`is_valid`, `spread_e4`, `uncrossed`, `spread_ok`, `volume_positive`, `tradable_cross`). **On-disk NBA 2025–26 CSVs do not include those flags** (older pipeline). `tradable_sequence` / `quality(bid, ask, vol)` still apply from bid/ask/volume. Do not invent missing flags.

`team_side` is populated (`home` / `away`) from ticker suffix vs home/away codes (`team_side()` in `ingest/kalshi.py`). Example: `KXNBAGAME-25OCT17SACLAL-LAL`.

### PBP columns (on disk)

```text
internal_game_id, source_game_id, event_number, event_timestamp, available_at,
ingested_at, availability_quality, timestamp_status, period, clock,
home_score, away_score, score_differential_home, event_type, event_description,
team_tricode, possession, source_dataset, source_file_hash, pipeline_version,
derived_at
```

Scores are integer runs. `home_score` / `away_score` are the game-state source. Team YES observations must map `team_side=home|away` → team vs opponent points. Do not use `games.final_*` or `games.home_win` as entry state or as Kalshi settlement.

On-disk PBP often lacks later pass-through columns (`time_actual`, `person_id`, …). `project_events()` fills empties. Do not invent `timeActual`.

### Games columns (relevant)

Identity + schedule + **terminal box fields** (`final_home_score`, `final_away_score`, `home_win`, `away_win`, `result_available_at`). Those box/terminal fields are **post-game**. They must not enter Base TE entry-state. They must not substitute for `kalshi_markets.result`.

### Forbidden as Base TE source

- `derived/game_state_features.csv` — tagged future information
- `derived/first80_triggers.csv` — future-tagged FIRST80 book
- Polymarket candles — last-trade, not `yes_bid_close`
- 2024–25 XIB warehouse (`Backtesting Suite/Data/.../terminal_efficiency/`)
- L2 / trades / orderbook snapshots (configured, not required for v1)

---

## 3. Timestamp and PIT semantics

### Constitutional I(t) (binding for Base TE)

From `ROLLER/docs/POINT_IN_TIME.md` and `roller.json` `as_of`:

```text
I(t) = { x | available_at(x) < t }
boundary: half-open
available_at == t  → invisible
```

Do not change this to `<=`. Informal `<=` in other docs is rejected.

Three clocks on warehouse rows:

| Field | Meaning |
|-------|---------|
| `event_timestamp` | When the event happened |
| `available_at` | When it could have been known. **as_of uses only this.** |
| `ingested_at` | When ROLLER processed the row. Never an as_of filter. |

Candles: `candle_timestamp` = `event_timestamp` = `available_at` = candle **close**. The minute is not knowable before it ends. Research-query `TradableBar.ts` is `available_at` (fallback candle/event timestamp).

PBP: `event_timestamp` is wall clock when `availability_quality=OBSERVED`. Missing wall time is `CLOCK_ONLY` + `CONSERVATIVE_PROXY`. ROLLER does not invent wall time from tip + remaining.

### Two-clock snap (must not leak)

`snap_events(events, snap_ts)` selects the last event with

```text
event_timestamp <= snap_ts
```

tie-break higher `event_number`. Docstring: **events must already be I(t)-filtered.**

`events_visible()` applies `available_at < cutoff` only.

**Contradiction in generic query (do not “fix” it):** `default_snap` in `entry_engine.py` calls `snap_events` on the full-game PBP list. That can include a row with `event_timestamp <= bar.ts` and `available_at >= bar.ts`. Base TE must not copy that leak. Phase 2: `events_visible(..., as_of=observation_ts)` then `snap_events`.

Public `clock_snap()` already does `events_visible` unless `full_history=True`. Prefer that pattern.

### Alignment statuses already in the repo

`entry_engine._alignment`: `aligned` / `unaligned` / `modeled` / `ambiguous` from snap `status` / `slice`. Missing events → `{status: UNALIGNED, slice: UNALIGNED}`. Base TE should reuse these words; missing game state is `UNALIGNED` / `UNAVAILABLE`, not a fabricated 0–0.

---

## 4. Settlement availability

Canonical market columns (`canonical/markets.py`):

```text
result, settlement_value_e4, kalshi_yes_settled,
close_time, expiration_time, settlement_time,
result_available_at, available_at, team_side, ticker, ...
```

Canonical decoder already in the repo (`roller.research.first80.settled_yes`):

```text
result == "yes" → "1"
result == "no"  → "0"
settlement_value_e4 == 10000 → "1"
settlement_value_e4 == 0     → "0"
else → ""
```

`execute._settled_yes` is the same idea as `bool | None`. **Reuse `settled_yes`; do not copy either function into Base TE. Do not modify `first80.py` or `execute.py`.**

**Gap:** `kalshi_markets.csv` does not exist anywhere under `ROLLER/data`. `INCREMENT2_DESIGN.md`: generic load census = 0; every generic matrix row is `terminal_missing = N`. Frozen FIRST80 still settles on its own path. Base TE must not invent a second source. v1 builds will report `TERMINAL_MISSING` until markets are canonicalized.

`games.home_win` / box score / last candle / PBP final score are **not** Kalshi settlement.

Hold-to-expiration in Base TE is **terminal settlement**, not `HORIZON_WIN_E4` (that constant is `5000` = candle 50¢ at a clock bar — not settlement).

---

## 5. Reusable libraries (import; do not fork)

| Need | Reuse | Do not |
|------|--------|--------|
| Warehouse read | `load_dataset` | second CSV walker |
| Tradable series | `tradable_sequence` + `quality()` | reimplement spread/volume rules |
| Game snap | `events_visible` + `snap_events` / `clock_snap` | unfiltered `default_snap` as-is |
| Clock labels | `clock_remaining_seconds`, `entry_slice`, `elapsed_game_seconds` | invent period math |
| Path exits | `run_path` / `first_later` (later bars only; entry close is `prior`) | modify `path_engine.py` |
| Exit race | **new** `base_terminal_efficiency/exits.py` | `_classify_exits` (minute `TIE_EXCLUDED`) |
| Settlement decode | `settled_yes` | box score; copy-paste decoder |
| Team side | candle `team_side` or `ingest.kalshi.team_side` | guess from ticker order |
| File checksums | `io_csv.sha256_file` | ad-hoc hash |
| Observation id pattern | `make_observation_id` **plus ticker** (see contradictions) | random UUIDs |
| CLI shape | `python -m roller.research_query.indexes build --league NBA --season 2025-2026` | new CLI framework |
| WIN/LOSS price side | same rules as `validate_question` (WIN not below entry; LOSS not above) | flip invalid books |

Do **not** duplicate `research_query/indexes/` (`bars.parquet`, `transitions.parquet`, …). That tree is a generic-query fact index. Base TE derived tree is separate:

```text
ROLLER/data/nba/2025_2026/derived/base_terminal_efficiency/1.0.0/
```

That directory does not exist yet.

Reserved generic-query families `xib` / `mcd` stay `OPERATION_REQUIRED`. Do not add Base TE as a candle `PathOp`.

---

## 6. XIB / MCD isolation confirmation

| Check | Result |
|-------|--------|
| Package | `apps/terminal-efficiency` v0.1.0, `PHASE7_AUTHORIZED = False` |
| Write root | `Backtesting Suite/Data/{NBA,NCAAB}/2024-2025/warehouse/derived/.../terminal_efficiency/` |
| Kalshi in XIB features | Forbidden (`allowed_in_xib=false`) |
| This recon | Did not edit any file under `apps/terminal-efficiency/` |
| This recon | Did not overwrite `TERMINAL_EFFICIENCY_RECON.md`, `CURRENT_STATE.md`, `POINT_IN_TIME_DATA_CONTRACT.md`, or model cards |
| 2024–25 XIB warehouse | Not a Base TE source |

Frontend `roller-terminal` “terminal” language is Kalshi **settlement partition** in generic query results, not XIB and not Base TE. Dashboard wiring is out of Phase 0–6 isolation (`frontend/roller-terminal/` must not be modified in this workstream).

---

## 7. Proposed Base TE package boundaries

**Create later (Phase 2+), not now:**

```text
ROLLER/roller/base_terminal_efficiency/
  __init__.py
  versions.py      SEMANTICS_VERSION=1.0.0; CODE_VERSION e.g. base_te_v1.0.0
  models.py        OBSERVED | DERIVED | UNAVAILABLE | AMBIGUOUS
  pit.py
  score.py
  market.py
  builder.py
  exits.py
  settlement.py
  empirical.py
  manifest.py
  cli.py           python -m roller.base_terminal_efficiency.cli build --league NBA --season 2025-2026
```

**Tests (later):** `ROLLER/tests/test_terminal_efficiency_{pit,exits,settlement}.py` plus reconciliation.

**Docs (this workstream only):**

| File | Status |
|------|--------|
| `docs/research/terminal_efficiency/RECON.md` | **this file** |
| `DATA_CONTRACT.md` | Phase 1 |
| `README.md` | Phase 1 |
| `COMPLETION_REPORT.md` | Phase 6 |

**Do not modify:** `research_query/`, `first80.py`, frozen FIRST80 tests, `frontend/roller-terminal/`, `apps/terminal-efficiency/`, live trading, Risk, FIRST01, W9, `crates/research-engine`, `game_state_features.csv`.

**Observation grid (v1):** one row per `(ticker, tradable yes_bid_close bar)` after first aligned game-state exists. Team YES moneyline only. Exit books are query parameters. Do not bake WIN 90 / LOSS 40 into the warehouse.

**Versioning convention (proposed, Phase 1 will lock):**

- `SEMANTICS_VERSION = "1.0.0"` (Base TE field meanings)
- `CODE_VERSION = "base_te_v1.0.0"` (do not collide with `research_query_v1.2_ops`)
- `SCHEMA_VERSION` for the observation row layout
- `dataset_version` = fingerprint of source paths (size/mtime or `sha256_file`), same idea as `dataset_fingerprint`
- Manifest fields per implementation contract §34

---

## 8. Contradictions discovered

1. **I(t) vs informal `<=`.** Spec drafts sometimes say `availability_timestamp <= observation_timestamp`. ROLLER constitution is `available_at < t`. Base TE follows ROLLER.

2. **Generic snap leak.** `default_snap` does not I(t)-filter. Base TE must filter first. Do not change `entry_engine.py`.

3. **Tie semantics.** Generic `_classify_exits` uses calendar-minute `TIE_EXCLUDED`. Base TE requires exact `observation_ts` → `AMBIGUOUS` / `exclusion_reason=TIE_EXACT_TIMESTAMP`. Separate classifier.

4. **Hold vs horizon.** Generic `HORIZON_WIN_E4 = 5000` is a candle 50¢ clock-bar rule. Base TE hold-to-expiration is Kalshi settlement only.

5. **`make_observation_id` is game+time+state schema, not ticker.** A dense panel has two team-YES tickers per game at the same candle close. Phase 1 must define a Base TE id that includes `ticker` (compose or extend the pattern). Do not change `observation_id.py` if that would alter existing O_t consumers.

6. **Candle writer schema vs on-disk schema.** Quality flag columns are missing on disk. Use `quality()` on bid/ask/volume.

7. **Settlement function location.** Canonical `settled_yes` lives in `first80.py`. Importing it is reuse, not a FIRST80 semantic change. Do not move or edit it.

8. **`games.home_win` vs Kalshi `result`.** Easy to confuse. Base TE settlement is Kalshi-only. Box `home_win` is a different object.

9. **Existing `TERMINAL_EFFICIENCY_RECON.md` is XIB Phase 0.** This file (`RECON.md`) is Base TE Phase 0. Keep both.

---

## 9. Data gaps

| Gap | Status | Base TE behavior |
|-----|--------|------------------|
| `kalshi_markets.csv` | Missing for all sports | `TERMINAL_MISSING` — not NO |
| Candle quality columns on disk | Absent | `quality()` from bid/ask/vol; do not invent flags |
| PBP pass-through / `time_actual` | Often empty | `UNAVAILABLE` / existing snap; do not invent wall clock |
| Research-query indexes | Not built | Irrelevant; do not depend on them |
| Spread / O-U / team total / Polymarket TOB / L2 / ticks | No tradable source | `DATA_REQUIRED` |
| WNBA / NCAAB Base TE | Out of v1 | not implemented |
| Dashboard UI | Isolated | no frontend work in this waterfall |

PBP and Kalshi candles **are** present for NBA 2025–26. Score snap is not DATA_REQUIRED for that warehouse. Game-clock **exits** still fail closed if a query needs PBP and a given game has no I(t)-visible events (`UNALIGNED` / `UNAVAILABLE` / `DATA_REQUIRED` for that book — not Reach-only relabeled as clock).

Coverage (NBA 2025–26, raw row counts, not yet tradable-filtered):

- games: 1,362
- candle rows: 6,165,183 (Oct 2025 – Jun 2026 partitions)
- PBP rows: 780,137
- Base TE observation count: unknown until Phase 3 (tradable filter + first aligned snap)

---

## 10. Confirmation — no existing code modified

Phase 0 created **one new file**:

```text
docs/research/terminal_efficiency/RECON.md
```

No Python was added. No existing source, test, frontend, XIB/MCD, research_query, FIRST80, or trading file was edited.

**STOP.** Phase 1 (`DATA_CONTRACT.md` + `README.md`) waits for explicit instruction.
