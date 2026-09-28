# Corrections relative to first78_67_portfolio_v1

The v1 run `first78_67_20260926T074540Z` is left unchanged.

- Sharpe here is the daily change in account equity. v1 divided the day's dollar P&L by the original $20,000.
- A p-value here is a studentized centered day-cluster bootstrap, or `P_VALUE_NOT_ESTIMABLE`. v1 reported the share of uncentered bootstrap means at or below zero.
- Drawdown here uses the one-minute grid. v1's bid mark was taken at portfolio events.
- A first print already at or above 78¢ is `UNPROVEN_FIRST`. v1 folded that case into “no cross.”
- An entry bar that already traded at or below 67¢ is left unresolved. v1 recorded the flag and still booked the trade.
- The population here is the in-window inventory. v1 started from the locked 936.
- Cash-delay and stop-failure scenarios are new. They are not in the v1 ledger.
- The within-game model fitted on later 2025–26 dates is not applied. Scoring it on these earlier windows would be a backward transport.
