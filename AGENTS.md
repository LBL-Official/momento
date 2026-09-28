# AGENTS.md
# Keep this file in sync with docs/architecture/.

Momento is a production-grade algorithmic sports trading platform.

**Systems roadmap (canonical):**
`docs/architecture/MOMENTO_SYSTEMS_ROADMAP.md`.
Program board: `docs/architecture/MOMENTO_SYSTEMS_PROGRAM_BOARD.md`.
Agent rule: `.cursor/rules/17-momento-roadmap.mdc`.
October 1, 2026 is dual-market ingest + Autoingest for NBA/NCAAB, not
Terminito / RV HFT / agentic traders. Notion is a readable copy only.

**19-system bracket (ownership architecture):**
`docs/momento/ARCHITECTURE.md`. Freeze:
`docs/momento/ARCHITECTURE_FREEZE_V0.md`. Machine registry:
`momento/registry/systems.yaml`. Package + API:
`ROLLER/roller/momento/` and `/momento/*` on `:8791`. Dashboard is a
separate Vite instance: `frontend/momento-systems` on `:5190`. It is
not a product tab inside `frontend/roller-terminal`. Algorithmic
Execution is `NOT_IMPLEMENTED` (NBA Bot 001 worker `momento-nba-001.service`
collects data in SHADOW; the deployed build links no submission adapter,
and the source adapter is fixture/demo only with production orders
compiled out; see
`docs/operations/NBA_001.md`). Its Frontend is a
momento_page, not Vital `:5180`. MLB 001 is reference_only.
`LIVE EXECUTION = FALSE`. Hedging Analysis Frontend is Ballhog
`:5192` (exposure-removal optimizer, not live, not a 20th system).
BDR `#/bdr` remains the write-up library.
Relative Value Hedging Frontend is TK Ultra `#/tk-ultra`
(GENERIC_RV + BINARY_COMPLEMENT_V0, not live, not a 20th system).
Agent rule: `.cursor/rules/23-tk-ultra.mdc`. Bottom-layer
infrastructure: Data Ingestion, System Maintenance (Systimo Frontend
`:5193`; Momento LS remains the live-host observe adapter), Trade
Reconciliation (observe-only, not Vital), System Orchestration
(not the champion Momento Systems box). Agent rule:
`.cursor/rules/20-momento-systems.mdc`. Systimo:
`.cursor/rules/24-systimo.mdc`.
DRE objective SSOT: `research/dre/PORTFOLIO_OBJECTIVE_V1.md`.
Agent rule: `.cursor/rules/21-dre.mdc`.
This is not a replacement for the 16-row program board.

## Current Objective

Build and validate the MLB trading system first.

**Vital (canonical MLB 001 owner):** Execution control plane. ROLLER and
SuperASI stay research. Jump frontend is the Data Modeling Drive and
does not call Vital. MLB 001 (`mlb-001`, alias `mlb-bot-one`) is the
first Vital bot. Package + API: `ROLLER/roller/vital/` and `/vital/*`.
Dashboard is a separate Vite instance: `frontend/vital-terminal` on
`:5180`. It is not a product tab inside `frontend/roller-terminal`.
ROLLER can open that origin. Disk library:
`research/vital/`. Recon: `research/vital/RECON.md`. Ownership:
`research/vital/OWNERSHIP.md`. Agent rule: `.cursor/rules/16-vital.mdc`.
Phases 2–9 + SuperASI ITI are implemented in repo. Production systemd
writes stay fail-closed (`VITAL_AWS_CONTROL` unset). Do not SSM
start/stop/restart/kill `momento-live.service` unless control is
explicitly enabled. Do not move `apps/trading-engine` or
`strategies/mlb`. Do not change live FIRST01 / 80/81/83/89.
Vital also owns the MLB 001 execution ledger
(`research/vital/bots/mlb-001/execution/`, `/vital/bots/{id}/execution/*`):
observed fills and reconstructed trades only. It does not invent fills
or submit orders. Recon: `research/vital/EXECUTION_LEDGER_RECON.md`.
Live-service integration proof (L1–L8, suites A–D):
`research/vital/LIVE_SERVICE_INTEGRATION.md`. `RUNNING ≠ HEALTHY ≠
EXECUTING`. Demo writes only. No production test order.

