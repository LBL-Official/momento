# Assumptions

Live execution is off. A minute bid close is not a fill.

Both windows start at $20,000 and do not share cash, open positions, or completion counts. Positions entered inside a window are followed through the recorded exit or settlement after the cutoff. Cutoff marked equity and final equity are separate.

The headline fill is an assumed 78¢ buy and an assumed 67¢ sale. Fees use the user coefficient 0.0175, ceiling to the cent once per aggregate order. That schedule is not a verified 2025 print. Settlement payouts stay $1 or $0, with no settlement sale fee.

Holds release the slot and the cash at `settlement_time`, labeled `HYPOTHETICAL_CASH_AT_SETTLEMENT_TIME`. Stops release the slot at the stop signal and, in the baseline, the assumed sale cash at that same time. `close_time` and `expiration_time` are not cash.

A contract whose first quality bar is already at or above 78¢ is `UNPROVEN_FIRST`. An entry bar whose low is already at or below 67¢ is `CHRONOLOGY_UNRESOLVED` and is not given a winning exit.

NBA clocks are Q2 and Q3 on the inherited as-of snap. NCAAB clocks are period 1 with remaining at or under 600 seconds, and period 2 with remaining over 600 seconds. Missing clocks stay missing.

October uses the 2025–26 normalized minute book. April NBA uses the partial raw candlestick files and a date-plus-team identity join to the 2024–25 play-by-play. April NCAAB has no candlesticks in that tree. Absent games are not filled with another sport or another month.

No preseason or conference drop is applied unless the source row already carries that exclusion. Stage is a label when the schedule file has one.

The future 80¢ cross is a diagnostic label only. Oracle acceptance and the oracle stop-failure bound are not baseline scenarios and are not executable policies.

The v1 study’s uncentered bootstrap fraction is not used as a p-value. Sharpe uses the change in account equity from one local day to the next.
