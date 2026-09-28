# Read-only documentation snapshot

## 07_final_report/findings.md

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

## 07_final_report/launch_assessment.md

# Launch assessment

Target evaluation window: America/Los_Angeles [2026-11-01 00:00, 2027-04-02 00:00).

Status: **NOT_YET_IDENTIFIABLE**.

The historical replay is a close-proxy accounting result on a FIRST80-conditioned 2025–26 book. A deployable FIRST78 population would need a definition that does not use a later 80¢ event. Executable fills, queue position, and prospective outcomes are not in this run. No expected ending equity, win rate, or drawdown is stated for 2026–27.

| Gate | State |
|---|---|
| Ledger identity on this run | PASS for gross − fees = net, sport nets sum to combined, max open 6 |
| Population valid for all prospective FIRST78 trades | FAIL |
| Execution evidence | INSUFFICIENT_EVIDENCE |
| Prospective validation | INSUFFICIENT_EVIDENCE |
| Capacity | bankroll scale computed; depth and fill fraction NOT_IDENTIFIED |
| Live authorization | REQUIRED_USER_INPUT |

A positive assumed-fill point estimate is not a launch gate.

## 07_final_report/limitations.md

# Limitations

- The 936-game book exists because FIRST80 landed in the designated windows. Results are conditional on that later event.
- 640 of 647 headline trades used the same contract the FIRST80 log had selected.
- Minute bid closes are not executable quotes, size, or maker fills. Order-book replay is unavailable. `orderbook_depth_available` on the candles does not establish queue position.
- `close_time` precedes `settlement_time` on the NBA market file. Using it as cash is a hypothesis. `expiration_time` is a later lifecycle field and is not settlement cash.
- NBA seconds inside a quarter are modeled by the existing period-bounded clock. NCAAB uses ESPN wall times, with interpolation only where a wall was missing.
- The user fee is a hypothetical cent-ceiling charge. It is not a verified 2025–26 series schedule.
- The historical path never held 7 positions. Cap behavior is covered by the unit test.
- There were no held-to-zero settlements in this close-proxy sample. A gap through 67¢ is still possible and is not priced here.
- Sharpe uses starting capital and a five-month span. sqrt(365) does not make it a year.
- Block-bootstrap paths that stay above $20,000 do not prove a positive live edge or zero ruin. Ending equity was stored for 12,255 primary paths. Intra-path drawdown was stored only on a 400-path subsample. Families A and B are reduced-form reshuffles of admitted dollars, not the seven-slot ledger. Nested outer refits were not run.
- The bid-close equity curve is a mark at event times. It is not an executable liquidation.
- The bankroll curve changes the starting cash and still admits every eligible candidate. Queue depth and fill fraction stay unidentified.
- The within-game stop model was scored inside the same examined season. It is not prospective validation.
- Holm p-values for the historical mean sit on the Monte Carlo resolution floor of the day-cluster resample. They are not a test against a matched timing null.
- Deflated Sharpe and probability of backtest overfitting are not estimable. The full list of abandoned trials is not in this repository as a complete registry.
- Sealed Austin confirmation cohorts were not opened.
- This study does not change FIRST80, `book.json`, live 80/81/83/89, or `momento-live.service`.

## assumptions.md

# Assumptions

Frozen before the performance tables were used to change the rule.

- Headline signal is the first quality minute `yes_bid_close` at or above 78¢ after a prior quality close below 78¢. Spread must be uncrossed and at most 10¢. This matches the reference FIRST80 scanner's per-contract rule, moved from 80¢ to 78¢.
- `CONTRACT_WISE_FIRST` is the headline. A contract is eligible only if its own first cross is inside the inherited window and the local entry interval. One game yields the earliest eligible contract. Ties use ticker sort.
- `GAME_WIDE_FIRST` rejects the game when the earliest cross across the two contracts is outside the window. It is not averaged with the headline.
- NBA windows are Q2 and Q3 from the as-of PBP period, HIGH or MEDIUM confidence. NCAAB windows are H1 second 10 (`period == 1` and remaining ≤ 600s) and H2 first 10 (`period == 2` and remaining > 600s). The 600-second boundary belongs to the first 10 minutes.
- Entry dates are America/Los_Angeles `[2025-11-01, 2026-04-02)`. The season is the 2025–26 tape in the locked file.
- Assumed accounting prices are 78¢ and 67¢ even when the close overshoots. Overshoot and stop gaps are stored. Settlement pays 100¢ or 0¢ and is not shifted in the adverse-price stresses.
- Fee raw is `0.0175 × C × p × (1−p)`. The charged fee is the cent ceiling once per aggregate order. This is the user scenario, not a verified historical Kalshi series multiplier.
- Baseline hold cash and slot release use `settlement_time`. `close_time` is an earlier trading-close field and is only the hypothesis `HYPOTHETICAL_CASH_AT_CLOSE_TIME`. Stop sales in the baseline release cash at the stop signal.
- Sizing balance updates after completions 10, 20, 30, …. Open quantities stay as entered. Strict ten-entry batches are a second policy.
- The seven-position cap is shared. This historical path peaked at 6.
- Block length 7 and seed 20260926 were set in the runner before the quantiles were read. Path count was cut from 20,000 to 12,255 by a 90-second runtime budget.

