# Vital Phase 1 — Recon

Dated: 2026-09-13.

**2026-09-14 Bot Standard lock:** MLB Bot 001 Phase 1 recon is
`research/vital/BOT_001_PHASE1_RECON.md` — **ACCEPTED** 2026-09-14.
Phases 3–6: `BOT_001_PHASE3.md` … `BOT_001_PHASE6.md`.
This document stays the 2026-09-13 product recon.

Facts from the repository. Not a design essay. Not Phase 2.

Vital is the planned execution control plane. This file records what exists
today and what must not be moved or rewritten until a later accepted phase.

```text
ROLLER = measure
SUPERASI = research consumer → A Base → B Debase → Final → ITI (target)
VITAL = execution infrastructure (not implemented)
JUMP = terminal; today still owns ITI + bot labels
```

Phases 2–9 + S are implemented in repo. Production systemd writes stay
fail-closed. Do not SSM start/stop/restart/kill `momento-live.service`
unless `VITAL_AWS_CONTROL` is explicitly enabled.
Do not edit `strategies/mlb`, `apps/trading-engine`, `config/live.toml`,
or `deploy/momento-live.service`.

---

## 1. Product map

| Layer | Role today | Role locked |
| --- | --- | --- |
| ROLLER | Research / measurement / warehouse | Unchanged. Does not execute. |
| SuperASI | A Base → B Debase → Final Results | Research consumer. **ITI belongs after Final.** Not implemented yet. |
| Jump | ITI (A), bot registry (B), dashboard (C), read-only Kalshi book | Operating terminal. Later a Vital client. Does not own execution. |
| Vital | `ROLLER/roller/vital/` + `/vital/*` | Canonical bot + AWS + runtime ownership. |
| Jump-AE | Name only | `apps/trading-engine` + Risk + `mlb_factory_v1`. Not a second engine. |

ITI is a 25-slot research catalog graded by SuperASI A+B. It is not a live
signal and not a Vital bot. Jump A is transitional.

---

## 2. Current MLB execution (repository authority)

Write path (unchanged by Vital):

```text
Kalshi WS book
  → MlbStrategy::observe → TradeIntent
  → crates/risk PaperRiskEngine
  → apps/trading-engine live.rs submit_approved
  → KalshiVenue Create V2
```

Strategy does not submit. Risk does not submit. Only an approved intent
reaches the venue.

| Piece | Path | Role |
| --- | --- | --- |
| Host | `apps/trading-engine/src/live.rs` | Live loop: observe → Risk → Kalshi |
| Entry | `apps/trading-engine/src/main.rs` | `mode=live` only after `is_live_armed()` |
| Strategy | `strategies/mlb/` | Locked 80/81/83/89, maker 80–83, 89 lock |
| Risk | `crates/risk/` | Entry / liquidation / occupancy / kill |
| Venue | `crates/kalshi/` | Production transport; secrets never in API |
| Live gates | `crates/core/src/config.rs` | `mode=live` AND `live.enabled=true` AND `confirmation=ENABLE_LIVE_TRADING` |
| Config | `config/live.toml` | Production desk config |
| Unit | `deploy/momento-live.service` | systemd: `/usr/local/bin/momento-trading-engine` |
| Secret fetch | `deploy/m10-fetch-secret.sh` | `momento/kalshi/production` → `/dev/shm/momento-kalshi-live.json` |

Host on the live box (documented; re-verify before any later adapter
hard-codes identity):

- Instance: `i-0f0849d5829476c31` (us-east-1) — observed default in
  `ROLLER/roller/jump/dashboard/host_state.py` and desk docs
- Service: `momento-live.service`
- Binary: `/usr/local/bin/momento-trading-engine`
- Config: `/var/lib/momento/config/live.toml`
- State: `/var/lib/momento/state/live-runtime.json`, `weekly-snapshot.json`
- Kill: `state/KILL` or `MOMENTO_KILL_SWITCH` (existing). Later Vital
  operates this. Do not invent a second flatten.

Factory display identity `mlb_factory_v1`: $50 / 12.5% / $6.25 / max 5 /
entry 80–83. Not an editor.

---

## 3. Current Jump bot architecture

