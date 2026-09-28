# Ballhog recon

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
asked-six 1182 ≠ derived four 936 ≠ NBA 604
Austin a_t is not Ballhog alpha
```

Written from the repository as of implementation. Not aspirations.

## Austin modules inspected

- `ROLLER/roller/austin/api.py` — `handle_query`, `handle_query_historical`, `handle_replay`, `_run_query`
- `ROLLER/roller/austin/query.py` — KNN match
- `ROLLER/roller/austin/hedge.py` — 41/42 path lab; `hedge_fill_observed=False`
- `ROLLER/roller/austin/config.py` — `dataset_version=choosin_nba_2q3q_604`, `model_version=austin_v2`
- `ROLLER/roller/austin/locks.py` — `N_TRADES=604`
- `ROLLER/roller/dre/adapters/austin.py` — `query_at(..., persist=False)`, `get_trade`, `get_replay`, `list_trades`
- `research/austin/`

### Active data path

`query_at` → `build_historical_query_state` → `_run_query(persist=False)`.

### Universe

| Field | Value |
|---|---|
| dataset_version | `choosin_nba_2q3q_604` |
| N | 604 |
| feed_mode | `HISTORICAL_QUERY` |
| live_feed | `UNAVAILABLE` |

### Query fields used by Ballhog

- `conditional_ev.conditional_ev_cents` → `a_t` (one unhedged A1)
- `conditional_ev.ci_lower_cents` → `a_L` (existing 95% weighted bootstrap)
- `conditional_ev.ci_upper_cents`, `ci_level`, `method`
- `support` / `match.effective_sample_size` / `support` OBSERVED vs LOW HISTORICAL SUPPORT
- `state_change.ev_change` → `alpha_delta_from_entry` (not Λα)
- `match.weighted_T40_rate`, `weighted_survival_rate`
- reconstructed clock/score/price via `form`

### Missing from Austin product query

Live quote, fills, L2, fees, BUY NO, hazard, Λα, current A2 hedge-side PIT price as a first-class field.

## Choosin Texas modules inspected

- `ROLLER/roller/choosin_texas/api.py` — `handle_universe`
- `ROLLER/roller/choosin_texas/locks.py` — `POOL_N=936`
- `ROLLER/roller/choosin_texas/ev.py`, `rates.py`, `sources.py`
- `ROLLER/roller/dre/adapters/choosin.py` — `get_trade_context` STATIC prior
- `docs/research/lebronner/TABLES.md`

### Active data path

`handle_universe()` reconstructs locked integers. No warehouse rescan. No `as_of`.

### Universe

| Field | Value |
|---|---|
| cohort | derived_four |
| N | 936 |
| pit_kind | STATIC |
| per_ticker_path_economics | UNAVAILABLE |

NBA path/Dallas 604 scatter exists on `/choosin-texas/nba-path` but is not an as_of path query. Ballhog does not treat it as PIT hedge-side price.

## DRE

- `ROLLER/roller/dre/composer.py` already joins 604 trade + Austin query + 936 prior.
- Ballhog reuses adapters, not `dre.position_state.v1`.
- λ is memo-only in `research/dre/PORTFOLIO_OBJECTIVE_V1.md`. Not implemented.
- Λα forbidden / not computed.

## TK Ultra

- `GET /momento/tk-ultra`, `GET /momento/tk-ultra/assess`
- Inputs: wing/base/beta/anchors. Unchanged by Ballhog.
- Ballhog emits `BallhogHedgeIntent` only.

## Frontend hosts

| Product | Port |
|---|---|
| Momento Systems / TK Ultra / BDR | 5190 |
| DRE | 5191 |
| Ballhog | 5192 |

## Northbound interface created

`ROLLER/roller/ballhog/` wraps Austin `query_at` + Choosin `get_trade_context`.
HTTP `/ballhog/*` on `:8791`.

## Feed modes Ballhog may emit

`HISTORICAL` | `REPLAY` | `UNAVAILABLE`

Never `LIVE`.
