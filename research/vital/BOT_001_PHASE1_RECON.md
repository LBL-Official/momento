# MLB Bot 001 — Phase 1 Reconnaissance & Ownership Lock

Dated: 2026-09-14.

Facts from the repository. Not a design essay. Not Phase 2.

```text
PHASE 1  recon + ownership lock  ACCEPTED 2026-09-14
PHASE 2  isolated folder          see research/vital/BOT_001_PHASE2.md
PHASE 3  backend control plane    see research/vital/BOT_001_PHASE3.md
PHASE 4  worker contract          see research/vital/BOT_001_PHASE4.md
PHASE 5  market→signal→risk→exec  see research/vital/BOT_001_PHASE5.md
PHASE 6  ledger / one-row trades  see research/vital/BOT_001_PHASE6.md
```

**Operator decision:** Phase 1 **ACCEPTED** 2026-09-14.
The factual vs requested ownership CONFLICT remains recorded. Acceptance
does not move `apps/trading-engine`, invent RDS, or implement the trade
table. Phase 2 does not start in this step.

This file does **not** move `apps/trading-engine` or `strategies/mlb`.
It does **not** implement a trade table, reconstruct trades from catalog
fills, fetch host `live-runtime.json` over SSM, or restyle
`frontend/vital-terminal`.

Every claim is tagged:

```text
FACT       directly in repo or on-disk files
OBSERVED   current disk / local-desk state
INFERRED   logical conclusion from facts
UNKNOWN    not established from this repository
```

Related:

- Prior Vital recon: `research/vital/RECON.md` (2026-09-13)
- Ownership: `research/vital/OWNERSHIP.md`
- Execution ledger recon: `research/vital/EXECUTION_LEDGER_RECON.md`
- Agent rule: `.cursor/rules/16-vital.mdc`

---

## Executive Summary

**FACT** — MLB Bot 001 already exists as Vital identity `mlb-001`
(alias `mlb-bot-one`). It is the sole Vital bot on disk
(`research/vital/bots/mlb-001/`). Kind: `grandfathered`. Environment:
`PRODUCTION`. Factory: `mlb_factory_v1`.

**FACT** — If the Vital dashboard and Jump dashboard both disappear,
production execution continues as:

```text
systemd  momento-live.service
binary   /usr/local/bin/momento-trading-engine
cwd      /var/lib/momento
config   /var/lib/momento/config/live.toml
```

Unit file: `deploy/momento-live.service`.
Source binary: `apps/trading-engine` (`momento-trading-engine`).
Strategy: `strategies/mlb` (proposes; does not submit).
Risk: `crates/risk` (approves; does not submit).
Venue: Kalshi Create V2 from `apps/trading-engine/src/live.rs`.

**FACT** — There is no Jump worker process in this repository.
Jump `LIVE_EXECUTION = False` (`ROLLER/roller/jump/versions.py`).
Vital `LIVE_EXECUTION = False` (`ROLLER/roller/vital/versions.py`).

**FACT** — There is no RDS / PostgreSQL / `DATABASE_URL` for trading,
Vital, or Jump. Durable state today is host JSON
(`/var/lib/momento/state/live-runtime.json`) plus Vital append-only
files under `research/vital/bots/mlb-001/execution/`.

**FACT** — There is no `.github/` directory and no GitHub Actions
workflows in this repository.

**OBSERVED** — On this Mac, host `live-runtime.json` is unread
(`execution/observed.json`: `host state path unset`).
`trades.jsonl` is **absent**. `fills.jsonl` has **139** rows.
Jump catalog `research/jump/catalog/trades.jsonl` also has **139** rows.
The Vital MLB 001 page therefore shows a **fill blotter**, not one row
per market / per logical trade. Trades render
`OBSERVATION_UNAVAILABLE`. Most catalog-sourced fills have
`ticker: null`, so market prints `OBSERVATION_UNAVAILABLE`.

**CONFLICT** — You asked that Vital own bot workers and bot logic, and
that Jump be only a dashboard client of Vital. That is the
**requested lock**. Today's **factual lock** is: Vital observes and
fail-closed-controls; `momento-live.service` / `apps/trading-engine`
executes. This file records both. It does not silently resolve them.

**STOP** after this report. Phase 2 does not start until a human
accepts this file.

---

## Current Architecture

```text
LOCAL MAC (dev desk)
  frontend/vital-terminal     :5180   Vital UI
  frontend/roller-terminal    :5179   ROLLER / SuperASI / Jump UI
  ROLLER/scripts/terminal_api.py :8791
      /vital/*   Vital handlers (ROLLER/roller/vital/api.py)
      /jump/*    Jump handlers (client of Vital for Bot One)
  research/vital/bots/mlb-001/        Vital disk library
  research/jump/bots/mlb-bot-one/     Jump registry alias
  research/jump/catalog/trades.jsonl  fill observation (139 rows)

AWS us-east-1 (documented)
  EC2 instance id (documented default): i-0f0849d5829476c31
  momento-live.service
    → /usr/local/bin/momento-trading-engine
    → Kalshi production (when triple-gated)
  Secrets Manager momento/kalshi/production
    → /usr/local/libexec/m10-fetch-secret.sh
    → /dev/shm/momento-kalshi-live.json
  Host state /var/lib/momento/state/live-runtime.json
```

**UNKNOWN** — Whether `momento-live.service` is active on that instance
right now. The repo documents intended shape, not live host status.
`research/vital/RECON.md` §9 says re-verify `i-0f0849d5829476c31`
before treating it as identity.

Write path (**FACT**, unchanged by Vital):

