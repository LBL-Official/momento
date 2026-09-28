# Data lineage

All paths under `Backtesting Suite/Data/NBA/2025-2026/warehouse/` unless
noted.

## Inputs (read-only)

| Object | Path | Role |
| --- | --- | --- |
| Frozen first-80 scan | `apps/nba-data/scripts/nba_80_40_execution_audit.py` | Label definition |
| Markets | `normalized/nba/markets/markets.parquet` | Ticker, team, settlement |
| Games | `normalized/nba/games/nba_games.parquet` | Home/away codes, window |
| 1m candles | `normalized/nba/candles_1m/**` | Market path; entry decision |
| PBP V3 | `raw/nba_stats/pbp_v3/{nba_game_id}.json` | Period, game clock, scores, descriptions |
| Box score | `raw/nba_stats/boxscore_summary/{nba_game_id}.json` | `gameTimeUTC`, `gameEt`, `duration` |
| Crosswalk | `normalized/nba/pbp/game_crosswalk.json` | Kalshi event → NBA GAME_ID |

V1 warehouse may be **read** for comparison. It is never overwritten.

## Outputs (V2 only)

`derived/nba/momento_game_path_engine_v2/`

- `observations.parquet` — one row = one game × one first-80 team contract
- `market_entry_state.parquet` / `game_state_entry.parquet`
- `score_path_features.parquet` / `lead_path_features.parquet` /
  `game_volatility_features.parquet` / `market_path_features.parquet`
- `bucket_assignments.parquet`
- `experiments/` `models/`
- `leakage_audit.json` `time_alignment_audit.json` `feature_audit.json`
- `REPORT.md` `summary.json`

## What is never invented

- Per-play structured wall-clock (NBA Stats PlayByPlayV3 does not provide
  `timeActual`).
- Tip-off inferred from Kalshi market open.
- L2 order book.
- Future PBP actions after entry.
- Future candles after `ENTRY_DECISION_TIME` as predictors.

## Team identity

Kalshi ticker suffix after the last `-` is the NBA tricode (`DET`, `LAL`).
That code is joined to PBP `teamTricode` and to `home_team_code` /
`away_team_code`. City strings (`Los Angeles L`) are display-only.
