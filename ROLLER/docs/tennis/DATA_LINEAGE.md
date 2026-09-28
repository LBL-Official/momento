# Tennis data lineage

Research only. Canonicalize once, index once, query many times.
Runtime query never calls the network.

## Sources

| stream | source | license | PIT |
|---|---|---|---|
| Kalshi ATP/WTA match-winner | Public REST `KXATPMATCH` / `KXWTAMATCH` | Kalshi public research reads | Market timestamps are real. Prices are integer E4. |
| Match Charting Project | Jeff Sackmann, `tennis_MatchChartingProject` | **CC BY-NC-SA 4.0 NonCommercial — commercial use PROHIBITED** | Sequence only. No point timestamps. |

MCP must stay swappable. Every MCP-derived manifest carries
`roller.tennis.pbp.LICENSE_FIELDS`.

## Layers

```
raw/kalshi/{atp,wta}/{events,markets,candlesticks,trades}
raw/mcp/charting-{m,w}-{matches,points-*}.csv
        ↓ normalize (Rust momento-tennis-data; Python roller.tennis.pbp)
normalized/{atp,wta}/ + MCP canonical rows
        ↓ crosswalk (UUID+date → name+date → surname+date+tournament → FAIL CLOSED)
ROLLER/data/tennis/2025_2026/canonical/{games,pbp,kalshi_*}
```

Three Kalshi layers stay separate: trade ticks, native candles (`yes_bid` /
`yes_ask` / `price`), last-trade 1m derived from ticks only.
Do not derive yes-bid from prints. Do not forward-fill.

`dataset_version` is a content hash, not mtime.

## Crosswalk (measured 2026-09-11)

Window: Kalshi + MCP 2025-06-18 → 2026-09-11. Identity join only.
`SEQUENCE-ONLY PBP ≠ PIT`. MCP `Time` is never a point timestamp.

Real Kalshi↔MCP on disk (`ROLLER/data/tennis/2025_2026/canonical/crosswalk.csv`):

- Charted matches in window: 855
- Matched: 688 (UUID 682, full name 0, surname+tournament 6)
- Ambiguous fail-closed: 3 (2 multiple MCP per event, 1 multiple Kalshi)
- Unmatched: 164 (111 `NOT_LISTED_COMPETITION`, 53 `NO_CANDIDATE`)
- Ceiling after dropping unlisted competitions: 744 / 855 (87.0%)
- Recall on listed competitions: 688 / 744 (92.5%)
- Kalshi games written: 9,097 (ATP 4,628 / WTA 4,469). Linked to PBP: 688
- Official W: Kalshi `result` yes/no only (17,640 markets). `scalar` is not coerced.

MCP charted points in this clone end in 2026-05. Later Kalshi events stay
market-only (`UNMATCHED` / `NO_POINT_DATA`), never N=0.

Candle/last-trade layers are whatever Kalshi ingest has marked COMPLETE.
Re-run `python -m roller.tennis.ingest` after `momento-tennis-data download-all`
finishes to refresh market-path coverage. Do not invent missing minutes.

Duplicate MCP `match_id` values and one-name-to-many-UUID collisions fail closed.

## What this is not

Not a fill. Not live execution. Not FIRST01 / 80/81/83/89. Not W9.
Missing PBP is `NO_POINT_DATA`, never N=0. Layers are independent:
identity / settlement / yes-bid / last-trade / MCP sequence / PIT point-state
are not collapsed into one `DATA_REQUIRED`. See `roller.tennis.observability`.
