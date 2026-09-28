# PADE V1 — Repository Audit

Program: `MOMENTO_POSSESSION_ADJUSTED_DETERIORATION_ENGINE_V1`  
Scope: research only. Live execution unchanged.  
Date: 2026-09-03  

This audit records **paths that exist in the repository**. No paths were invented.

---

## Verdict of reconnaissance

PADE V1 is a **new derived engine**. Nothing named PADE exists yet.

The closest prior work is:

- Frozen FIRST-80 audit (`nba_80_40_execution_audit.py`)
- FIRST-80 V1/V2 fee/hedge research (do not edit)
- Research Engine V2 Test 2 possession overlay (MODELED walls)
- Game Path V2/V4 `PERIOD_BOUNDED_LINEAR_GAME_CLOCK` (MODELED walls)

PADE V1 must **not** treat those modeled walls as observed fact.  
Observed per-play wall clock (`timeActual`) is now available on the live CDN feed.

---

## 1. Frozen FIRST-80 universe (do not redefine)

| Role | Path |
|------|------|
| Builder (do not rerun as source of truth) | `apps/nba-data/scripts/nba_80_40_execution_audit.py` |
| Frozen candidates | `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/first80_execution_audit/candidates.json` |
| V1 loader (import only) | `apps/ncaab-data/scripts/first80_realistic_exit_fee_audit_v1.py` → `load_frozen` / `reproduce_path` |
| Games table | `Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba/games/nba_games.parquet` |
| Markets | `Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba/markets.parquet` |

Gates (must reproduce exactly):

| Sport | n | survivors | stops | leaks | surv % |
|-------|--:|----------:|------:|------:|-------:|
| NBA | 1230 | 910 | 320 | 0 | 73.9837 |

Definition (unchanged):

- Universe: settled `KXNBAGAME` events
- Game window: `game_date + 16h` … `min(close_ts, game_date + 52h)`
- FIRST-80: first tradable `yes_bid_close >= 80¢` after a prior tradable close `< 80¢`
- Entry price label: `entry_price_e4 = 8000` (candle proxy, not a fill)
- Split: TRAIN `game_date <= 2025-12-31`, VALIDATION `<= 2026-03-15`, OOS after

PADE must call `load_frozen("nba")` + `reproduce_path`. Halt on mismatch.

---

## 2. NBA play-by-play

| Dataset | Path | Files | Wall clock |
|---------|------|------:|------------|
| Stats V3 | `.../warehouse/raw/nba_stats/pbp_v3/{nba_game_id}.json` | 1352 | period + game clock only |
| Live CDN | `.../warehouse/raw/nba_stats/pbp_live/{nba_game_id}.json` | 1352 | **`timeActual` on every action** (780,137 / 780,137) |
| Boxscore summary | `.../warehouse/raw/nba_stats/boxscore_summary/{nba_game_id}.json` | 1347 | `gameTimeUTC` = scheduled tip, not observed tip |
| Ingest live | `apps/nba-data/scripts/nba_pbp_live_timeactual_ingest.py` | | |
| Ingest V3 | `apps/nba-data/scripts/nba_pbp_overnight_ingest.py` | | |

Live action types (not V3 names): `2pt`, `3pt`, `rebound` (`defensive`/`offensive`), `turnover`, `freethrow`, `foul`, `period`, `jumpball`, `substitution`, `timeout`, `steal`, `block`, `violation`, `heave`, `game`.

Clock field: ISO duration `PT12M00.00S` (counts down).  
`periodType`: `REGULAR` / overtime.  
`possession`: NBA team id (integer).  
`teamTricode`: offensive/acting team when present.

---

## 3. Kalshi → NBA game mapping

| File | Path |
|------|------|
| Crosswalk | `.../warehouse/normalized/nba/pbp/game_crosswalk.json` |
| FIRST-80 index | `.../derived/nba/first80_multidimensional_exit_hedge_fee_v2/pbp/first80_pbp_index.json` |

Crosswalk: 1362 rows, 1352 MATCHED, 10 UNMATCHED (`game_date + team_pair`).  
FIRST-80 with `nba_game_id` + live `timeActual`: **1223 / 1230**.

Unmatched FIRST-80 (no invented IDs):

