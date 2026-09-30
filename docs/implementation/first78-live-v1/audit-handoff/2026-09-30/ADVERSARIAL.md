# Adversarial reproduction (isolated)

Frozen semantics: Drevo/Positman are observations only. Opponent mid ≤25¢ **after** a ≥36¢ hedge trigger starts the residual-original A taker path. It is **not** a promised 25¢ fill and **not** the successor of every emergency exit.

Use fixtures and demo. **Do not** send synthetic production orders. While MLB is Live, production inspect stays read-only.

## Cargo entry points

```sh
# Capital examples ($20 / $20k) and no hardcoded bootstrap
cargo test --locked -p momento-strategy-nba --test live_v1 -- --nocapture

# 25¢ vs deterioration; 36→35→34→25; late fill; zero collateral; 1 and thousands
cargo test --locked -p momento-strategy-nba --test live_v1_exits -- --nocapture

# Money parsers: 20.00, 19.98, unit mismatch
cargo test --locked -p momento-strategy-nba money_v1 -- --nocapture

# P5 season / incomplete evidence
cargo test --locked -p momento-strategy-nba p5 -- --nocapture

# Epoch 9/10, DST, window
cargo test --locked -p momento-strategy-nba --test sizing_epoch -- --nocapture

# Orders: timeout=unknown, cancel/fill, residual, IOC remainder, overhedge
cargo test --locked -p momento-strategy-nba --test orders -- --nocapture

# Worker: torn ledger, unread recon ≠ $0, outbox persist-before-send, WAL corruption
cargo test --locked -p momento-nba-001 -- --nocapture

# Fractional count parse
cargo test --locked -p momento-nba-001 venue::count_tests -- --nocapture
```

Replay CLI (hypothetical actions; no fills invented):

```sh
cargo run --locked -p momento-nba-001 -- v1-replay \
  research/vital/bots/nba-001/strategy/execution_contract_v1.json \
  INPUT.jsonl STATE_DIR
```

`v1-replay` requires a JSONL of `{ "at_ms", "input" }`. Start each scenario in a **new** STATE_DIR.

## Map to the requested cases

| Case | Where it is / is not covered |
|---|---|
| $20, $20,000 same policy | `live_v1::same_policy_and_lifecycle_at_twenty_and_twenty_thousand` |
| $19.98 display/parse | `money_v1::twenty_and_nineteen_ninety_eight_are_exact` |
| No funds / size below minimum | `live_v1_exits::no_bid_and_zero_collateral_block` |
| Missing/stale snapshot | `live_v1::no_reference_bankroll_and_stale_account_cannot_bootstrap` |
| Earlier FIRST78 / no re-entry | `live_v1::ncaab_requires_both_p5_and_never_retries_a_prior_touch` |
| Gap / incomplete history | `live_v1::gap_and_stale_pregame_cannot_create_a_second_chance` |
| P5 current season | `p5::prior_season_is_rejected`, empty `p5_membership_2026_27.json` |
| Duplicate / late fill | `orders` suite; `live_v1_exits::cancel_then_late_fill_holds_residual` |
| Fractional | `venue::count_tests::fractional_count_is_none_without_fall_through`; ARMED blocker |
| Deterioration ≠ 25¢ relabel | `live_v1_exits::deterioration_does_not_become_floor25_because_residual_remains` |
| Recovery then 25¢ | `live_v1_exits::floor25_triggers_from_recovery_path_only`, `recovery_ratchet_36_35_34_then_25` |
| Overhedge | `orders::over_hedge_holds_without_automatic_action` |
| Timeout = unknown | `orders::timeout_is_unknown_not_rejected_then_found` |
| Torn log / two writers | `ledger::torn_and_hash_mismatch_fail_closed`; `epoch_store` single-writer; `lease_is_single_writer` |
| Linear down | `v1::alerts::tests::linear_failure_does_not_drop_alert` |
| Sequence gap | `v1::kalshi::tests::sequence_gap_and_repeated_snapshot_never_restore_first_touch_history` |
| Peak-load / p99 / 1500-contract impact | **not measured** |
| Production disconnect while exposed | **not injected** on the live host |

Demo: `momento-nba-001 demo-exercise` (refuses production). Demo success ≠ production fees/routing.

## Destructive tests

Crash-before-send, disk full, reboot-under-risk: **demo or a spare state dir only**. Do not induce an unprotected failure on `momento-live.service` while submission is enabled.
