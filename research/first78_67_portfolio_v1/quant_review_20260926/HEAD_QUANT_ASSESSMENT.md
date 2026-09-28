# FIRST78→67 — independent head-quant assessment

Review date: September 26, 2026. Source run: `first78_67_20260926T074540Z`. Author role: independent quant review of the saved Cursor artifacts and their implementation. This is an audit, not a new strategy version or live authorization.

## Decision

**Accept the baseline as reproducible conditional threshold accounting. Do not accept this package as validated executable profitability, a reliable portfolio risk forecast, or a completed implementation of the original research specification.**

I reproduced all 647 baseline trades from the existing source readers, independently reconstructed every cash event, and passed 6,472 audit checks. Net $235,488.18 is not a simple addition or fee error. It is the result of favorable modeled payoff economics on a FIRST80-conditioned population, fixed 78¢/67¢ assumed prices, and repeated reinvestment. Several surrounding validation claims are materially defective: invalid p-values, calendar-distorting simulation, a next-bar timing leak and incomplete marked risk. The earlier completion claims should be superseded by this assessment.

## Scope and evidence

All 824 files in the run were read and fingerprinted; CSVs were parsed, JSON validated, all trade TXT records ingested, and narrative documents examined. There were no parse errors or empty files. The file inventory records row counts and hashes; duplicate-content groups prevent repeated views from inflating totals. I also inspected the experiment's Python modules, three report generators, tests, root contract/schema/inventory/protocol, and the referenced clock implementations. Original artifacts were not edited. Sealed Austin cohorts, live control and orders were not accessed.

The source replay deliberately reuses the original source readers and clock conventions. Agreement establishes reproducibility; it does not independently validate exchange timestamps, raw-feed authenticity or point-in-time clock reconstruction. The cash calculation is independent of the original portfolio engine. Supplemental intervals and chart calculations are review diagnostics on already examined data, not a prospectively frozen experiment.

## What the ledger supports

The requested historical population is 936 games: 604 NBA and 332 NCAAB. Candidate exclusions are 104 date-window, 179 first-cross outside-window, and six no-cross classifications. These are mutually exclusive program reasons, not proof that the source underwent a complete independent missing-data funnel. The final 647 positions comprise 382 NBA and 265 NCAAB. All were admitted; no baseline cap or cash rejection occurred. The maximum verified open count is six under the supplied close/cash assumptions.

Gross P&L is $256,120.15; charged fees are $20,631.97; net is $235,488.18. Ending cash and realized accounting equity are $255,488.18, with no remaining baseline holdings/receivables. Net divided by $20,000 is 1,177.44% for this historical scenario, not an expected annual return. NBA contributes $120,607.86 and NCAAB $114,880.32 to this one shared portfolio.

Checks independently covered principal = quantity × entry price, aggregate-order ceiling fees, gross minus fees, 6% frozen-balance integer sizing at every entry, completion-driven balance updates, entry-before-exit chronology, nonnegative cash/receivables, open-count limits, and cash + receivables + cost principal at every event. All 13 original acceptance tests also passed. Passing those narrow fixtures does not cover the missing partial-fill, void, uncertainty or full mark-path requirements.

There are 330 profitable settlements and 317 negative stop exits, no flats and no held-to-zero settlements. Positive strategy rate is 51.00%; terminal team win rate is 83.77%. Of the 317 stopped positions, 212 later won and 105 later lost. A stopped-then-winning team remains a negative strategy outcome. These observed zero held-to-zero losses do not mean stops prevent failed-exit losses.

## Why the dollar result is so large

At the opening balance, 1,538 contracts cost $1,199.64 plus $4.62 entry fee. A winning settlement nets $333.74 and a modeled 67¢ stop nets −$179.76. That binary example breaks even at 35.0068% profitable outcomes; this selected sample records 51.00%. Mean trade-level net P&L per contract is 5.3415¢. Increasing quantities after each tenth completion amplifies that modeled edge; sizes reach 18,036 contracts.

Keeping every admitted trade at exactly 1,538 contracts and applying exact rounded aggregate fees gives **$53,150.28**, versus $235,488.18 with resizing. This is a fixed-quantity economic diagnostic on the same entries and exits, not a new admission replay. The earlier approximately $53,152 estimate scaled rounded fees linearly; the exact fixed-size figure is $53,150.28.

