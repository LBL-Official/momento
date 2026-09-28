# ROLLER Tennis — Reconnaissance

Canonical reference for the tennis implementation. Later phases should read this
instead of rediscovering the repository or re-probing external sources.

```
RESEARCH ONLY
LIVE EXECUTION = FALSE
CANDLE/PRINT PATH != FILL
LAST TRADE != YES BID
SEQUENCE-ONLY PBP != PIT PBP
OFFICIAL W = KALSHI SETTLEMENT
```

Status date: 2026-09-11.

---

## 1. Source table

| field | Kalshi tennis markets | Match Charting Project (MCP) |
|---|---|---|
| source_name | Kalshi public REST | Jeff Sackmann — Match Charting Project |
| coverage | ATP + WTA singles match-winner | ATP + WTA charted matches, shot-by-shot |
| date_range | 2025-06-18 .. 2026-09-12 | 1960-05-29 .. 2026-05-24 |
| point_level | none (market only) | full point sequence |
| timestamp_level | sub-second on trades; 1-minute candles | **none** |
| pit_joinable | yes (market side) | **no** |
| license | public API, no credentials for research reads | **CC BY-NC-SA 4.0 — NonCommercial** |
| retrieval_method | `momento-tennis-data download-all --tour {atp,wta}` | HTTPS raw.githubusercontent.com |
| gaps | see §5 | ~6% of Kalshi universe; charting lags ~3.5 months |

### Sources rejected

- **`JeffSackmann/tennis_slam_pointbypoint`** — repo returns 404 (removed upstream).
- **Archival mirror `Aneeshers/tennis-sackmann-archive`** — has slam point-by-point but only
  **2011 .. 2024 Wimbledon**. Zero temporal overlap with the Kalshi window, which starts
  2025-06-18. Unusable for any Kalshi-joined research object. Also CC BY-NC-SA.
- **ESPN tennis API** — the `summary` endpoint did not return point-by-point on probing.
  Not pursued further.
- **Sportradar / other licensed timestamped feeds** — no credentials exist in this repo
  (`grep` for sportradar/betsapi/sportsdataio found nothing). This is the only known route
  to `TIMESTAMPED_OBSERVED` tennis PBP. Flagged as a purchase decision, not a code task.

---

## 2. Network

Kalshi reachability is environment-dependent and this distinction is load-bearing:

- Home Wi-Fi DNS-sinkholes `api.elections.kalshi.com` to `198.51.100.91`
  (RFC 5737 TEST-NET-2). That is `NETWORK_UNREACHABLE`, never `NO_DATA_EXISTS`.
- Phone hotspot resolves normally (`52.84.20.45`) and returns HTTP 200.
- AWS fallback is proven: account `895492487332`, instance `i-0f0849d5829476c31`
  (`momento-paper`, t4g.nano, us-east-1, SSM Online, no SSH key), S3 bucket
  `momento-paper-artifacts-895492487332`. Do not run bulk acquisition on that box —
  it is production trading infrastructure with 0.5 GB RAM. Launch an ephemeral
  `t4g.medium` instead.

Acquisition is resumable per ticker, so a run may start on one network and finish on another.

**Kalshi historical cutoff is `2026-07-13T00:00:00Z`** (all four `/historical/cutoff` fields).
Older data routes to `/historical/*`; newer to the live endpoints. The pipeline handles this.

---

## 3. Kalshi tennis universe

| | ATP | WTA |
|---|---|---|
| series | `KXATPMATCH` | `KXWTAMATCH` |
| events | 4,628 | 4,470 |
| markets | 9,256 | ~8,940 |
| settlement source | ATP (atptour.com) | WTA |

Exactly 2 markets per event; `mutually_exclusive: true`.

Derivative series exist (`KXATPSETWINNER`, `KXATPGAME`, `KXATPTIEBREAK`, `KXATPGAMESPREAD`,
`KXATPACES`, ~100 more). V1 registers **match-winner only**. The registry accepts more
without architectural change.

