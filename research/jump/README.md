# Jump

Data Modeling filesystem in the ROLLER Vite app:
`http://127.0.0.1:5179/?app=jump`.

```
ROLLER + SUPERASI → Jump Drive (folders / strategies / results / ITI pointers)
```

```
JUMP = DRIVE
NO BOT UI
NO VITAL ON JUMP
BROWSER IS NOT THE ENGINE
CANDLE PATH ≠ ACTUAL FILL
ITI LINEAGE ≠ LIVE SIGNAL
DO NOT CHANGE LIVE FIRST01 / 80/81/83/89
DO NOT START W9
```

Jump organizes pointers. It does not copy warehouses, create bots, or
open Vital. Drive API: `GET /jump`, `/jump/tree`, `/jump/folders/*`.
Data plane: `/jump/data/*`, explorer `#/{sport}/data`. Spec:
`research/jump/JUMP_CANONICAL_DATA_PLANE_V0.md`. How-to:
`docs/operations/JUMP_DATA.md`.
`/jump/bots*` remains compatibility HTTP for Vital until that backend
is migrated. ITI lives on SuperASI (`/superasi/iti/*`).

Jump is not a trading system and does not submit orders from the browser.
This is not the Lebronner five-weight “Ian Tali Index.”

## Jump-AE — name the engine; do not rebuild it

**Jump-AE** is the existing write path, not a second Risk or order router:

```
strategy proposes → Risk Decision Engine → apps/trading-engine executes
```

Factory identity is `mlb_factory_v1`. MLB **Bot One** (`mlb-bot-one`, host
`momento-live.service`) is the production foundation. New bots are isolated
`momento-demo@<id>` units of the same binary + Risk + locked MLB factory.

Jump reads Vital-confirmed state. It does not start `momento-live.service`.
It does not nest a second Risk. It does not move `strategies/mlb`. It does
not POST Kalshi orders from Python or the browser. Dashboard books come
from Vital observe, including Demo top-level versus sports shard 3.

## Jump A — Ian Taleb Index

From one SuperASI Final Result, ITI clones the persisted
`ResearchQuestion` and builds a frozen 25-slot price catalog: ±5% of
each condition’s current cents, up to 3 steps. Same ROLLER ops. Missing
question → `DATA_REQUIRED`. Inverted win/loss vs entry → `SKIPPED`.

Each runnable slot is warehouse execute, Labs save, SuperASI A, SuperASI
B. The desk orchestrator is `optimized`: no extra compile, sequential
in-process warehouse (keeps the index warm), SuperASI A+B pipelined
behind the next warehouse slot, and `ITI-00` reused when the source
question hash matches. Ranked by `DEBASE_GRADE` then `BASE_GRADE`. You
pick one.

Per-slot stage timings (`compile_ms`, `execute_ms`, `lab_ms`, `base_ms`,
`debase_ms`, `slot_ms`) are written to `job.json` and
`research/jump/library/<run_id>/timings.json`. Do not invent totals.

Full-path stress (fresh Confirm & Run → SuperASI A+B → 25-slot ITI):

```text
cd ROLLER && .venv/bin/python scripts/jump_iti_stress.py --pass all
```

Facts land in `research/jump/stress/`.
Commit writes `{strategy}_ITI` under the source Phase B folder:

```
superasi_labs/phase_b/<Strategy>/<Strategy>_ITI/
  metadata.json
  Roller[<Strategy>_ITI]/Roller[<Strategy>_ITI].csv
  SuperasiABase[<Strategy>_ITI]/SuperasiABase[<Strategy>_ITI].csv
  SuperasiBDeBase[<Strategy>_ITI]/SuperasiBDeBase[<Strategy>_ITI].csv
```

The source Roller / SuperASI A / SuperASI B files are not rewritten.

## Compatibility backend — to be migrated

The sections below document remaining Jump Python / HTTP that Vital still
imports. They are not Jump UI. Do not add them back to `?app=jump`.

## Jump B — Bot Creation

Jump Python still owns bot identity records for Vital. It does not move
`apps/trading-engine` or `strategies/mlb`. It does not reimplement
`MlbStrategy`. It does not submit Kalshi orders.

- **Bot One** (`mlb-bot-one`) is the already-running MLB desk. Grandfathered.
  No ITI required. Status comes from a read-only host probe. If the probe
  is unset or unreachable: `OBSERVATION_UNAVAILABLE`. Jump does not invent
  RUNNING or P&L.
- **New bots** must pick a committed `{name}_ITI` folder (`artifact=jump_iti`).
  ITI is versioned lineage. The live signal stays the MLB factory
  (80→81, maker 80–83, 89 lock, Risk in the middle).
- **Factory** `mlb_factory_v1` is a display/identity snapshot: $50 bankroll,
  12.5%, $6.25/game, max 5 MLB, entry 80–83. Not an algorithm editor.