```text
Kalshi WS
  → strategies/mlb MlbStrategy::observe → TradeIntent
  → crates/risk PaperRiskEngine
  → apps/trading-engine live.rs submit_approved
  → Kalshi Create V2
```

Observation path (**FACT**):

```text
live-runtime.json (host, when readable)
  + Jump catalog trades.jsonl (fills only)
      → ROLLER/roller/vital/reconcile.py
      → research/vital/bots/mlb-001/execution/
      → GET /vital/bots/mlb-001/execution*
      → frontend/vital-terminal BotDetail
```

Jump path (**FACT**):

```text
ROLLER/roller/jump/vital_client.py
  → in-process Vital handlers
  → Jump dashboard / Bot One status
```

Jump does not submit orders. Browser does not submit orders.

### File map

| Path | Role | Tag |
| --- | --- | --- |
| `apps/trading-engine/` | Production order submitter | FACT / CANONICAL execution |
| `apps/trading-engine/src/live.rs` | Live YES-bid → 80/81 → Risk → Create V2 | FACT |
| `strategies/mlb/` | Proposes `TradeIntent`; no Kalshi | FACT |
| `crates/risk/` | Approves / rejects; no submit | FACT |
| `crates/kalshi/` | Venue transport | FACT |
| `crates/pnl/` | `PnlBreakdown::from_position` | FACT |
| `config/live.toml` | Triple live gate + desk config | FACT |
| `deploy/momento-live.service` | Production systemd unit | FACT |
| `deploy/momento-paper.service` | Paper unit; Conflicts with live | FACT |
| `deploy/momento-demo@.service` | Jump demo bots; same binary | FACT |
| `deploy/m10-fetch-secret.sh` | Production secret fetch | FACT |
| `ROLLER/roller/vital/` | Control plane + ledger package | FACT |
| `ROLLER/roller/vital/api.py` | `/vital/*` handlers | FACT |
| `ROLLER/scripts/terminal_api.py` | Local HTTP mount `:8791` | FACT |
| `research/vital/bots/mlb-001/` | Sole Vital bot tree | FACT |
| `frontend/vital-terminal/` | Separate dashboard `:5180` | FACT |
| `ROLLER/roller/jump/` | Jump client / registry / catalog | FACT |
| `ROLLER/roller/jump/vital_client.py` | Jump → Vital in-process | FACT / PROXY |
| `research/jump/bots/mlb-bot-one/` | Jump alias registry | FACT / PROXY |
| `research/jump/catalog/trades.jsonl` | Fill observation | FACT |
| `apps/jump-fills-read` | Read-only Kalshi CLI | FACT |
| RDS / Postgres | — | FACT: not found |
| `.github/workflows` | — | FACT: not found |
| Jump worker daemon | — | FACT: not found |

---

## Runtime Ownership

For every row: who owns it **today** (factual), whether it executes,
and the classification.

| Component | Current location | Current owner | Executes? | Reads? | Writes? | Lives on | Class |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Market data (live) | Kalshi WS into `apps/trading-engine` | Engine | Consumes | Yes | Host state | AWS | CANONICAL |
| Strategy | `strategies/mlb` | Engine path | Proposes | Book | No orders | AWS (binary) | CANONICAL |
| Risk | `crates/risk` | Engine path | Approves | Intents | No orders | AWS | CANONICAL |
| Execution / submit | `apps/trading-engine/src/live.rs` | Engine | **Yes** | Risk + venue | Kalshi + host JSON | AWS | CANONICAL |
| Orders (live) | Host tracker / `live-runtime.json` | Engine | — | — | Engine | AWS | CANONICAL |
| Orders (Vital API) | `GET /vital/bots/{id}/orders` | Vital | No | Host / Jump book | Observe stub | Local API | PROXY / stub |
| Fills (authoritative) | `tracker.positions[].fill_history` | Engine | — | — | Overwrites snapshot ~5s | AWS | CANONICAL when readable |
| Fills (Vital ledger) | `research/vital/bots/mlb-001/execution/fills.jsonl` | Vital | No | Host + catalog | Append-only | Local Mac | CANONICAL Vital history |
| Fills (Jump catalog) | `research/jump/catalog/trades.jsonl` | Jump | No | Ledger / Kalshi GET | Catalog refresh | Local Mac | OBSERVATION |
| Positions (engine) | `tracker.positions[]` | Engine | — | — | Host snapshot | AWS | CANONICAL logical trade |
| Positions (Vital API) | `GET /vital/bots/{id}/positions` | Vital | No | Host count or Jump book | Observe | Local API | PROXY |
| Heartbeat producer | Engine writes `live-runtime.json` | Engine | — | — | ~5s overwrite | AWS | CANONICAL |
| Heartbeat consumer | `ROLLER/roller/vital/observe.py` / `aws.py` | Vital | No | Local path or SSM inspect | Runtime snapshots | Local API | CANONICAL observe |
| Heartbeat (Jump) | `jump/dashboard/heartbeat.py` via `vital_client` | Jump | No | Vital | — | Local API | PROXY |
| Logs | systemd journal `momento-live`; Vital `/logs` | Engine / Vital | No | journal / empty local `logs/` | Host journal | AWS / Local | CANONICAL host; local empty |
| Runtime state | `/var/lib/momento/state/` | Engine | — | — | Engine | AWS | CANONICAL |
| API orchestration | `terminal_api.py` `/vital/*` | Vital | No | Disk + inspect | Commands (fail-closed) | Local Mac | CANONICAL control plane |
| Frontend | `frontend/vital-terminal` | Vital UI | No Kalshi | `/vital/*` | Control POST | Local Mac | CANONICAL UI |
| Jump UI | `frontend/roller-terminal` `?app=jump` | Jump | No | `/jump/*` + Vital origin | Demo/bot registry | Local Mac | CLIENT |
| Database / RDS | — | — | — | — | — | — | FACT: absent |
| Credentials | Secrets Manager → tmpfs | Host fetch script | — | Engine | tmpfs | AWS | CANONICAL |
| Deployment | systemd + S3/user-data (paper documented) | Operator / AWS | — | — | Host install | AWS | CANONICAL unit; live install path INFERRED |
| Monitoring | journalctl + Vital observe | Operator | No | Host | — | AWS / Local | CANONICAL; no PagerDuty/Datadog in repo |

