# W7 architecture — Canonical EventMarketPath

Research only. Does not modify production trading, Risk, or Kalshi execution.

`momento-research-path` joins accepted W5 synchronized TRADE observations onto
W6 canonical `GameState` rows using W5’s AS-OF `prior_event_id`.

W5 remains the synchronization owner. W6 remains the game-truth owner. W7 does
not reconstruct PBP, invent L2, or implement strategy replay.

See [../research/backtesting_rebuild/W7_EVENT_MARKET_PATH.md](../research/backtesting_rebuild/W7_EVENT_MARKET_PATH.md).
