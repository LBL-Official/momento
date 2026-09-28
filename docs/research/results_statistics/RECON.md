# Results statistics — Phase 0 reconnaissance

**Status:** COMPLETE (recon only). No production behavior changed by this document.

Empirical query semantics stay bit-for-bit. This layer is additive analysis on already-materialized result rows.

## Current architecture

```text
compile_draft / compile_question
        │
        v
execute_compiled  (ROLLER/roller/research_query/execute.py)
        │
        ├─ observe_entry / run_path / _classify_exits
        ├─ _result_row  → population.trades[]
        ├─ measure_rows → path_rate, kalshi_yes_rate, 2×2
        ├─ measure_finite_math → mean hyp_pnl, max DD, $50 RoR
        └─ _envelope → ResultEnvelope
                │
                v
frontend ResultsAnswer + FiniteMathPanel + UncertaintyPanel + ScenarioPanel
```

Frozen FIRST80 (`execute_research_object`) does **not** emit `hyp_pnl_cents` or finite-math measurements. Generic candle query does. Last-trade / Polymarket is P&L-banned.

## Existing calculations

| Object | Source | Formula | Type |
|--------|--------|---------|------|
| `hyp_pnl_cents` | `_result_row` | `(exit_bid − entry_bid) // 100` when exit bar exists and basis is tradable | int cents |
| `observed_hyp_ev_cents` | `measure_finite_math` | mean of `hyp_pnl_cents` | float |
| Wilson 95% | `frontend/.../wilson.ts` | score interval, z=1.96 | client |
| Max DD | `max_drawdown_cents` | peak-to-trough on chronological `hyp_pnl_cents` | int |
| Risk of ruin | `risk_of_ruin` | asymptotic gambler’s ruin, **$50 snapshot** | float |
| Model A EV | enter-80 / reach-40 only | `20 − 60q` | float |
| L4 scenarios | `scenarioPresets.ts` | 80→40 fee cards; **hold-to-settlement copies observed EV when terminal is absent** | UI bug |

## Exact source fields on a generic trade row

Present today:

- `ticker`, `internal_game_id`, `entry_ts`, `exit_ts`
- `entry_close`, `exit_close` (e4)
- `entry_price_e4` (condition threshold / band floor, not necessarily `entry_close`)
- `hyp_pnl_cents`, `path_true`, `win_exit`, `loss_exit`, `exit_outcome`
- `terminal_yes` (None if Kalshi settlement missing)
- `alignment`, `price_basis`, `entry_operation`, `entry_ordinal`

Optional nested `te` from Base TE attach — do not redefine TE.

Funnel + `identity.exclusions` already exist for an exclusion ledger.

Hashes: `hashes.question_hash`, `dataset_version`, `CODE_VERSION=research_query_v1.2_ops`.

## Missing fields (do not invent)

| Need | Available? | Decision |
|------|------------|----------|
| Fees / fills | No | Cost overlay is HYPOTHETICAL. Fee = UNAVAILABLE on rows. |
| MAE / MFE | Not on row; `after` bars exist inside `_result_row` | Additive later-bar min/max deltas. Entry bar excluded. Last-trade: skip. |
| Holding time | `entry_ts`, `exit_ts` | Additive seconds if both present. |
| Train / validation / OOS labels | No | UNAVAILABLE unless `sample_partition` appears on a row. Do not invent a split. |
| Team / possession / score on row | Only via TE attach | Cluster by `internal_game_id` / `ticker`. Score buckets stay TE-scoped, not rewritten. |
| Subsequent bar series in envelope | No | Do not rescan warehouse in the math layer. MAE/MFE only if attached at row build. |
| Settlement | Often ABSENT (`kalshi_markets.csv` missing) | Settlement EV = UNAVAILABLE. Do not map path WIN → settle YES. |

## Semantic conflicts

1. UI label **HYPOTHETICAL EV +0.79¢** is actually **observed** mean exit−entry. Relabel.
2. **Hold to settlement** showing +0.79¢ when terminal is missing overwrites absence with path EV. Forbidden.
3. **Risk of ruin 0.01% · $50 snapshot** is not a defined sequential bankroll model. Remove from Results. Keep the function for existing unit tests; do not present it.
4. Wilson is a CI for a binomial proportion, not for “edge.”
5. `N` observations ≠ `N` independent games (`internal_game_id` clusters).
6. Book-price EV (chip prices) ≠ observed path EV ≠ settlement EV.
7. Integer `// 100` truncates sub-cent e4 before averaging. Do not change `hyp_pnl_cents`. New stats use that same vector.

## Proposed additive integration

New package: `ROLLER/roller/results_math/` (versioned). Consumes rows + compile question + funnel + identity.

`_envelope` grows an `analysis` object. Query N, entry, exit, and terminal semantics unchanged.

Optional additive row fields only (tradable, later bars already in memory):

- `mae_cents`, `mfe_cents`, `holding_seconds`

Do not modify:

- `ROLLER/roller/research/first80.py`
- frozen FIRST80 tests
- `apps/terminal-efficiency/`
- compiler / path / index semantics
- `hyp_pnl_cents` formula
- live trading / Risk / FIRST01 / W9

## Blockers

None for observed EV, distribution, Sharpe, t/bootstrap CIs, book-price EV, capitalization, sequence DD, clustering, cost overlay, exclusion ledger.

**UNAVAILABLE without new warehouse scans:** full remaining-path MAE if `_result_row` is not extended; intra-bar MAE; fee-inclusive net P&L; pre-specified train/OOS; cluster-robust Wilson replacement (disclose separately, do not change existing Wilson).
