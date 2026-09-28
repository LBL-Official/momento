# Data limitations

- 1-minute candles. Intrabar path is unknown.
- No historical L2, queue, or displayed size.
- No Momento live fill tape in this warehouse (L4 empty).
- Fees unresolved (gross ¢).
- Actual FIRST80 maker entry at 80 is unobserved; nominal 80 used.
- 80→40 Model A is itself a fill assumption on A1.
- persist_subsequent_min is lookahead if used as a fill gate (E1 does not use it).
- NCAAB working universe is P5 vs P5 (721), not warehouse 4099.
- P5 OOS n is small.
- A1 artifacts were not overwritten.
