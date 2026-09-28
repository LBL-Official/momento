# Data lineage V2

V1 lineage in `docs/DATA_LINEAGE.md` still applies. V2 adds query-time assembly on top of those tables.

```text
IMMUTABLE HISTORY → CANONICAL EVENTS
        → POSSESSIONS / MARKETS / INFORMATION
        → TEMPORAL STATE TABLES
        → S_t  and  Γ_t
        → OBSERVATION ASSEMBLER  O_t
        → PIT CHOKE POINT  (available_at < cutoff)
        → RESEARCH API
        │  explicit boundary
        ▼
      FUTURE LABELS  L_{t→}
```

## Sources (unchanged warehouse)

| Object | Source | Notes |
|--------|--------|-------|
| Events | V1 canonical PBP | NBA pass-through: `personId`, `subType`, `shotResult`, `teamId`. Never invent `timeActual`. |
| Players | `pbp_live.personId` | `meta/players.csv`. Same display name + different ids → `REVIEW_REQUIRED`. No silent merge. |
| Possessions | NBA event grammar | Auxiliary raw `possession` teamId is not the segment key. Other sports: not written as REAL. |
| Market | V1 Kalshi candles | Integer E4. `available_at` = candle close. Not a fill. |
| Team priors | V1 `*_pre` / D2D | Shift-then-roll. Unchanged. |
| Lineups | Substitutions only | Opening five is not in the NBA warehouse. |
| Information | none in V2 | No new scrapers. |
| Labels | games + full PBP | Generated at `db.labels()` time. Not a public dataset. |

## Versions

| Object | Version field |
|--------|----------------|
| Database / pipeline | `roller.json` `2.0.0` |
| Assembled observation | `state_schema_version` `2.0.0` |
| Feature families | `meta/feature_registry.json` (`lookahead: false`) |
| Possession grammar | `possession_rule_version` `2.0.0` |
| Labels | `label_version` `2.0.0` |

## Discrepancies recorded (not invented away)

1. V1 PBP column remains `event_timestamp`. Events alias `event_time`.
2. NCAAB `scheduled_start` is empty in the warehouse; V1 conservative proxy stays.
3. `game_state_features.csv` is future information and is no longer readable via `dataset()`.
4. WNBA/NCAAB normalized plays have no `player_id`. Names are not parsed from text.
