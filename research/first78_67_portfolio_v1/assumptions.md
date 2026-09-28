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
