# Choosin Texas

FIRST80 80/40 NBA + NCAAB four-partition research desk.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
N = FIRST80 trigger events, not Kalshi prints
k/n integers are the authority
asked-six (1182) ≠ NBA+NCAAB four (936)
terminal W/N ≠ 80/40 trade S
ledger EV ≠ fill ≠ live EV
Texas (75) FIRST75 913 ≠ FIRST80 936 ≠ asked-six FIRST75 1126
```

Does not submit orders. Does not rescan the warehouse. Does not change
live FIRST01 / 80/81/83/89. Does not remount inside ROLLER.

## Universe

Locked FIRST80 asked-six slices, WNBA excluded. Source:
`docs/research/lebronner/TABLES.md` §3 / §7.

| Partition | N | W | L | W∩¬T40 | W∩T40 | L∩¬T40 | L∩T40 |
|---|---:|---:|---:|---:|---:|---:|---:|
| NBA 2Q | 314 | 267 | 47 | 239 | 28 | 0 | 47 |
| NBA 3Q | 290 | 238 | 52 | 211 | 27 | 0 | 52 |
| NCAAB 1H second 10 | 193 | 163 | 30 | 142 | 21 | 0 | 30 |
| NCAAB 2H first 10 | 139 | 118 | 21 | 108 | 10 | 0 | 21 |
| derived four | 936 | 786 | 150 | 700 | 86 | 0 | 150 |

Complement only: asked-six 1182 = 936 + WNBA 2Q∪3Q 246.

Terminal `p = W/N`. 80/40 trade `S = P(¬T40)`. `W∩T40` is a terminal
win and an 80/40 loss.

## Path ladder EV

`Tx = post_entry_min_yes_bid_cents ≤ x`. Nested
`T25 ⊂ T30 ⊂ T35 ⊂ T40 ⊂ T45 ⊂ T50`. Ledger
`EV = 20S − L(1−S)` with `L = 80 − stop`. Candle path, not a fill.

25 / 30 / 35 / 40 / 45 / 50 use the full **936** book. 80/55 stays
**entry &lt; 86** (N=905).

| Path | N | S | L | EV / trade | Book |
|---|---:|---|---:|---|---:|
| 80/25 | 936 | 746/936 | 55 | 745/156 = 4.7756¢ | 4470¢ |
| 80/30 | 936 | 736/936 | 50 | 590/117 = 5.0427¢ | 4720¢ |
| 80/35 | 936 | 721/936 | 45 | 365/72 = 5.0694¢ | 4745¢ |
| 80/40 | 936 | 700/936 | 40 | 190/39 = 4.8718¢ | 4560¢ |
| 80/45 | 936 | 680/936 | 35 | 580/117 = 4.9573¢ | 4640¢ |
| 80/50 | 936 | 650/936 | 30 | 85/18 = 4.7222¢ | 4420¢ |
| 80/55 | 905 | 579/905 | 25 | 686/181 = 3.7901¢ | 3430¢ |

Pool ledger rank on this sample: 35 > 30 > 45 > 40 > 25 > 50 > 55.
Slice ranking is not the pool ranking. Do not treat 35 as a live stop.

## NBA T40 clock and margin

`GET /choosin-texas/nba-path`. NBA 2Q+3Q only (N=604, T40=154).
Clock is `PERIOD_BOUNDED_LINEAR_GAME_CLOCK` at the T40 candle, not
warehouse PIT. Scatter is entry bought-team margin vs final margin,
survive vs T40. Survivors have no T40-time score.

## Dallas (page 2)

`#/dallas` and `GET /choosin-texas/dallas`. NBA 2Q+3Q only. Historical
snapshots, not a live current quote.

| Cohort | N |
|---|---:|
| survive | 450 |
| W ∩ T40 | 55 |
| L ∩ T40 | 99 |

Layers: Game (lead at 80 vs pregame bid), Snapshots (lead vs price at
PREGAME / FIRST80 / T40 / FINAL), Collapse (lead at 80 → lead at T40).
Cuts show T40 / W∩T40 / L∩T40 / survive by lead at 80, by 5¢ opening
price, and by both. Hover lines and axis ticks are API-emitted.
Not an early-exit rule. `W∩T40` recovered after the path stop.

Research note (not a live book), including NCAAB H1_2/H2_1
validation: `research/choosin_texas/NBA_8040_2026_27_NOTE.md`.
Dallas stays NBA-only.

## 2026-27 research book

`#/book` and `GET /choosin-texas/book`. Locked library:
`research/choosin_texas/library/nba_2q_regular_8040_1lot_2026_27/book.json`.
Write-up: `research/choosin_texas/NBA_8040_2026_27_BET.md`.

Registered book: NBA 2Q, regular season, FIRST80 80/40, 1 contract,
no filters. Baseline 2025-26 Q2 RS: N=280, S=218/280, EV=+6.7143¢,
book 1880¢. `RESEARCH_REGISTERED ≠ LIVE_ARMED`. Watch cells are
logged, not skipped. Does not submit.

## Katy

`#/katy` is the labeled experiment index. Each card is `#/katy/{slug}`.
Books are never combined. Search is not a freeze. Houston lock is
declared, not a fill.

