# FIRST78→67 findings

Run `first78_67_20260926T074540Z`. Evidence tier: `THRESHOLD_ACCOUNTING_REFERENCE` using `FIRST78_CLOSE_PROXY`.

This is an assumed fill at 78¢ and an assumed stop sale at 67¢ after a minute bid-close signal. A close at another price is recorded as overshoot or a gap. It is not a maker fill and not live P&L. `OBSERVED_PRICE_REPLAY` and `MAKER_EXECUTION_REPLAY` are unavailable. A later minute bid close is reported only as `NEXT_BAR_PRICE_PROXY`.

## Sample

The locked book is 936 games. Membership is the FIRST80 derived four: NBA 2Q, NBA 3Q, NCAAB 1H second 10 minutes, NCAAB 2H first 10 minutes. Those games were kept because a contract's first 80¢ bid close landed in the window. A 78¢ signal can happen earlier. These results are conditional on that selected population. They do not estimate every prospective FIRST78 opportunity.

Headline rule, taken from the per-ticker FIRST80 scanner: `CONTRACT_WISE_FIRST`. Each contract has its own first up-cross. The cross must land in the window and in America/Los_Angeles `[2025-11-01, 2026-04-02)`. One position per game is the earliest eligible contract. `GAME_WIDE_FIRST` is a separate run and is not pooled.

| Step | Games |
|---|---:|
| Locked derived four | 936 |
| No 78¢ up-cross on either contract | 6 |
| First crosses outside the clock window | 179 |
| Outside the Nov 1–Apr 1 entry window | 104 |
| Candidates | 647 |
| Admitted | 647 |
| Ledger rejections | 0 |

640 of the 647 admitted contracts are the same ticker the FIRST80 log had already selected. Seven are not.

## Portfolio

Starting cash $20,000. Entry principal target is 6% of the frozen sizing balance. Fees are extra, user coefficient 0.0175, ceiling to the cent once per aggregate order. Cap is seven positions across both sports. Sizing updates after every tenth completion. Holds release the slot and the cash at `settlement_time` (`HYPOTHETICAL_CASH_AT_SETTLEMENT_TIME`). Stops release both at the stop signal under the assumed sale. `close_time` is the earlier trading-close timestamp and is only a named stress. `expiration_time` is not used as cash.

- Admitted 647. Max concurrent positions 6. The cap of 7 did not bind on this path. The unit test, not this history, is what shows an eighth simultaneous candidate is rejected.
- Net P&L $235,488.18. Gross $256,120.15. Fees $20,631.97. Gross minus fees equals net.
- Ending realized-accounting equity $255,488.18.
- NBA attribution $120,607.86. NCAAB attribution $114,880.32. Those sum to the combined net. They are not two separate $20,000 books.
- Exits: 330 winning settlements, 317 stops, 0 losing settlements. Of the stops, 212 later settled yes and 105 settled no. Held-to-zero did not occur on this close-proxy path. That is an observation, not a claim that a loss cannot gap through 67¢.
- Event-equity peak-to-trough drawdown on cash + receivables + open principal was about 6.51% ($135,187.04 peak to $126,385.54 trough). That series is not a bid-marked liquidation path, and minute data cannot show the path inside a bar.
- Calendar span of exit days: 152 local days, 12 with zero exit P&L. Sharpe of daily net dollars divided by the starting $20,000 is about 0.56 unannualized and about 10.6 if multiplied by sqrt(365). That annualization is a convention on five months. It is not a return on prior equity and it is not a realized year. See `03_statistical_validation/sharpe_calendar_on_starting_capital.json`.

## Stop versus hold

On the same admitted quantities, stop-policy net minus hold-to-settlement net sums to −$51,075.03. For these fixed sizes, the 67¢ sale made less than holding the same contracts to the contractual $1 or $0 settlement.

A second replay that holds every selected contract, and therefore changes how long slots and cash are tied up, admitted 645 and netted $203,108.14. That is lower than the stop portfolio's $235,488.18. The gap is not the paired sum. Resource release, later admissions, and resizing move together, and the order of that decomposition matters. Both files are under `05_profitability_dissection/`.

`GAME_WIDE_FIRST` admitted 626 and netted $242,975.27 on its own ledger. It is not an average with the headline.

