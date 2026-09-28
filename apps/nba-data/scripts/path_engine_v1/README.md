# Path Engine V1 research scripts

Run with the NBA research venv (pyarrow + numpy):

```text
/tmp/momento-nba-venv/bin/python run_pipeline.py
```

Order: observations → features → leakage audit → models → report.

Does not modify `nba_80_40_execution_audit.py` or live trading.
