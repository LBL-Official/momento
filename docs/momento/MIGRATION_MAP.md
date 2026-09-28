# Momento Systems — Migration Map

Phase 0 recon recorded here. Action vocabulary:

- **LEAVE** — stay put; ownership recorded.
- **ADAPTER** — Phase 2 façade over an existing API.
- **POINTER** — registry paths only.
- **NEW** — shell / placeholder. No fake analytics.
- **DO NOT MOVE** — physical relocation would break locks or live paths.

Do not duplicate logic. Do not overwrite locked research. Do not rewrite
working products for aesthetics. Use `git mv` only if a later phase
justifies a physical move.

## Conflicts (do not “fix” by rewrite)

1. Austin `#/austin` is Position Stratification. DRE is `:5191` / `/dre`.
2. `crates/risk` is not Austin DRE.
3. SuperASI computes path/terminal analysis; second-round systems own models.
4. `base_terminal_efficiency` is measurement; XIB/MCD is in-house odds.
5. Austin opponent-YES@40 maker ≠ YES + BUY NO taker.
6. N universes 1182 / 936 / 905 / 604 / 1230 / 797 / 280 must not mix.
7. “Momento Systems” name: program board ≠ National Champion.
8. `ROLLER/roller/maintenance` is ingest, not System Maintenance.
9. DRE product UI is `:5191`; dre-v2…v7 / PADE are artifacts.
10. Research Vite apps collide on 5179–5182. Product ports stay.
11. `nba_path_fe` Family E must not enter Austin `enter_skip` or Austin query.
12. Research FIRST80 ≠ live FIRST01.

## Component rows

### ROLLER warehouse

- **Current path:** `ROLLER/roller/warehouse/`, `ROLLER/data/`
- **Purpose:** Canonical parquet memory, GameMarketLink, Confirm & Run execute
- **System:** `database`
- **Action:** LEAVE + ADAPTER
- **Dependencies:** ingest, identity, settlement
- **Tests:** warehouse / frontend_contract suites
- **Risk:** Phase 21 forbidden; Confirm & Run path must stay
- **Status:** COMPLETE

### ROLLER research_query

- **Current path:** `ROLLER/roller/research_query/`
- **Purpose:** Generic empirical compiler / jobs / indexes
- **System:** `database`
- **Action:** LEAVE
- **Dependencies:** warehouse, `first80.py` frozen objects
- **Tests:** `ROLLER/tests/test_*research_query*`
- **Risk:** Do not route FIRST80 through a new generic index rewrite
- **Status:** COMPLETE

### Base terminal efficiency

- **Current path:** `ROLLER/roller/base_terminal_efficiency/`
- **Purpose:** Empirical entry-bar attach on Confirm & Run
- **System:** `database` (measurement)
- **Action:** LEAVE
- **Dependencies:** PIT `available_at < t`
- **Tests:** `test_terminal_efficiency_*.py`
- **Risk:** Do not relabel as Game Modeling
- **Status:** COMPLETE as measurement

### first80.py

- **Current path:** `ROLLER/roller/research/first80.py`
- **Purpose:** Frozen touch-80 / T40 research rule
- **System:** `signal_generation` (research) + `database` (loader)
- **Action:** LEAVE. DO NOT EDIT
- **Dependencies:** asked-six CSV, game window
- **Tests:** `test_first80_objects.py`
- **Risk:** Any edit changes locked research
- **Status:** COMPLETE frozen

### SuperASI

- **Current path:** `ROLLER/roller/superasi/`, `frontend/roller-terminal/src/superasi/`
- **Purpose:** A→B→Final→ITI decomposition
- **System:** `data_analysis`
- **Action:** LEAVE + ADAPTER
- **Dependencies:** ROLLER labs / frozen execute
- **Tests:** SuperASI seed / path_windows suites
- **Risk:** Do not move into Path/Game Modeling
- **Status:** COMPLETE research

### STAX

