# Vital MLB 001 Connectivity Incident

Dated: 2026-09-16. Incident B only (Vital observe / manage path).

Incident A (stale occupancy / fill ingest) stays
[2026-09-15-vital-execution.md](2026-09-15-vital-execution.md) and was not
repaired here.

```text
DESIRED  ≠  OBSERVED  ≠  CONFIRMED
HTTP 200 ≠ RUNNING
process exists ≠ HEALTHY EXECUTION
stale disk ≠ current host
```

No restart. No `VITAL_AWS_CONTROL`. No `live.toml` / unit / Risk / 80/81 /
Create V2 / credential / bankroll edits.

## Status

**CONNECTED** (observe path, after repair).

Pre-repair classification was **PARTIALLY_CONNECTED**: read-only SSM reached
`i-0f0849d5829476c31` / `momento-live.service`, but Vital omitted recon /
reservations / unknown / `open_slots`, `runtime/observed.json` had no
`observed_at`, GET overlays could keep leftover `RUNNING`, and
`host_fetch_enabled()` defaulted off so in-process Jump missed SSM unless
`terminal_api` had `setdefault("VITAL_AWS_HOST_FETCH", "ssm")`.

Not `BROKEN` (wrong instance/unit or parser refuse). Not
`OBSERVATION_UNAVAILABLE` (SSM auth/dispatch succeeded on the Phase 1 proof).

Occupancy / fill-body / `order_submission=blocked` remain Incident A. They
are now **visible** on the observe path; they were not “fixed” via Vital or
Risk.

## Architecture

Verified call graph (no Jump SSM bypass for Bot One):

```text
Jump dashboard / vital-terminal
  → terminal_api /vital and /jump
    → observe_bot
      → inspect_mlb_001
        → inspect_local (VITAL_BOT_STATE_DIR / VITAL_BOT_RUNTIME_PATH)
        → inspect_ssm if local unread and host_fetch_enabled()
          → i-0f0849d5829476c31  us-east-1
            → momento-live.service
              → /var/lib/momento/state/live-runtime.json
      → compose_runtime desired / observed / confirmed
    → GET /vital/bots/mlb-001 /status /runtime /health
  → Jump vital_client.vital_observe / jump_heartbeat_from_vital
```

| Token | Value |
|---|---|
| bot_id | `mlb-001` (alias `mlb-bot-one`) |
| instance | `VITAL_AWS_INSTANCE_ID` or `i-0f0849d5829476c31` |
| region | `VITAL_AWS_REGION` / `AWS_REGION` / `us-east-1` |
| factory unit | `momento-live.service` (hardcoded in `INSPECT_SHELL`) |
| ITI units | `momento-demo@{id}` / `momento-live@{id}` — `journal_unit()` refuses the factory unit for non-grandfathered bots |
| host runtime | `/var/lib/momento/state/live-runtime.json` |
| host.state | **does not exist**. `load_local_runtime()` is `host state path unset` unless `VITAL_BOT_STATE_DIR` / `VITAL_BOT_RUNTIME_PATH` points at a copy |
| control | `control.py` fail-closed unless `VITAL_AWS_CONTROL=1` **and** `confirmation=VITAL_ENABLE_CONTROL`. Unset. Not enabled. |
| Jump C | `vital_client` in-process. `load_host_state()` sets `ssm_skipped=True`. No second AWS path for Bot One. |

## Direct Host

Read-only SSM on `i-0f0849d5829476c31` at **2026-09-16T20:25Z** using the
existing `INSPECT_SHELL` / `AWS-RunShellScript`. `assert_readonly` stayed on.
`VITAL_AWS_CONTROL` unset.

Direct-host extras (ExecStart / User / cmdline) used one additional read-only
snippet. The unit was not changed.

| Fact | Host |
|---|---|
| systemd | `active` (`momento-live.service`) |
| MainPID | `1101134` |
| start | `2026-09-16 20:00:11 UTC` |
| executable | `/usr/local/bin/momento-trading-engine` |
| SHA256 | `610dd470b1769a0385c81942ec634362ce8607b2db6f8f44156cf7757a147250` |
| `momento-demo@mlb-001.service` | inactive (not the production inspect target) |
| `live.toml` | `mode=live`, `enabled=true`, `ENABLE_LIVE_TRADING` present, no `research_iti` |
| `MOMENTO_KALSHI_ENV` | name present; value `production` (already in inspect; no secret printed) |
| `/dev/shm/momento-kalshi-live.json` | present (presence only) |
| kill | not tripped; `KILL` file absent |
| positions | 0 open MLB tracker fills |
| reservations | 0 |
| unknown submissions | 0 |
| tracker.recon | `Ambiguous` |
| heartbeat | `reconciliation=ambiguous`, `open_slots=0`, `unknown_orders=0`, `order_submission=blocked` |
| `live-runtime.json` `updated_at` | **null** (host schema; not invented) |