## review_bundle/questions_for_review.md

# Questions for review

1. Accounting. `summary.json` net cents 23548818 equals gross 25612015 minus fees 2063197. Sport nets sum to that total. Ending equity is 2000000 + net. Does that identity hold on `01_trade_logs/trades.csv` if recomputed independently?
2. Sample. Is it clear that 936 games were selected by a later FIRST80, and that 640 of 647 trades reused that contract?
3. Stop utility. Same-quantity paired difference is negative (stop minus hold = −5107503 cents). The full hold replay is a different book (645 admitted, net 20310814 cents). Are those being kept apart?
4. Executable economics. Is `NEXT_BAR_PRICE_PROXY` (net 6581478 cents) being read as a price number rather than a fill, and are maker and observed-quote replays left unavailable?
5. Uncertainty and capacity. The block bootstrap did not finish below $20,000 inside this sample. Is that being refused as a live ruin probability? Depth and queue were not identified.
6. Launch. November 1, 2026–April 1, 2027 stays `NOT_YET_IDENTIFIABLE`. No live authorization is implied.
7. Marks. Is the 6.92% bid-close drawdown being kept apart from the 6.51% realized-accounting drawdown, and is neither being called a fill?
8. Uncertainty. Are families A and B being read as reduced-form dollar reshuffles, and is the zero count of primary paths below $20,000 being refused as proof that a loss is impossible?

## review_bundle/review_index.md

# Review index

Run `research/first78_67_portfolio_v1/runs/first78_67_20260926T074540Z/`.

- `summary.json` — headline counts and cents
- `07_final_report/findings.md`
- `07_final_report/limitations.md`
- `07_final_report/launch_assessment.md`
- `01_trade_logs/trades.csv` — 647 admitted trades
- `01_trade_logs/candidate_audit.csv` — exclusions
- `01_trade_logs/trade_txt/` — one text file per admitted trade
- `02_portfolio_logs/events.csv`
- `02_portfolio_logs/completion_batches.csv`
- `05_profitability_dissection/paired_stop_vs_hold.csv`
- `05_profitability_dissection/portfolio_stop_vs_hold.csv`
- `05_profitability_dissection/stresses.csv`
- `04_monte_carlo/primary_summary.json`
- `04_monte_carlo/families.json`
- `02_portfolio_logs/mark_equity_curve.csv`
- `03_statistical_validation/day_cluster_intervals.json`
- `03_statistical_validation/timing_null.json`
- `05_profitability_dissection/capacity_curve.csv`
- `05_profitability_dissection/ordering_and_all_in.csv`
- `06_markov_chains/within_game_state_definitions.json`
- `review_bundle/questions_for_review.md`

Unavailable, with the reason in the file rather than a zero:

- maker execution and observed executable quotes
- market depth and fill fraction
- a timing null
- nested outer refits
- deflated Sharpe
- November 2026–April 2027 numerical forecast

The within-game file is a development-only score on this same season. It is not a deployment model.

## validation_report.md

# Validation

Unit tests, before the warehouse scan:

`ROLLER/.venv/bin/python -m unittest research/first78_67_portfolio_v1/tests/test_acceptance.py`

13 tests, all passed. They cover the 1,538-contract fee example, contract-wise versus game-wide selection, April 1 and DST, the seven-position cap, no re-entry, completion-epoch resize, strict batches, insufficient cash, held-to-settlement losses, and cash identity.

Full run: `ROLLER/.venv/bin/python research/first78_67_portfolio_v1/run_backtest.py`

Run id `first78_67_20260926T074540Z`. Elapsed about 122 seconds before manifest writing. Git metadata was unavailable at the repository path used by that process (`GIT_UNAVAILABLE`).

Output checks on the written files:

- 936 locked games.
- 647 admitted, 0 ledger rejections, max open 6.
- Gross − fees = net.
- NBA net + NCAAB net = combined net.
- Monte Carlo paths actually run: 12,255 of 20,000 requested. Seed 20260926.

The historical tape did not reach seven concurrent positions. Cap enforcement is the unit test, not this sample.

Follow-up, without rewriting `trades.csv` or `summary.json`:

`ROLLER/.venv/bin/python -m unittest research/first78_67_portfolio_v1/tests/test_acceptance.py`

13 tests passed again.

`ROLLER/.venv/bin/python research/first78_67_portfolio_v1/complete_plan_outputs.py`

`ROLLER/.venv/bin/python research/first78_67_portfolio_v1/finish_report_artifacts.py`

Those commands wrote the day-cluster intervals, the named Monte Carlo families, the bid-mark series, the bankroll scale, the development-only within-game score, and `manifest.json`. Git metadata remained `GIT_UNAVAILABLE`. Protected-file hashes are in that manifest. Austin confirmation outcomes were not opened.
