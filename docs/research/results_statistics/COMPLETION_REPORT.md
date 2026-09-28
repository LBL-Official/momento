# Results statistics — completion report

**semantics_version:** 1.0.0  
**code_version:** results_math_v1.0.0  
**date:** 2026-09-09

## Implementation summary

Additive `ROLLER/roller/results_math/` consumes generic-query rows and attaches `analysis` on the result envelope. Query N, entry, exit, terminal, and `hyp_pnl_cents` are unchanged. Results UI Levels 2–8 render that envelope. The $50 Risk-of-Ruin card is gone.

## Files created

- `ROLLER/roller/results_math/` (versions, models, observations, proportions, means, bootstrap, returns, economics, payoff, sizing, drawdown, sequence, dependence, robustness, multiple_testing, comparisons, inference, provenance, analyze)
- `ROLLER/tests/test_results_math_*.py`, `ROLLER/tests/test_finite_sample_economics.py`
- `frontend/roller-terminal/src/v2/results/ResultsMathStack.tsx`
- `docs/research/results_statistics/{RECON,README,MATH_CONTRACT,ECONOMICS_CONTRACT,INFERENCE_CONTRACT,ROBUSTNESS,COMPLETION_REPORT}.md`

## Files modified

- `ROLLER/roller/research_query/execute.py` — additive `mae_cents` / `mfe_cents` / `holding_seconds` on tradable rows; `analysis` on envelope; stop emitting `risk_of_ruin` as a COMPLETE measurement
- `frontend/roller-terminal/src/App.tsx` — Results math stack
- `frontend/roller-terminal/src/v2/results/{ResultsAnswer,wilson,markdownReport}.tsx|ts`
- `frontend/roller-terminal/src/styles.css`

## Files explicitly untouched

- `ROLLER/roller/research/first80.py`
- `ROLLER/tests/test_research_executor_phase4.py`
- `ROLLER/tests/test_population_expansion_phase6.py`
- `apps/terminal-efficiency/`
- `crates/research-engine`
- compiler / path / index semantics
- live trading, Risk, FIRST01, W9
- Base TE measurement definitions

## Tests

- New results_math + economics tests: passed
- `test_research_query_engine.py`, harden, increment2, polymarket, TE attach, operations: 120 passed (with the listed suite)
- Frozen FIRST80 phase4 + phase6: 17 passed
- `npx tsc --noEmit`: passed

## Browser

Results on a stale N=228 snapshot (no `analysis` yet):

- Wilson 62.6%–74.5% on 157/228
- Risk of ruin **NOT COMPUTED** (no $50 card)
- Settlement EV **UNAVAILABLE** (not 0, not path EV)
- Capital overlay: $20,000 / 5% / $1,000 → 1,428 contracts, $999.60 deployed, $0.40 residual
- Observed EV dashes when the snapshot has no `hyp_pnl_cents` (honest, not zero)

Re-run a generic query to populate `analysis` (distribution, Sharpe, t/bootstrap CIs, book EV, MAE/MFE, sequence).

## Status by capability

| Item | Status |
|------|--------|
| Observed EV / contract | IMPLEMENTED |
| Observed EV / $1,000 from Σπᵢ | IMPLEMENTED |
| Book-price EV + decomposition | IMPLEMENTED (needs tagged WIN/LOSS chips) |
| Settlement EV | IMPLEMENTED — UNAVAILABLE when terminal missing |
| Breakeven + rate margin | IMPLEMENTED on book payoff |
| Wilson + t CI + bootstrap | IMPLEMENTED |
| Std / var / quantiles / Sharpe unannualized | IMPLEMENTED |
| MAE/MFE / holding time | IMPLEMENTED on **new** tradable rows |
| Drawdown / streaks / recovery | IMPLEMENTED |
| Unique games / clustering disclosure | IMPLEMENTED |
| Game-cluster bootstrap | IMPLEMENTED when n_games < n |
| Cost sensitivity grid | IMPLEMENTED |
| Adjacent entry buckets + disclosure | IMPLEMENTED |
| Season groups | IMPLEMENTED from `entry_ts` |
| Train/validation/OOS | IMPLEMENTED as UNAVAILABLE unless `sample_partition` exists (not invented) |
| Exclusion ledger + provenance | IMPLEMENTED on new envelopes |
| Risk of ruin | NOT COMPUTED (function kept for old unit tests only) |
| Compare A vs B engine | PARTIALLY IMPLEMENTED (effect-size helpers; no dual-query UI) |
| Sequence bootstrap of equity curves | PARTIALLY IMPLEMENTED (return bootstrap only) |
| Histogram viz | PARTIALLY IMPLEMENTED (quantiles, no chart) |
| Cross-sport / notebook / ML | NOT IMPLEMENTED (out of this layer) |
| Fee-inclusive net P&L | BLOCKED — fees not on rows |
| Pre-specified OOS | BLOCKED — no partition labels on warehouse rows |

No metric is mocked. Unavailable stays unavailable.
