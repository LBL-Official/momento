# CTO-W2 PROGRESS

**Waterfall status:** W2-E/W2-B complete on StatsAPI 2026-06-18..30; 2025 PBP still missing; theta estimator deferred  
**Authorization:** Free StatsAPI collection authorized 2026-08-26. Do not write Data-Real.

## Current progress

174/174 Final games reconstructed. 168 Kalshi mappings unique. Event Theta value UNAVAILABLE (ADR-0010).

## Control-plane steps

| ID | Intent | State |
|----|--------|-------|
| CTO-W2-A1-S1 | GameState / PBPEvent schema + FIXTURE | COMPLETE |
| CTO-W2-A1-S2 | Adapter traits | COMPLETE (MLB) |
| CTO-W2-A2-S1 | Identity graph | COMPLETE |
| CTO-W2-A2-S2 | Map official pks | COMPLETE (unique matches); AMBIGUOUS DH left unmapped |
| CTO-W2-A3-S1 | PBP source | COMPLETE for StatsAPI window; 2025 still missing |
| CTO-W2-A4-S1 | Reconstruct GameState from PBP | COMPLETE 174/174 in window |
| CTO-W2-A5-S1 | UNAVAILABLE labeling | COMPLETE (2025 / unmatched / theta value) |

## Next authorized action

CTO review. Do **not** start W3. Do **not** invent Event Theta formulas (W9).


## Current progress

Crate `momento-research-event` exists. Tests: 13 lib + 31 integration passed. Clippy `-D warnings` clean.

W1 owns `foundation/w2_contract.rs`. W2 **consumes** it (no mirror).

## Control-plane steps

| ID | Intent | State |
|----|--------|-------|
| CTO-W2-A1-S1 | GameState / PBPEvent schema + FIXTURE | COMPLETE (engine) |
| CTO-W2-A1-S2 | Adapter traits | COMPLETE (MLB) |
| CTO-W2-A2-S1 | Identity graph (tickers as aliases) | COMPLETE |
| CTO-W2-A2-S2 | Map official pks | BLOCKED without source |
| CTO-W2-A3-S1 | PBP source/license gate | BLOCKED on CEO+license |
| CTO-W2-A4-S1 | Reconstruct GameState from authorized historical PBP | BLOCKED on data |
| CTO-W2-A5-S1 | UNAVAILABLE event-state labeling | COMPLETE |

Crate ledger: `W2-A1-S1` … `W2-A10-S10` in `Backtesting Suite/Foundation/W2/ledger.json`. One crate step BLOCKED: `W2-A2-S7` (official crosswalk).

## Next authorized action

CTO review. Do **not** start W3.

## Evidence

[../W2_COMPLETION_REPORT.md](../W2_COMPLETION_REPORT.md) · `cargo test -p momento-research-event`