- `KXNBAGAME-26JAN24GSWMIN`
- `KXNBAGAME-26APR14MIACHA`
- `KXNBAGAME-26APR14PORPHX`
- `KXNBAGAME-26APR15GSWLAC`
- `KXNBAGAME-26APR15ORLPHI`
- `KXNBAGAME-26APR17CHAORL`
- `KXNBAGAME-26APR17GSWPHX`

These remain `UNRESOLVED` in PADE. They are not dropped from the universe.

---

## 4. Kalshi 1-minute candles

| Layer | Path |
|-------|------|
| Normalized | `.../warehouse/normalized/nba/candles_1m/month=YYYY-MM/{TICKER}.parquet` (2724 files) |

Timestamp: `end_period_ts` = Unix seconds UTC (candle **end**).  
Prices: `yes_bid_{open,high,low,close}_e4`, `yes_ask_close_e4`, `price_close_e4`.  
Tradability: `nba_80_40_execution_audit.quality` (bid/ask, spread ≤ 10¢, volume or prior quality).

V1 reader (import only): `load_ticker_quotes`, `subsequent_tradable`, `attach_scan_window`.

---

## 5. Existing possession / alignment code (reuse rules, not walls)

| Component | Path | PADE stance |
|-----------|------|-------------|
| V2 Test 2 possessions | `apps/nba-data/scripts/research_engine_v2_test2/possessions.py` | Reuse **boundary logic**, not V3 type names; do not copy `modeled_wall_ts` |
| V2 Test 2 output | `.../derived/nba/momento_research_engine_v2_test2/possessions.parquet` | Read-only reference; do not overwrite |
| GPE V2/V4 aligner | `apps/nba-data/scripts/game_path_engine_v4/pbp_align.py` | `PERIOD_BOUNDED_LINEAR_GAME_CLOCK` is a **PROXY**. Not PADE primary |
| GPE V2 audit | `.../momento_game_path_engine_v2/time_alignment_audit.json` | Historical modeled-confidence only |

PADE primary wall clock: live `timeActual` (OBSERVED, grade A).  
Fallback if a game lacks live PBP: no invented interpolation as “observed.” Mark `UNRESOLVED`.

---

## 6. Dashboard infrastructure to clone

Existing `frontend/first80-*` apps are single-file Vite/React SPAs:

- Fetch `/data/dashboard.json`
- Dark theme (`#0b0d10`, gold `#c8a25a`)
- Ports 5176–5182 occupied; **5183** is free

Clone pattern: `frontend/first80-multidimensional-exit-hedge-fee-v2/` → `frontend/pade-v1/`.

---

## 7. Python environment

`/tmp/momento-nba-venv/bin/python` — pyarrow 25, scikit-learn 1.9, numpy, pandas.

---

## 8. What PADE must not touch

- FIRST01, Risk, live execution, production config
- Hedge V1–V4 engines and derived dirs
- `first80_realistic_exit_fee_audit_v1.py`
- `first80_multidimensional_exit_hedge_fee_v2.py`
- Frozen `candidates.json`
- `apps/nba-data/scripts/capture_program_v1/fee_models.py`
- Test2 / Game Path derived artifacts (read only)

---

## 9. Proposed implementation plan (from actual structure)

1. **Gate A:** `V1A.load_frozen("nba")` + `reproduce_path` → 1230/910/320/0.
2. **Timeline + PBP:** parse live JSON; `elapsed_game_seconds` from period + countdown clock; `real_time_start` = first period-start `timeActual` (observed), not `gameTimeUTC`.
3. **Possession engine:** new live-schema builder (explicit `rebound|defensive`). Write `03_possessions.parquet`. Do not reuse Test2 walls.
4. **Alignment:** as-of join candle `end_period_ts` → last/next `timeActual`. Confidence HIGH/MEDIUM/LOW/UNRESOLVED. Never drop unresolved. Never linear-map 48 min → 2.5 h.
5. **Panel:** FIRST-80 trade × post-entry possession; as-of A1/A2 candles; `market_age_seconds`.
6. **Features / labels / remaining-possessions R1–R3** with leakage audit.
7. **Nested models B0–M5**, game-level chronological splits, OOS metrics.
8. **Dashboard** `frontend/pade-v1` port 5183.
9. **Report + verdict.** NCAAB is a stub (no joinable PBP).

Output root:

`Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/possession_adjusted_deterioration_engine_v1/`
