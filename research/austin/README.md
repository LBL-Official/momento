# Austin — Choosin Texas query desk

PCA + KNN historical matching for Choosin Texas NBA 2Q/3Q.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
DATA MODE = HISTORICAL QUERY
LIVE FEED = UNAVAILABLE
N = 604 (NBA 2Q∪3Q). Not 936. Not 1182. Not 1230.
```

Austin is research only. It does not submit. It does not skip FIRST80
entries. 3 / 4 / 5% is an entry-allocation research band
(`ENTRY_SIZING_REFERENCE` on POST-80). Query games are warehouse NBA
games and are not the training N.

Labels are only:

```
CONDITIONAL EV FROM CURRENT STATE
95% CI
HISTORICAL SUPPORT
STATE CHANGE FROM ENTRY
```

Never BUY / SKIP / SELL / HOLD / EXIT NOW / CONFIDENCE.

Fort Worth is a later read-only policy + contract page. Not an engine.

Austin is Position Stratification. It forwards a stratum into DRE.
It does not own the portfolio objective. DRE SSOT:
`research/dre/PORTFOLIO_OBJECTIVE_V1.md`.

## Surfaces

| Piece | Path |
|---|---|
| Package | `ROLLER/roller/austin/` |
| Library | `research/austin/` |
| Feature SSOT | `research/austin/features/registry.yaml` |
| Dashboard | `frontend/choosin-texas` `#/austin` `:5182` |
| API | `/austin/*` on ROLLER `:8791` |
| Fort Worth | `#/fort-worth` + `GET /austin/fort-worth/contract` |

## Universe

Locked Dallas / nba-path book:

```
SPORT = NBA
MARKET = CHOOSIN TEXAS
PERIOD = 2Q + 3Q
N_trades = 604
2Q = 314
3Q = 290
S = 450 / 604
```

Identities from `first80_asked_six.csv`. Path snapshots join warehouse
1m `TRADABLE_YES_BID` after entry. PBP is sequence-joined, not candle-PIT.

Do not mix:

- 936 derived four (includes NCAAB)
- 1182 asked-six (includes WNBA)
- 1230 NBA FULL FIRST80 / hedge V1 (citation only)

## Query mode

There is no live Choosin quote. The researcher supplies a `QueryState`.
It enters the same `build_feature_vector` as historical `RawState`.

The query never enters training and has no outcome.

## What Austin learned from path-FE

Residual enter/skip was anti-edge. Austin does not emit BUY / SKIP.
Unfiltered touch-80 stays the entry policy. The research lever is
**sizing band + maker-40 hedge hypothesis**, both labeled as candle-path
and `FILL_UNAVAILABLE`.

## Run

```text
python3 -m roller.austin
python3 ROLLER/scripts/terminal_api.py
cd frontend/choosin-texas && npm run dev
```

Open `http://127.0.0.1:5182/#/austin`.

## Do not

- Remount inside `frontend/roller-terminal`
- Edit `first80.py` or live FIRST01 / 80/81/83/89
- Change `book.json`, start W9, or warehouse Phase 21
- Import path-FE Family E into Austin features
- Treat a 40¢ close as a maker fill
- Invent N on `LOCK_MISMATCH`
- Claim 1230 hedge EV on the 604 book
