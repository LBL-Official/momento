# NBA Bot 001 — contract field to code

Contract: `execution_contract.json` (`nba-001-first78_67-v1`). The worker
hashes the deployed copy and reports the sha256 in `status.json`.

| Contract field | Status | Code |
| --- | --- | --- |
| `entry` (78 up-cross, quality, UNPROVEN_FIRST) | RESOLVED | `strategies/nba/src/signal.rs` `CrossTracker`, `strategies/nba/src/bars.rs` `MinuteBar::is_quality` |
| `slice` (Q2/Q3, clock age, period break) | RESOLVED | `strategies/nba/src/slice.rs` `bucket_for`, `ClockObservation` |
| `one_per_game` | RESOLVED | `strategies/nba/src/selection.rs` `select_candidate` |
| `top_out` (85 ceiling) | RESOLVED | `strategies/nba/src/signal.rs` `top_out_at_signal`, `top_out_while_resting` |
| `exit_trigger` (≤67 later close, intrabar ambiguity) | RESOLVED | `strategies/nba/src/signal.rs` `StopTracker` |
| `hedge_instrument` + complement checks | RESOLVED | `strategies/nba/src/hedge.rs` `verify_complement` |
| `hedge_pre_trigger_orders = false` | RESOLVED | `strategies/nba/src/hedge.rs` `HedgePlanner::on_close` (68 → `LocalPrepared`, no order) |
| `hedge_ladder_prices` (limit = 100 − path, 33..45) | RESOLVED | `strategies/nba/src/hedge.rs` `opponent_limit_for_path` |
| `hedge_ladder_advancement` | UNRESOLVED_OWNER_INPUT | `strategies/nba/src/contract.rs` `Field::HedgeLadderAdvancement` → `CONTRACT_UNRESOLVED` blocker |
| `emergency_action` + worst-price bound | UNRESOLVED_OWNER_INPUT | `strategies/nba/src/reserve.rs` `ExitBound::Unbounded` → `EXIT_CAPACITY_UNBOUNDED` |
| `entry_order` (price, TIF, expiry, partials) | UNRESOLVED_OWNER_INPUT | `strategies/nba/src/contract.rs` `Field::EntryOrder` |
| `slot_and_batch_release` | UNRESOLVED_OWNER_INPUT | `strategies/nba/src/lifecycle.rs` (transitions exist; release timing not chosen) |
| `sizing` (600 bps, floor, never shrink) | RESOLVED | `strategies/nba/src/sizing.rs` `contracts_for_reference` |
| `batch_resize` (cash + open principal after 10) | RESOLVED | `strategies/nba/src/batch.rs` `BatchLedger` |
| `shared_slots` (7 ceiling) | RESOLVED | `strategies/nba/src/admission.rs` `evaluate_admission` |
| `fees` (0.07 reservation bound) | UNVERIFIED | `strategies/nba/src/fees.rs` `fee_bound_cents` → `FEE_UNVERIFIED` blocker |
| `reservation` | RESOLVED | `strategies/nba/src/reserve.rs` `reserve_for_entry` |
| `collateral_isolation` | REQUIRED | `strategies/nba/src/admission.rs` `CollateralPool` → `SHARED_COLLATERAL_UNACCOUNTED` |
| `routing` (per-market `exchange_index`) | VERIFY_PER_MARKET | `strategies/nba/src/routing.rs` `route_for_pair`; worker `apps/nba-001/src/discovery.rs` |
| `lifecycle_transitions` | RESOLVED | `strategies/nba/src/lifecycle.rs` `Lifecycle::apply` |
| `modes` | RESOLVED | `strategies/nba/src/mode.rs` `derive_mode` |
| `submission_requires` | — | `strategies/nba/src/admission.rs` `submission_blockers`; `apps/nba-001/src/venue.rs` `production_permit` (always refused: `PRODUCTION_ORDERS_NOT_COMPILED`, `FRACTIONAL_FILLS_UNSUPPORTED`) |
| placeholders | — | `apps/nba-001/src/status.rs` reports `PLACEHOLDER` with no approval and no probability |

Worker (`apps/nba-001`, binary `momento-nba-001`):

| Concern | Code |
| --- | --- |
| Market discovery, candles, route per market | `apps/nba-001/src/discovery.rs` |
| NBA clock (scoreboard) | `apps/nba-001/src/clock.rs` |
| Signed read-only balance, positions, resting orders, fills | `apps/nba-001/src/account.rs` via `momento_kalshi::ProductionObserveTransport` |
| Single-writer lease | `apps/nba-001/src/lease.rs` |
| Controls file | `apps/nba-001/src/controls.rs` |
| Append-only journal | `apps/nba-001/src/journal.rs` |
| `status.json` heartbeat | `apps/nba-001/src/status.rs` |
| Loop | `apps/nba-001/src/main.rs` |