Requested future owner for worker + bot logic: **Vital**.
That is **not** true of today's submit path. See Ownership Lock.

---

## Jump Runtime

**FACT** — Jump is not a production execution runtime.

| Question | Answer | Tag |
| --- | --- | --- |
| Jump host/runtime location | No Jump systemd unit in `deploy/` | FACT |
| Worker process | None named Jump worker / jump-worker | FACT |
| Process manager | N/A for execution | FACT |
| Executable | HTTP handlers in `terminal_api.py` | FACT |
| Working directory | Dev: repo + `research/jump/` | FACT |
| Heartbeat | Proxies Vital (`jump_heartbeat_from_vital`); legacy SSM fallback in `host_state.py` | FACT / PROXY + LEGACY |
| Logs | `/jump/dashboard/logs` — observation | FACT |
| API | `/jump/health`, `/jump/iti/*`, `/jump/bots/*`, `/jump/dashboard*`, `/jump/catalog*`, `/jump/kalshi`, `/jump/mybots` | FACT |
| Exchange credentials | Read-only catalog via `JUMP_KALSHI_SECRET_FILE_*`; never submit | FACT |
| State persistence | `research/jump/bots/`, `research/jump/catalog/` | FACT |
| Database | None | FACT |
| Production entry point | None for order submit | FACT |

**If Vital disappeared completely, what Jump process would continue to execute MLB Bot 001?**

**None.** Jump would not execute. The process that continues is
`momento-live.service` on AWS, which is not a Jump process.

Jump Bot One metadata (`research/jump/bots/mlb-bot-one/metadata.json`)
points at `apps/trading-engine`, `strategies/mlb`,
`aws_runtime_id: momento-live.service`. That is a pointer, not a worker.

Demo bots (**FACT**): `ROLLER/roller/jump/bots/demo_host.py` may SSM-start
`momento-demo@{id}.service`. That still launches `momento-trading-engine`,
not a Jump worker. It cannot start/stop/restart/kill `momento-live.service`
(`research/vital/RECON.md` §3).

---

## Jump API

**FACT** — Orchestration for MLB 001 **observation and control** is
`/vital/*`, not `/jump/*`.

Jump API is a research / operating-terminal HTTP surface on the same
`terminal_api.py` process. For Bot One it **reads Vital** in-process
(`ROLLER/roller/jump/vital_client.py`).

| Route family | Purpose | Production impact |
| --- | --- | --- |
| `/jump/health` | Jump product health | None |
| `/jump/iti/*` | Alias; ITI lives on SuperASI | None on live trading |
| `/jump/bots*` | Registry, draft, demo production transition | Demo units only |
| `/jump/dashboard*` | Operating view; Bot One from Vital | Observation |
| `/jump/catalog*`, `/jump/kalshi*` | Read-only book / fill catalog | Observation |
| `/jump/mybots` | Profiles | None |

**FACT** — Jump `LIVE_EXECUTION = False`.
Kalshi helpers (`ROLLER/roller/jump/catalog/kalshi.py`) are GET-only.

Requested: Jump writes to Vital so you can operate edits easily.
**FACT today:** Jump reads Vital for Bot One. Jump can write its own
registry and demo-host SSM. Jump does not own MLB 001 runtime writes
except as a client calling `/vital/*` (same fail-closed control).

---

## VITAL Frontend

**FACT** — Separate Vite app. Not a tab inside ROLLER.

| Item | Value |
| --- | --- |
| Root | `frontend/vital-terminal/` |
| Dev origin | `http://127.0.0.1:5180` |
| API | `/vital/*` on `http://127.0.0.1:8791` (`src/api/base.ts`) |
| CORS | `terminal_api.py` allows `http://127.0.0.1:5180` |
| Routes | hash `#/` Home, `#/bots` Bots, `#/bots/mlb-001` BotDetail |
| Nav | `src/navigation.ts`: `home \| bots \| detail` |
| Hardcoded bot | `VitalApp.tsx` `BOT_ID = "mlb-001"` |
| Auth | None in frontend. Control uses confirmation string on POST |
| WebSocket | None. Refresh is request/response |
| Cross-app | JUMP / ROLLER / SUPERASI open `:5179?app=…`; they open `:5180` |

**FACT** — Browser does not submit Kalshi orders. Header states
`CONTROL PLANE` and `DOES NOT SUBMIT`.

**FACT** — MLB 001 page (`src/BotDetail.tsx`) is a generic identity /
runtime / **fill blotter** / fail-closed controls / logs / events
surface. It is not the Bot Standard one-row-per-market trade table.

Phase 1 does not build a new page. It only records where that page
must live later: `frontend/vital-terminal`, routed per bot, fed by
Vital backend trade objects.

---

## AWS / RDS

### AWS (documented)

