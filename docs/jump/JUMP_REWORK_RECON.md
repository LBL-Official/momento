# Jump Rework — Reconnaissance

**Date:** 2026-09-20
**Status:** Sport-first research Drive is current. Bot UI remains removed.
`/jump/bots*` HTTP kept for Vital until backend migration. Current
product facts: `docs/jump/CURRENT.md`.
**LIVE EXECUTION = FALSE**

```text
TARGET LOCK (not applied in Phase 0)

Database      → ROLLER     "What happened?"
Data Analysis → SUPERASI   "What does the evidence say?"
Data Modeling → JUMP       "What modeling objects have we built from it?"
                  ↓
            SIGNAL GENERATION
```

Jump today is the Data Modeling research filesystem (sport-first Drive).
Bot product chrome is gone from `?app=jump`. `/jump/bots*` HTTP remains
for Vital. This document keeps the inventory and migration history.
Current layout: `docs/jump/CURRENT.md`.

---

## 1. Current identity

Jump is **not** an 18th Momento system. It is a **submodule** of `momento_systems`.

| Layer | Location |
|---|---|
| Entry | `http://127.0.0.1:5179/?app=jump` (same Vite app as ROLLER / SuperASI) |
| UI | `frontend/roller-terminal/src/jump/` (10 files) |
| Package | `ROLLER/roller/jump/` (51 Python modules) |
| Disk | `research/jump/` |
| Docs | `research/jump/README.md`, `.cursor/rules/15-jump.mdc`, AGENTS.md Jump section |

It is a **research filesystem**, not a bot control plane:

```text
ROLLER measurements + SuperASI packages
        → resolve_jump_research_object
        → sport-first Drive (NBA landing)
```

Hash routes in `frontend/roller-terminal/src/jump/routing.ts`:

```text
#/nba
#/nba/FIRST80_ASKED_SIX_80_40
#/nba/FIRST80_ASKED_SIX_80_40/roller-measurement
```

`/jump/bots*` HTTP is compatibility only. No bot UI.

**Data Modeling today is not Jump.** Registry `data_modeling.frontend_target`:

```yaml
kind: momento_page
url: http://127.0.0.1:5190/#/systems/data_modeling
product: Momento
```

Database Frontend is already ROLLER `http://127.0.0.1:5179`.
Data Analysis Frontend is already SuperASI `http://127.0.0.1:5179/?app=superasi`.

```text
Momento :5190 ──► data_modeling momento_page
Momento :5190 ──► Database ──► ROLLER :5179
Momento :5190 ──► Data Analysis ──► SuperASI ?app=superasi
Jump ?app=jump ──► creates / observes bots ──► Vital :5180
```

---

## 2. Frontend inventory

All Jump UI is under `frontend/roller-terminal/src/jump/`.

| File | Role | Classification |
|---|---|---|
| `JumpApp.tsx` | Thin wrapper → JumpShell | CURRENT |
| `JumpShell.tsx` | Hash router, NBA landing | CURRENT |
| `JumpTopBar.tsx` | Search + breadcrumbs (no Open ROLLER) | CURRENT |
| `JumpSidebar.tsx` / `SportSelector.tsx` | Sport-first nav | CURRENT |
| `FolderView.tsx` / `FileTable.tsx` / `FileRow.tsx` | Drive list | CURRENT |
| `DocumentView.tsx` / `DatasetPreview.tsx` / `DetailsPanel.tsx` | Viewers | CURRENT |
| `api/jumpApi.ts` | `/jump/*` client | CURRENT |
| Bot / Vital UI files | Removed from Jump product | HTTP-only `/jump/bots*` |

Related, not in `jump/`:

| File | Role | Classification |
|---|---|---|
| `frontend/roller-terminal/src/App.tsx` | `?app=jump` product switch | KEEP |
| `frontend/roller-terminal/src/origins.ts` | `openVitalDashboard()` | KEEP (Vital still needs it) |
| `frontend/roller-terminal/src/superasi/ITI.tsx` | "Create Jump bot" handoff | DELETE button in Phase 4; ITI stays SuperASI |
| `frontend/roller-terminal/src/styles.css` (`ju-*`) | Jump + ITI styles | REWORK / MOVE ju-iti-* conceptually to SuperASI |
| `frontend/vital-terminal/src/origins.ts` | `openJump()` → `/?app=jump` | REWORK after Jump is Drive |

