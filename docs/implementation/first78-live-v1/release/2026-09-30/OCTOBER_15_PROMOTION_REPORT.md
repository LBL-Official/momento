# October 15 capital promotion — status

Target date: 2026-10-15 America/Los_Angeles.
This file is written on 2026-09-30 so the gate is explicit before the date arrives.

## Rule

Funding is an external deposit verified from the authenticated account feed.
This increment does not initiate a transfer.
`$20,000` is not a software override. The frozen 6% epoch still requires ≥10 completions and the 01:00–03:00 Los Angeles window. A date is not an exception.

## Gates (plan §12)

| Gate | Status |
|---|---|
| Deposit observed on the account feed | UNAVAILABLE — not initiated, not verified |
| No unresolved P0; no unknown orders/positions | UNAVAILABLE — V1 not RECONCILED |
| Canary lifecycle through settlement | not EXECUTING |
| Partial / fractional / late-fill at larger size | fractional still `UNSUPPORTED` (ARMED blocker) |
| Collateral routing + hedge capacity | SHARED_COLLATERAL_UNACCOUNTED on shipped config; MLB unit still live |
| Liquidity / slippage at ~1,500 contracts | not measured |
| Performance headroom | not measured (`PERFORMANCE.md`) |
| P0 alerts delivered | outbox IMPLEMENTED; delivery CONNECTED = no |
| Unchanged reviewed policy | `emergency_floor_cents` still UNRESOLVED_OWNER_INPUT |
| Overnight / 10-completion epoch | IMPLEMENTED in reducer/store; no live completions |

## Report line for October 15 if nothing else changes

**funded, increased sizing blocked** — unless every row above is evidenced.

If no deposit has posted: **not funded**. Do not size from a hardcoded `$20,000`.