| Item | Value | Tag |
| --- | --- | --- |
| Region | `us-east-1` | FACT (`versions.py`, unit file) |
| Instance | `i-0f0849d5829476c31` | OBSERVED default; re-verify (RECON §9) |
| Account | `895492487332` | OBSERVED in `deploy/user-data.sh` |
| Live unit | `momento-live.service` | FACT |
| Paper unit | `momento-paper.service` (Conflicts with live) | FACT |
| Demo units | `momento-demo@.service` | FACT |
| SSM | Vital inspect (`aws.py`); Jump demo host; Jump legacy Bot One fetch | FACT |
| CloudFormation | `deploy/ingest-cfn.yaml` DATA-INGEST only | FACT |
| Docker / Terraform | None for trading | FACT |
| Live binary install | Paper uses S3 `momento-paper-artifacts-895492487332` | FACT for paper; live path INFERRED analogous |

**FACT** — Vital SSM inspect (`ROLLER/roller/vital/aws.py`) is
read-only. `WRITE_FORBIDDEN` blocks systemctl start/stop/restart/kill
and writes under `/var/lib/momento`. Inspect does **not** fetch
`live-runtime.json` over SSM (`EXECUTION_LEDGER_RECON.md` §4).

**FACT** — Production systemd writes require `VITAL_AWS_CONTROL=1` and
`confirmation=VITAL_ENABLE_CONTROL`. Default: `CONTROL_DISABLED`.
Live SSM dispatch is not enabled except `VITAL_AWS_CONTROL_DISPATCH=mock`
for tests.

### RDS

**FACT** — No RDS instance, schema, table, or `DATABASE_URL` for MLB
001, Vital, or Jump exists in this repository.

Durable truth **today**:

| Store | Holds | Authority |
| --- | --- | --- |
| Host `live-runtime.json` | Positions, fill_history, occupancy | Authoritative fills + logical trades when readable |
| Host `weekly-snapshot.json` | Bankroll / week bounds | Bankroll observation |
| Host `audit.jsonl` | 80/81/89 events | Not fills |
| Vital `execution/fills.jsonl` | Append-only fills | Vital history |
| Vital `execution/trades.jsonl` | Append-only trades | Absent until host positions readable |
| Jump `catalog/trades.jsonl` | Per-fill rows | Observation only |
| Jump `catalog/bankroll_history.jsonl` | Account cents over time | Account, not per-trade |
| In-memory tracker/risk audit | Engine events | Lost on restart |

Requested durable truth = AWS RDS. That is **not present**. Do not
invent schemas in Phase 1.

---

## Credentials & Secrets

Do not print values. Names and paths only.

| Secret / variable | Source | Consumer | Runtime | Purpose |
| --- | --- | --- | --- | --- |
| `momento/kalshi/production` | AWS Secrets Manager | `m10-fetch-secret.sh` | AWS live unit | Production Kalshi key id + PEM |
| `/dev/shm/momento-kalshi-live.json` | Fetch script output | `momento-trading-engine` | AWS tmpfs | Engine creds. **Vital must not read.** |
| `momento/kalshi/demo` | Secrets Manager | `m-demo-fetch-secret.sh` | AWS demo units | Demo Kalshi |
| `/dev/shm/momento-kalshi-demo.json` | Demo fetch | Demo engine | AWS tmpfs | Demo creds |
| `MOMENTO_KALSHI_SECRET_FILE` | Unit env | Engine | AWS | Path to tmpfs JSON |
| `MOMENTO_KALSHI_ENV` | Unit env | Engine | AWS | `production` / `demo` |
| `JUMP_KALSHI_SECRET_FILE_DEMO` / `_PRODUCTION` | Local env | Jump catalog GET | Local Mac | Read-only book |
| `VITAL_AWS_CONTROL` | Local env | Vital `control.py` | Local API | Gate systemd writes (unset = fail-closed) |
| `VITAL_ENABLE_CONTROL` | POST body confirmation | Vital control | Local API | Confirmation token name |
| `ENABLE_LIVE_TRADING` | `config/live.toml` | Engine triple gate | AWS | Live arm. **Rejected** as Vital control confirmation |
| `VITAL_BOT_STATE_DIR` / `VITAL_BOT_RUNTIME_PATH` | Local env | Vital `aws.py` | Local API | Host snapshot path (unset on this Mac) |
| `VITAL_AWS_HOST_FETCH` | Local env | Vital AWS | Local API | `local` vs `ssm` inspect |
| `VITAL_AWS_INSTANCE_ID` / `VITAL_AWS_REGION` | Local env | Vital AWS | Local API | SSM target |
| `VITAL_ROOT` | Local env | Vital store | Local API | Disk library root |
| `MOMENTO_KILL_SWITCH` | Host env | Engine | AWS | Kill override |
| `MOMENTO_CONFIG` / `MOMENTO_STATE_DIR` | Unit env | Engine | AWS | Config + state |

**FACT** — Secrets must never appear in frontend, `bot.json`, API
bodies, events, or logs (`OWNERSHIP.md`).

Expected production JSON **field names** (not values): `environment`,
`api_key_id`, `private_key_pem` (`crates/kalshi/src/secret.rs`).

---

## Heartbeat / Health

**FACT** — There is no independent heartbeat daemon.

