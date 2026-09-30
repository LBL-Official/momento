# FIRST78 Live V1 — acceptance matrix (§9)

Expected outcomes were written **before** the local runs recorded below.
Policy file: `research/vital/bots/nba-001/strategy/execution_contract_v1.json`.
Artifact root: `docs/implementation/first78-live-v1/release/2026-09-30/`.

Honesty: IMPLEMENTED / TESTED / CONNECTED / RECONCILED / DEPLOYED / HEALTHY / ARMED / EXECUTING are distinct.

| Area | Predeclared expected outcome | Command / artifact | Result |
|---|---|---|---|
| Identity / eligibility | Prior touch, late attach, non-window, unverified NCAAB P5 → no admit; reason retained | `cargo test --locked -p momento-strategy-nba --test live_v1` | TESTED locally. `ncaab_requires_both_p5_and_never_retries_a_prior_touch` pass. |
| Capital | No default bankroll; `$20` and `$20,000` are examples; stale snapshot cannot bootstrap | `live_v1::no_reference_bankroll_and_stale_account_cannot_bootstrap`; `money_v1` parsers | TESTED locally. V1 path has no hardcoded fallback. |
| Epochs | 6% frozen; resize only LA 01:00–03:00 after ≥10 completions | incoming `sizing_epoch` tests + `epoch_store` | TESTED locally (incoming + store). Not CONNECTED to a live account. |
| Orders | Persist before send; production compiled out; timeout = unknown | `v1/outbox.rs`; `venue::PRODUCTION_ORDERS_COMPILED=false` | IMPLEMENTED + TESTED locally. Not CONNECTED to production send. |
| Fills | Dedup; late fill after cancel counted; fractional unsupported blocks ARMED | `live_v1_exits::cancel_then_late_fill_holds_residual`; `FRACTIONAL_FILLS_UNSUPPORTED` | TESTED locally for whole contracts. Fractional remains an ARMED blocker. |
| Exit | Deterioration stays deterioration after a later 25¢ print; 25¢ only from working/recovery hedge; unresolved floor blocks 1 and thousands | `live_v1_exits` | TESTED locally. |
| Account | Missing secret → unread, not `$0`; units must agree | `recon::missing_secret_is_unread_not_zero`; `reconcile_balance_cents` | TESTED locally. Not RECONCILED against a signed production account in this increment. |
| Crash / storage | Torn ledger / outbox tail fail-closed | `ledger::torn_and_hash_mismatch_fail_closed`; outbox torn-tail | TESTED locally. Two-writer lease IMPLEMENTED. |
| Feeds | Gap / stale ESPN / name-join refused | incoming ESPN tests; discovery refuses missing ESPN mapping | IMPLEMENTED. Live feed CONNECTED = no. |
| Dependencies | Linear/Sunsama/Drevo down must not block | alert outbox; Drevo/Positman projected `UNAVAILABLE` | IMPLEMENTED. Delivery CONNECTED = no. |
| Deployment | Wrong account/host fails preflight; never declares ready | `deploy/nba001-v1-preflight.py` | See release evidence. DEPLOYED = no until gates. |
| Performance | Do not invent p50/p95/p99 | `PERFORMANCE.md` | Not measured this increment. |

## Commands run (local)

See `release/2026-09-30/TEST_RUN.md` after the locked cargo/pytest invocation.
