# MLB / WNBA retirement evidence

Unit in scope: `momento-live.service` only (MLB + WNBA).
NBA unit `momento-nba-001.service` stays up.
Do not wildcard-kill Momento processes.

## Gate

Drain-and-disable is authorized **only** through Vital control (`VITAL_AWS_CONTROL` + confirmation) after a **fresh** inventory of:

- open positions (MLB, WNBA, any other series on that credential)
- resting orders and client/exchange IDs
- unresolved / unknown submissions
- late fills after cancel
- host `unknown` / occupancy vs exchange

The 2026-09-30T13:26Z heartbeat (`open_mlb_positions=0` / `open_wnba_positions=0`) is stale and is **not** this gate.

## This increment

See `STOP_BLOCKED.json`. Stop/disable was **not** performed. Shared MLB secret was **not** revoked.