![Equity comparison](/Users/user/Desktop/Momento/research/first78_67_portfolio_v1/quant_review_20260926/charts/01_equity.png)

The growth is highly sensitive to assumed price concessions: 434 of 647 entry bids already exceed 78¢; their overall mean is 79.8516¢. The stop-trigger bid averages 63.5363¢, yet the reference credits a 67¢ sale. The worst observed stop trigger is 25¢, a 42¢ gap. These are quote-close observations, not guaranteed executable prices; a bid is particularly not a buyable entry quote.

![Price gaps](/Users/user/Desktop/Momento/research/first78_67_portfolio_v1/quant_review_20260926/charts/06_price_gaps.png)

## Sensitivity assessment

The saved adverse-price scenarios retain the 78/67 signal policy but worsen assumed transaction prices and rerun sizing. Entry +1¢ reduces net to $135,557.08; entry +2¢ to $75,525.17. Joint entry 80¢ / stop sale 65¢ gives $39,725.73, an approximately 83% reduction from reference. The user-fee coefficient 0.07 scenario gives $106,370.83. They are useful conditional cost sensitivities; none verifies actual historical fee eligibility, size or fills. Contractual settlement payouts are unchanged.

**Withdraw the $65,814.78 next-bar number as a causally valid replay.** `candidate_from_contract(use_next_bar_price=True)` uses the next observed bid to size at the original signal timestamp. A minimal reproduction uses a price from timestamp 160 at timestamp 100. Moreover, the trade exporter labels default 78¢ even when actual principal was funded at another candidate price. One-bar-delay mode is separate and can allow entry and stop at the same timestamp; the original stop is not always recomputed strictly after entry. Changing a label to PRICE_PROXY did not correct these chronology errors.

![Cost sensitivity](/Users/user/Desktop/Momento/research/first78_67_portfolio_v1/quant_review_20260926/charts/03_sensitivity.png)

## Risk, marks and calendar performance

The independent realized-accounting drawdown reproduces 6.5106%, or $8,801.50 from its relevant peak. Original bid marks at portfolio event times report about 6.92%. I rebuilt 24,947 observation/event timestamps while holdings are open: the carried-bid-close diagnostic drawdown rises to **7.4352%**, or **$10,178.89**. This compares end-of-timestamp marks against a global peak including opening equity.

This 7.44% is still not clean executable liquidation risk: 3,553 timestamps have a carried mark older than 60 seconds; maximum mark age is 125.93 minutes. Missing/stale quote risk, price moves within a minute and order-size impact remain unresolved. The audit CSV retains mark ages rather than silently declaring the path complete.

![Drawdown](/Users/user/Desktop/Momento/research/first78_67_portfolio_v1/quant_review_20260926/charts/02_drawdown.png)

The original Sharpe used daily P&L divided by initial capital, initially on active dates only. A separate audit diagnostic uses 152 Pacific calendar days from November 1 through April 1, includes 12 zero-change days, and computes realized-equity return from the previous day's equity. Unannualized Sharpe is 0.6738; applying sqrt(365) gives 12.8730. This is a corrected **realized-accounting** statistic, not MTM Sharpe and not a prospective performance claim. It remains conditional on the same selected sample and hypothetical fills; I have not established dependence-adjusted uncertainty for it.

![Monthly attribution](/Users/user/Desktop/Momento/research/first78_67_portfolio_v1/quant_review_20260926/charts/04_monthly.png)

Monthly closed-trade attribution totals: November $11,057.01; December $12,780.90; January $40,464.99; February $50,884.14; March $104,646.14; April 1 only $15,655.00. This pattern partly reflects increasing exposure, not proof that later months have a stronger edge. The top five signal dates contribute 24.15% of total net and the top ten 39.03%; top ten games contribute 15.76%. These concentration ratios use final trade P&L attributed to entry dates, not a daily MTM return definition.

## Does the 67¢ stop add value?

