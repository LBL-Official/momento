# Account observation (do not treat as V1 RECONCILED)

No funds were moved. No `$20` or `$20,000` was substituted.

## Source

Deployed FIRST78_67 worker GET-only snapshot inside host `status.json`, observed **2026-09-30T13:55:53Z** via SSM (command `7bb420af-430b-4358-9a0d-24b846412e81`).
`account.read_at` unix `1790776530` (host clock). `account.ok=true`, `non_get_sent=false`, `gets_sent=24340`.

This is **not** the V1 paginated recon in `apps/nba-001/src/recon.rs` (that binary is not on the host).
Equity formula `cash + position_value` was **not** proven disjoint on a signed raw body in this handoff.

## Integers as reported

| Field | Value | Meaning |
|---|---|---|
| `balance_total_cents` | 5797 | `$57.97` if the field is cents (host parser) |
| `portfolio_value_cents` | 0 | no open position value reported |
| shard 0 `balance` raw | `"57.4100"` / `shard_cash_cents.0=5741` | `$57.41` on exchange_index 0 |
| shard 1, 2 | `"0.0000"` | unread-as-zero only if the API returned that string |
| shard 3 | `"0.5682"` / `56` cents | `$0.56` on exchange_index 3 (routing shard) |
| `positions_by_series` | `{}` | no open positions in this GET |
| `resting_orders_total` | 0 | |
| `bot_client_orders_found` | 0 | |

Reservations: not an exchange field. Host does not report a reservation ledger. V1 source keeps reserved cash at 0 until the outbox supplies it.

`momento-live` heartbeat `bankroll_cents=5000` is a **different process** (MLB Live). Do not add it to NBA shards. Shared-credential warning is already a blocker (`SHARED_COLLATERAL_UNACCOUNTED`).

## What V1 source requires (not running)

- Authenticated snapshot only; no `REFERENCE_INITIAL_CENTS` / config `capital.reference_capital_cents` on the V1 path.
- Deposits/withdrawals as external flows, not P&L (`portfolio_v1`).
- Frozen 6% epoch; resize only 01:00–03:00 America/Los_Angeles after ≥10 completions (`sizing_epoch.rs`). **No live epoch file exists on the host.**
- Unknown/manual activity → `account_clean=false` / `ACCOUNT_UNRECONCILED` in the V1 reducer. **Not exercised against production.**

## Kalshi MCP

This session: credentials **not configured**. No second balance was fetched. Do not mix an operator personal Kalshi account with these host integers.