**Systimo (System Maintenance Frontend):** Connection registry, graph,
structured query, immutable artifacts, allowlisted APPLY. Package + API:
`ROLLER/roller/systimo/` and `/systimo/*` on `:8791`. Dashboard is a
separate Vite instance: `frontend/systimo` on `:5193`. It is not a
product tab inside `frontend/roller-terminal` or `:5190`. CSV SSOT:
`research/systimo/`. Registers tunnels; does not own Austin/Choosin/Vital
data. Jump research-context: `/jump/research-context/austin|choosin`
(QUERY only). Does not submit. Does not start/stop
`momento-live.service`. How-to: `docs/operations/SYSTIMO.md`. Agent rule:
`.cursor/rules/24-systimo.mdc`.

**NBA Bot 001 (`nba-001`, FIRST78_67):** Worker `momento-nba-001.service`
(`apps/nba-001`, strategy crate `strategies/nba`, state
`/var/lib/momento/nba-001`). Production public data + GET-only account
observe, contract-wise 78 up-cross in Q2/Q3 (Kalshi `live_data` clock),
admission blockers, local intents, SHADOW opponent-complement hedge path.
The deployed build links no submission adapter. The source has an
isolated NBA order adapter, lifecycle, and reconciler (`venue.rs`,
`executor.rs`, `lane.rs`) tested on fixtures and on the Kalshi demo. Production
orders are compiled out (`PRODUCTION_ORDERS_COMPILED = false`), and
fractional production fills are unsupported (`FRACTIONAL_FILLS_UNSUPPORTED`).
Deploying an adapter build to the production host, or compiling production
orders in, needs a resolved contract and explicit owner approval. Execution
contract `research/vital/bots/nba-001/strategy/execution_contract.json` has
six `UNRESOLVED_OWNER_INPUT` fields; entries stay blocked
(`EXIT_CAPACITY_UNBOUNDED`, `SHARED_COLLATERAL_UNACCOUNTED`,
`LIVE_GATES_UNSET`). Fees are verified for KXNBAGAME at multiplier 1;
routing follows the market `exchange_index`. Desk `#/execution/nba` on `:5190` reads
status over read-only SSM. How-to: `docs/operations/NBA_001.md`. Does not
touch `momento-live.service`. Does not move funds.

**Momento LS:** Direct observe of `momento-live.service`. Not Vital.
Not the System Maintenance product UI (that is Systimo).
Package + API: `ROLLER/roller/ls/` and `ROLLER/scripts/ls_api.py`
(`:8792`, `/health` `/observe`). Dashboard is a separate Vite instance:
`frontend/momento-ls` on `:5181`. It is not a product tab inside
`frontend/roller-terminal` or `frontend/vital-terminal`. Read-only SSM.
Does not submit. Does not set `VITAL_AWS_CONTROL`. Does not change live
FIRST01 / 80/81/83/89. How-to: `docs/operations/MOMENTO_LS.md`.