- **Create Bot** always starts `DEMO` (`MOMENTO_KALSHI_ENV=demo`). Missing
  AWS/demo credentials → `DEPLOY_REQUIRED`, not fake RUNNING.
- **Production** is a separate confirmed action: `mode=live`,
  `live.enabled=true`, `confirmation=ENABLE_LIVE_TRADING`. A second live
  MLB factory while Bot One is the live host is refused.

Registry: `research/jump/bots/`.
Package: `ROLLER/roller/jump/bots/`.
API: `GET /jump/bots`, `GET /jump/bots/{id}`, `POST /jump/bots/draft`,
`POST /jump/bots`, `POST /jump/bots/{id}/production`.
Dashboard: not on Jump. Vital owns the MLB console.

## Trade catalog

Append-only store under `research/jump/catalog/` (not inside `job.json`).

Jump shells a read-only Rust CLI (`apps/jump-fills-read`) that uses the
existing Kalshi crate + a secret file. Demo secret id is
`momento/kalshi/demo`. Production is `momento/kalshi/production`. The CLI
refuses using the production secret against the demo host and the reverse.
Jump never logs the secret. Missing secret or host → that book is
`OBSERVATION_UNAVAILABLE`. Host ledger trades still show.

Each record has a stable `jump_trade_id`, `bot_id` or `UNATTRIBUTED`,
`DEMO` | `PRODUCTION`, Kalshi ids, ticker, integer cents, qty, `exchange_ts`,
`result` from host ledger `realized_cents` when the position rule allows
(else `UNAVAILABLE`), and `source` `kalshi` / `ledger` / `reconciled`.

**Linking:** Kalshi fill ↔ host `fill_history` on ticker/market, timestamp
(±5 seconds), price cents, and qty. Production matches go to Bot One. Demo
matches go to the demo unit whose isolated `live-runtime.json` contains that
fill. No match → `UNATTRIBUTED`. Never guess a bot.

**First Bot One trade:** the earliest confirmed MLB fill on the Bot One host
ledger. Persist that `exchange_ts` as `catalog.origin.bot_one_first_fill_ts`.
Do not invent a date. Production catalog rows start at that fill, not before.

Candle charts on posts are observational yes-bid SVG around the fill.
Candle path ≠ fill. L2/tick stay `DATA_REQUIRED`. Missing candles →
`DATA_REQUIRED`, not a fake path.

API: `GET /jump/catalog`, `GET /jump/catalog?environment=`,
`GET /jump/bots/{id}/trades` (catalog-backed), `POST /jump/catalog/refresh`
(read-only pull).

## Jump C — Operating Dashboard

Jump C is the operating dashboard. It is not an engine. Tracks are Jump B
bots (Bot One first). Actual and expected stay separate. Confirmed
heartbeat keys may display. Bot One MLB day/week PNL is read from the
host ledger (`live-runtime.json`) with the same integer formula as
`crates/pnl` `PnlBreakdown::from_position`. Live EV does not exist on
the desk and stays `UNAVAILABLE` — SuperASI/ITI EV is not stamped onto
Bot One. Missing host state is `OBSERVATION_UNAVAILABLE`, not `$0`.
The rollup does not sum missing fields into `$0`. Dashboard rollups read the
trade catalog when present and still do not add demo cents to live cents.
ITI grades stay research lineage, not live Ex. PNL.

Set `JUMP_BOT_ONE_STATE_DIR` to a directory containing `live-runtime.json`
and optional `weekly-snapshot.json`, or set `JUMP_BOT_ONE_HOST_FETCH=ssm`
to read `/var/lib/momento/state/` on the Bot One instance. Probe JSON
may also include `day_pnl_cents` / `week_pnl_cents`.

Package: `ROLLER/roller/jump/dashboard/`.
API: `GET /jump/dashboard`, `GET /jump/dashboard/logs`.
UI: not on Jump. HTTP remains until backend migration.

## My Bots — sequence 05

Prefetch `GET /jump/mybots` with health/dashboard. Payload includes every
profile and its posts. First paint must not show “Loading profile…”.

Posts (identity feed, not followers):

- one post per catalog trade: identity, realized result or `UNAVAILABLE`, chart SVG or `DATA_REQUIRED`
- one weekly snapshot post per Pacific week (Monday 04:00 PT)
- one every-10-trades snapshot post (n=10, 20, 30, …)

Dashboard track click opens that bot’s statically loaded profile.

## Layout

Package: `ROLLER/roller/jump/` (`iti/`, `bots/`, `dashboard/`, `catalog/`).
API: `GET /jump/health`, `/jump/iti/*`, `/jump/bots/*`, `/jump/dashboard`,
`/jump/catalog`, `/jump/mybots`.
Dashboard: `frontend/roller-terminal/src/jump/` is Drive only.
Vital dashboard (separate instance): `frontend/vital-terminal` on `:5180`.
Jump frontend does not call `/vital/*`.
ITI jobs: `research/jump/library/`.
Bot records: `research/jump/bots/`.
Catalog: `research/jump/catalog/`.
