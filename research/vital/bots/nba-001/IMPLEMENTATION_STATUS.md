# NBA Bot 001 — implementation status

Bot `nba-001` (alias `nba-first80-001`). Strategy FIRST78_67.
Policy `nba-001-v1` (`strategy/policy_v1.json`). `nba-001-v0`
(`strategy/policy.json`, FIRST80 80/40) is kept as history.

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
ORDER ADAPTER LINKED: FIXTURE + DEMO ONLY
PRODUCTION ORDERS COMPILED OUT (PRODUCTION_ORDERS_COMPILED = false)
RUNNING ≠ HEALTHY ≠ EXECUTING
NO FUNDS MOVED
```

## Where this stands (2026-09-27)

- The production worker is deployed and collecting (SHADOW, GET-only).
- The desk is operational.
- The NBA order adapter, order lifecycle, reconciler, and execution lane
  are implemented. They are tested against a fixture exchange and
  exercised against the Kalshi demo environment.
- Production submission is compiled out, so the production binary cannot
  place, amend, or cancel an order. This stays true while contract fields
  are unresolved.
- Execution validation is incomplete in two areas:
  - Owner decisions are open (see below).
  - Fractional production fills are not yet supported
    (`FRACTIONAL_FILLS_UNSUPPORTED`). This is engineering work, not an
    owner decision.
- Funding alone will not activate trading.
- The latest source build is `nba001-20260927T073448Z` (binary
  `496620dd…0438`). All suites passed on ARM64 and the demo exercise passed
  (7 pass, 0 fail). It is **not deployed**: the production-host exception
  in `research/vital/BOT_STANDARD.md` covers a build without the order
  adapter. The host keeps the GET-only build.

The GET-only build `nba001-20260927T042347Z` (binary `9ef129e1…6789`)
stays as the fallback. Its backup is at
`/usr/local/bin/momento-nba-001.9ef129e1.bak` on the host.

## Technical facts resolved (not owner choices)

| Topic | Finding | Document |
| --- | --- | --- |
| Routing | The market/event `exchange_index` is authoritative. The series index names the shard only for new events. Series ≠ market is expected, so `ROUTE_CONFLICT` was removed. Pair legs must match (`ROUTE_PAIR_MISMATCH`). | `FUNDING_ROUTING.md` |
| Fees | taker 7% and maker 1.75% (maker only for `quadratic_with_maker_fees`); per-order rounding to $0.0001. Verified against 235 production fills: 28 of 29 multiplier-1 orders match exactly. KXMLBGAME publishes 0.5 but was charged at 1, so only multiplier 1 counts as verified. | `FEES.md` §5 |
| Account | API tier `basic` (no subaccounts); netting off; auto-rebalancing off; cash shard 0 $57.41, shard 3 $0.57 | `FUNDING_ROUTING.md` |
| Fractional fills | 49 of 235 production fills are fractional, including 19 whole-contract MLB orders | `FEES.md` §5 |
| Collateral | YES+YES hedges free no collateral before settlement | `strategy/EQUITY_AND_BATCH_SIZING.md` |
| Venue behaviour | See the table below. | demo reports |

Venue behaviour observed on demo:

| Behaviour | Evidence |
| --- | --- |
| Single-order `GET` returns 404 for about 1 s after create or amend | demo diagnostics |
| A price-only amend returns no counts; the price shows after about 1 s | demo diagnostics |
| An amend's `fill_count` counts amend-caused fills only | V2 docs |
| A client id stays reserved after cancel (409 `order_already_exists`) | demo |
| A post-only order that would cross is rejected with 400 `invalid_order` | demo |
| Reduce-only IOC without a position fills 0 | demo |
| A GTC order with an expiration is cancelled by the venue | demo |

## Changes made because of demo evidence

1. **Amend counts.** `OrderEvent::Amended` no longer carries counts, and
   every amend is followed by a snapshot. The old code read the amend
   `fill_count` as the order total, which would have put every ladder
   amend after a partial fill on an inconsistency HOLD.
   - Tests: `amend_after_prior_fills_is_not_a_contradiction` and
     `amend_total_below_confirmed_fills_holds`.
2. **Read visibility.** A known order id that returns 404 within
   `READ_VISIBILITY_GRACE_S` (15 s) of its last change is "not yet
   visible". After that it is an error, and the order state is unchanged.
   - Test: `known_order_404_inside_visibility_grace_is_pending_not_error`.
3. **Client-id search.** Search by client id no longer uses a time
   window, so a retry after lost state finds the order it collided with.
   - Test:
     `retry_after_lost_state_collides_and_finds_the_old_cancelled_order`.
4. **Lane client ids.** They take a namespace. Production ids are
   deterministic per event, role, and sequence; demo runs add a run id.
5. **Stale reads after an amend (demo run 3).** A 2-lot amended down to 1
   was later read as 0 filled + 2 remaining. The book let that read raise
   the cap back to 2, so a cancel removing 1 booked a fill that never
   happened. Snapshot rules now:
   - A resting snapshot that lags known evidence changes nothing.
   - Fill counts never fall.
   - A snapshot never raises the cap.
   - A final snapshot that contradicts a cancel count holds the order.
   - An ambiguous amend keeps the larger total until a read shows the
     requested total; a cancel ack then waits for a final snapshot.

   Demo runs 4–10 cross-check booked fills against venue fill records and
   the venue's final count.
   - Tests: `stale_pre_amend_snapshot_cannot_raise_the_cap_or_invent_a_fill`
     and six more in `strategies/nba/tests/orders.rs`.
   - Executor tests: `stale_get_after_amend_down_does_not_invent_a_fill_on_cancel`,
     `amend_timeout_that_applied_resolves_from_the_next_read`, and
     `amend_timeout_that_did_not_apply_cancels_to_a_final_read`.
6. **Count parsing.** A present count that is not whole no longer falls
   through to an older field, and the demo book parser keeps fractional
   levels.

## Order capability

| Piece | File |
| --- | --- |
| Order spec, state machine, fills, late fills, `Inconsistent` hold | `strategies/nba/src/orders.rs` |
| Exposure, reconciled residual, emergency and hedge planners | `strategies/nba/src/exposure.rs` |
| V2 adapter (create, cancel, amend, reads), production permit | `apps/nba-001/src/venue.rs` |
| Executor (persist-before-send, reconcile, ghost watch) | `apps/nba-001/src/executor.rs` |
| Execution lane (owner fields as `Option`; unresolved → hold) | `apps/nba-001/src/lane.rs` |
| Fixture exchange (fees, 409, post-only, reduce-only, IOC, races, faults) | `apps/nba-001/src/fake.rs` (test only) |
| Demo exercise (`momento-nba-001 demo-exercise`) | `apps/nba-001/src/demo.rs` |
| GET-only evidence (`momento-nba-001 evidence`) | `apps/nba-001/src/account.rs` |

The production gates work in layers:

1. `PRODUCTION_ORDERS_COMPILED = false` with a compile-time assert.
2. `production_permit()` always returns `PRODUCTION_ORDERS_NOT_COMPILED`
   and `FRACTIONAL_FILLS_UNSUPPORTED`, plus any contract, fee, gate, or
   collateral blocker.
3. `NbaVenue` refuses mutations in `Production`.
4. The production transport (`ProductionObserveTransport`) refuses every
   non-GET locally.
5. The build script fails on `ProductionTradingTransport`,
   `NbaVenue::production`, or `place_order` in NBA sources.

MLB's binary, service, and policy are untouched.

## Contract and money (proposals, not approved)

- `strategy/EXECUTION_CONTRACT_PROPOSAL_V2.md` gives six worked examples:
  a stop at 67, a gap to 60, a close below 55, a partial hedge then
  emergency, a late fill during cancel, and a data outage. Each shows
  orders, quantities, bounds, exposure, and cash.
- `strategy/EQUITY_AND_BATCH_SIZING.md`: the $20,000 reference
  ($5,000 funded + $15,000 external reserve), spendable cash tracked
  separately, the batch formula, and reproduced reservations.
- `execution_contract.json`:
  - Six fields are `UNRESOLVED_OWNER_INPUT`.
  - `batch_resize` is `PROPOSED_NOT_APPROVED`.
  - `fees` is `VERIFIED` with scope `quadratic_with_maker_fees` at
    multiplier 1 (`engine::fees_verified_for`).
  - `routing` is `VERIFIED_DOCUMENTED`.

## Tests

| Suite | Result |
| --- | --- |
| `cargo test -p momento-strategy-nba` | 61 (`first78_67`) + 35 (`orders`) passed |
| `cargo test -p momento-nba-001` | 56 passed, 1 ignored network replay (it passed on the builder). Includes the executor fixture suite, 8 lane full-trade scenarios, fee-evidence tests, and count-parsing tests |
| `cargo test -p momento-kalshi` | passed (incl. `production_auth`: the new GET paths are allowed, and POST/PUT/DELETE on subaccount, transfer, netting, and allocation are refused) |
| `cargo clippy -p momento-nba-001 -p momento-strategy-nba --all-targets` | clean |
| `cargo check --workspace --all-targets` | clean |
| ROLLER `test_nba_001_deploy`, `test_nba_001_runtime`, `test_nba_001_desk`, `test_momento_registry` | 31 passed |
| ROLLER `test_nba_001_replay::test_protected_hashes_match_manifest` | **fails: pre-existing `INTEGRITY_DRIFT`**. `ROLLER/roller/choosin_texas/locks.py` changed on 2026-09-24, before this work; it is not repaired here |
| `frontend/momento-systems` `tsc --noEmit` | clean |
| ARM64 builder (`deploy/nba001-arm64-build.sh`) | all of the above suites passed |
| Demo exercise | see `DEPLOYMENT_PROOF.md` (supersession section) |

## Blockers on production entries

- `UNRESOLVED_OWNER_INPUT`:
  - `hedge_ladder_advancement`
  - `hedge_initial_limit_gap_policy`
  - `emergency_action`
  - `data_outage_policy`
  - `entry_order`
  - `slot_and_batch_release`
- `EXIT_CAPACITY_UNBOUNDED` (follows from `emergency_action`).
- `FRACTIONAL_FILLS_UNSUPPORTED` (engineering: counts must become
  hundredths through orders, exposure, and hedge sizing).
- `SHARED_COLLATERAL_UNACCOUNTED` (see the subaccount section of
  `FUNDING_ROUTING.md`).
- `BATCH_RESIZE_UNAPPROVED` (batch 2 onward).
- `LIVE_GATES_UNSET`.
- `PRODUCTION_SUBMISSION_DISABLED` (compiled out).

## Next step

1. The owner selects the contract fields, using the worked examples.
2. The owner chooses the subaccount configuration.
3. Engineering: hundredths-of-a-contract counts end to end, so fractional
   fills do not halt a lane.
4. Then comes a separate, reviewed change that compiles production
   submission in, behind the live gates, plus owner approval to deploy an
   adapter build to the host.
