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
