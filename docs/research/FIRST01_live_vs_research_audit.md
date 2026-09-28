# FIRST01 Live vs Research Audit (canonical lifecycle)

| Rule | Live | Research FIRST01 | Identical? | Notes |
|------|------|------------------|------------|-------|
| Qualifying price = YES bid | yes | yes | Yes | — |
| first_80 sticky per GameId | never cleared | never cleared | Yes | — |
| Opponent market after bind | ignored | `SuppressedByOpponentMarket` | Yes | — |
| 80→81→maker intent | Build directive | EntryOpportunity + EntryIntent | Yes | `FIRST01_80_TO_81_CONFIRMED_MAKER` |
| has_working_entry gate | blocks Build | `EntryContext` + suppression | Yes | — |
| PositionOpen / Flat / OpenComplete | permanent no re-entry | `canonical_lifecycle_consumed` sticky | Yes | Live: `can_attempt_entry` |
| Unfilled cancel | may re-Build **same** opportunity | same opportunity; **no second trade** | Yes | — |
| Second independent opportunity after flat | **No** | **No** (fixed) | Yes | Prior research incorrectly allowed seq++ |
| GAME_LOCK ≥89 | permanent; no flatten | GameLocked; opportunity intact | Yes | — |
| Remainder Builds (PositionBuilding) | same PositionId | remainder intents same opportunity | Yes | — |

See also: `docs/research/FIRST01_live_entry_lifecycle_reset.md`