- **Current path:** `ROLLER/roller/stax/`
- **Purpose:** Multi-strategy research composition
- **System:** `data_analysis` submodule
- **Action:** POINTER
- **Dependencies:** research_query / frozen execute
- **Tests:** STAX suite
- **Risk:** Do not invent a stack EV
- **Status:** COMPLETE research

### Research Engine v1

- **Current path:** `crates/research-engine/`, `apps/research-api/`, `frontend/research-console/`
- **Purpose:** B1 first-exact-83 research OS
- **System:** `data_analysis` submodule
- **Action:** POINTER. Separate `:8787`
- **Dependencies:** research-features
- **Tests:** research-engine crate tests
- **Risk:** Do not fold into ROLLER
- **Status:** COMPLETE as separate OS

### Historical W0–W8 crates

- **Current path:** `crates/research-*`
- **Purpose:** MLB reconstruction / replay
- **System:** `database` submodule
- **Action:** LEAVE. Do not start W9
- **Status:** COMPLETE for observed window

### v4b / v4c greeks

- **Current path:** `ROLLER/roller/v4b/`, `ROLLER/roller/v4c/`
- **Purpose:** Empirical greek measurements
- **System:** `data_analysis` submodule
- **Action:** POINTER
- **Status:** Research measurement

### Terminal efficiency XIB/MCD

- **Current path:** `apps/terminal-efficiency/`
- **Purpose:** Frozen in-house P(win)
- **System:** `in_house_odds_modeling`
- **Action:** POINTER
- **Dependencies:** frozen manifests / hashes
- **Tests:** `apps/terminal-efficiency/tests/test_frozen_loader.py`
- **Risk:** Phase 7 / ROLLER query consumption not authorized
- **Status:** PARTIAL

### Fair odds / Terminito X

- **Current path:** none
- **Purpose:** External implied probability
- **System:** `fair_odds_modeling`
- **Action:** NEW placeholder
- **Status:** NOT_IMPLEMENTED

### Choosin Texas universe / EV

- **Current path:** `ROLLER/roller/choosin_texas/`, `frontend/choosin-texas/`
- **Purpose:** 80/40 economics, path ladder, locked N
- **System:** `trade_breakdown`
- **Action:** LEAVE + ADAPTER
- **Dependencies:** TABLES.md, asked-six CSV
- **Tests:** `test_choosin_texas.py`
- **Risk:** Do not rescan; do not remount
- **Status:** COMPLETE

### Choosin Dallas

- **Current path:** `ROLLER/roller/choosin_texas/dallas.py`, `#/dallas`
- **Purpose:** NBA 2Q/3Q deterioration snapshots
- **System:** hosted in Choosin; **points** at `data_modeling`
- **Action:** POINTER
- **Status:** COMPLETE research

### Choosin Book

- **Current path:** `research/choosin_texas/library/.../book.json`, `#/book`
- **Purpose:** 2026-27 research-registered 80/40 1-lot book
- **System:** `trade_breakdown`
- **Action:** LEAVE. Do not edit book.json
- **Status:** RESEARCH_REGISTERED ≠ LIVE_ARMED

### Austin PCA+KNN

- **Current path:** `ROLLER/roller/austin/`, `#/austin`
- **Purpose:** Neighborhood / stratum / conditional EV query
- **System:** `position_stratification`
- **Action:** ADAPTER. No git mv
- **Dependencies:** N=604 locks, feature registry
- **Tests:** `test_austin.py`
- **Risk:** Shared package with DRE
- **Status:** PARTIAL

### Austin Risk / DRE experiments

- **Current path:** `ROLLER/roller/dre/`, `frontend/dynamic-risk-engine/`, `#/austin/risk` pointer
- **Purpose:** Persistence, downfall, hazard research. V1 portfolio objective in `research/dre/`
- **System:** `dynamic_risk_engine`
- **Action:** ADAPTER + POINTER
- **Tests:** `test_austin_{experiments,persistence,downfall_states,hazard_recovery}.py`
- **Risk:** Locked hashes. Not execution policy
- **Status:** PARTIAL

### DRE v2–v7 / PADE