**Does not exist:** Bot Library, Bot Builder, `/create-bot`, `/bot-builder` routes.

**Reusable research seed:** Home's SuperASI Final Results list (`listDebaseResults()`). That is the only existing Jump UI that already inventories research objects.

ROLLER AppHeader has SuperASI + Vital only. No Jump masthead link.

---

## 3. Backend route table

Mounted on `ROLLER/scripts/terminal_api.py` `:8791`. Handler errors use `JumpError`.

| Method | Path | Subsystem | After rework |
|---|---|---|---|
| GET | `/jump` | Drive root (NBA default) | CURRENT |
| GET | `/jump/sports` | Sport list | CURRENT |
| GET | `/jump/research` | Research objects by sport | CURRENT |
| GET | `/jump/research/{key}` | Canonical object | CURRENT |
| GET | `/jump/research/{key}/children` | Folder children | CURRENT |
| GET | `/jump/documents/{doc_id}` | Generated markdown + lineage | CURRENT |
| GET | `/jump/artifacts/{id}/preview` | Pointer preview | CURRENT |
| POST | `/jump/index/refresh` | Rebuild in-memory index | CURRENT |
| GET | `/jump/tree` | Drive tree | CURRENT |
| GET | `/jump/search` | Search | CURRENT |
| GET | `/jump/recent` | Recent | CURRENT |
| GET | `/jump/health` | Shell | KEEP |
| POST | `/jump/iti/run` | A alias → SuperASI ITI | COMPATIBILITY |
| GET | `/jump/iti` | A alias | COMPATIBILITY |
| GET | `/jump/iti/{run_id}` | A alias | COMPATIBILITY |
| POST | `/jump/iti/{run_id}/commit` | A alias | COMPATIBILITY |
| GET | `/jump/iti-commits` | B — SuperASI `{name}_ITI` folders | REWORK as artifact index later |
| GET | `/jump/bots` | B | COMPATIBILITY until Vital owns |
| GET | `/jump/bots/{bot_id}` | B | COMPATIBILITY |
| POST | `/jump/bots/draft` | B | COMPATIBILITY |
| POST | `/jump/bots` | B — always DEMO | COMPATIBILITY |
| POST | `/jump/bots/{bot_id}/production` | B — DEMO→PRODUCTION | COMPATIBILITY / MOVE |
| PATCH | `/jump/bots/{bot_id}/profile` | B | COMPATIBILITY |
| GET | `/jump/bots/{bot_id}/avatar` | B | COMPATIBILITY |
| GET | `/jump/bots/{bot_id}/trades` | B + catalog | COMPATIBILITY |
| GET | `/jump/dashboard` | C | COMPATIBILITY |
| GET | `/jump/dashboard/logs` | C | COMPATIBILITY |
| GET | `/jump/catalog` | Catalog | COMPATIBILITY / MOVE |
| POST | `/jump/catalog/refresh` | Catalog | COMPATIBILITY / MOVE |
| GET | `/jump/kalshi` | Catalog | COMPATIBILITY / MOVE |
| POST | `/jump/kalshi/sync` | Catalog | COMPATIBILITY / MOVE |
| GET | `/jump/mybots` | My Bots | COMPATIBILITY |

Canonical ITI HTTP is `/superasi/iti/*`. `/jump/iti/*` is the same implementation via `roller.jump.iti.*` module aliases.

`GET /jump/iti-commits` is **Jump B**, not ITI run history. Naming collision risk with `/jump/iti`.

---

## 4. Package classification (`ROLLER/roller/jump/`)

### KEEP (Jump product after rework, or shared infra)

