# FIRST78 V1 implementation status — September 30, 2026

Branch: `feat/first78-live-v1-overnight-sizing`.
Policy: `MOMENTO_FIRST78_LIVE_V1`.
October 3 handoff: `CURSOR_IMPLEMENTATION_PLAN_2026-10-03.md`.

## Implemented and tested locally

- Pure deterministic V1 reducer in `strategies/nba/src/live_v1.rs`: event-wide
  first-touch state, prior-touch/gap disqualification, NBA Q3 / NCAAB H2 window,
  supplied P5 membership-evidence gate, entry ladder, midpoint-86 cancellation,
  hedge/recovery/deterioration intents and reconciled residual exit primitives.
  This is replay logic, not an active production worker.
- No default V1 bankroll. A fresh caller-supplied clean account snapshot initializes
  sizing; missing/stale evidence leaves it uninitialized. Subsequent balance
  changes do not bypass the frozen epoch. The caller's reconciliation assertion
  still needs authoritative live verification; replay input is not trusted live data.
- Same-policy $20 and $20,000 tests exercise fee-inclusive quantity selection,
  order acknowledgement, cancellation and waiting for confirmation before replacement.
- Sizing epochs: ten distinct reconciled completions, frozen 6% acquisition budget,
  01:00–03:00 America/Los_Angeles rollover, DST/freshness/construction guards,
  before/after evidence and completion deduplication across restart/epochs.
- `epoch_store.rs`: exclusive lease, durable atomic snapshot commit and fail-closed
  persistence. Not yet a shared live transaction with admission reservations.
- Portfolio authority and account performance primitives in `portfolio_v1.rs`:
  independent incident reasons, priority/state, evidence-based clearing, exact
  integer equity and external-flow-adjusted total P&L/drawdown. Deposits are not profit.
- Isolated replay CLI with single-writer, fsynced hash-chain journal, policy identity,
  deterministic recovery, action comparison, torn-tail/corruption refusal.
  This WAL is not immutable external storage or a production order outbox.
- ESPN summary adapter: bounded read-only request, explicit event/team ID mapping,
  game-state/clock validation, score ordering and explicit unavailable provider time.
- Kalshi read-only websocket observation command and sequence-checked book
  normalization using the existing client. Gaps remain explicit; snapshots do
  not restore missing FIRST78 history. No production order transport is called.
- Read-only AWS identity/SSM preflight script. It never starts/stops a service and
  deliberately cannot certify execution readiness.

## Validation evidence

`cargo test --locked -p momento-strategy-nba -p momento-nba-001`
passed with **170 tests passed, 0 failed, 1 existing test ignored** using Rust 1.98.0.
This includes existing lifecycle/regression coverage and new V1/portfolio/parser/
WAL cases. It does not imply 170 end-to-end V1 or live tests. Changed new Rust
modules were formatted with the pinned rustfmt. A full workspace release gate,
production credentials, demo end-to-end V1, AWS deployment, and actual canary
validation have not been performed by this increment.

Read-only AWS preflight returned `AWS_CLI_UNAVAILABLE` in the authoring environment.
AWS was not connected. No production order, fund transfer, service change,
MLB/WNBA shutdown, or live arming was performed.

## Commands now available

```sh
cargo run --locked -p momento-nba-001 -- v1-replay POLICY_JSON INPUT_JSONL STATE_DIR
cargo run --locked -p momento-nba-001 -- v1-espn MAPPING_JSON
cargo run --locked -p momento-nba-001 -- v1-kalshi-observe MAPPINGS_JSON SECRET_FILE DURATION_SECONDS
```

Replay inputs are `{ "at_ms": <UTC milliseconds>, "input": <tagged Input> }`.
Start each independent replay with a new directory. Reopening restores committed
state; do not resend a whole scenario and assume generic event-ID deduplication.
Replay actions are hypothetical. ESPN/Kalshi commands observe only and require
valid explicit mappings; the Kalshi command requires authorized production data
credentials and a duration of 1–3600 seconds. Protect redirected account artifacts.
The existing `probe`/`evidence` commands provide signed GET-only account observations.
Observed account summaries are not a complete V1 reconciliation service.

## Still required before production

1. Continuous V1 service integration and a shared durable transaction for admission,
   reservations, lifecycle, completion and epochs; production order/alert outboxes.
2. Authoritative paginated account/order/fill/fee/settlement reconciliation, exact
   monetary and fractional quantity handling, snapshot consistency and route-aware
   collateral/hedge reserves. No caller boolean may certify live reconciliation.
3. Current-season P5 manifest and verified complement/game/team mappings. Replay
   `both_p5` and evidence strings are fixtures, not a runtime membership validator.
4. Full-game coverage/heartbeat and reconnect semantics, independent game-feed
   supervision, feed correction handling and raw evidence persistence.
5. Exact unresolved policy settings: session boundary/counting, reprice timing,
   deterioration/timeouts, direct-exit price protection/retries, exposure/hedge
   limits, freshness and actual venue fees/routing/precision. Replay settings
   and `Some(1)` test exit floors are not approved production policy.
6. Full final cash-flow accounting: replay completion currently trusts supplied
   final P&L and reconciliation ID. Its settled-order checks alone do not establish
   actual flatness/settlement. Prevent production use until a real reconciler owns it.
7. Stronger live safety/action dispatch gates, durable P0/P1/P2 delivery, actual
   Systimo projections/UI, model observations and Linear outbox integration.
8. Larger-size liquidity/performance, fault injection, security/retention/backup,
   demo/shadow/canary, host/reboot/rollback and full release evidence.
9. Controlled discovery/drain/disable of MLB/WNBA execution and proof sole-bot
   ownership. Retirement is requested in the October 3 plan, not yet performed.

Production orders remain compiled out. Legacy FIRST78_67 behavior is unchanged;
V1 is not wired into the existing `run` loop. Never advertise this increment as
an operating $20/$20,000 bot or deploy it as though those gaps were complete.

## Current governing instructions

`OPERATIONS_AND_CAPITAL_V1.md` overrides old fixed-$20,000 examples and the October
10 launch target. October 3 is the $20 target; October 15 is the increased-capital
target, both gated. The actual authenticated account supplies capital, with no
hardcoded fallback. Overnight epoch rules remain. NCAAB is verified P5 vs P5 only.
The 25¢ condition is the opponent midpoint recovery boundary that triggers a
residual original-contract taker-capable exit, not a promised 25¢ execution price.

Follow the comprehensive Cursor plan to complete integration, testing, retirement,
AWS deployment and increased-capital promotion. A date never substitutes for evidence.