### Field map

- `yes_sub_title` — full player name ("Alexander Zverev").
- `custom_strike.tennis_competitor` — **stable per-player UUID**, verified identical across
  different matches (Zverev = `dc4002ad-fb32-4f36-b59f-7c7af1927c57`). Strongest crosswalk key.
- `product_metadata.competition` — tournament ("US Open Men Singles", "ATP Cincinnati").
- `rules_primary` — contains the round ("...2026 US Open Men Singles Semifinal...").
- Settlement: `result`, `status`, `settlement_ts`, `settlement_value_dollars`.
- Prices are **decimal dollar strings** (`"0.8800"`) and quantities `_fp` strings (`"27.77"`).
  `warehouse/normalize.rs` already converts these to exact integer E4. Never use floats.

### Ticker parsing warning

Do **not** split the event-ticker code blob in half. Measured over 800 events per tour,
17 ATP and 2 WTA break a 3+3 split: `26SEP03VANDE`, `26AUG24KWONLAJ` (KWON+LAJ),
`26AUG01MARMAR2` (rematch suffix). Player codes are derived from the actual market ticker
suffixes instead. Validated: **18,196 / 18,196 markets resolved to exactly two sides, zero unresolved.**

### Known data-policy items

- `KXATPMATCH-25JUL10SAJT` is a **doubles exhibition** that leaked into the singles series.
  It uses `custom_strike.Competitor` as a plain string with no UUID. Crosswalk records `null`
  rather than inventing an ID. Not filtered — exclusion is a policy decision.
- 7 ATP events exist only as orphan markets with no raw event JSON; they land as phase
  `UNKNOWN` but their sides resolve correctly.

---

## 4. Three market layers — never merged

| layer | basis | source |
|---|---|---|
| `kalshi_trade_ticks` | `KALSHI_TRADE_TICK` | raw prints: `trade_id`, sub-second `created_time`, `taker_side`, `taker_outcome_side`, `yes_price`, `count` |
| `kalshi_candles` | `KALSHI_NATIVE_CANDLE` | exchange-native 1m, separate `yes_bid_*_e4` / `yes_ask_*_e4` / `price_*_e4`, `volume`, `open_interest` |
| `kalshi_last_trade` | `KALSHI_LAST_TRADE_1M` | ROLLER-derived from ticks only |

Tennis native candles carry a genuine `yes_bid`, so **tennis supports `TRADABLE_YES_BID`**.
It must not inherit MLB's `LAST_TRADE_PRINT` default in `market_path.py`.

A real acquired candle showing the honesty property — quoted book present, no trade printed,
`price` left null rather than forward-filled:

```json
{"end_period_ts":1753056960,"volume":"0.00",
 "price":{"close":null,"high":null,"low":null,"mean":null,"open":null,"previous":null},
 "yes_ask":{"close":"1.0000","high":"1.0000","low":"1.0000","open":"1.0000"},
 "yes_bid":{"close":"0.0400","high":"0.0400","low":"0.0400","open":"0.0400"}}
```

### Synthetic candle audit — result: none exist

Audited `normalize.rs`, `ingest.rs`, `derive.rs`, `query.rs`. There is no synthetic or
forward-filled candle logic anywhere: `parse_candle_row` emits `None` for absent fields and
sets `is_valid = false` when bid-close or ask-close is missing; `fetch_candles` only bisects
oversized windows; `causal_features` returns `None` past the array edge; `complementarity`
and `aligned_two_sided` inner-join on exact `end_period_ts`. `price_previous_e4` is Kalshi's
own `price.previous` copied verbatim, not computed. Missing minutes stay missing.

---

## 5. PBP reality

MCP point schema:
`match_id, Pt, Set1, Set2, Gm1, Gm2, Pts, Gm#, TbSet, Svr, 1st, 2nd, Notes, PtWinner`