- `__init__.py`, `api.py`, `versions.py`, `vital_client.py` (adapter until Jump stops observing live)
- `errors.py` — SuperASI ITI still imports `JumpError`
- `library.py` — SuperASI ITI still uses `default_library_root()` → `research/jump/library/`
- `bots/store.py`, `bots/pipeline.py`, `bots/api.py` — keep until Vital owns create/promote
- `bots/source_iti.py`, `bots/status.py`, `bots/profile.py`, `bots/trades.py`, `bots/versions.py`
- `dashboard/api.py`, `tracks.py`, `heartbeat.py`, `rollup.py`, `store.py`, `versions.py`
- `catalog/api.py`, `refresh.py`, `mybots.py`, `charts.py`, `identity.py`

### COMPATIBILITY ONLY

All of `iti/` (`__init__.py`, `pipeline.py`, `store.py`, `source.py`, `catalog.py`, `rank.py`, `timings.py`, `versions.py`, `stress_question.py`). Each re-exports `roller.superasi.iti.*`.

### MOVE to Vital before any deletion

Vital **imports** these today. Deleting them breaks MLB observe / demo / promote.

| Module | Vital consumers |
|---|---|
| `bots/demo_host.py` | `demo_control`, `demo_attach`, `unit_observe`, `reconcile`, `parameters` |
| `bots/live_host.py` | `reconcile` |
| `bots/deploy.py` | Jump B; move with host control |
| `bots/factory.py` | `vital/parameters.py` (`FACTORY`) |
| `bots/engine.py` | `vital/register.py` |
| `dashboard/ledger.py` | `vital/aws.py`, `vital/reconcile.py`, `vital/mlb_001/trade_row.py` |
| `dashboard/host_state.py` | demo/live host helpers |
| `catalog/store.py` | `bankroll`, `reconcile`, `demo_attach`, `mlb_001/kalshi_observe` |
| `catalog/kalshi.py` | `demo_shard`, `mlb_001/kalshi_observe` |
| `catalog/bankroll.py` | `vital/bankroll.py`, `demo_shard` |
| `catalog/connection.py` | `vital/observe.py`, `mlb_001/kalshi_observe` |
| `catalog/reconcile.py` | move with catalog truth |
| `catalog/versions.py` | secret ids used by Vital demo_shard / demo_attach |
| `catalog/analysis.py` | `vital/bankroll.py` |

Promote handoff: `POST /vital/bots/{id}/promote` calls `jump.bots.pipeline.promote_bot` (`ROLLER/roller/vital/api.py`).

### REWORK

- `library.py` — shared ITI run root; later a neutral path or SuperASI-owned store
- `errors.py` — later `roller.errors` so SuperASI does not depend on "Jump" naming
- `bots/pipeline.py` — thin delegate after Vital owns units
- `catalog/analysis.py` — split Vital fill truth vs Jump display

### DELETE safe today

**None.** Rust `apps/trading-engine` and `strategies/mlb` do not import Jump. Python Vital does.

---

## 5. Who imports Jump

### Vital → Jump (MOVE, do not delete)

```text
vital/api.py            → bots.pipeline.promote_bot, bots.store
vital/register.py       → bots.store, bots.engine, bots.versions
vital/demo_attach.py    → bots.demo_host, bots.store, catalog.store, catalog.versions
vital/demo_control.py   → bots.demo_host, errors.JumpError
vital/demo_shard.py     → catalog.bankroll, catalog.kalshi, catalog.versions, library.repo_root
vital/bankroll.py       → catalog.*, bots.store, bots.versions
vital/reconcile.py      → dashboard.ledger, catalog.store, bots.demo_host, bots.live_host
vital/observe.py        → catalog.connection
vital/aws.py            → dashboard.ledger, library.repo_root
vital/parameters.py     → bots.factory, bots.demo_host
vital/mlb_001/*         → catalog.store, catalog.connection, library, dashboard.ledger
vital/unit_observe.py   → bots.demo_host
```

### SuperASI → Jump (KEEP / later rework naming)

