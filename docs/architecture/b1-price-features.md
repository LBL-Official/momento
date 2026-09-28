# B1 architecture — price-dissection features

Research only. Does not modify production trading, Risk, or Kalshi execution.

`momento-research-features` builds one observational `B1EntrySnapshot` per W8
primary entry. Prices are W7 TRADE cents. Historical L2 is unavailable and is
not inferred from last trade.

The snapshot is the research unit:

```text
game + game state + starting belief + path + current TRADE + typed L2 holes
  + A1 entry/exit targets + forward TRADE/settlement labels
```

A1 buckets (`80-83` entry × hold / FIRST01 50% stop / hard 75–60 / horizons)
are research targets for “when is this print different.” They are not live
parameter changes.

See [../research/backtesting_rebuild/B1_PRICE_FEATURES.md](../research/backtesting_rebuild/B1_PRICE_FEATURES.md).