| Item | Value | Tag |
| --- | --- | --- |
| Producer | `apps/trading-engine` overwrite of `live-runtime.json` | FACT |
| Frequency | Atomic overwrite ~5s | FACT (`EXECUTION_LEDGER_RECON.md`) |
| Destination | `/var/lib/momento/state/live-runtime.json` | FACT |
| Last-seen | File fields parsed by `ledger.py` / Vital observe | FACT |
| Vital attach | `aws.py` `_heartbeat_from_runtime` when local path readable | FACT |
| Jump | Prefers Vital; else probe env / legacy SSM | FACT / PROXY + LEGACY |
| Confirmed keys | `bankroll_cents`, open positions, kill, live_armed, day/week pnl, last_trade, `aws_runtime_id` | FACT (`heartbeat.py`) |
| Live EV / Sharpe | Always `UNAVAILABLE` | FACT |
| Stale heartbeat → warning | Vital health `UNKNOWN` / `OBSERVATION_UNAVAILABLE` when unread | FACT |
| Stale heartbeat → restart | No automatic restart from Vital/Jump | FACT |
| Stale heartbeat → halt | No | FACT |
| Monitor / alert product | Not in repo (no PagerDuty/Datadog) | FACT |
| systemd | `Restart=on-failure` on the unit; not heartbeat-driven | FACT |

**OBSERVED** — This Mac: host unread → lifecycle `OBSERVATION_UNAVAILABLE`,
health `UNKNOWN`. That is honest, not a crashed engine.

HTTP 200 from `/vital/health` is not `RUNNING`.

---

## GitHub Actions

**FACT** — No `.github/` directory. No workflows that build, deploy,
restart, monitor, or reconfigure MLB 001 / Vital / Jump.

| Workflow | Trigger | Purpose | Target | Production impact |
| --- | --- | --- | --- | --- |
| — | — | — | — | None in repo |

Obsolete / duplicate / dangerous workflows: none to delete (none exist).

**INFERRED** — Live deploys are operator-driven (cargo build, S3, SSM,
or manual install). Paper bootstrap is `deploy/user-data.sh`.

---

## Deployment

| Path | Mechanism | Class |
| --- | --- | --- |
| Production MLB 001 | `momento-live.service` + `live.toml` + Secrets Manager | CANONICAL |
| Paper | `momento-paper.service` + `paper.toml`; no live creds | CANONICAL paper |
| Jump demo bots | `momento-demo@.service` via Jump SSM | CANONICAL demo |
| Vital / Jump API | `python scripts/terminal_api.py` on a desk | Local Mac only |
| Vital UI | `npm run dev` `:5180` | Local Mac only |
| Research ingest | CFN + timer; docs `LOCAL_CRON_ONLY` | Isolated research |
| Research collector | `momento-research-collector.timer` daily 03:00 PT | Isolated research |

**FACT** — Triple live gate (`crates/core` + `config/live.toml`):

```text
mode = live
AND live.enabled = true
AND confirmation = ENABLE_LIVE_TRADING
```

`POST /vital/.../commands` `start` is not that gate.

Kill = touch `/var/lib/momento/state/KILL`. Does not flatten.
Stop = systemd stop (fail-closed; not the same as kill).

---

## Duplicate Implementations

| Implementation | Class | Notes |
| --- | --- | --- |
| `momento-live.service` + `apps/trading-engine` live | CANONICAL | Sole production submitter |
| `momento-paper.service` | DUPLICATE binary, different mode | Conflicts with live; no live submit |
| `momento-demo@.service` | DUPLICATE binary, demo env | Jump new bots; `live.enabled=false` |
| Vital Python package | CANONICAL control / ledger | Does not submit |
| Jump HTTP + catalog | PROXY / OBSERVATION | Client of Vital for Bot One |
| `apps/jump-fills-read` | PROXY | Read-only Kalshi CLI |
| Jump `host_state.py` SSM Bot One | LEGACY | Superseded by Vital for Bot One (`test_bot_one_runtime_comes_from_vital_not_ssm`) |
| Jump registry `mlb-bot-one` vs Vital `mlb-001` | PROXY alias | Same desk; two IDs |
| Replay / engine tests | TEST | No live submit |
| Local Mac `terminal_api.py` | DEV | Not the AWS runtime |
| Catalog fill rows vs host fill_history | OBSERVATION vs CANONICAL | ID formats do not match (0 reconciled) |
| Second Vital/Jump worker that submits | PROHIBITED | Must not be created |
| RDS | ABSENT | Do not invent |

---

## MLB Bot 001 Folder Boundary

**FACT** — Isolated disk tree already exists and is the only Vital bot:

```text
research/vital/bots/mlb-001/
  metadata/      bot.json
  source/        fingerprints.json
  config/        identity.json
  deployment/    identity.json
  runtime/       desired.json observed.json confirmed.json
  logs/          empty on this Mac
  events/        events.jsonl
  execution/     fills.jsonl  observed.json
                 trades.jsonl ABSENT
```

Seeded by `ROLLER/roller/vital/store.py` `TREE_DIRS`:

```text
metadata source config deployment runtime logs events execution
```

Plus top-level `research/vital/commands/`.

### Proposed canonical locations (document only — not created / not moved)

```text
PROPOSED MLB BOT 001 ROOT
  research/vital/bots/mlb-001/

FRONTEND
  frontend/vital-terminal/          shared Vital dashboard
  (later: bot-specific route, not a second Vite app)

BACKEND / CONTROL PLANE
  ROLLER/roller/vital/              shared package
  /vital/bots/mlb-001/*             bot-scoped API

WORKER (current factual)
  apps/trading-engine               unchanged in Phase 1–2
  deploy/momento-live.service

STRATEGY (current factual)
  strategies/mlb                    unchanged in Phase 1–2

CONFIG
  research/vital/bots/mlb-001/config/
  pointer → config/live.toml

DEPLOYMENT
  research/vital/bots/mlb-001/deployment/
  pointer → deploy/momento-live.service

DOCS
  research/vital/bots/mlb-001/      plus this file
  research/vital/OWNERSHIP.md
```

