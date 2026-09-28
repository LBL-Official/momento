# Current architecture (audit, 2026-08-30)

This document describes the repository **as it exists**. It is not a target
design. Source of truth: the code, not prior plans.

---

## 1. Languages and build

| Layer | Language | Build |
|---|---|---|
| Platform / research / trading | Rust 1.85, edition 2024 | Cargo workspace (`Cargo.toml`) |
| Public/trading dashboard | Declared React/TS | `dashboard/` is a **stub README only** |
| Research console | `frontend/research-console` | Vite + React, local `:5173` |
| Notebooks | Not a first-class research path | — |

Workspace resolver `2`. `unsafe_code` is forbidden at workspace lint level.

Research HTTP: `apps/research-api` (axum, `127.0.0.1:8787`). Not live trading.

---

## 2. Package layout (source of truth)

```text
apps/
  trading-engine          paper/live composition root
  replay-engine           production replay host (not B1)
  research-collector      research collection
  backtest-runner         legacy candle runner host
  sandbox-validate        Kalshi demo
  prod-auth-validate      production read-only auth
  research-ingest         DATA-INGEST waterstream
  research-w3 … research-w8
  research-b1             B1 CLI (extract + 83¢ search)

crates/
  core, risk, execution, positions, pnl, kalshi, market-data, sports, prediction
  research-data, research-event, research-ingest, research-reconstruction
  research-market, research-sync, research-state, research-path
  research-replay, research-features
  research-strategies, research-backtest, research-execution   # LEGACY_V1 candle

strategies/
  mlb                     live FIRST01 (80/81/89) — frozen for research work
  wnba, nba, ncaab, nfl   stubs
```

`momento-research-backtest` / candle FIRST01 is **LEGACY_V1**. The authorized
research platform is the W0–W8 + B1 reconstruction stack, not that backtester.

---

## 3. Data plane (what actually exists)

Heterogeneous reconstruction lake, SQLite artifacts, gitignored large files.

| Waterfall | Artifact | Role |
|---|---|---|
| Ingest | `Backtesting Suite/Foundation/Ingest/` | Landing / committed (local cron) |
| W4 | price paths | TRADES_ONLY foundation; L2 not invented |
| W5 | `W5/sync.sqlite` | Event↔market sync; no invented L2 |
| W6 | `W6/state.sqlite` | Canonical MLB state + settlement labels |
| W7 | `W7/path.sqlite` | EventMarketPath + TRADE prints |
| W8 | `W8/replay.sqlite` | FIRST01 observational replay |
| B1 (first in-band) | `B1/features.sqlite` | First TRADE in 80–83¢ band (~2,884 games) |
| B1 (first exact 83) | `B1/first83/features.sqlite` | First exact 83¢ TRADE (2,906 games) |

Raw W4–W8 sqlite files are gitignored. JSON/CSV research reports are kept.

**Two 83¢ universes must not be mixed:**

| Universe | Definition | N |
|---|---|---:|
| A | First in-band 80–83¢ TRADE (original B1 extract) | 497 at 83¢ |
| B | First exact 83¢ TRADE, W8-bound else earliest | **2,906** |

Universe B counts (locked): W7 games 3,384; never 83¢ 386; bound contract
never 83¢ 92; unbound earliest-83 313; canonical 2,906.

Fill status for B1 research: `TRADE_PRINT_MODELED`. TRADE ≠ fill. L2 =
`UNAVAILABLE_SOURCE`. Settlement is a **label**, not a predictor.

---

## 4. B1 dependency map

```text
W6 state.sqlite ──┐
W7 path.sqlite  ──┼─► momento-research-features
W8 replay.sqlite ─┘         │
                            ├─ extract (first in-band 80–83)
                            ├─ extract_first83 (first exact 83)
                            ├─ search / search_83 / search_83_opt / search_83_exh
                            └─ FeatureStore (SQLite snapshots)
                                      │
                                      ▼
                            apps/research-b1  (CLI only)
```

CLI binary: `momento-research-b1`

| Flag | Behavior |
|---|---|
| `--extract` / default | First-in-band 80–83 extract → `B1/features.sqlite` |
| `--search` | A1 bucket search |
| `--search-83` | Condition search on 83¢ snapshots |
| `--search-83-opt` | Intersection search (40–49 is seed, not answer) |
| `--search-83-exhaustive` | 1–4 way search, TRAIN/VAL select, TEST lock, BH FDR |
| `--extract-first83` | First exact-83 extract → `B1/first83/` (does not overwrite Universe A) |
| `--first-exact-83` | Point exhaustive search at `first83/` |
| `--validate-83-prospective` | Frozen A–F on post-`2026-06-27` holdout → `B1/prospective83/` |

Shared defaults (`B1RunConfig::defaults`):

- W6/W7/W8 sqlite under `Backtesting Suite/Foundation/`
- Out: `Backtesting Suite/Foundation/B1`

Official chronological split (exhaustive / first-exact-83; **not** the
re-cut 60/20/20 used by older `--search-83`):

- TRAIN `< 2025-10-07`
- VAL `< 2026-05-03`
- TEST through last dated game (observed end `2026-06-27`)

Stake: `qty = 625 // 83 = 7`. Sharpe = game-mean P&L / sample stdev,
unannualized. Independence unit = **GAME**.

---

## 5. Data-flow map (B1 first-exact-83)

