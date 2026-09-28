# Choosin Texas

FIRST80 80/40 NBA + NCAAB four-partition research desk. Not Vital. Not
Momento LS. Not a ROLLER product tab.

```text
browser :5182
  → ROLLER research API :8791
  → /choosin-texas/universe
  → /choosin-texas/universe-60
  → /choosin-texas/universe-75
  → /choosin-texas/universe-77
  → /choosin-texas/asked-six
  → /choosin-texas/universe-81
  → /choosin-texas/universe-83
  → /choosin-texas/nba-path
  → /choosin-texas/nba-path-75
  → /choosin-texas/nba-path-77
  → /choosin-texas/dallas
  → /choosin-texas/book
  → /choosin-texas/sugarland
  → /austin/*
  → TABLES.md locks + tables.json + asked-six CSV
  → research/choosin_texas/library/nba_2q_regular_8040_1lot_2026_27/book.json
  → research/austin/
```

HTTP 200 is not a fill. Observed integers are not live EV.

## Surfaces

| Piece | Path / port |
|---|---|
| Dashboard | `frontend/choosin-texas` `:5182` |
| API | `ROLLER/scripts/terminal_api.py` `:8791` `/choosin-texas/*` |
| Inspect | `ROLLER/roller/choosin_texas/` |

Routes: `/choosin-texas/health`, `/choosin-texas/universe`,
`/choosin-texas/universe-60`,
`/choosin-texas/universe-75`, `/choosin-texas/universe-77`, `/choosin-texas/asked-six`,
`/choosin-texas/universe-81`, `/choosin-texas/universe-83`,
`/choosin-texas/nba-path`, `/choosin-texas/nba-path-75`,
`/choosin-texas/nba-path-77`, `/choosin-texas/dallas`,
`/choosin-texas/book`, `/choosin-texas/sugarland`, `/choosin-texas/katy`,
`/choosin-texas/katy/{id}`, `/austin/*`. No submit.

Texas is `#/`. 80/60 is `#/texas-60` (FIRST80 stop 60 on the same
derived four; N=936; T60 = post-entry min ≤ 60; s_L = 0; EV = 20S − 20(1−S)).
The 86 filter stays on 80/55. Texas (75) is `#/texas-75` (FIRST75 on the same
four clock slices; N=913; 75/25–75/50 on 913; 75/55 is entry&lt;81
N=868; EV = 25S − L(1−S) with L = 75 − stop). Texas (77) is
`#/texas-77` (FIRST77 on the same slices; N=933; 77/25–77/50 on 933;
77/55 is entry&lt;83 N=883; EV = 23S − L(1−S) with L = 77 − stop).
Asked-six is `#/asked-six` (NBA 2Q, NBA 3Q, NCAAB 1H second 10,
NCAAB 2H first 10, WNBA 2Q, WNBA 3Q). FIRST80 1182 ≠ 936.
FIRST75 1126 ≠ 913. FIRST77 1158 ≠ 933. FIRST81 asked-six 1193
(four 940 + WNBA 253). FIRST83 asked-six 1243 (four 973 + WNBA 270).
FIRST81 / FIRST83 are entry thresholds (gain 19 / 17; 81/55 entry&lt;87;
83/55 entry&lt;89), not stops on 75/77/80 and not live 80/81/83.
OOS uses CSV `dataset_split` (train=IN_SAMPLE, test=OOS). Slice test
N &lt; 20 is DATA_REQUIRED. `#/`, `#/texas-75`, and `#/texas-77` also
show a FIRST81+FIRST83 derived-four companion tile.
Dallas is `#/dallas` (NBA 2Q/3Q deterioration
snapshots, not a live quote). The 2026-27 research book is `#/book`
(`RESEARCH_REGISTERED`, not live). Austin is `#/austin` (PCA+KNN
query desk, historical query only, live feed UNAVAILABLE). DRE is
`http://127.0.0.1:5191/` (separate desk; objective
`research/dre/PORTFOLIO_OBJECTIVE_V1.md`). `#/austin/risk` is a pointer.
Fort Worth is `#/fort-worth` (read-only policy + contract, not an engine).
Katy is `#/katy` (labeled experiment index). Each experiment is
`#/katy/{slug}`. Sugarland is `#/sugarland`
(`SUGARLAND_PREGAME_V1`, NBA and NCAAB pregame quotes). It is not
the FIRST80 936 book. WNBA and MLB results stay in
`research/sugarland/v1/` and are not that dashboard. Research only;
execution disabled. Houston lock is declared, not a fill. Search is
not a freeze.

Ledger EV for 80/25 through 80/50 is on N=936. 80/60 is on that
same N=936 (`#/texas-60`), with 80/65 and full-book 80/55 beside it.
The NBA T60 clock is a modeled snap at the first ≤60 close. The Texas
ladder 80/55 is the entry-below-86 book (905). `#/paired` is a research
replay of these same 936 events for 80/40 and 80/65. The equal flat-stop
risk grid is unchanged. `CAPITAL_6PCT_CAP3` is a separate mode: 6% entry
premium per position, three positions, 18% aggregate premium. Session dates
are America/New_York calendar dates of Unix timestamps read as UTC. Exits are
the first through-close. `flat_stop_stress_proxy` is not marked-to-market
equity. Realized-capital drawdown is not mark-to-market drawdown.
`PLANNED_RISK_CAP3` is a third mode on the same session clock: 80/40 is
sized by the tighter of 6% entry premium and 2% planned stop risk, and
80/65 stays at 6% premium. Both keep the three-position cap. The 2%
figure is the planned stop, not a guaranteed realized-loss cap. A gap
below the stop stays in P&L in full. The position cap is three open
positions for the whole derived four, and the 820 and 865 accepted counts
are cumulative admissions under that cap. Neither book is live.
`#/paired` also shows execution validation for that frozen three-position
policy. The candle profit stays the reference. Minute closes and public
trades do not establish maker fills. Depth, queue, and sequence numbers
are unavailable, so the page does not publish an execution-aware portfolio
P&L. `CAPITAL_6PCT_CAP3` remains a separate labeled result. Prospective
observation is candle-close only. A live-quote trigger is a different
specification. A hypothetical 80¢ intent is a record after the close is
received, not an order. Entry lifetime and the stop response are unresolved.
Public quotes, depth, trades, and candle closes may be collected while fills
and returns stay blocked. The collector does not submit. FIRST75 75/25–75/50 is on N=913. 75/55
is the entry-below-81 book (868). FIRST77 77/25–77/50 is on N=933.
77/55 is the entry-below-83 book (883). Frontend only renders API-emitted displays.

## Run

```text
python3 ROLLER/scripts/terminal_api.py
cd frontend/choosin-texas && npm run dev
```

Open `http://127.0.0.1:5182`.

Locks disagree → `LOCK_MISMATCH`. The desk shows the error. It does
not invent N, percents, or EV.

## Do not

- Remount the shell inside `frontend/roller-terminal`.
- Edit `first80.py`.
- Rescan the warehouse to change N.
- Conflate asked-six 1182 with derived four 936.
- Conflate FIRST77 933 with FIRST75 913 or FIRST80 936.
- Conflate terminal `W/N` with 80/40 `S`.
- Treat ledger EV as a fill or live EV.
- Change live FIRST01 / 80/81/83/89.
- Start W9 or warehouse Phase 21.
- Treat `#/book` as live-armed or as a Kalshi submit.
- Apply 2025-26 watch cells as 2026-27 filters.