The same-entry, same-quantity stop-minus-hold sum is −$51,075.03. That is a dollar-weighted economic comparison using quantities determined by the stop strategy. It is not the result of an independently cash-funded hold portfolio. The full saved hold replay admits 645 and nets $203,108.14; the stop portfolio exceeds it by $32,379.04, combining different timings, admissions, quantities and resizing.

At an unweighted trade-level per-contract denominator, the paired stop effect is only **-0.1294¢**. A 10,000-draw local-signal-day clustered percentile interval is **[-2.4988, 2.2365]¢** at 95%. This spans zero. The much larger dollar difference reflects when larger quantities occurred and must not be presented as a uniform per-contract stop penalty. The data do not establish a robust standalone stop advantage or disadvantage. No policy change is recommended from this reviewed sample.

![Outcomes](/Users/user/Desktop/Momento/research/first78_67_portfolio_v1/quant_review_20260926/charts/05_outcomes.png)

## Statistical inference: what survives and what does not

Conditional day-cluster percentile intervals can describe variability in the selected historical trade mean. My independent 10,000-draw recomputation gives combined mean 5.3415¢ and 95% interval [4.1664, 6.5420]¢; NBA mean 4.9187¢ with [3.3501, 6.5237]¢; NCAAB mean 5.9510¢ with [4.2356, 7.7449]¢. These are day-cluster diagnostics, not contiguous multi-day dependence protection, not a portfolio-return confidence interval, and not a correction for population selection or prior research reuse.

The original one-sided p-value counts bootstrap means <=0 after resampling from the observed distribution. No null distribution is constructed. Adding one to numerator and denominator does not make it a valid Monte Carlo null test; Holm adjustment does not cure this. **The p≈0.0001 / Holm≈0.0003 significance claims should be removed.** I provide no replacement significance claim.

The stated timing-null blocker is also too broad. FIRST80 selection prevents extrapolation to all prospective FIRST78 opportunities, but does not alone prove that every explicitly conditional timing comparison is unidentifiable. Such a comparison still needs a defensible matched support set, executable/price assumptions and causal follow-up. Those components were not implemented here.

## Monte Carlo: the primary simulation is not a valid calendar replay

A direct probe of `block_bootstrap_equity(block=7)` gives **604,805 seconds between adjacent sampled days**, rather than approximately one local day. The code adds `86400 * block + 5` after every sampled day, not after a whole seven-day block. It uses active days rather than all calendar days, and rebases every day's first arrival to the same time. This distorts cross-day overlap, capacity pressure, settlement funding and simulated horizon. The 400-path risk subsample repeats the same bug.

Therefore the original median $229,554.86, tail quantiles, no-terminal-loss result, and simulated drawdown frequencies are **not approved portfolio-risk estimates**. Monte Carlo standard error only measures numerical noise conditional on that flawed generator. More paths cannot fix it. Family A's fixed-dollar permutations and family B's dollar bootstrap are labeled reduced-form and may be read as such, but they are not capital-feasible account paths. Family D is transition counts, not an implemented regime-switching simulation. Family E is a deterministic stress grid, not an estimated tail mixture. Nested parameter uncertainty was not run.

## Markov and within-game modeling

Entry-order combined outcome transitions give P(next win | win)=48.33% and P(next win | loss)=53.63%. On the observed W/L subchain, both directions and self-loops exist; its stationary W occupancy is about 50.93% with zero numerical residual at shown precision. This is descriptive trade-step occupancy. F has no observations; the full W/L/F matrix has an undefined row, and stationary convergence for that three-state process is not established. Overlapping games, sport composition and time-varying sizing make a synchronized-market interpretation inappropriate.

The within-game artifact is not the mandated survival/competing-risk model. It is one observation per trade, binned by entry distance and period time; it omits recent-volatility covariates, changing game-time hazards, game-clustered snapshot dependence, censoring and proper stop-versus-terminal transitions. Its duration uses observed path endpoints rather than settlement cash time. On 279 scored later-segment observations, Brier is 0.254901; a training-only constant base rate scores 0.250022, and a constant 0.5 scores 0.25. The model does not improve this probability-score baseline. This does not by itself establish absence of discrimination; Brier measures calibration and resolution jointly. The later split remains previously examined development data.