```text
W7 path_observations (TRADE prints)
        │
        ├─ filter trade_price_cents == 83
        ├─ if W8 bound (market_id, side) exists: restrict to that contract
        │     if none → skip (bound_no_83)
        └─ else earliest (timestamp, market_id, side, observation_id)
        │
        ▼
one snapshot / game
        │
W6 state at-or-before entry timestamp  (no lookahead)
W7 path at-or-before entry timestamp
        │
        ▼
B1EntrySnapshot  (features + A1 labels + settlement label)
        │
        ▼
FeatureStore  first83/features.sqlite
        │
        ▼
flatten → official chrono split → TRAIN tertiles → enrich/enrich_opt/enrich_exh
        │
        ▼
eval / eval_screen  (HOLD_TO_SETTLEMENT)
        │
        ▼
BH FDR on TRAIN P(mean P&L ≤ 0)   TEST locked after freeze
        │
        ▼
artifacts: report.md, rankings.csv, candidates.json, FDR/bootstrap/permutation JSON

Prospective holdout (`B1_FIRST83_PROSPECTIVE/v1`): same extract definition,
games strictly after `2026-06-27`, frozen candidates only. Artifacts under
`B1/prospective83/`. W6-only games are not first-83 observations.
```

Lookahead protection today: feature extract uses path/state **at or before**
the entry timestamp (`state_at_or_before`, `priced_at_or_before`). Tertiles
fit on TRAIN only. Forbidden predictor keys include settlement, MFE/MAE,
future, PnL, OBI, microprice.

---

## 6. Existing backtest-flow map

There is **no** generic experiment engine, job queue, or dashboard-driven
backtest.

What exists:

1. **B1 CLI search** — in-process, writes files, exits. Not a job.
2. **W8 observational replay** — FIRST01 plugin over EventMarketPath.
   Observational. Not fills. Not a parameterizable experiment object.
3. **Legacy candle backtest** (`momento-research-backtest`) — not the
   research platform. Do not extend it as the OS.

There is no ExperimentDefinition, no dataset registry, no promotion
workflow, no model-health service, no research API.

---

## 7. Test map (B1 / research-features)

| Location | What it protects |
|---|---|
| `crates/research-features/tests/b1_features.rs` | Causality, L2 unavailable, determinism, side orientation |
| `extract_first83.rs` unit tests | Bound-contract earliest 83; unbound earliest 83 |
| `search_83.rs` unit tests | Condition helpers |
| `search_83_exh.rs` unit tests | Leakage denylist; family grouping |
| `search.rs` unit tests | Metrics / split helpers |
| `game_state.rs`, `a1_targets.rs`, `microstructure.rs`, `normalization.rs` | Local invariants |

**Missing for platform lock-in:**

- Characterization of Universe B counts (3,384 / 386 / 92 / 2,906)
- Characterization of official split constants
- Characterization of unconditional HOLD_TO_SETTLEMENT metrics
- Characterization of `start_price_band=40_49` benchmark
- Experiment determinism / TEST-isolation as a first-class experiment object
- API / UI tests (no API / UI)

Existing tests must not be deleted. New tests wrap them.

---

## 8. Configuration

- Trading: `config/` — paper default; live requires three explicit gates.
- Research paths: hardcoded defaults in `B1RunConfig` / CLI flags.
- No experiment-level config object.
- No hidden live arming from research crates (research crates do not talk
  to Kalshi order APIs).

Secrets: `.env`, `credentials*`, keys gitignored. Do not put venue keys in
any future frontend.

---

## 9. Frontend / deployment

| Surface | Status |
|---|---|
| `dashboard/` | Stub. Trading observability later. Not research. |
| Public site `momentosystems.com` | Separate. Must not host research. |
| Research console | Local `frontend/research-console` → `127.0.0.1:5173`. Not public. |
| AWS paper deploy | Milestone 7 done (trading paper host) |
| Research ingest cloud | `LOCAL_CRON_ONLY` — do not deploy AWS ingest |

---

## 10. Locked B1 reference results (Universe B)

Must remain reproducible. Fill = `TRADE_PRINT_MODELED`. Not production.

**Unconditional first-83 HOLD_TO_SETTLEMENT**

| Split | N | WR | EV¢ | P&L $ |
|---|---:|---:|---:|---:|
| ALL | 2,906 | 83.3% | +0.28 | +56 |
| TRAIN | 1,699 | 83.1% | +0.11 | +13 |
| VAL | 494 | 82.2% | −0.81 | −28 |
| TEST | 713 | 84.4% | +1.43 | +71 |

**40–49 benchmark:** TRAIN +3.42¢ n=486 · VAL +1.40¢ n=141 · TEST +2.41¢
n=233 · FDR q=0.17 · **CANDIDATE** (not approved).

**VAL-selected simple primary:** `inning_grp=7 & p_max_vs_83=PEAK_AT` —
CANDIDATE, not a production rule.

3-way cells that the exhaustive classifier labeled ROBUST were selected
from 6,128 tests and remain hypotheses.

Artifacts: `Backtesting Suite/Foundation/B1/first83/`
(do not overwrite `B1/features.sqlite`).

---

## 11. Research Engine v1 (now in tree)

Present: dataset/experiment/model registry (`crates/research-engine`),
`ExperimentDefinition`, async jobs, `apps/research-api`, React console,
promotion gate (CANDIDATE ↛ PRODUCTION), imported B1 first-83 (2,906),
orchestration clocks (all disabled / manual).

Still a **snapshot HOLD_TO_SETTLEMENT wrap**, not a new tick replay clock.
B1 search is not rewritten as `Strategy.on_event`. Live execution is a
typed hole (`LiveExecutionGate::may_submit() == false`). L2 remains
`UNAVAILABLE_SOURCE`. Production count is 0.
