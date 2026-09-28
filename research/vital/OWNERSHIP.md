# Vital — Production ownership

Dated: 2026-09-13.

Bot Standard Phase 1 (2026-09-14): **ACCEPTED**.
Phase 2 isolated folder: `research/vital/BOT_001_PHASE2.md`.
Phases 3–6 (2026-09-14): control plane / worker / pipeline / trade row —
`research/vital/BOT_001_PHASE3.md` … `BOT_001_PHASE6.md`.
Requested Vital-owned-worker lock vs factual `momento-live.service`
execution remains recorded in `research/vital/BOT_001_PHASE1_RECON.md`.
This file is not silently rewritten.

```text
Vital = canonical owner of MLB 001
Jump = client of Vital
Execution = same
```

```text
MLB 001
  → VITAL
  → existing AWS unit (momento-live.service)
  → apps/trading-engine
  → crates/risk
  → Kalshi Create V2
```

## Unchanged execution

- `strategies/mlb` 80/81/83/89
- `crates/risk` Risk Decision Engine
- `apps/trading-engine` live submit
- Triple live gate: `mode=live` AND `live.enabled=true` AND `confirmation=ENABLE_LIVE_TRADING`
- Kill = existing host `state/KILL` (does not flatten)
- `POST /vital/.../commands` start ≠ live arm

## Secrets

Never in API bodies, frontend, `bot.json`, events, or logs.

Host fetch remains:

```text
AWS Secrets Manager momento/kalshi/production
  → m10-fetch-secret.sh
  → /dev/shm/momento-kalshi-live.json
  → trading-engine
```

Vital does not read `/dev/shm/momento-kalshi-live.json`.

## Execution ledger

Vital is the execution-observation and execution-history layer for MLB 001.

```text
research/vital/bots/mlb-001/execution/
```

Fills and reconstructed trades are append-only. Host `live-runtime.json`
is authoritative for logical trades. Jump catalog is fill observation
only. Unread sources stay `OBSERVATION_UNAVAILABLE` (not `[]` / `$0`).
Recon: `research/vital/EXECUTION_LEDGER_RECON.md`.

The write path is unchanged: Kalshi WS → `strategies/mlb` → Risk →
`apps/trading-engine` → Kalshi Create V2.

## Live-service integration proof

Formal acceptance of Vital as the control plane over the existing
worker is `research/vital/LIVE_SERVICE_INTEGRATION.md`.

```text
RUNNING ≠ HEALTHY ≠ EXECUTING
DESIRED ≠ WRITTEN ≠ OBSERVED ≠ LOADED
```

L1–L8 stay independent. Demo lifecycle/strategy writes never target
`momento-live.service`. Production L8 is not claimed. No production
test order. No second engine.

## Control gate

Production systemd writes require `VITAL_AWS_CONTROL=1` and
`confirmation=VITAL_ENABLE_CONTROL`. Default is fail-closed.
HTTP 200 ≠ `RUNNING`. Command ACK ≠ confirmed health.

## Dashboard

Vital UI is a separate Vite instance:

```text
frontend/vital-terminal   :5180
frontend/roller-terminal  :5179   ROLLER / SuperASI / Jump
```

Live unit observatory: `:5180#/live`
([`LIVE_SERVICE_DESK.md`](LIVE_SERVICE_DESK.md)).
Layout: [`docs/architecture/MOMENTO_LAYOUT.md`](../../docs/architecture/MOMENTO_LAYOUT.md).

Jump opens that origin. Jump does not embed the Vital shell.

## Jump

Jump may display Vital-confirmed state. Jump does not own MLB 001,
does not own the live AWS unit, and does not keep a second registry
of truth.