Jump is a research product on the ROLLER terminal API. It observes and
labels Bot One. It does not own the engine.

| Field | Value | Source |
| --- | --- | --- |
| `bot_id` | `mlb-bot-one` | `ROLLER/roller/jump/bots/versions.py` |
| Display | MLB Bot 001 | `research/jump/bots/mlb-bot-one/metadata.json` |
| Kind | `grandfathered` | same |
| Factory | `mlb_factory_v1` | same |
| Engine pointer | `apps/trading-engine` | same |
| Strategy pointer | `strategies/mlb` | same |
| `aws_runtime_id` | `momento-live.service` | same |

On-disk Bot One status is `OBSERVATION_UNAVAILABLE` unless a probe, SSM
ledger, or Kalshi book is present. Jump does not invent `RUNNING`.

| Capability | Supported? |
| --- | --- |
| Observe host ledger | Yes — local path or SSM when `JUMP_BOT_ONE_HOST_FETCH=ssm` |
| Read-only Kalshi book | Yes — `GET /jump/kalshi`, `POST /jump/kalshi/sync` (GET venue only) |
| Start demo unit | Partial — `POST /jump/bots` may SSM-start `momento-demo@{id}` |
| Start/stop/restart/kill `momento-live.service` | No |
| Promote starts live | No |
| Browser POST Kalshi orders | No |

Jump-AE = existing write path, not a second Risk or order router.

---

## 4. API and frontend

- API: `ROLLER/scripts/terminal_api.py` hosts `/jump/*`, `/superasi/*`,
  `/stax/*`. Do not create a second backend framework. Future Vital
  mounts `/vital/*` here (Phase 2+).
- Frontend product switch: `frontend/roller-terminal/src/App.tsx` is
  `"roller" | "superasi" | "jump"`. Vital was first sketched as a fourth
  product in that same Vite app. **2026-09-14:** Vital UI is a separate
  dashboard instance (`frontend/vital-terminal` on `:5180`). Jump opens
  that origin and remains an API client of `/vital/*`.
- SuperASI spine today (`frontend/roller-terminal/src/superasi/navigation.ts`):
  Roller CSVs → A Base → Labs A → B Debase → Final Results.
- Jump spine today includes Ian Taleb Index as the first route. SuperASI
  JUMP button opens Jump at ITI. That split is the failed boundary.

Target SuperASI spine (Phase S, not this slice):

```text
Roller CSVs → A Base → Labs A → B Debase → Final Results → ITI
```

ITI HTTP may stay `/jump/iti/*` until SuperASI owns an equivalent route.
Do not rewrite the 25-slot catalog. Do not convert `{name}_ITI` into a
Kalshi signal.

---

## 5. Credential and heartbeat flow

```text
AWS Secrets Manager momento/kalshi/production
  → m10-fetch-secret.sh on host
  → /dev/shm/momento-kalshi-live.json
  → trading-engine (never Jump, never browser, never Vital API body)

Heartbeat / ledger
  → live-runtime.json on host
  → Jump host_state (local path or SSM) today
  → later: Vital AWS adapter; Jump reads Vital
```

Live EV and Sharpe stay `UNAVAILABLE`. Unread host stays
`OBSERVATION_UNAVAILABLE`. Never invent `$0` or `RUNNING`.

---

## 6. File ownership map

### Remain where they are (do not relocate in Phase 1–4)

Moving these rewrites the Cargo workspace and risks the live host.

- `apps/trading-engine/`
- `strategies/mlb/` — UNTOUCHED (80/81/83/89)
- `crates/risk/`, `crates/kalshi/`, `crates/core/`, `crates/positions/`,
  `crates/pnl/`
- `config/live.toml` as the live unit config until a later equivalence gate
- `deploy/momento-live.service`, `deploy/m10-fetch-secret.sh`
- Host files under `/var/lib/momento/` (artifacts, not canonical source)

### Become Vital-owned (Phase 3+, not now)

Logical tree (disk library; not a second git root):

```text
research/vital/
  bots/mlb-001/
    metadata/bot.json
    source/          # fingerprints + pointers first; no crate move yet
    config/          # versioned snapshots of live.toml / factory
    deployment/
    runtime/         # desired / observed / confirmed
    logs/
    events/          # append-only
  aws/
  commands/
```