## Stresses that reran admission

Joint adverse case, entry assumed at 80¢ and stop sale at 65¢: net $39,725.73, still on an assumed fill. Fee coefficient 0.07: net $106,370.83. Next-bar bid close as a price proxy, which is not a buyable quote: net $65,814.78. Strict ten-entry batches: 574 admitted, net $190,852.41. Full grid: `05_profitability_dissection/stresses.csv`. Settlement payouts stayed $1 or $0.

## Uncertainty

Block bootstrap of 7 local days, seed 20260926, 12,255 paths of a 20,000-path request. The cut was a runtime budget, recorded before the quantiles were used as a decision. Median ending equity about $229,554.86. 5th percentile about $147,408.57. 95th about $354,986.99. None of these resampled paths finished below $20,000. That is process variation inside this winning, FIRST80-conditioned sample. It is not a probability that a live account cannot lose money, and it is not a one-year forecast.

Completion-order W/L transitions are in `06_markov_chains/completion_order_transitions.json`. They describe this trade list. They are not a synchronized market process.

## Launch window

November 1, 2026 through April 1, 2027 is not identified. No numerical expectation is filled in from this history. Live trading is not authorized.

## Measurements added beside the headline

These files do not replace `summary.json` or `01_trade_logs/trades.csv`.

Realized event equity, a bid-close mark, and that mark after an estimated sale fee are separate series in `02_portfolio_logs/mark_equity_curve.csv`. The bid-close mark fell about 6.92% from $136,145.37 to $126,722.20. After the user fee charged as if that bid were a sale, the drop was about 6.91%. Neither number is a liquidation fill. The earlier 6.51% figure remains the realized-accounting path only.

Day-cluster 95% intervals for mean net cents per contract, 10,000 resamples, are about 4.19 to 6.55 combined, 3.32 to 6.48 NBA, and 4.27 to 7.75 NCAAB. Every resampled mean in this draw was above zero, so the one-sided Monte Carlo p-value sits on the floor 1/10,001. Holm adjustment across those three endpoints is about 0.0003. That interval is not a posterior probability of a live edge. The timing null is `NOT_IDENTIFIABLE`. Nested outer refits were not run.

Monte Carlo families stay named. A and B reshuffle or resample the admitted dollar results and cannot validate the seven-slot calendar book. Dollar permutation is not an exchangeability test, because contract counts change. Family C is the 7-day block ledger: 12,255 paths, mean ending equity about $237,780.77, Monte Carlo standard error of that mean about $580.69. The 1st percentile of ending equity is about $122,026.27 and the 99th is about $419,416.72. None of those paths finished below $20,000. A plug-in standard error of zero on that count is not proof the probability is zero. Block lengths 1 and 3 are smaller sensitivities. A 400-path subsample, seed 20260929, is the only place intra-path drawdown was stored: about 4.5% of those paths had a realized-accounting drawdown above 10%, and none above 15%. About 2.25% were below the starting equity after 40 completions; none of that subsample were below it after 100 completions. One-year and 1,000-trade horizons were not produced.

Family D uses pre-entry volatility only. 530 entries are HIGH, 112 are LOW, and 5 are UNKNOWN. The UNKNOWN cell is too small to interpret. Family E is the already-run price and fee grid. It does not estimate a probability of gapping through 67¢.

Same-timestamp reverse priority admitted 647 and netted $235,333.42. Putting the entry fee inside the 6% principal cap admitted 647 and netted $233,075.74. Bankrolls of $10,000, $20,000, $40,000, and $100,000 each still admitted all 647 candidates, because the cap and the cash test did not bind. That is a sizing scale, not a depth curve. The extra round-trip cost that would zero the unweighted mean net is about 5.34¢ per contract, and about 5.56¢ if weighted by contracts. That is a tolerance on this assumed-fill sample. It is not a claim that real costs are below it.

The within-game cell model is development-only. Fit on signals before 2026-02-01 and scored later in the same season, the later-segment Brier score for the stop indicator is about 0.255 on 279 scored trades. Predicting 0.5 on every trade would score 0.25, so this fit did not show useful discrimination. It did not filter entries or change size. Full-sample absorption is 317/647 stops and 330/647 winning settlements, with no losing settlement on this close proxy.
