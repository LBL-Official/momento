# Vital Live Service Desk

How to read `#/live` on `frontend/vital-terminal` (`:5180`).
Observe only. Factory MLB 001. No start/stop/restart on this page.

Layout map: [`docs/architecture/MOMENTO_LAYOUT.md`](../../docs/architecture/MOMENTO_LAYOUT.md).

```text
WATCHING  ≠  SIGNAL  ≠  SUBMIT  ≠  FILL
DESIRED   ≠  OBSERVED ≠  CONFIRMED
open_mlb_positions = 0  ≠  empty Risk cap
```

## Open

1. Vital on `:5180`.
2. Spine **Live** or `#/live` (key `2`).
3. **Refresh host** — read-only SSM inspect. Does not enable control.

## Panels

| Panel | Trust this | Do not infer |
|---|---|---|
| Communication | `source=ssm`, instance, `momento-live.service`, `observed_at` age ≤ 5m | Disk `RUNNING` without a stamp |
| Process | active, PID, start, SHA256 | HTTP 200 |
| Occupancy | `open_slots` / cap, reservations, unknown | `open_mlb_positions=0` as idle |
| Recon / submit | `reconciliation`, `order_submission` | HEALTHY means it can enter |
| Today MLB | last `KXMLBGAME` ticker + bid/ask, yes-bid count | A 36¢ book is an 80→81 |
| Gates | live.toml armed, env **names** | Secret file contents |
| Ledger | fills_status; unread fill body | `$0` or empty history |
| Proof | L1–L8 suites | Production L8 |

## Occupancy trap

Flag when `open_slots >= max_open_slots` (5) **and** tracker fills are 0.
That is the ghost-five incident. `open_slots=0` is not a trap.

Ambiguous recon is a **different** hard stop: `order_submission=blocked`
even with empty slots.

## Communication proof

Must all be true at once:

- `observed.source = ssm`
- `observed.instance_id = i-0f0849d5829476c31`
- `observed.service = momento-live.service`
- `observed_at` fresh
- PID / SHA / heartbeat match the host

If `observed_at` is missing or older than 300s, status is
`OBSERVATION_UNAVAILABLE`.

Desired stays `OBSERVATION_UNAVAILABLE` until an operator writes a desired
lifecycle. That is correct.

## Trading / Risk / submit / restart

None from this desk. Control stays on Unit and fail-closed
(`VITAL_AWS_CONTROL` unset).
