# MLB Bot 001 — Phase 4 Trading Runtime / Worker

Dated: 2026-09-14.

This file is Phase 4. It does **not** create a Jump worker or a second
Python submitter.

## FACT

Phase 1 recon already established the canonical runtime:

```text
systemd  momento-live.service
binary   /usr/local/bin/momento-trading-engine
cwd      /var/lib/momento
config   /var/lib/momento/config/live.toml
```

Repo pointers (unchanged):

```text
unit     deploy/momento-live.service
source   apps/trading-engine
```

If Vital UI, Vital API, and Jump all disappear, that unit still runs.

## Contract

`GET /vital/bots/{id}/worker` (`roller.vital.mlb_001.worker`) reports:

| Field | Value |
| --- | --- |
| `independent_of_vital` | `true` |
| `vital_submits` | `false` |
| `second_worker` | `false` |
| `moved` | `false` |
| `if_vital_down` | `continues` |
| `unit` | `momento-live.service` |
| `submitter` | host binary |
| unread host | `OBSERVATION_UNAVAILABLE`, not `RUNNING` |

Vital's role is observe + fail-closed control. It is not the process
manager that must stay up for MLB 001 to execute.

## Acceptance checklist

- [x] Worker contract points at the existing systemd unit
- [x] Worker can run independently of Vital (`independent_of_vital`)
- [x] No second submitter added
- [x] `apps/trading-engine` not moved
- [x] Host unread remains `OBSERVATION_UNAVAILABLE`

## STOP

Do not SSM start/stop/restart/kill `momento-live.service` in this phase.
Do not start Phase 6.