Match schema:
`match_id, Player 1, Player 2, Pl 1 hand, Pl 2 hand, Date, Tournament, Round, Time, Court, Surface, Umpire, Best of, Final TB?, Charted by`

This covers sets, games, point score, **server**, tiebreak, point winner, plus `Best of`
(3 and 5 both present), `Surface`, `Round`, and `Final TB?` for final-set tiebreak rules.

**There is no timestamp column.** Therefore every MCP row is
`pbp_basis = SEQUENCE_ONLY`, `pit_joinable = false`, and the point-to-market PIT join
fails closed with `NO_POINT_DATA`.

The matches-index `Time` column is a match start time, blank on 208 of 387 men's matches in
our window and inconsistently formatted ("11:10 AM", "5pm"). **It must never be used to
synthesize point timestamps.** Neither may even spacing, scheduled start, interpolation,
fixed point duration, or game boundaries.

### Measured source semantics (do not "fix" these back)

These were measured on the real MCP 2020s files by the PBP canonical build, not assumed.

- **`Pts` is server-first, score before the point.** Left token = this point's server.
  Replay: `left = server` is 404,674 consistent / 201 inconsistent in games;
  `left = player 1` is wrong on all 168,875 transitions where player 2 serves.
  `Set1`/`Set2` and `Gm1`/`Gm2` **are** player-indexed (78,800 / 0). Canonical rows
  therefore keep both `points_server_raw`/`points_returner_raw` and
  `points_p1_raw`/`points_p2_raw`. Unknown server → player-indexed pair is `None`.
- **`TbSet` is not "this point is a tiebreak."** It is true on 546,865 / 547,478
  2020s men's rows because it marks a tiebreak-*eligible set*. `is_tiebreak` is
  derived from point-score tokens per game (27,931 tiebreak points; `AD` never
  enters a tiebreak).
- **`Gm#` is match-cumulative.** Within-set `game_number` is derived; `Gm#` is
  retained as `source_game_number`.