SSM letters A–K did not fire. Host proof is not `OBSERVATION_UNAVAILABLE`.

## Vital Observation

### Disk before repair (not acceptance)

- `runtime/observed.json`: `source=ssm`, `ok=true`, `lifecycle_guess=RUNNING`. **No `observed_at`.**
- `runtime/confirmed.json`: `RUNNING` / `HEALTHY`.
- `runtime/desired.json`: `OBSERVATION_UNAVAILABLE` (correct: desired is not observed).
- `execution/observed.json`: host file present; `fill_body=OBSERVATION_UNAVAILABLE` (`VITAL_BOT_STATE_DIR` unset). `ts=2026-09-16T20:27:23Z`.
- `metadata/bot.json`: `aws_runtime_id=momento-live.service`, pointers `apps/trading-engine` + `strategies/mlb`, `updated_at=2026-09-16T20:27:22Z`.

Critical question then: Vital could show leftover `RUNNING` on disk without a
fresh host stamp.

### After repair

`inspect_mlb_001` + `observe_bot` (when host fetch is on and local path unset)
take the SSM inspect, not a fabricated local `RUNNING`.

`compose_runtime` now stamps `observed.observed_at`, `instance_id`, `service`
and exports `reconciliation`, `reservations_n`, `unknown_orders`, `open_slots`,
`order_submission`.

`overlay_confirmed_lifecycle` refuses missing/stale `observed_at` (>300s) and
sets `status=OBSERVATION_UNAVAILABLE` (`observation_freshness` `UNREAD` |
`STALE` | `FRESH`). Leftover `RUNNING` without a stamp is no longer confirmed.

`host_fetch_enabled()` defaults **on**. Explicit `0` / `false` / `no` / `off`
disables. Control writes still require `VITAL_AWS_CONTROL`.

Jump `jump_heartbeat_from_vital` copies the new ledger counts. Jump does not
call SSM for Bot One.

## Comparison table

Phase 2 compare used the same 2026-09-16T20:25Z host proof against Vital
inspect / observe. Pre-repair match:

| Field | Direct Host | Vital Observation (pre-repair) | Match |
|---|---|---|---|
| systemd | active | active (when HOST_FETCH on / API setdefault) | yes, if fetch on |
| MainPID | 1101134 | 1101134 | yes |
| executable | `/usr/local/bin/momento-trading-engine` | binary exists + SHA | yes |
| SHA256 | `610dd470…147250` | same | yes |
| service start | 2026-09-16 20:00:11 UTC | `started_at` on inspect | yes |
| heartbeat / `updated_at` | host `updated_at` null; journal current | inspect `updated_at` omitted/null; **no `observed_at`** | **no** (freshness) |
| kill | not tripped | `kill_switch=false` | yes |
| positions | 0 | `open_mlb_positions=0` | yes |
| reservations | 0 | omitted | **no** |
| unknown | 0 | omitted | **no** |
| recon | `Ambiguous` / heartbeat `ambiguous` | omitted | **no** |
| `open_slots` | 0 | omitted | **no** |
| `order_submission` | blocked | omitted | **no** |
| environment | production / `MOMENTO_KALSHI_ENV` | env name + production label | yes |

Post-repair live compare (**2026-09-16T20:32:43Z**, `observe_bot` persist,
`VITAL_AWS_CONTROL` unset):

| Field | Direct Host | Vital Observation | Match |
|---|---|---|---|
| systemd | active | `service.active=active` source=`ssm` | yes |
| MainPID | 1101134 | 1101134 | yes |
| executable / SHA256 | `610dd470…147250` | same | yes |
| service start | 2026-09-16 20:00:11 UTC | `started_at` same | yes |
| freshness | host `updated_at` null; journal current | `observed_at=2026-09-16T20:32:43Z` | yes (Vital stamp) |
| kill | not tripped | `false` | yes |
| positions | 0 | 0 | yes |
| reservations | 0 | 0 | yes |
| unknown | 0 | 0 | yes |
| recon | `Ambiguous` | `Ambiguous` | yes |
| `open_slots` | 0 | 0 | yes |
| `order_submission` | blocked | blocked | yes |
| environment | production / `MOMENTO_KALSHI_ENV` | same env names | yes |
| desired | n/a | `OBSERVATION_UNAVAILABLE` | desired ≠ observed |

