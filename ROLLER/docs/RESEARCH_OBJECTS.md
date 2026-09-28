# FIRST80 research objects (4.1.0-R)

Research only. Does not change live FIRST01 / Risk / Execution. Candle path ≠ fill.

These objects reconstruct the frozen mid-game 80→40 book from ROLLER tables. They are **off `O_t`**. `db.observation()` still cannot contain FIRST80. Public `dataset("first80_triggers")` is refused; use `db.first80()` or `db.labels()`.

| Object | Rule | Where |
|--------|------|--------|
| FIRST80 trigger | First tradable `yes_bid_close ≥ 80¢` after a prior tradable close `< 80¢`. One per event. Same-timestamp tie → exclude. | `db.first80()`, label `first80_trigger` |
| T40 | First **later** tradable close `≤ 40¢` (close path, not wick) | label `first80_t40` |
| Clock snap / slice | Last visible PBP with `event_timestamp ≤ snap`. NBA/WNBA Q1–Q4; NCAAB H1_1–H2_2. Asked-six = Q2∪Q3 / H1_2∪H2_1. UNALIGNED if period or remaining missing. | `db.clock_snap()`, label `first80_entry_slice` |
| Kalshi W | Ticker expiration (`result=yes` or `settlement_value_e4=10000`). Not box `home_win`. | `kalshi_markets`, label `kalshi_yes_settled` |
| quality() / tradable-cross | Uncrossed spread ≤ 10¢ and (volume > 0 or prior tradable bar). Warehouse `is_valid` stored. Sequential `had_quality` is the scan, not one isolated row. | candle columns + `roller.research.quality` |
| Game window | `game_date` 16:00Z → +52h. Scan end = min(window end, market close). | `games.game_window_*` |
| Trades tape | Warehouse prints. `market_data_type=TRADE_PRINT`. Not fills. | `kalshi_trades` |
| Orderbook snapshots | Forward-only official GET. Best YES = last `yes_dollars` level. No historical L2 backfill. | `kalshi_orderbook_snapshots` |

NCAAB FIRST80 and F_t corpora use `p5_vs_p5=1` only.

```python
db.clock_snap(gid, ts, as_of=ts)
db.first80(internal_game_id=gid, as_of=...)
db.dataset("NBA", "2025-2026", "kalshi_trades", as_of=...)
db.dataset("NBA", "2025-2026", "kalshi_markets", as_of=...)  # settlement masked until result_available_at
```