**Unsafe (HIGH):**

- Turning `strategies/mlb` into a shared dump for Bot 002+.
- Creating `momento/vital/bot-worker` that also submits to Kalshi
  (second engine).
- Moving crates into `vital/bots/mlb-001/source` (breaks Cargo and the
  live binary path; already warned in `RECON.md` §9).

Phase 2 (only after acceptance) may add an isolated **package
boundary around these pointers**. It must not copy the engine.

Requested: `VITAL / MLB Bot 001 / {backend, worker, strategy, …}`.
**FACT:** worker and strategy crates are still repo-global. The
requested tree is the **target shape**, not the present tree.

---

## Data / State Ownership

| Fact | Owner today | Tag |
| --- | --- | --- |
| Open / closed logical trade | Engine `Position` (one per game) | FACT |
| Fill list on host | `fill_history[]` inside that Position | FACT |
| Fill list on desk | Vital `fills.jsonl` (139) + Jump catalog (139) | OBSERVED |
| Logical trades on desk | Absent (`trades.jsonl` missing) | OBSERVED |
| Bankroll | Host weekly snapshot; Jump `bankroll_history.jsonl` | FACT |
| Desired / observed / confirmed | Vital `runtime/*.json` | FACT |
| Commands | `research/vital/commands/{id}.json` | FACT |
| Kill switch file | Host `state/KILL` | FACT |
| RDS rows | None | FACT |

Engine persistence: **no append-only host fill log**. The runtime file
is overwritten ~5s. That is why Vital keeps its own ledger
(`EXECUTION_LEDGER_RECON.md` §1).

---

## Current Trade Display Failure

What the Vital MLB 001 page shows is **not a broken paint of a good
ledger**. It is the honest rendering of the current contract.

```text
FILL   ≠  TRADE
jump_trade_id  =  one catalog / Vital fill row
engine Position  =  one logical trade per game
```

### Trades stay `OBSERVATION_UNAVAILABLE`

**FACT** — `ROLLER/roller/vital/reconcile.py` reconstructs trades only
from host `tracker.positions[]`. Jump catalog is fills only.

**FACT** — Precedence (`EXECUTION_LEDGER_RECON.md` §4):

```text
HOST_LEDGER readable  → fills + position trades
JUMP_CATALOG readable → fills only (no trade reconstruction)
neither + empty Vital ledger → OBSERVATION_UNAVAILABLE
```

**OBSERVED** — `execution/observed.json` (2026-09-14T16:36:53Z):

```text
host.status = OBSERVATION_UNAVAILABLE
host.detail = host state path unset
catalog.status = CONFIRMED
trades_opened = 0
```

**OBSERVED** — `trades.jsonl` does not exist.
`GET /vital/bots/mlb-001/execution` therefore reports
`trades_status: OBSERVATION_UNAVAILABLE` and a fill blotter.

### The table is a fill blotter

**FACT** — `frontend/vital-terminal/src/BotDetail.tsx` lists fills:
time, market, qty, price, amount, kind, source.

There is no entry/exit pair, no game name, no bankroll %, no allocated
ROI. Those fields are not on a fill.

`jump_trade_id` in the catalog is **one row per fill**, not
entry→exit (`EXECUTION_LEDGER_RECON.md` §2).

### Market is `OBSERVATION_UNAVAILABLE` on most rows

**FACT** — Catalog `source=ledger` rows typically have `"ticker": null`
(`research/jump/catalog/trades.jsonl`).

**FACT** — `KALSHI_ACCOUNT` / catalog Kalshi-sourced rows often have a
ticker (`KXMLBGAME-26AUG291915TEXMIL-MIL`) but qty / kind / premium
often unread (`EXECUTION_LEDGER_RECON.md` §2 table).

**FACT** — Ledger hashes and Kalshi UUIDs do not match. Catalog file
is documented as **0 reconciled**. Do not invent a merge key.

### Mixed sources look like two books

| Source label | Meaning | Typical gap |
| --- | --- | --- |
| `JUMP_CATALOG` | Catalog observation (`SOURCE_CATALOG`) | ticker null; qty/price often present |
| `KALSHI_ACCOUNT` | Catalog Kalshi-sourced (`SOURCE_KALSHI`) | ticker often present; other fields unread |
| `HOST_LEDGER` | Host position fills | Unread on this Mac |

Same economic event can appear twice. The page feels empty and
duplicate at once.

### Bankroll percentages cannot come from a blotter

**FACT** — Allocation % needs entry premium and bankroll-at-entry
(weekly snapshot / `bankroll_history.jsonl`).

**FACT** — Return % and allocated ROI need a **closed trade**, not one
fill.

Missing bankroll or missing exit = `UNAVAILABLE`, never `$0` / `0%`.

Phase 1 documents this gap. It does **not** group unpaired fills into
fake trades to make the page look better.

---

## Vital Bot Standard — Trade-Row Contract (locked, not implemented)

Every Vital bot (001, 002, …) must eventually expose this **backend**
object. The frontend only renders it.

```text
ONE ROW  =  ONE MARKET  =  ONE LOGICAL TRADE
```

Authoritative grouping when host is readable: engine `Position`
(already one per game).

Integer cents and basis points. No `f64` money.
Reuse `crates/pnl` ≡ `ROLLER/roller/jump/dashboard/ledger.py`
`realized_from_position`. Do not invent a second PnL.

