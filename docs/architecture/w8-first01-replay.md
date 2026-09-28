# W8 architecture — FIRST01 strategy replay

Research only. Does not modify production trading, Risk, or Kalshi execution.

`momento-research-replay` replays frozen FIRST01 sequencing over accepted W7
EventMarketPath TRADE observations. Outputs are observational ledger events
and `FIRST01Opportunity` records.

W7 remains the sole historical market/game path. W8 does not reconstruct PBP,
invent L2, simulate fills, compute P&L, or start W9 outcome labeling.

See [../research/backtesting_rebuild/W8_FIRST01_REPLAY.md](../research/backtesting_rebuild/W8_FIRST01_REPLAY.md).
