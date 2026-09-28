# Questions for review

1. Accounting. `summary.json` net cents 23548818 equals gross 25612015 minus fees 2063197. Sport nets sum to that total. Ending equity is 2000000 + net. Does that identity hold on `01_trade_logs/trades.csv` if recomputed independently?
2. Sample. Is it clear that 936 games were selected by a later FIRST80, and that 640 of 647 trades reused that contract?
3. Stop utility. Same-quantity paired difference is negative (stop minus hold = −5107503 cents). The full hold replay is a different book (645 admitted, net 20310814 cents). Are those being kept apart?
4. Executable economics. Is `NEXT_BAR_PRICE_PROXY` (net 6581478 cents) being read as a price number rather than a fill, and are maker and observed-quote replays left unavailable?
5. Uncertainty and capacity. The block bootstrap did not finish below $20,000 inside this sample. Is that being refused as a live ruin probability? Depth and queue were not identified.
6. Launch. November 1, 2026–April 1, 2027 stays `NOT_YET_IDENTIFIABLE`. No live authorization is implied.
7. Marks. Is the 6.92% bid-close drawdown being kept apart from the 6.51% realized-accounting drawdown, and is neither being called a fill?
8. Uncertainty. Are families A and B being read as reduced-form dollar reshuffles, and is the zero count of primary paths below $20,000 being refused as proof that a loss is impossible?