**Choosin Texas:** FIRST80 80/40 NBA + NCAAB four-partition research
desk. Package + API: `ROLLER/roller/choosin_texas/` and
`/choosin-texas/*` on the ROLLER research API (`:8791`). Dashboard is a
separate Vite instance: `frontend/choosin-texas` on `:5182`. It is not a
product tab inside `frontend/roller-terminal`. Reconstructs locked
TABLES.md integers; does not rescan. asked-six (1182) ≠ derived four
(936). `#/asked-six` is the asked-six page (NBA 2Q/3Q, NCAAB 1H
second 10 / 2H first 10, WNBA 2Q/3Q) for FIRST80/75/77/81/83.
FIRST81 asked-six 1193 (four 940). FIRST83 asked-six 1243 (four 973).
OOS is CSV `dataset_split`. `#/texas-75` is FIRST75 on the same four slices (N=913;
75/25–75/50 on 913; 75/55 entry&lt;81 N=868; EV = 25S − L(1−S),
L = 75 − stop). `#/texas-77` is FIRST77 on the same four slices (N=933;
77/25–77/50 on 933; 77/55 entry&lt;83 N=883; EV = 23S − L(1−S),
L = 77 − stop). `#/texas-60` is FIRST80 80/60 on the same derived
four (N=936; T60 = post-entry min ≤ 60; s_L = 0; EV = 20S − 20(1−S)).
`#/paired` replays that same 936 for 80/40 and 80/65 at equal flat-stop
risk, plus `CAPITAL_6PCT_CAP3` (6% entry premium, 3 positions, 18% premium
cap, America/New_York sessions), plus `PLANNED_RISK_CAP3` (80/40 sized by
the tighter of 6% premium and 2% planned stop risk; 80/65 stays at 6%
premium; both cap at 3 positions). The 2% figure is planned stop risk. A
gap is not cut to 2%. The cap is three open positions for the whole book.
820 and 865 are cumulative admissions, not a count of positions open at once.
Through-close ≠ fill. Execution validation on `#/paired` keeps that
candle result as the reference and does not publish a fill-based portfolio
P&L. Prospective observation follows the candle-close signal. A live-quote
trigger is a separate specification. A hypothetical 80¢ intent is a record
after the close is received, not an order. Entry lifetime and the stop
response stay unresolved. Public quotes, depth, trades, and candle closes
are being collected; fills and returns stay blocked. The collector does
not submit. 80/40 stays the research candidate. Neither book is live.
Terminal W/N ≠ 80/40 S. Path-ladder ledger EV (25–55) is
candle-path theoretical, not a fill. `/choosin-texas/nba-path` is NBA
T40 clock + margin only. `#/dallas` is NBA 2Q/3Q deterioration
snapshots, not a live quote. `#/book` / `/choosin-texas/book` is the
2026-27 research-registered NBA 2Q regular-season 80/40 1-contract
book (`RESEARCH_REGISTERED ≠ LIVE_ARMED`). `#/austin` / `/austin/*`
is the NBA 2Q/3Q PCA+KNN query desk (`ROLLER/roller/austin/`,
`research/austin/`). Query mode only; live feed UNAVAILABLE. Sizing
is 3/4/5% of $20,000, never BUY/SKIP. DRE is a separate desk:
`frontend/dynamic-risk-engine` on `:5191`, `/dre/*` on `:8791`.
It wraps Choosin Texas + Austin only. `#/austin/risk` is a pointer.
`#/fort-worth` is a read-only
policy + contract. `#/katy` is a labeled experiment index; each
experiment is `#/katy/{slug}`. `#/sugarland` is Sugarland
(`SUGARLAND_PREGAME_V1`), a pregame quote study for NBA and NCAAB.
It is not FIRST80 936 and not Austin 604. WNBA and MLB stay in
`research/sugarland/v1/`. Research only; execution disabled.
Houston lock is declared, not a fill.
Search is not a freeze. Neither submits. Does not submit. Does not
change live FIRST01 / 80/81/83/89. How-to:
`docs/operations/CHOOSIN_TEXAS.md`. Agent rule:
`.cursor/rules/18-choosin-texas.mdc`.

