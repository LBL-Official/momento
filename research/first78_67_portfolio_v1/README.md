# FIRST78→67 portfolio research

Isolated study. Live execution is off. The 6% sizing and the 78/67 levels apply only here.

Headline evidence is a close proxy: first tradable minute bid close at or above 78¢, then a later close at or below 67¢, with an assumed 78¢/67¢ fill and the user fee. That is not a maker fill.

Population is the locked 936-game derived four, conditional on FIRST80. Headline selection is `CONTRACT_WISE_FIRST`. `GAME_WIDE_FIRST` is stored separately.

Run the study with the ROLLER virtualenv:

```text
ROLLER/.venv/bin/python -m unittest research/first78_67_portfolio_v1/tests/test_acceptance.py
ROLLER/.venv/bin/python research/first78_67_portfolio_v1/run_backtest.py
```

The completed run is `runs/first78_67_20260926T074540Z/`. Start with `07_final_report/findings.md` and `summary.json`. Supplements that do not rewrite those headline files:

```text
ROLLER/.venv/bin/python research/first78_67_portfolio_v1/complete_plan_outputs.py
ROLLER/.venv/bin/python research/first78_67_portfolio_v1/finish_report_artifacts.py
```

November 1, 2026–April 1, 2027 performance is not identified.