```text
superasi/iti/store.py     → JumpError, default_library_root
superasi/iti/pipeline.py  → JumpError
superasi/iti/api.py       → JumpError
superasi/iti/source.py    → JumpError
superasi/iti/timings.py   → default_library_root
```

### Does not import Jump

Choosin Texas, Austin, Momento bracket (`ROLLER/roller/momento/`), `apps/trading-engine`, `strategies/mlb`.

---

## 6. Persistence

No Drive index exists. Listing is directory scan.

| Env | Default | Contents |
|---|---|---|
| `JUMP_LIBRARY_ROOT` | `research/jump/library/` | 11 ITI run dirs (`job.json`, optional `timings.json`). Also SuperASI ITI store. |
| `JUMP_BOTS_ROOT` | `research/jump/bots/` | `mlb-bot-one` + UUID bots (`metadata.json`, `events.jsonl`) |
| `JUMP_CATALOG_ROOT` | `research/jump/catalog/` | `trades.jsonl`, `analysis.json`, `bankroll.json`, `kalshi_book.json`, charts |
| `JUMP_DASHBOARD_ROOT` | `research/jump/dashboard/` | `notes.json` |

Also: `research/jump/stress/` (ITI stress artifacts), `research/jump/README.md`.

Vital writes `research/vital/bots/mlb-00N/` on Jump create. Jump `metadata.json` stores `vital_bot_id`.

**Future index (Phase 2):** `research/jump/index/` or `JUMP_INDEX_ROOT`. Identity / organization / relationship / pointer only. Do not copy `ROLLER/data/` or SuperASI labs.

---

## 7. Tests that must keep passing

Jump:

- `ROLLER/tests/test_jump_research.py`
- `ROLLER/tests/test_jump_drive.py`
- `ROLLER/tests/test_jump_bots.py`
- `ROLLER/tests/test_jump_catalog.py`
- `ROLLER/tests/test_jump_dashboard.py`
- `ROLLER/tests/test_jump_iti.py`
- `ROLLER/tests/test_jump_shell.py`
- `ROLLER/tests/test_jump_ledger.py`

Vital handoff (prove `/jump/bots` still works until moved):

- `ROLLER/tests/test_vital_jump_handoff.py`
- `ROLLER/tests/test_tennis_roller_to_vital_demo.py`
- `ROLLER/tests/test_vital_bankroll.py`
- `ROLLER/tests/test_vital_demo_shard.py`
- `ROLLER/tests/test_vital_execution_incident.py`
- `ROLLER/tests/test_superasi_iti.py` (`/jump/iti` ≡ `/superasi/iti`)

Do not delete these to make Jump look bot-free.

---

## 8. Locked decisions for later phases

- Jump **stays** at `http://127.0.0.1:5179/?app=jump`. Same origin as ROLLER and SuperASI. No new Vite port. Not remounted inside `:5190`.
- Jump stores identity / organization / relationship / pointer. It does not copy warehouses.
- Austin remains Dynamic Risk Engine. FIRST80 may hold **references** only.
- Algorithmic Execution stays `NOT_IMPLEMENTED`. Jump does not become the NBA bot. Vital `:5180` is not Data Modeling Frontend.
- `LIVE EXECUTION = FALSE`. Do not edit `first80.py`, W9, warehouse Phase 21, MLB 001, `apps/trading-engine`, `crates/risk`, `strategies/mlb`.
- New artifact index under `research/jump/index/` (or `JUMP_INDEX_ROOT`).

---

## 9. Target product (after Phase 7)

JUMP = Momento's Data Modeling filesystem.

It organizes research objects from ROLLER + SuperASI into a navigable workspace.

It answers: what data exists, what analysis exists, what model came from it, where it lives, what generated it, what consumes it, what version is canonical, what research stage it is in.

It does **not** create bots, deploy bots, or execute trades.

Current Drive roots are sports, not ROLLER/SUPERASI dumps:

```text
JUMP/
├── NBA/          # default landing
├── NCAAB/
├── MLB/          # empty state, no invented folders
├── WNBA/
└── TENNIS/
```

One folder per articulation (asked-six is MIXED, shared under NCAAB/WNBA).
Generated documents live inside the folder. Pointers only.