**DRE (Dynamic Risk Engine):** Post-entry hold-reason research desk.
Package + API: `ROLLER/roller/dre/` and `/dre/*` on `:8791`.
Dashboard is a separate Vite instance: `frontend/dynamic-risk-engine`
on `:5191`. Objective page: `#/objective`. Not a product tab inside
`frontend/roller-terminal` or Choosin Texas. Adapter only: Choosin
Texas Trade Breakdown + Austin Position Stratification / experiment
artifacts. V1 aim: preserve `αP > 0`, then `ΔP → ΔP*(Xt)`. Not
`crates/risk`. Phase 3 is not an execution policy. Do not invent
`Λα`. SSOT: `research/dre/PORTFOLIO_OBJECTIVE_V1.md`. How-to:
`docs/operations/DRE.md`. Agent rule: `.cursor/rules/21-dre.mdc`.

**Ballhog (Hedging Analysis):** Exposure-removal optimizer. Package +
API: `ROLLER/roller/ballhog/` and `/ballhog/*` on `:8791`. Dashboard is
a separate Vite instance: `frontend/ballhog` on `:5192`. Consumes
Austin N=604 (`query_at`, persist=False) and Choosin Texas N=936
(STATIC prior). Decides WHEN / q* / ρ* / Δ*. Dual-leg lock is
theoretical. BDR `#/bdr` remains the write-up library. TK Ultra is the
economic-expression sibling; do not call `/momento/tk-ultra/assess`
from Ballhog. Position Management is NOT_IMPLEMENTED. Does not submit.
Does not invent λ, Λα, fills, or L2. How-to: `docs/operations/BALLHOG.md`.
Agent rule: `.cursor/rules/22-ballhog.mdc`.

**TK Ultra (Relative Value Hedging):** Rich/cheap and gross route. Package
+ API: `ROLLER/roller/tk_ultra/` and `/momento/tk-ultra/*` on `:8791`.
Dashboard: `frontend/momento-systems` `:5190/#/tk-ultra`. `GENERIC_RV` is
the NQ/ES futures calculator. `BINARY_COMPLEMENT_V0` is FIRST80 A/B YES.
Independent Austin (604) and Choosin (936) adapters. Optional Ballhog
sibling via in-process `handle_intent`. Does not submit. Does not mix N.
Position Management is NOT_IMPLEMENTED. How-to:
`docs/operations/TK_ULTRA.md`. Agent rule: `.cursor/rules/23-tk-ultra.mdc`.

**NBA path-trade FE:** Research-only second filter (touch-80 kept;
enter/skip). Package: `ROLLER/roller/nba_path_fe/`. Library:
`research/nba_path_trade_fe/` (`features/registry.yaml` SSOT;
`artifacts/walkforward/summary.json`). Binding contract:
`research/nba_path_trade_fe/docs/{AGENTS,AMENDMENT_v3,FEATURE_ENGINEERING_SPEC}.md`.
Raw warehouse deferred — synthetic E2E only. Family E / `hedge_*` never
imported into `enter_skip`. Do not fabricate L2. Do not leak post-`t_s`
into enter/skip. Do not remount inside Choosin Texas or roller-terminal.
Do not change live FIRST01 / 80/81/83/89, `first80.py`, book.json, W9,
or warehouse Phase 21. Failed promotion → tighten, do not expand.
Agent rule: `.cursor/rules/19-nba-path-fe.mdc`.

**ITI:** last SuperASI step (after Final Results), not Jump A.
`/superasi/iti/*` is canonical; `/jump/iti/*` is an alias. ITI is not a
live Kalshi signal.

**Research Engine v1 (console):** Internal research OS wrapping B1
first-exact-83 (`crates/research-engine`, `apps/research-api`,
`frontend/research-console`). Does not change live FIRST01 / 80/81/83/89.
Does not invent L2. Does not start W9. Candidates are not production.

