# MLB Bot 001 — Phase 3 Backend Control Plane

Dated: 2026-09-14.

Phase 1 ACCEPTED. Phase 2 isolated folder is in place. This file is Phase 3.

```text
PHASE 3  backend control plane
         MLB BOT 001 API → existing worker
```

No crate move. No second worker. No trade reconstruction. No RDS.
No `VITAL_AWS_CONTROL`. No SuperASI migration. No Phase 6 trade table.

## Contract

Vital page → `/vital/bots/mlb-001/*` → observe / fail-closed control of
the existing host. The frontend does not own trading logic.

Required surfaces:

```text
status, configuration, strategy, positions, orders,
risk, heartbeat, logs, events, controls
```

New first-class GETs (this phase):

| Route | Layer |
| --- | --- |
| `GET /vital/bots/{id}/plane` | catalog of the Bot Standard API |
| `GET /vital/bots/{id}/configuration` | config pointer + factory; no secrets |
| `GET /vital/bots/{id}/strategy` | `strategies/mlb`; proposes; does not submit |
| `GET /vital/bots/{id}/risk` | `crates/risk` pointer; not a second engine |
| `GET /vital/bots/{id}/heartbeat` | host `live-runtime.json` observe |
| `GET /vital/bots/{id}/controls` | fail-closed action contract |
| `GET /vital/bots/{id}/boundary` | Phase 2 pointer map |

Existing surfaces stay: status, health, runtime, deployment, logs,
orders, positions, events, execution observe, `POST /commands`.

Package: `ROLLER/roller/vital/mlb_001/plane.py`.
Handlers: `ROLLER/roller/vital/api.py`.
Mount: `ROLLER/scripts/terminal_api.py`.

## Acceptance checklist

- [x] Backend starts (`/vital/health`)
- [x] Health works
- [x] Status model works (`desired ≠ observed ≠ confirmed`)
- [x] Config boundary works (pointer + factory; start ≠ live arm)
- [x] Worker communication stays observe (`inspect_mlb_001` / heartbeat)
- [x] Auth / control fail-closed (`CONTROL_DISABLED` unless gates set)
- [x] Errors explicit (`BOT_NOT_FOUND`, `REJECTED`)
- [x] No trading logic in the frontend (client GET helpers only)

## Honesty

- HTTP 200 ≠ `RUNNING`
- `ENABLE_LIVE_TRADING` is rejected as a Vital control token
- Unread strategy / risk / heartbeat stay `OBSERVATION_UNAVAILABLE`
- Live EV and Sharpe stay `UNAVAILABLE`
- Secrets are not in API bodies

## STOP

```text
PHASE 3 COMPLETE
        ↓
PHASE 4 worker contract (this session)
        ↓
PHASE 5 pipeline facts (this session)
        ↓
STOP before Phase 6
```
