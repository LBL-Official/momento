# Feature classes

Letter codes match the research brief. Timing and leakage live in
`FEATURE_CONTRACT.md` and `ROLLER/roller/nba_8040_reverse_features/catalog.py`.

| class | name | v1 status | predictive? |
| --- | --- | --- | --- |
| A | identity | implemented (columns) | keys only |
| B | market at 80 | implemented | yes, at entry |
| C | pre-80 level path | warehouse 1m TRADABLE_YES_BID | yes, before entry |
| D | micro-path into 80 | prior close vs entry close | yes |
| E | post-80 path | event_path / labels only | **no** |
| F | time / clock | CSV modeled clock | yes, at entry |
| G | score snapshot | CSV at 80 | yes, at entry |
| H | score trajectory | `OPERATION_REQUIRED` | no |
| I | possession / fouls / timeouts | `SOURCE_UNAVAILABLE` | no |
| J | path velocity / acceleration | warehouse windows | yes, before entry |
| K | path range / volatility | warehouse windows | yes, before entry |
| L | quote-at-entry | bid/ask/spread | yes, at entry; not L2 |
| M | opening / pre-tip | `KALSHI_LAST_PRE_TIP_YES_BID` | yes |
| N | opposite ticker | skipped | no |
| O | period grouping | Q2 / Q3 one-hot | **not in matrix** |
| P | labels / targets | isolated parquet | **no** |

Ablation sets used in analysis:

- PRICE — entry bid, jump/exact 80, prior close, 5m delta/velocity
- TIME — remaining seconds and fractions
- SCORE — margin / lead / favorite-leading
- OPEN — pregame and distance-from-open
- PRICE+TIME
- PRICE+SCORE
- ALL PRE-80 — every catalog row with predictive timing

These are diagnostics. They are not a rank score and not a trading filter.