**SuperASI** (rename of Lebronner): research-only decomposition laboratory
that consumes ROLLER measurements. Package + API live in
`ROLLER/roller/superasi/` and `ROLLER/scripts/terminal_api.py`
(`/superasi/*`). Dashboard shell is `frontend/roller-terminal/src/superasi/`
(one Vite app; not a second frontend). Disk library is
`research/superasi/library/`. SuperASI is not a trading system and does
not submit orders. Does not change live FIRST01 / 80/81/83/89. Does not
start W9. Does not treat candle path as a fill. Spec:
`research/superasi/` and `docs/research/superasi/`.

**Jump** (Data Modeling filesystem): Sport-first Drive for research
articulations built from ROLLER + SuperASI. Same ROLLER Vite app:
`frontend/roller-terminal/src/jump/` at `http://127.0.0.1:5179/?app=jump`
(hash routes, NBA landing). Package + Drive API: `ROLLER/roller/jump/`
(`research.py`, `drive.py`, `GET /jump`, `/jump/research/*`,
`/jump/documents/*`). Pointers and generated markdown projections only.
Does not copy warehouses or silently merge duplicate SuperASI folders.
`/jump/bots*` remains compatibility HTTP for Vital until that backend is
migrated. ITI stays on SuperASI (`/superasi/iti/*`; `/jump/iti/*` is an
alias). Does not submit. Does not change live FIRST01 / 80/81/83/89.
Does not start W9. Spec: `docs/jump/JUMP_REWORK_RECON.md`,
`docs/jump/CURRENT.md`.

**STAX** (multi-strategy research stack): ROLLER-native composition of
independent research objects. Package + API live in `ROLLER/roller/stax/`
and `/stax/*`. UI is `frontend/roller-terminal/src/stax/` (same Vite app;
ROLLER shell, not a second product). Disk library is
`research/stax/library/`. V1 timeframes are fixed; automation re-executes
the saved specification and does not expand dates. `member_id` is
durable; `position` is order only. `aggregation_method = NONE`. ADD STRATEGY
can create a new ROLLER research object in-place (`POST /stax/{id}/strategies`)
or add an existing object; both are ordinary members. STAX does
not submit orders, does not invent a stack EV, and does not change live
FIRST01 / 80/81/83/89 or SuperASI behavior. Spec: `research/stax/` and
`docs/research/stax/`.

**ROLLER warehouse + conditional backtest refactor (NBA-first):**
Canonical linked warehouse and general query engine so a previously
unseen NBA strategy can be created in the existing ROLLER UI, compiled,
executed against the warehouse, and reported on Results (W/L, R:R, EV,
coverage, row-level audit). Phases 0–20 complete (NBA identity, GameMarketLink,
1-minute TRADABLE_YES_BID observations, PBP sequence-only, Kalshi settlement,
orderbook SOURCE_UNAVAILABLE, physical Parquet layout, coverage catalog,
ResearchContext, isolated query compiler, conditional backtest,
reference ≡ optimized, edge/failure suite, performance, parquet-only
warehouse-backed execution, source-driven warehouse ingest, Auto Roller
verify, frontend ResearchQuestion construction, full NBA research desk).
Confirm & Run still reads CSV. Historical L2/tick remain DATA_REQUIRED.
PBP↔candle PIT remains OPERATION_REQUIRED. Candle-path results are not
fills and are not live trading. Do not start Phase 21. NCAAB/MLB use the
same contracts where data exists; they do not block NBA. Frozen locks
are regression fixtures only. Plan:
`research/warehouse_refactor/PLAN.md`.

**Milestone 10 (current):** $50 production MLB live trading. Explicit live
arming (`mode=live`, `live.enabled=true`, `live.confirmation=ENABLE_LIVE_TRADING`).
Production Kalshi Create V2 for maker-only entry and reduce-only IOC
liquidation. Do not invent fee or mid semantics. Do not submit synthetic
production orders. The first production order must be a real 80→81 signal.

**Milestone 9:** Production read-only authentication (done).

**Milestone 8:** Kalshi demo/sandbox validation (done).

**Milestone 7:** AWS us-east-1 paper deploy (done).

