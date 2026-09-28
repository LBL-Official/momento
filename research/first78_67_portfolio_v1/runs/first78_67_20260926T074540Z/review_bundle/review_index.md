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
