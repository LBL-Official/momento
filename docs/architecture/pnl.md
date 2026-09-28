# P&L foundation (Milestone 5)

`momento-pnl` records components. It does not implement Kalshi fee or
settlement formulas.

```text
ENTRY COST              fill premiums (entry)
ENTRY FEES              FeeKind::Entry
LIQUIDATION PROCEEDS    fill premiums (liquidation)
LIQUIDATION FEES        FeeKind::Liquidation
SETTLEMENT PROCEEDS     authoritative SettlementEvent only
REALIZED P&L            Some only after settlement or a flat liquidation
UNREALIZED P&L          always None until a verified mark model exists
TOTAL FEES              entry + liquidation
```

Realized P&L, when present, is:

`liquidation_proceeds + settlement_proceeds − entry_cost − total_fees`

using only recorded fills and the supplied settlement amount.

UNRESOLVED (do not invent):

- Kalshi quadratic/flat fee formula
- sub-cent fee mapping into integer cents
- yes/no `$1` settlement applied automatically
- mark-to-market / mid used as unrealized P&L
- stop-basis VWAP as a trading rule (proposed only)

Liquidation proceeds are not entry capacity and are not recycled into the
weekly 12.5% budget. Remaining entry target continues to use entry fills
and entry fees only.

`ZeroFeeModel` is not evidence of profitability.
