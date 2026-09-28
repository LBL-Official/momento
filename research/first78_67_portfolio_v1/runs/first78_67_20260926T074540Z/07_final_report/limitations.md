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