- **`tour` is MCP `M`/`W`**, not ATP/WTA. Davis Cup / BJK / ITF / college are charted.
- Points must be sorted by `Pt` (597 of 3,337 2020s men's matches are out of order).

State and snap consume **player-indexed** fields only. See `docs/tennis/STATE_MODEL.md`.

### Coverage

- Acquired: 1,853,115 point rows across 8 CSVs, 190 MB. Canonical parse validated
  on 880,606 2020s rows with zero PIT contract violations (no invented timestamps).
- Upstream commit `2c59eef194967e688b69e73df344184a06322cd8`,
  `dataset_version 4fc396d1146348214af013665ba19603c32bca5218a49e9ccd132fa64f4ab73b`.
- MCP matches inside the Kalshi window: **855** (387 men, 468 women).
- **111 / 855** are in competitions Kalshi does not list (United Cup 19, Davis Cup 11,
  BJK Cup 17, ITF 64). Realistic ceiling **744 / 855 (87.0%)**.
- Crude date+surname matcher with ±2 day tolerance: **527 / 855 (61.6%)**.
- Production matcher (UUID → full name → surname+tournament, fail-closed on
  ambiguous): **99.0% recall / 0 false positives on a synthetic Kalshi fixture
  (668 / 675 present; 2 AMBIGUOUS)**. Real rate awaits finished Kalshi acquisition.
- Against 9,098 Kalshi events that is roughly **5.8% point-level coverage**.
- Structurally unmatchable: ITF, Davis Cup, United Cup, BJK Cup — Kalshi does not list them.

The other ~94% of tennis matches have complete market data and no point state. They must be
reported as `NO_POINT_DATA`, never as zero observations.

### Licensing — commercial blocker

MCP is **CC BY-NC-SA 4.0, NonCommercial**. ROLLER is intended to become a commercial
B2B/D2C product, and that use is prohibited under this license. Attribution to Jeff Sackmann
is required and ShareAlike applies to derivatives. The manifest records
`license_commercial_use: PROHIBITED`. The PBP source must stay swappable.

---

## 6. Repository path index

### Rust acquisition (reused, not rewritten)

| path | role |
|---|---|
| `crates/kalshi/src/public_data.rs` | unsigned public client; all endpoints; no credentials |
| `crates/research-data/src/warehouse/http.rs` | `RetryingClient` — 4 RPS, 429/5xx retry, `Retry-After` |
| `crates/research-data/src/warehouse/ingest.rs` | cutoff routing, candle window bisection, resumable trade manifests |
| `crates/research-data/src/warehouse/normalize.rs` | decimal-dollar to exact integer E4 |
| `crates/research-data/src/sport.rs` | series registry; `TennisAtp` / `TennisWta` |
| `crates/research-data/src/warehouse/identity.rs` | `season_for_date_tennis`, `classify_tennis_phase`, `tennis_player_sides` |
| `crates/research-data/src/warehouse/catalog.rs` | `assign_tennis_sides`, `build_tennis_crosswalk` |
| `apps/tennis-data/` | `momento-tennis-data` CLI |

### ROLLER research engine touchpoints (for Phase 5)

`sport_family.py`, `compiler.py`, `availability.py`, `market_path.py`, `entry_engine.py`,
`execute.py`, `hashing.py`, and `base_terminal_efficiency/{score,builder,attach}.py`.
MLB is the reference pattern — see `roller/mlb/` for the package shape.

### Frontend touchpoints (for Phase 6)

`src/App.tsx`, `src/v2/workflow/sportFamily.ts`, `QuickStartScreen.tsx`,
`EntryConditionsScreen.tsx`, `periodPartitions.ts`, `types.ts`,
`src/v2/catalog/availabilityCatalog.ts`. Typecheck via `npm run typecheck`.

### Frozen — do not modify

FIRST01, FIRST80/81/83/89, Risk, W9, SuperASI execution/fill logic, live trading,
NBA/NCAAB clock semantics, MLB semantics. Existing basketball hashes must stay byte-identical.

---

## 7. Warehouse layout

```
Backtesting Suite/Data/TENNIS/2025-2026/warehouse/
  raw/kalshi/{atp,wta}/{events,markets,candlesticks,trades}/  cutoff.json
  raw/mcp/                                    charting-{m,w}-{matches,points-*}.csv
  normalized/{atp,wta}/{events,markets,games,candles_1m,trades}/
  normalized/{atp,wta}/crosswalk/{atp,wta}_tennis_crosswalk.json
  derived/{atp,wta}/
  manifests/{atp,wta}/  manifests/tennis/mcp_acquisition_manifest.json
```

ATP and WTA share the `TENNIS` directory but occupy separate layers.

`tennis_competitor` UUID and `product_metadata.competition` are retained verbatim in the raw
JSONL and additionally in the tennis-only crosswalk sidecar. They were deliberately **not**
added to the shared events parquet schema, which is written by the same code path as
NBA/NCAAB/MLB/NHL/WNBA.

ROLLER canonical output goes to `ROLLER/data/tennis/2025_2026/canonical/`, built from
on-disk warehouse files only. **The runtime query path never makes network calls.**

---

## 8. Open items

1. Kalshi ticker ingest still running (ATP/WTA `download-all`). Identity join is on disk.
2. Real crosswalk measured 2026-09-11: 688 / 855 MATCHED (682 UUID), 3 AMBIGUOUS, 164 UNMATCHED.
   See `docs/tennis/DATA_LINEAGE.md`.
3. No timestamped PBP source. Tennis PIT point research stays `NO_POINT_DATA` on MCP rows.
4. MCP NonCommercial license blocks commercial use.
5. Doubles-exhibition and orphan-market policy decisions remain open.
6. Canonical warehouse lives at `ROLLER/data/tennis/2025_2026/canonical/`.
   Re-run `python -m roller.tennis.ingest` after Kalshi download completes.