### Required fields

| Field | Meaning | Unreadable / open |
| --- | --- | --- |
| `market` | Kalshi ticker | `UNAVAILABLE` |
| `game` | Human game (teams + side) from ticker / host | `UNAVAILABLE` |
| `entry_price_cents` | Qty-weighted entry YES price | `UNAVAILABLE` |
| `exit_price_cents` | Qty-weighted exit (liquidation and/or settlement) | `UNAVAILABLE` if open |
| `amount_traded_cents` | Entry premium paid | `UNAVAILABLE` |
| `amount_exited_cents` | Exit proceeds (liquidation premiums + settlement) | `UNAVAILABLE` if open |
| `bankroll_at_entry_cents` | Weekly snapshot / history at entry | `UNAVAILABLE` |
| `pct_bankroll_allocated_bp` | `amount_traded / bankroll_at_entry` in basis points | `UNAVAILABLE` |
| `pct_bankroll_returned_bp` | `amount_exited / bankroll_at_entry` in basis points | `UNAVAILABLE` if open |
| `pct_allocated_pnl_bp` | `(amount_exited - amount_traded) / amount_traded` bp | `UNAVAILABLE` if open |

Honesty:

- Open trade: exit, returned %, allocated PnL = `UNAVAILABLE` (not 0).
- Unread host + no confirmed market grouping = trade list
  `OBSERVATION_UNAVAILABLE` (not invented rows).
- Fills remain **drill-down**, not the default table.

Existing Vital `TRADE_FACT_KEYS` (`execution.py`) already have entry /
exit amounts and prices plus gross/net realized. They do **not** yet
include `game`, `bankroll_at_entry_cents`, or the three basis-point
fields. That is a **gap to implement in a later accepted phase**
(ledger / Phase 6), not in Phase 1.

### CRITICAL product vs honesty conflict

**Question (do not decide by coding in Phase 1):**

If host stays unread, may Vital group `KALSHI_ACCOUNT` fills by ticker
into candidate trades so the page shows one row per market?

**FACT** — Phase 1 ledger recon said **no**
(`JUMP_CATALOG readable → fills only`).

That conflict was **CRITICAL**. A human had to accept a later phase
before any catalog-ticker reconstruction.

**Accepted 2026-09-14 (operator):** when the host is unread, group only
fills that already have a CONFIRMED `KXMLBGAME` ticker. `JUMP_CATALOG`
rows with `ticker: null` stay fills. Optional read-only observe:
`POST /vital/bots/{id}/kalshi/observe`. Do not invent CLOSED / PnL. Do
not merge unmatched ledger hashes onto Kalshi UUIDs.

---

## Migration Risks

| Risk | Rank | Notes |
| --- | --- | --- |
| Inventing trades from unpaired catalog fills | CRITICAL | Would violate ledger recon; false PnL / false market rows |
| Second worker that also submits to Kalshi | CRITICAL | Duplicate execution; double orders |
| Treating Jump as the execution home | CRITICAL | Repo refutes it; wrong ops target |
| Moving `apps/trading-engine` / `strategies/mlb` into a Vital folder | CRITICAL | Breaks Cargo + live binary path |
| Inventing RDS as if it already held truth | CRITICAL | No RDS; would orphan host JSON |
| Double execution (Mac worker + AWS unit) | CRITICAL | Prohibited |
| Enabling `VITAL_AWS_CONTROL` casually | CRITICAL | Can start/stop production |
| `POST /start` confused with `ENABLE_LIVE_TRADING` | CRITICAL | Already rejected in control.py |
| Host unread → empty trades shown as `[]` / `$0` | HIGH | Must stay `OBSERVATION_UNAVAILABLE` |
| Catalog + Kalshi duplicate fills merged on guessed IDs | HIGH | 0 reconciled; ID formats differ |
| Stale `i-0f0849d5829476c31` | HIGH | Re-verify before hard identity |
| Jump legacy SSM Bot One vs Vital | HIGH | Two observe paths; Vital is canonical |
| Kill vs stop vs flatten | HIGH | Kill ≠ stop; kill does not flatten |
| Frontend restyle without backend trade objects | HIGH | Would paint fake completeness |
| `strategies/mlb` reused as Bot 002 dump | HIGH | Destroys isolated-bot blueprint |
| Secrets leaking into API / UI / bot.json | HIGH | Absolute refusal |
| Paper / demo unit mistaken for live | MEDIUM | Same binary; config differs |
| Local `terminal_api.py` mistaken for AWS runtime | MEDIUM | Desk-only |
| Empty Vital `logs/` taken as no host logs | MEDIUM | Journal is on the host |
| DATA-INGEST CFN / collector timers | LOW | Isolated from live |
| Stale RECON.md line “Vital not implemented” | LOW | Historical; phases later marked IMPLEMENTED |
| SuperASI ITI contamination of runtime | MEDIUM if started now | Phase S is separate; out of this file's build |

Rollback: Phase 1 changes no production code. Rollback is “do not
accept / do not start Phase 2.”

---

## Unknowns

- Whether `momento-live.service` is **currently active** on the
  documented instance.
- Whether the host binary SHA256 matches this git tree.
- Whether `i-0f0849d5829476c31` is still the live instance.
- How the **live** binary is installed today (paper S3 path is
  documented; live path is inferred).
- Whether DATA-INGEST CloudFormation is deployed (docs:
  `LOCAL_CRON_ONLY`).