## Data-quality and contract details

The scan filters crossed/wide quotes before both entry and stop detection. Of 224 earlier low-bid observations excluded by that quality convention, 222 are 0¢ bid / 100¢ ask empty-book-like records; the other two have 20¢ and 26¢ spreads. These should not simply be reclassified as executable stops. They demonstrate why signal quality, disappearance of liquidity and failed-stop behavior need separate explicit rules. No baseline stop was found after the recorded settlement timestamp. The audit preserves these observations separately.

NCAAB has halves: H1_2 includes exactly 600 seconds remaining and H2_1 excludes exactly 600. The prose claiming the 600-second boundary belongs to the first ten contradicts the code. NBA period clocks use retrospective interpolation; an as-of lookup over modeled walls is not historical receive-time availability. The reference scan and inherited labels were preserved, not promoted into a deployable real-time specification.

## Completeness and auditability

All seven named report folders exist, but folder existence is not completion. Six sections contain repeated trade-period rollups generated by the same function; they are views, not independent statistical, simulation or model validation results. The run lacks several specified artifacts, including canonical trade-path observations, strict-batch records, cash-reconciliation and exposure tables, paired effect intervals, fill-selection analysis and machine-readable launch/forecast gates. Some metadata exists only at the experiment root, outside the run/review subfolder. `deliverable_coverage.csv` records exact existence checks; absence of a named file is distinguished from a related result elsewhere.

The original manifest hashes four sources but not the full raw candle/market/PBP inputs, and has no commit or dirty diff. Supplemental scripts target and rewrite the same historical run. Root and run contract copies differ. A protocol field asserting `written_before_outcome_inspection` cannot itself prove historical preregistration. The review records current hashes and does not manufacture a past freeze. The original review_bundle directory is an index/questions/summary, not a self-contained copy of all evidence.

## Head-quant assessment and repair priorities

1. Preserve the reproduced baseline as a **conditional assumed-fill reference** and issue a versioned erratum withdrawing the invalid p-values, primary MC inference and next-bar timing claim.
2. Repair chronology, candidate-specific price exports, deterministic tie order, same-bar stop handling, unresolved/void bookkeeping and source-observation audit trails; add targeted regression tests before generating a new run.
3. Rebuild observation-time MTM with missing/stale rules, correct calendar block episodes and admission-aware simulations. Reconcile every variant and preserve immutable versioned source/config/output manifests.
4. Treat entry-cell probabilities and stationary outcome occupancy as descriptive until the mandated time-dependent survival model, prospective validation protocol, dependence-aware inference and nested uncertainty are implemented.
5. Define a separately registered prospective FIRST78 population without later FIRST80 membership and measure executable costs, fills, cash releases and capacity. Do not tune the 78/67 thresholds to these audit results.

For November 1, 2026–April 1, 2027, **launch performance expectation remains NOT_YET_IDENTIFIABLE**. Accounting validity is a pass within the supplied assumptions; population transportability, execution, capacity and prospective validation remain insufficient. Risk limits and live authorization remain user decisions, not outputs of this audit.

## External methodological context

[Bailey et al., The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) motivates treating repeated strategy selection as a distinct uncertainty problem; no numerical PBO is estimated here because complete trial history is absent. [Kalshi fee-rounding documentation](https://docs.kalshi.com/getting_started/fee_rounding), consulted September 26, 2026, is current documentation, not proof of the historical series fee schedule. All fee computations above remain the user-imposed hypothetical formula.

## Reproduction and review files

Run `PYTHONDONTWRITEBYTECODE=1 ROLLER/.venv/bin/python research/first78_67_portfolio_v1/quant_review_20260926/audit.py`, then `probes.py` and `diagnostics.py` with the same interpreter. Render with the bundled Python executable and `build_review.py` (Pillow dependency). Exact original source hashes are recorded in `file_inventory.csv`; current review results are in `audit_metrics.json`; independent event evidence is `independent_event_reconciliation.csv`. `checks.csv` contains every audit check, `defect_reproductions.json` the minimal bug demonstrations, and `findings_register.csv` the prioritized remediation record. No repaired strategy or live trading is implied by this package.