Artifact record (Phase 2): `artifact_id`, `name`, `artifact_type`, `system_owner`, `sport`, `strategy`, `parent_folder`, `source_path`, `api_target`, `frontend_target`, timestamps, `version`, `status`, `research_stage`, `model_version`, `manifest_hash`, `tags`, `upstream_artifacts`, `downstream_artifacts`, `description`.

Types: `FOLDER`, `DATASET`, `BACKTEST`, `REPORT`, `MODEL`, `EXPERIMENT`, `STRATEGY`, `VALIDATION`, `STATE_MODEL`, `PATH_MODEL`, `RESULT_SET`, `NOTE`, `MANIFEST`.

---

## 10. Exact migration (Phases 1–7)

Do not start these until explicitly authorized after Phase 0.

### Phase 1 — Product identity (docs + registry only)

Rewrite Jump as Data Modeling / Path Efficiency.

- Registry `data_modeling.frontend_target`: `kind: same_app`, `url: http://127.0.0.1:5179/?app=jump`, `product: Jump`
- Keep Database → ROLLER and Data Analysis → SuperASI
- Update `docs/momento/{FRONTEND_MAP,ARCHITECTURE,DATAFLOW,MIGRATION_MAP,SYSTEM_REGISTRY}.md`, AGENTS.md, `.cursor/rules/15-jump.mdc`, `.cursor/rules/20-momento-systems.mdc`
- Tests: fail if Data Modeling Frontend is still a `:5190` momento_page or points at Vital `:5180`
- **Do not delete** `/jump/bots`

### Phase 2 — Filesystem core

New models + APIs. Stable ids. Directory walk is not the contract.

```text
GET /jump
GET /jump/tree
GET /jump/folders/{id}
GET /jump/artifacts
GET /jump/artifacts/{id}
GET /jump/search
GET /jump/recent
GET /jump/artifacts/{id}/upstream
GET /jump/artifacts/{id}/downstream
```

UI: Drive home with the six roots; breadcrumbs; list view; search; artifact detail. No fake Open buttons. No charts-first home. No bots.

### Phase 3 — Index ROLLER + SuperASI (pointers)

Discover existing canonical paths. Index, do not copy.

- `OPEN IN ROLLER` → `:5179` (or a real object URL)
- `OPEN IN SUPERASI` → `:5179/?app=superasi`

### Phase 4 — Remove bot UI from Jump

Only after Phase 2 exists **and** Vital still has a working create/promote path (compatibility HTTP or moved modules).

- Remove `Bots`, `MyBots`, `BotProfile`, bot Dashboard from Jump nav
- Remove SuperASI "Create Jump bot"
- Keep `/jump/bots*` as compatibility if Vital/tests still call them, or relocate under `/vital/*` first
- Redirect old Jump bot screens to Drive home. Do not 404 blindly

### Phase 5 — FIRST80 workspace

Seed:

```text
STRATEGIES/NBA/FIRST80/
  ROLLER/
  SUPERASI/
  Path Efficiency/
  Austin References/    # pointers only; DRE owns Austin
  Execution Research/   # research pointers; not a live bot
  Reports/
```

Show ROLLER + SuperASI → derived path-efficiency object → Signal Generation (reference only).

### Phase 6 — Bracket wiring

Prove: `:5190` Data Modeling → Frontend → `?app=jump`.
Backend inspector stays `/momento/systems/data_modeling`.

### Phase 7 — Audit

- Jump UI has no bot product semantics
- Jump does not submit, deploy, or own MLB 001
- Vital health + jump-handoff tests still pass
- Choosin / Austin lock integers unchanged
- Write `docs/jump/JUMP_DATA_MODELING_FREEZE.md`

---

## 11. Phase 0 gate

This file is the Phase 0 deliverable.

- Registry was **not** remapped.
- Drive UI is sport-first (`?app=jump`, hash routes, NBA landing).
- Bot code was **not** deleted.
- Vital import graph is recorded. **DELETE safe today: none.**