- **Current path:** `frontend/dre-v2` … `dre-v7`, `frontend/pade-v1`
- **Purpose:** Static DRE research dashboards
- **System:** `dynamic_risk_engine` research_paths
- **Action:** POINTER
- **Status:** Artifact only

### Austin hedge / Fort Worth

- **Current path:** `ROLLER/roller/austin/hedge.py`, `fort_worth.py`, `#/fort-worth`
- **Purpose:** 41/42 opponent-YES@40 maker hypothesis; read-only policy
- **System:** hedge → `hedging_analysis`; policy points at `signal_generation` + `position_management`
- **Action:** POINTER
- **Risk:** Not the YES+BUY-NO-taker design
- **Status:** PARTIAL / policy only

### Ballhog (Hedging Analysis product Frontend)

- **Current path:** `frontend/ballhog/`, `ROLLER/roller/ballhog/`, `research/ballhog/`
- **Purpose:** WHEN / q* / ρ* / Δ* exposure-removal optimizer
- **System:** `hedging_analysis` product Frontend on `:5192`. Not a 20th system.
- **Action:** POINTER. Research only. Does not submit.
- **Status:** RESEARCH_ONLY

### BDR (Hedging Analysis write-up library)

- **Current path:** `research/bdr/`, `docs/research/BDR_80_40_BARRIER_DEFENSE.md`, `docs/research/DUAL_LEG_MAKER_LOCK_POSITION_MANAGEMENT.md`, `docs/research/BDR_LIQUIDATION_CORRIDOR.md`, `docs/research/BDR_ACQUISITION_CORRIDOR.md`, `docs/research/BDR_77_RIDGE.md`, `docs/research/BDR_STAGED_ACQUISITION.md`, `frontend/momento-systems` `#/bdr`
- **Purpose:** 80→40 barrier-defense / synthetic-exit write-ups
- **System:** `hedging_analysis` library. Not the product Frontend. Not an 18th system.
- **Action:** POINTER. Research only. Does not submit.
- **Status:** RESEARCH_ONLY

### nba_path_fe

- **Current path:** `ROLLER/roller/nba_path_fe/`, `research/nba_path_trade_fe/`
- **Purpose:** Failed enter/skip filter; Family E hedge features
- **System:** `data_modeling` + `hedging_analysis`
- **Action:** POINTER. DO NOT expand
- **Tests:** `test_nba_path_fe.py`
- **Status:** INACTIVE_NO_RESIDUAL_EDGE

### nba_8040_reverse_features

- **Current path:** `ROLLER/roller/nba_8040_reverse_features/`
- **Purpose:** Q2 vs Q3 reverse features on N=604
- **System:** `position_stratification`
- **Action:** POINTER
- **Tests:** `test_nba_8040_reverse_features.py` (SHA256 locks)
- **Status:** Research

### FIRST80 hedge audit UIs

- **Current path:** `frontend/first80-*`, `frontend/a1-hybrid-hedge`
- **Purpose:** Static hedge / exit / fee audits
- **System:** `hedging_analysis` research_paths
- **Action:** POINTER
- **Status:** Artifact only

### Relative value / tk_relative_value_v1

- **Current path:** `ROLLER/roller/momento/relative_value.py`, `ROLLER/roller/momento/tk_ultra.py`, `ROLLER/roller/tk_ultra/`, `research/tk_ultra/`, `frontend/momento-systems` `#/tk-ultra`
- **Purpose:** Pluggable hedge richness. GENERIC_RV signed ticks plus BINARY_COMPLEMENT_V0 route/relationship/budget.
- **System:** `relative_value_hedging`
- **Action:** POINTER
- **Status:** PARTIAL. Formula + TK Ultra desk. Not market truth. Missing = UNAVAILABLE. Not program 13 RV HFT.

### Position current vs target

- **Current path:** none
- **Purpose:** Desired exposure
- **System:** `position_management`
- **Action:** NEW
- **Status:** NOT_IMPLEMENTED

### crates/positions

- **Current path:** `crates/positions/`
- **Purpose:** Fill-authoritative MLB/WNBA tracker
- **System:** reference only (not the NBA box)
- **Action:** LEAVE. Do not treat as an NBA bot
- **Status:** COMPLETE for MLB/WNBA live only