- External monitors (Datadog, PagerDuty, etc.) — none in repo.
- Host `live-runtime.json` contents from this Mac (path unset).
- Per-trade bankroll-at-entry series sufficient for the three %
  fields without host / history alignment.
- Whether a later phase will accept ticker-grouped catalog trades
  when host stays unread.

---

## Recommended Canonical Architecture

Map the requested five-system shop onto **facts**, and keep the
requested Vital-owned-worker lock as the **target**, not the present.

```text
TODAY (factual)

  TRADING CONTROL     frontend/vital-terminal + Jump client
  CONTROL PLANE       ROLLER/roller/vital + /vital/*
  TRADING ENGINE      momento-live.service / apps/trading-engine
  OBSERVABILITY       journal + Vital observe + fill ledger
  DURABLE STATE       host JSON + Vital jsonl   (no RDS)

TARGET (requested; not built)

  VITAL               owns workers, bot logic, backend
  JUMP                dashboard client; reads/writes Vital
  ONE ROW PER MARKET  backend trade object on every bot
  RDS                 not present; do not invent in Phase 1
```

Do not collapse MODEL / RISK / EXECUTION into “the bot traded.”
Do not put the frontend on the critical path: if Vital UI is down,
`momento-live.service` must remain a valid runtime (it already is).

---

## Ownership Lock

### Requested lock (human, 2026-09-14)

```text
VITAL
  = Momento algorithmic execution arm
  = owns bot workers, bot logic, backend

JUMP
  = dashboard client of Vital
  = reads / writes Vital so the operator can edit via Jump
  = does not own runtime

LOCAL MAC
  = development / research only

GITHUB ACTIONS
  = none in repo; deploy/automation only if added later

DUPLICATE EXECUTION PATHS
  = prohibited

AWS RDS
  = requested durable truth  —  NOT PRESENT
```

### Factual lock (repository, 2026-09-14)

```text
VITAL
  = control plane / observability / execution ledger
  = LIVE_EXECUTION = False

JUMP API
  = operating terminal; Bot One observation via Vital
  = LIVE_EXECUTION = False
  = no worker

CANONICAL PRODUCTION EXECUTION
  = AWS systemd momento-live.service
  = /usr/local/bin/momento-trading-engine
  = apps/trading-engine + crates/risk + strategies/mlb

DURABLE TRUTH TODAY
  = host live-runtime.json (when readable)
  = Vital append-only fills.jsonl
  = RDS absent

GITHUB ACTIONS
  = absent

LOCAL MAC
  = Vital/Jump/ROLLER UI + terminal_api.py
```

### CONFLICT

```text
REQUESTED  Vital owns the worker
FACTUAL    the worker is momento-trading-engine under momento-live.service

REQUESTED  RDS is durable truth
FACTUAL    RDS does not exist

REQUESTED  one row per market on the Vital page
FACTUAL    page is a fill blotter; trades unread without host positions
```

**This file does not resolve the conflict.**
It does not move the engine.
It does not create a second worker.
It does not invent trades.

A human must accept this recon (and later, any Phase that changes
factual ownership) before Phase 2.

---

## Phase 1 Acceptance Checklist

- [x] Where does MLB Bot 001 currently execute?
      AWS `momento-live.service` → `momento-trading-engine` (when armed).
- [x] Which exact Jump process owns execution?
      **None.** Jump is not the execution home.
- [x] Which files own that runtime?
      `deploy/momento-live.service`, `apps/trading-engine/`,
      `strategies/mlb/`, `crates/risk/`, `config/live.toml`.
- [x] Which API owns orchestration (control / observe)?
      `/vital/*` on `ROLLER/scripts/terminal_api.py`.
- [x] Which VITAL files own the control-plane surface?
      `ROLLER/roller/vital/*`, `frontend/vital-terminal/`.
- [x] Which RDS resources contain durable state?
      **None.** Host JSON + Vital jsonl.
- [x] Where are credentials sourced?
      Secrets Manager `momento/kalshi/production` → tmpfs; Vital does
      not read the file.
- [x] How does heartbeat work?
      Engine overwrites `live-runtime.json` ~5s; Vital observes;
      unread → `OBSERVATION_UNAVAILABLE`; no auto-restart from Vital.
- [x] Which GitHub Actions affect production?
      **None** in repo.
- [x] Are duplicate execution paths present?
      Same binary, paper/demo/live modes. Only live submits.
      Jump/Vital do not submit. Catalog is observation.
- [x] Where should the isolated MLB Bot 001 folder live?
      `research/vital/bots/mlb-001/` (already). Do not move crates.
- [x] What are the migration risks?
      Ranked above. Critical: second worker, invented trades, RDS fiction.
- [x] What remains unknown?
      Listed above (host liveness, instance id, live install path, …).
- [x] Is the canonical execution home definitively Jump?
      **No. FACT: it is `momento-live.service`.**
- [x] Requested Vital-owned-worker lock vs factual engine lock is explicit.
- [x] Fill blotter failure explained (ticker null, host unread, fill ≠ trade).
- [x] One-row-per-market trade contract locked (not implemented).
- [x] No invented trades / no BotDetail rewrite / no production code change.

---

## STOP

```text
PHASE 1
RECON COMPLETE
        ↓
ACCEPTED  2026-09-14
        ↓
STOP
```

Phase 1 is **ACCEPTED**.

Do not start Phase 2 in this step.
Do not build the bot.
Do not build the frontend.
Do not reconstruct trades from catalog.
Do not migrate SuperASI.
Do not enable `VITAL_AWS_CONTROL`.

Phase 2 (isolated folder foundation) requires a separate explicit start.
