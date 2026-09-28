# Possessions

NBA reconstruction is REAL when team grammar is present. WNBA / NCAAB use ESPN `type_text` plus team / `homeAway` when those fields exist. Sport-level capability is PARTIAL because team is often missing. Other sports return `NOT_SUPPORTED`. Do not parse player names from text.

```text
possession_status: CONFIRMED | RECONSTRUCTED | AMBIGUOUS | UNRESOLVED
```

Statuses are categorical. V2 does not emit a numeric confidence.

NBA raw `possession` is an auxiliary offensive `teamId`, not a segment key. Segments are derived from event grammar.

## Rules (version 2.0.0)

| End reason | Status | Trigger |
|------------|--------|---------|
| `MADE_FIELD_GOAL` | `CONFIRMED` | Made FG, unless the next event is a same-team free throw (and-1 stays on this possession) |
| `DEFENSIVE_REBOUND` | `CONFIRMED` | `event_type` rebound + `sub_type` defensive |
| `TURNOVER` | `CONFIRMED` | `event_type` turnover |
| `STEAL` | `CONFIRMED` | `event_type` steal |
| `PERIOD_END` | `CONFIRMED` if offense known, else `RECONSTRUCTED` | period end |
| `TEAM_CHANGE` | `RECONSTRUCTED` | Actor team changes without an explicit ending type |
| `OPEN_AT_CUTOFF` | `RECONSTRUCTED` / `UNRESOLVED` | Sequence ends without a closer |

Start and end statuses may differ. Example: period start with no team is `UNRESOLVED`; a later made FG can still close `CONFIRMED`.

`AMBIGUOUS` is used when a jump ball (or similar) has conflicting `team_tricode` and auxiliary `possession` team.

`UNRESOLVED` is used when no team can be assigned.

## What V2 does not do

- Import PADE or DRE
- Parse player names from WNBA/NCAAB text to invent possessions
- Fabricate a fifth lineup player to “complete” a possession
- Write possessions into `db.dataset()` as future information
- Treat possession **data** as `possession_delta` (that Greek stays NOT_YET_IMPLEMENTED)

Persisted table (pipeline tail): `derived/possessions.csv` for NBA, WNBA, and NCAAB. Observations assemble visible possessions at query time using `available_at < cutoff`.