| # | Slug | Austin |
|---|---|---|
| 1 | `late-underwater-41-70-ev5` | yes |
| 2 | `q4-open-8040-search` | yes |
| 3 | `2h-last-10-price-search` | no |
| 4 | `last10-clock-trail-55-45` | no |
| 5 | `last10-austin-four-book` | yes |

2H last 10 = NBA Q4 12:00 remaining = NCAAB 2H 10:00 remaining.

## Surfaces

| Piece | Path / port |
|---|---|
| Dashboard | `frontend/choosin-texas` `:5182` |
| API | `/choosin-texas/health` `/universe` `/universe-75` `/universe-77` `/asked-six` `/universe-81` `/universe-83` `/nba-path` `/dallas` `/book` `/katy` on `:8791` |
| Package | `ROLLER/roller/choosin_texas/` |

How-to: `docs/operations/CHOOSIN_TEXAS.md`.

## Asked-six

`#/asked-six` and `GET /choosin-texas/asked-six`. Not Texas `#/` (936).
Six CSV slices: NBA 2Q, NBA 3Q, NCAAB H1_2 (1H second 10), NCAAB H2_1
(2H first 10), WNBA 2Q, WNBA 3Q. τ 80/75/77/81/83. All stops
25–55 including mid 33/37/43/47. OOS is CSV `dataset_split`.
NCAAB test N is too small to lock S/EV (`DATA_REQUIRED`).

| τ | asked-six | derived four | WNBA |
|---|---:|---:|---:|
| 80 | 1182 | 936 | 246 |
| 75 | 1126 | 913 | 213 |
| 77 | 1158 | 933 | 225 |
| 81 | 1193 | 940 | 253 |
| 83 | 1243 | 973 | 270 |

FIRST81/83 are research entry books (`GET /choosin-texas/universe-81`
and `/universe-83`). Not live FIRST01 / 80/81/83/89.

## What this is not

- Texas `#/` is derived four 936, not asked-six 1182.
- Not SuperASI fill / fee.
- Not a fill, live P&L, or a tradable filter.
- Not W9.

## Texas (75)

`#/texas-75` and `GET /choosin-texas/universe-75`. Same four clock
slices as Texas. FIRST75 trigger, entry 75. Locked from
`docs/research/lebronner/TABLES.md` §2 / §7. Does not rescan.

| Partition | N | W | L | W∩¬T40 | W∩T40 | L∩¬T40 | L∩T40 |
|---|---:|---:|---:|---:|---:|---:|---:|
| NBA 2Q | 318 | 242 | 76 | 208 | 34 | 1 | 75 |
| NBA 3Q | 258 | 192 | 66 | 167 | 25 | 0 | 66 |
| NCAAB 1H second 10 | 204 | 152 | 52 | 126 | 26 | 0 | 52 |
| NCAAB 2H first 10 | 133 | 110 | 23 | 99 | 11 | 0 | 23 |
| derived four | 913 | 696 | 217 | 600 | 96 | 1 | 216 |

Complement only: asked-six FIRST75 1126 = 913 + WNBA 2Q∪3Q 213.

`S = P(¬T40) = 601/913`. `s_L` is not 0. Ledger
`EV = 25S − 35(1−S)` = `4105/913` = +4.4962¢ / trade. Not the
Lebronner assumed-fill-80 +20 object.

Event ledger: `research/first75_asked_six_chatgpt_export/first75_asked_six.csv`
(1126 asked-six rows). Reconstructs 75/25–75/50 on N=913 and 75/55 on
the entry&lt;81 book (N=868, excluded 81-first = 45). NBA T40 clock +
scatter is `GET /choosin-texas/nba-path-75` (N=576, survive 376, T40 200).
Do not reuse `first80_asked_six.csv`.

## Texas (77)

`#/texas-77` and `GET /choosin-texas/universe-77`. Same four clock
slices as Texas. FIRST77 trigger, entry 77. TABLES.md has no FIRST77.
Locked from the collected ledger. Does not rescan.

| Partition | N | W | L | W∩¬T40 | W∩T40 | L∩¬T40 | L∩T40 |
|---|---:|---:|---:|---:|---:|---:|---:|
| NBA 2Q | 324 | 250 | 74 | 218 | 32 | 1 | 73 |
| NBA 3Q | 281 | 223 | 58 | 196 | 27 | 0 | 58 |
| NCAAB 1H second 10 | 188 | 153 | 35 | 131 | 22 | 0 | 35 |
| NCAAB 2H first 10 | 140 | 120 | 20 | 109 | 11 | 0 | 20 |
| derived four | 933 | 746 | 187 | 654 | 92 | 1 | 186 |

Complement only: asked-six FIRST77 1158 = 933 + WNBA 2Q∪3Q 225.

`S = P(¬T40) = 655/933`. `s_L` is not 0. Ledger
`EV = 23S − 37(1−S)` = `4779/933` = +5.1222¢ / trade. Not the
Lebronner assumed-fill-80 +20 object.

Event ledger: `research/first77_asked_six_chatgpt_export/first77_asked_six.csv`
(1158 asked-six rows). Reconstructs 77/25–77/50 on N=933 and 77/55 on
the entry&lt;83 book (N=883, excluded 83-first = 50). NBA T40 clock +
scatter is `GET /choosin-texas/nba-path-77` (N=605, survive 415, T40 190).
Do not reuse `first80_asked_six.csv` or `first75_asked_six.csv`.
