# FIRST78 V1 implementation status — 2026-09-30

Policy: `MOMENTO_FIRST78_LIVE_V1`.
Incoming: `0ffd6ca79b29cbee09771fb02cbf1f343f3395af`.
Merge: recorded in `DEVELOPMENT_LEDGER.md`.
Contract: `research/vital/bots/nba-001/strategy/execution_contract_v1.json`.
This is not FIRST78_67.

## Honesty terms

| Term | This increment |
|---|---|
| IMPLEMENTED | V1 reducer, epochs, recon service, supervised `first78_live_v1` loop, outbox, ledgers, Systimo projection, P5 fail-closed file |
| TESTED | Locked NBA crate tests + Systimo projection unit test. See acceptance matrix |
| CONNECTED | Production Kalshi GET recon not proven here. ESPN/Kalshi live observe commands exist; supervisor discovery uses public events only when the process runs |
| RECONCILED | No signed whole-account snapshot in this increment |
| DEPLOYED | No |
| HEALTHY | Not claimed |
| ARMED | No — owner price protection and other unresolved fields |
| EXECUTING | No |

## What changed after the incoming merge

- `apps/nba-001` `run` dispatches `mode=first78_live_v1` to `v1::runtime::run_supervised`.
- Production policy must leave `emergency_floor_cents` unset. Compiled production is refused.
- Paginated GET-only recon; equity only after cash and position value are proven disjoint.
- Durable execution/portfolio/development ledgers; order outbox persist-before-send; P0/P1/P2 alert outbox.
- Discovery registers a pair only with an explicit ESPN mapping. Name similarity is refused. NCAAB also requires a VERIFIED 2026–27 P5 file.
- ExitKind distinguishes deterioration from the 25¢ trigger. Residual after deterioration stays on the emergency path.
- Systimo `GET /systimo/nba-001/v1` projects the control room. Missing is `UNAVAILABLE`, never `$0`.
- Legacy FIRST78_67 collector and `batch.rs` reference constants are unchanged.

## Still blocking ARMED

See `UNRESOLVED_CHECKLIST.md`. Largest owner blank: direct-exit price protection.
P5 2026–27 is `EVIDENCE_INCOMPLETE` (engineering, not an owner constant).
`FRACTIONAL_FILLS_UNSUPPORTED` remains an ARMED blocker.
MLB/WNBA `momento-live.service` is **not** disabled; see retirement `STOP_BLOCKED`.

## Commands

```sh
cargo test --locked -p momento-strategy-nba -p momento-nba-001
cargo test --locked -p momento-kalshi
# mode=first78_live_v1 in config; MOMENTO_NBA_V1_ONCE=1 for a single supervisor tick
```

Production orders remain compiled out. A date does not pass a gate.
