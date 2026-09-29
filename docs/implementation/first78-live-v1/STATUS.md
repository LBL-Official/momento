# FIRST78 live V1 — first implementation increment

Policy: `MOMENTO_FIRST78_LIVE_V1`. Source specification: `SPECIFICATION.txt`.
Branch: `feat/first78-live-v1-overnight-sizing`.
Base inspected: `57422a6`.

## Implemented in source

- Version-specific sizing epochs in `strategies/nba/src/sizing_epoch.rs`.
- Ten distinct reconciled completions request a resize; extended epochs preserve
  the frozen fee-inclusive 6% acquisition budget.
- IANA America/Los_Angeles window [01:00, 03:00), including DST.
- Reconciliation freshness, clean snapshot, and entry-construction guards.
- Immutable admission-budget values for existing trades.
- Proposal leaves active state unchanged until durable commit.
- Persisted before/after equity, budget, epoch, UTC timestamps and snapshot ID.
- Worker `epoch_store.rs` uses the existing exclusive Lease, file fsync,
  atomic rename and directory fsync before publishing state in memory.
- Completion deduplication survives epochs/restarts. Failed persistence makes
  the store unusable until reopened and reconciled. Corrupt/missing restart
  state does not silently reset the bankroll.

This is a foundation, not an activated runtime path. The existing FIRST78_67
EquityLedger and worker loop remain legacy policy. V1 must not be advertised as
active until admissions, reconciliation and the store are integrated under a
shared transactional boundary. An immutable admission budget alone is not a
transactional cash reservation. Caller-provided reconciliation evidence still
needs to be wired to the authoritative account reconciler.

## Validation

Added six Rust strategy tests and one worker storage test covering extended
batches, duplicate completions, reconciliation guards, window boundaries,
DST, restart roundtrips, corruption, file persistence and exclusive writer.
Rust compilation and tests: NOT RUN; cargo/rustc are unavailable in this host.
Required before merge:

```sh
cargo fmt --all -- --check
cargo test --locked -p momento-strategy-nba
cargo test --locked -p momento-nba-001
```

No production execution flags, AWS services, credentials or funds changed.
No AWS/shadow/canary/host reboot validation has been performed.

## Inspected integration points and next work

- Worker: `apps/nba-001/src/engine.rs`, `lane.rs`, `executor.rs`, `venue.rs`.
- Current capital ledger: `strategies/nba/src/batch.rs` (immediate legacy rollover).
- Fee/reservation/hedge/lifecycle components: `strategies/nba/src/`.
- Existing deployment: `docs/operations/NBA_001.md`, `deploy/momento-nba-001.service`.
- Ownership: `AGENTS.md`, `.cursor/rules/20-momento-systems.mdc`.

Next: resolve and encode the remaining V1 policy constants; implement event-wide
midpoint FIRST78 with observation-gap disqualification, ESPN clock joins and
NBA Q3/NCAAB H2 window verification; integrate this sizing store with verified
completions and transactional entry reservations; add the combined eight-trade
session cap; implement the specified hedge/fallback lifecycle using existing
order reconciliation primitives. Reuse Positman, Drevo and Systimo ownership.

Still requires precise policy choices/evidence: daily session boundary, entry
ladder reprice timing, hedge deterioration comparator/timeouts, direct-exit
price protection/retries, global exposure and hedge collateral reserves,
freshness tolerances, and verified exchange market/fee/precision rules.
These are not silently supplied by this increment. The +1.5 cent EV is a
user-supplied comparison benchmark; this implementation does not validate it.

All deployment/readiness gates remain unpassed. No claim of live readiness.

## NCAAB scope clarification

Owner confirmed P5 vs P5 only. The specification now requires both teams to
qualify, with missing/ambiguous or stale-season membership blocking entry.
Evidence: `ROLLER/config/sports.json`, `ROLLER/config/conferences.json`, and
`research/choosin_texas/lubbock/LUBBOCK_SPEC_V1.md`.
The historical mapping is 2025-2026: ACC, B1G, BIG12, SEC, PAC12.
A reviewed 2026-2027 membership manifest and runtime admission integration
remain required. This change specifies the gate and its required tests;
it does not claim that the current legacy worker enforces the new V1 gate.

## 50-trade objective and October handoff

Specification sections 92–108 incorporate the supplied scorecard and exit-quality
requirements. Sections 109–110 define realized accounting, actual-contract EV,
overnight-sizing precedence, P5 eligibility, deadline/50th-trade snapshots, and
the October 8 Cursor / October 10 target launch handoff.
These are specification additions, not implemented ledger/dashboard features.
The October 10 target does not override the shadow/canary/readiness gates.