Package later: `ROLLER/roller/vital/` + `/vital/*`.

IDs: Vital `bot_id=mlb-001`, aliases `mlb-bot-one` / display MLB Bot 001.
Kind `grandfathered`. Do not invent ITI lineage for MLB 001.

### Become SuperASI-owned (Phase S, not now)

- `frontend/roller-terminal/src/jump/ITI.tsx`
- `ROLLER/roller/jump/iti/`
- `research/jump/library/` (committed `{name}_ITI` folders)
- SuperASI Final → JUMP handoff in `frontend/roller-terminal/src/superasi/SuperASIApp.tsx`

Jump B may still pick a committed ITI folder as research lineage for a
new demo bot. SuperASI produces that folder.

### Stay Jump-owned until Phase 8 (then Vital)

- `research/jump/catalog/` Kalshi/ledger cache
- Jump B/C UI until they become Vital clients

---

## 7. State model (lock now; implement in Phase 2)

Do not collapse into one string `LIVE`.

- Lifecycle: `DRAFT` `CREATED` `DEPLOYING` `DEPLOYED` `STARTING` `RUNNING`
  `STOPPING` `STOPPED` `RESTARTING` `FAILED` `OBSERVATION_UNAVAILABLE`
  `KILLED`
- Environment: `DEMO` | `PRODUCTION`
- Health: `HEALTHY` `DEGRADED` `UNHEALTHY` `UNKNOWN`
- Every runtime fact: **desired / observed / confirmed**
- Command ACK ≠ `RUNNING`
- Unverified deploy ≠ `RUNNING`

---

## 8. Locked waterfall

| Phase | Work | Status |
| --- | --- | --- |
| 1 Recon | This file + agent rule + AGENTS.md pointer | ACCEPTED |
| 2 Skeleton | `ROLLER/roller/vital/`, models, `/vital/health` | IMPLEMENTED |
| 3 Ownership | `research/vital/bots/mlb-001/` fingerprints | IMPLEMENTED |
| 4 AWS adapter | Read-only SSM / systemctl / journal / ledger | IMPLEMENTED (read-only) |
| 5 Observability | Health, logs, existing telemetry | IMPLEMENTED |
| 6 Control | deploy/start/stop/restart; command_id + confirm | IMPLEMENTED (fail-closed) |
| 7 Production ownership | Vital canonical for MLB 001 | IMPLEMENTED |
| S SuperASI ITI | ITI after Final Results | IMPLEMENTED |
| 8 Jump client | Jump reads `/vital/*` | IMPLEMENTED |
| 9 Vital UI | Separate dashboard `frontend/vital-terminal` `:5180` | IMPLEMENTED |

Live write gate remains STOP until an operator sets `VITAL_AWS_CONTROL=1`.

---

## 9. Risks

- Physical crate move into `vital/bots/mlb-001/source` breaks Cargo and
  the live binary path. Pointers + fingerprints first.
- SSM start/stop of `momento-live.service` can halt production. Control
  is Phase 6+. `POST /start` must never equal `ENABLE_LIVE_TRADING`.
- Kill ≠ stop. Kill = existing host kill switch. Stop = systemd stop.
  Do not flatten.
- Do not create a second execution engine.
- After Phase 8, Jump must not keep a second Bot One source of truth.
- Confirm `i-0f0849d5829476c31` before the AWS adapter treats it as identity.
- Jump Kalshi book is observation, not ownership.
- ITI left on Jump keeps research hanging off the operating terminal.
  Move it after SuperASI Final in Phase S, not now.

---

## 10. Absolute refusals

- No ITI → Kalshi signal
- No second Risk, no second engine, no browser submit
- No demo cents added to live cents
- No invented `$0`, Sharpe, live EV, or `RUNNING` from UI success
- No weakening of live gates or kill switch
- Production credentials never in frontend, `bot.json`, logs, or API bodies
- Do not start W9 or warehouse Phase 21
- Do not edit Confirm & Run `execute` / `compiler` / `load_dataset`