Host `updated_at` remains null; Vital does not invent one.

## Failure Boundary

**Observation path / persist / ledger projection.** Not AWS, not SSM, not the
wrong instance, not a dead unit, not Jump owning a second inspect.

1. `host_fetch_enabled()` previously defaulted off. HTTP via `terminal_api`
   set `VITAL_AWS_HOST_FETCH=ssm`. In-process Jump `vital_observe` →
   `observe_bot` → `inspect_mlb_001` skipped SSM and returned local
   `host state path unset` unless that env was already set.
2. Inspect ledger exported only kill / armed / positions / bankroll /
   `updated_at`. Host `live-runtime.json` and journal already had recon /
   reservations / unknown / `open_slots` / `order_submission`.
3. `runtime/observed.json` had no `observed_at`. Overlay treated confirmed
   `RUNNING` as current.

Not: Risk rewrite. Not: fill ingest. Not: unit retarget to
`momento-demo@mlb-001`.

## Root Cause

Vital could reach the factory unit when the API process enabled host fetch,
but the observe contract was incomplete:

- fetch default disagreed between HTTP and in-process Jump
- heartbeat omitted occupancy / recon counts already on the host
- confirmed lifecycle could outlive a missing observe stamp

The host process itself was up. HTTP 200 and a disk `RUNNING` were not proof
of a fresh observe.

## Repair

Allowed minimal repairs only:

- `ROLLER/roller/vital/aws.py`: `host_fetch_enabled()` default on;
  `INSPECT_SHELL` + `_heartbeat_from_inspect` + `inspect_local` export recon /
  reservations / unknown / `open_slots` / `order_submission`.
- `ROLLER/roller/vital/observe.py`: persist `observed_at` + `instance_id` +
  `service`; overlay stale/unread → `OBSERVATION_UNAVAILABLE`.
- `ROLLER/roller/jump/vital_client.py`: Jump heartbeat copies the new fields.

Isolate tests now set `VITAL_AWS_HOST_FETCH=0` so CI does not hit live SSM.

## Trading / Risk / submit / restart

**NONE.**

No `momento-live.service` start/stop/restart/kill. No `VITAL_AWS_CONTROL`.
No binary replace. No `live.toml` edit. No Risk / 80/81 / Create V2 /
credential / bankroll change. Occupancy was not “fixed” via Vital.

## Tests

`ROLLER/tests/test_vital_mlb001_connectivity.py` plus updates in
`test_vital_aws.py`, `test_vital_observe.py`, and isolate helpers:

1. MLB 001 targets `i-0f0849d5829476c31` + `momento-live.service`.
2. Production inspect ≠ `momento-demo@mlb-001`; ITI uses `@` units.
3. Official-shaped inspect JSON (including `live-runtime.json` presence and
   recon / `open_slots`) parses.
4. Local path unset + SSM ok → observe from SSM, not fabricated local RUNNING.
5. Missing / stale host → `OBSERVATION_UNAVAILABLE`.
6. Desired ≠ observed ≠ confirmed.
7. API/Jump read the same observe payload; `load_host_state()` skips SSM.
8. Control stays disabled (`VITAL_AWS_CONTROL` unset).
9. No secrets in fixtures.

CI uses `VITAL_AWS_SSM_RUNNER` / fixtures. One live read-only compare is
evidence in this report, not a required CI test.

## Remaining Risks

- Host `live-runtime.json` has no `updated_at`. Freshness is Vital
  `observed_at` plus journal heartbeat, not a host wall-clock on that file.
- `execution/observed.json` `fill_body` stays `OBSERVATION_UNAVAILABLE` until
  Incident A (local copy or fill ingest) is authorized separately.
- Host `reconciliation=ambiguous` and `order_submission=blocked` are **observed
  host facts**, not a Vital disconnect. Do not clear them by restarting or
  editing Risk from this incident.
- `_SSM_TTL_S=60`. A GET without `refresh` can reuse a minute-old inspect.
- Overlay stale window is 300s. Operators must re-observe; leftover disk
  `RUNNING` is no longer sufficient.
- Default host fetch on means any process that calls `observe_bot` without
  `VITAL_AWS_HOST_FETCH=0` will SSM. Tests must isolate.