### Vital / trading-engine / crates/risk

- **Current path:** `ROLLER/roller/vital/`, `apps/trading-engine/`, `crates/risk/`, `strategies/mlb/`, `strategies/wnba/`
- **Purpose:** Existing MLB/WNBA live path
- **System:** **reference_only** — not `algorithmic_execution` implementation
- **Action:** LEAVE. DO NOT MODIFY MLB 001. Do not adapt `/vital` as the NBA bot
- **Tests:** Vital integration + risk crate tests (must keep passing)
- **Risk:** Accidental live arming; false claim that MLB is the NBA desk
- **Status:** MLB production exists. NBA bot does not.

### NBA algorithmic execution contract

- **Current path:** `ROLLER/roller/momento/execution.py`
- **Purpose:** Schemas, reserved `nba-first80-001` identity, dry-run hooks
- **System:** `algorithmic_execution`
- **Action:** NEW contract boundary
- **Status:** NOT_IMPLEMENTED

### strategies/nba

- **Current path:** `strategies/nba/README.md`
- **Purpose:** Workspace stub
- **System:** future Oct 2 bot, not this freeze
- **Action:** LEAVE stub
- **Status:** NOT_IMPLEMENTED

### Jump

- **Current path:** `ROLLER/roller/jump/drive.py`, roller-terminal `?app=jump`
- **Purpose:** Data Modeling filesystem (ROLLER + SuperASI pointers)
- **System:** `data_modeling`
- **Action:** POINTER
- **Status:** PARTIAL. Bot HTTP remains for Vital until backend migration. No bot UI.

### Systimo

- **Current path:** `ROLLER/roller/systimo/`, `frontend/systimo/`
- **Purpose:** System Maintenance product Frontend (connection registry)
- **System:** `system_maintenance`
- **Action:** POINTER
- **Status:** PARTIAL. CSV registry + `/systimo` on `:8791`. Not a 20th system.

### Momento LS

- **Current path:** `ROLLER/roller/ls/`, `frontend/momento-ls/`
- **Purpose:** Observe `momento-live.service`
- **System:** `system_maintenance` (observe adapter, not the product UI)
- **Action:** ADAPTER
- **Status:** PARTIAL

### ROLLER maintenance update.py

- **Current path:** `ROLLER/roller/maintenance/update.py`
- **Purpose:** Offline warehouse refresh pipeline
- **System:** `data_ingestion`
- **Action:** POINTER
- **Risk:** Name collision with System Maintenance
- **Status:** PARTIAL

### Ingest scripts / research-ingest / auto_roller

- **Current path:** `ROLLER/scripts/ingest_*.py`, `ROLLER/roller/ingest/`, `crates/research-ingest/`, `ROLLER/roller/auto_roller/`
- **Purpose:** Canonical handoff into ROLLER
- **System:** `data_ingestion`
- **Action:** ADAPTER + POINTER
- **Status:** PARTIAL. Autoingest / Autojest not built

### Trade Reconciliation

- **Current path:** `ROLLER/roller/momento/execution.py` `empty_reconciliation`, `PositionReconciliation` contract
- **Purpose:** Reconcile intended trades against observed fills and exchange state
- **System:** `trade_reconciliation`
- **Action:** LEAVE stub. Observe-only. Not Vital. Not an OMS.
- **Status:** NOT_IMPLEMENTED

### System Orchestration

- **Current path:** registry only
- **Purpose:** Runtime job and pipeline sequencing
- **System:** `system_orchestration`
- **Action:** LEAVE stub. Distinct from champion `momento_systems`.
- **Status:** NOT_IMPLEMENTED

### config/live.toml

- **Current path:** `config/live.toml`
- **Purpose:** Existing MLB live gates
- **System:** MLB live only. Not the NBA `algorithmic_execution` box.
- **Action:** LEAVE. Do not touch
- **Risk:** Already contains `ENABLE_LIVE_TRADING`
- **Status:** Production MLB only
