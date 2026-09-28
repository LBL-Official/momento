# W2 Validation

Engine tests: `cargo test -p momento-research-event` — **13 lib + 31 integration passed** (2026-08-26 closeout).

Clippy: `cargo clippy -p momento-research-event --all-targets --no-deps -- -D warnings`  
(W1 `momento-research-data` currently fails workspace-wide `-D warnings`; not modified by W2.)

## Required classes

| Class | Coverage |
|-------|----------|
| Unit | identity, source contract, invariants |
| Integration | StatsAPI-shaped envelope parse + replay |
| Schema | serde round-trip; SQL DDL presence |
| State transition | catalog of play types; fail-closed illegal outs/score |
| Replay / determinism | same input → same fingerprint and transitions |
| Fixtures | all labeled `SYNTHETIC_TEST_FIXTURE` |
| No lookahead | state at seq=2 has no winner/final_score; score ≠ outcome final |
| Walk-off / extras / review | apply tests |
| Coverage honesty | 2025 reported `MISSING_HISTORICAL_SOURCE`; no PBP AVAILABLE rows |

## Game validation summary fields

`GameId, Source, Events, Valid, Invalid, Warnings, Missing fields, Final score, Computed final score, Reconciled, Parser version`

Emitted by `replay::validate_game` and `validations.json`.

## What is not validated

Live production strategy/risk/execution. No Kalshi sync. No historical PBP checksums (no files).