**Milestone 6:** MLB 80/81/89 strategy.

Initial experimental account (runtime values come from `config/`, not strategy code):

- Bankroll snapshot: $50
- Position allocation: 12.5% of the weekly snapshot (fee-inclusive)
- Maximum economic entry budget at $50: $6.25
- One logical position per game
- Maximum 5 simultaneously open MLB positions (Risk-enforced)
- Permitted maker-only entry: 80–83 cents (max 83)
- Live trading: armed only when all three live gates are set

## Sports

- MLB (first)
- NBA, NCAAB, NFL (stubs only)

## Architecture Rule

Strategy proposes.

Risk approves.

Execution executes.

Position Tracker reconciles.

PNL calculates.

Dashboard observes.

No component bypasses this hierarchy.

## Development Rule

Infrastructure first, then MLB strategy:

1. domain types (Milestone 1)
2. weekly snapshot + config
3. audit events
4. TradeIntent / strategy interface
5. risk engine (Milestone 2)
6. paper execution (Milestone 3)
7. Kalshi adapter (Milestone 4)
8. position/reconciliation (Milestone 5)
9. MLB strategy (Milestone 6)
10. AWS paper deploy (Milestone 7)
11. Kalshi demo/sandbox validation (Milestone 8)
12. production credentials only after explicit approval (Milestone 9)
13. live execution only after explicit approval (Milestone 10)

Every stage must be testable before proceeding.

## Research / Backtesting Engine (reset 2026-08-26)

We are **not** extending the legacy candle FIRST01 backtester as the research
platform. We are building a new **historical event–market reconstruction and
simulation engine**, with MLB as the reference sport. FIRST01 is the first
**strategy plugin** on that platform.

Development uses strict **W# → A# → S#** waterfall governance. Do not skip
waterfalls. Do not implement a later S-step unless explicitly authorized.

Governing documents (keep in sync with code):

- **Roadmap:** `docs/research/BACKTEST_ENGINE_WATERFALL.md`
- **CEO/CTO spec:** `docs/research/BACKTEST_ENGINE_SYSTEM_SPECIFICATION.md`
- **W/A/S registry:** `docs/research/BACKTEST_ENGINE_WATERFALL_REGISTRY.csv`
- **Current state:** `docs/research/BACKTEST_ENGINE_CURRENT_STATE.md`
- **ADRs:** `docs/research/architecture-decisions/`
- **Reset:** `docs/research/BACKTESTING_ENGINE_RESET.md`
- **Full plan (waterfalls 0–26, phases 1–27):**
  `docs/research/HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md`
- **Agent rule:** `.cursor/rules/11-historical-research-engine.mdc`

Primary research objects: `StateTransition` (atomic) inside
`GameMarketEpisode` (container). A trade is downstream.

Waterfall 0 (recon + governance baseline) is complete.
W1 is **ACCEPTED / CLOSED** (CEO 2026-08-26).
W2 engine is COMPLETE for the observed committed window.
W3 is **ACCEPTED / CLOSED** (CTO 2026-08-26).
Authorized parallel: **DATA-INGEST** waterstream (CODE READY; backfill not
complete; cloud **LOCAL_CRON_ONLY**). CTO-W4 market reconstruction is
**COMPLETE** as a price-path foundation (238 TRADES_ONLY paths; L2 not
invented). CTO-W5 event↔market synchronization is **IMPLEMENTED**.
CTO-W6 canonical MLB state engine is **IMPLEMENTED**.
CTO-W7 EventMarketPath is **IMPLEMENTED**.
CTO-W8 FIRST01 observational replay is **IMPLEMENTED**.
B1 price-dissection feature engine is **IMPLEMENTED** (schema 1.1.0;
A1 entry/exit target buckets; L2 remains UNAVAILABLE).
**Do not start W9** (Greeks, fills, live P&L, strategy retune) unless
explicitly authorized.
Research never automatically changes live trading.
