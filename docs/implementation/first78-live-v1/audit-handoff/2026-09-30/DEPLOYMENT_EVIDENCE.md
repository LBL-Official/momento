# Deployment evidence (read-only)

No service was restarted. No production order was sent. `VITAL_AWS_CONTROL` remained unset.

## Identity

| Field | Value |
|---|---|
| Observed at | **2026-09-30T13:55:53Z** (host `date -u`) |
| AWS account | `895492487332` |
| Region | `us-east-1` |
| Instance | `i-0f0849d5829476c31` |
| Arch | `aarch64` |
| SSM command (identity) | `7bb420af-430b-4358-9a0d-24b846412e81` |
| SSM command (contract + heartbeat) | `5bddb119-9568-4a6b-a8c3-a618f0be1276` |
| Prior inventory | `0dbaa619-ad89-41ed-978f-d8f75d8c0e4a` at 2026-09-30T13:53:56Z |

Preflight `deploy/nba001-v1-preflight.py --expected-account 895492487332` at ~13:55Z: account verified, SSM online, exit 78, blocker `HOST_RUNTIME_AND_LIVE_READINESS_NOT_VERIFIED`.

## `momento-nba-001.service` (what is actually running)

| Field | Observation |
|---|---|
| Active / sub | active / running |
| UnitFileState | **enabled** |
| ExecStart | `/usr/local/bin/momento-nba-001 run` |
| PID | 1619966 (also holds `lease.lock`) |
| Process start | 2026-09-27T04:30:09Z |
| Binary mtime / size | 2026-09-27 04:30, 4939232 bytes |
| Binary SHA-256 | `9ef129e1d8b1ee111666e80265d70cd3dad1ddfa3dd5017d9865b848e57d6789` |
| `--version` | `momento-nba-001 0.1.0 build=nba001-20260927T042347Z submission_adapter_linked=false` |
| Config SHA-256 | `fff031f2736f38f0fe00373de0844ab18dfaccaee856b86bc4bf47583b21434c` |
| Host contract SHA-256 | `ef1c488ab450aadd82e78c2bde2f40506d6baccee15e35f4e09fb3f9869d5ab9` |
| Mode | **SHADOW** |
| Live gates | `enabled=false`, confirmation empty |
| Submits | false |
| Blockers in `status.json` | 7: `CONTRACT_UNRESOLVED` (`hedge_ladder_advancement`), `EXIT_CAPACITY_UNBOUNDED`, `FEE_UNVERIFIED`, `LIVE_GATES_UNSET`, `ROUTE_CONFLICT` (series 3 vs market 0), `SHARED_COLLATERAL_UNACCOUNTED` (`momento-live.service`), `SUBMISSION_ADAPTER_NOT_LINKED` |
| Heartbeat 13:55:30Z | `games=3 feed_age_s=121 account_ok=true shard0_cents=5741 shard3_cents=56` |
| Feed | Kalshi public `live_data`; `feed_age_s` cycles 0–300 while no game is in the 24h window (see `docs/operations/NBA_001.md`) |
| ESPN | **not** in this deployed FIRST78_67 worker. V1 ESPN adapter is source-only |
| Restart | `Restart=always`, `RestartPreventExitStatus=78`, `StartLimitBurst=10`, `StartLimitInterval=5min` |
| Backup binary | `/usr/local/bin/momento-nba-001.9ef129e1.bak` (same digest) |

This binary is **not** commit `2a22a2a`. It is FIRST78_67 GET-only. Host `capital.reference_capital_cents = 2000000` is the **legacy** config; V1 source must not use it for sizing.

`status.json` `contract_sha256` equals the host contract file. Repo `execution_contract.json` SHA `b8d119a5…` **differs** from the host file. Do not assume they are identical.

## `momento-live.service` (MLB + WNBA)

| Field | 2026-09-30T13:56:12Z heartbeat |
|---|---|
| Active / enabled | active / **enabled** |
| Mode | **Live** |
| `order_submission` | **enabled** |
| MLB / WNBA strategies | active / active |
| `open_mlb_positions` / `open_wnba_positions` | 0 / 0 (host heartbeat, **not** a signed GET) |
| `unknown_orders` | 0 |
| `bankroll_cents` | 5000 |
| Same minute | journal still `fill_coalesced` and `fill_fractional_unrepresentable` |

**Retirement is incomplete.** Stop/disable was not performed. Shared infrastructure left running. See `research/vital/bots/nba-001/retirement/STOP_BLOCKED.json`.

No momento cron/timer resurrection unit was listed in `systemctl list-timers` (only OS timers). That is not proof no CI redeploy exists.

## Restart / reboot

| Claim | Evidence class |
|---|---|
| systemd will restart NBA 001 except exit 78 | **Configured** on the unit |
| V1 supervisor survives restart and restores epochs | **Implemented** in source (`lease` + `sizing_epochs.json`); **not tested on the host** (V1 not deployed) |
| Host reboot of FIRST78_67 | **Not re-run** in this handoff |

Alert delivery: V1 alert outbox is source-only. Host FIRST78_67 has no V1 P0/P1/P2 Linear outbox.

Rollback: `deploy/nba001-atomic-deploy.sh` refuses `live` mode; host has `.9ef129e1.bak`. Restoring that backup was **not** executed.

## Single-writer / state

State dir `/var/lib/momento/nba-001` (`journal.jsonl`, `lease.lock`, `state.json`, `status.json`). PID 1619966 holds the lease. Secret file present at `/dev/shm/momento-kalshi-nba-001.json` — **not read**.
