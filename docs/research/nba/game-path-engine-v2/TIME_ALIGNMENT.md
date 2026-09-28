# Time alignment (hard gate)

V2 requires three timelines:

```text
A. NBA game events (PBP period + game clock)
B. Kalshi 1m candles (unix end_period_ts)
C. Market entry event (END_OF_FIRST_80_CANDLE)
```

The engine must answer: **what was happening in the NBA game at the moment
the contract first reached 80¢?**

## Observed fields (inspected, not assumed)

PlayByPlayV3 actions contain:

- `period` (1–4 regulation, 5+ OT)
- `clock` ISO-8601 duration (`PT12M00.00S`)
- `scoreHome` / `scoreAway`
- `actionType` / `description`
- **No** structured `timeActual` / `time` wall-clock field

BoxScoreSummaryV3 contains:

- `gameTimeUTC` — observed scheduled/tip UTC
- `gameEt` — Eastern (or local) clock **incorrectly tagged with `Z`**
- `duration` — wall duration `H:MM`
- `arena.arenaTimezone`

Period **start** and **end** descriptions embed local wall times:

```text
Start of 1st Period (7:44 PM EST)
End of 1st Period (8:15 PM EST)
```

Instant replay descriptions sometimes embed additional intra-period times.
Those are treated as optional **knots**, not as a complete play clock.

Ingest policy (`nba_pbp_overnight_ingest.py`) correctly refuses to *claim*
reconstructed per-play wall clock as observed. V2 does **not** reverse that.
It publishes an explicit **modeled** alignment and an audit.

## Alignment model (transparent)

`PERIOD_BOUNDED_LINEAR_GAME_CLOCK`

1. Convert description local times to UTC using the offset implied by
   `gameTimeUTC − naive(gameEt)`. NBA often prints `EST` during EDT; the
   abbreviation is **not** trusted over the boxscore offset.
2. Each period contributes knots: start, end, and any replay timestamps
   in that period, keyed by remaining game clock.
3. Intra-period wall time is **piecewise linear in remaining game clock**
   between adjacent knots. Timeouts (clock stopped) are smeared across the
   period. This is a model, not a fact.
4. Snap: last PBP action in official order whose modeled wall timestamp is
   `≤ ENTRY_DECISION_TIME`.
5. Intermission (first-80 between period end and next start): snap to the
   last action of the completed period.
6. Before first period start: `GAME_NOT_STARTED` (no in-game path).
7. After last period end: `GAME_ENDED` (final score; path complete).

Never infer tip from Kalshi open. Never fabricate missing period stamps.

## Confidence

| Level | Rule |
| --- | --- |
| HIGH | Period start **and** end parsed; first-80 strictly inside that period; period wall duration plausible (6–50 min Q1–Q4, 3–25 min OT); if ≥2 replay knots exist, median leave-one-out residual ≤ 180s |
| MEDIUM | Inside a period with both bounds but no replay check; **or** intermission with adjacent stamps; **or** HIGH-quality bounds but residual > 180s |
| LOW | Missing a period bound; fallback duration scaling from tip only |
| UNUSABLE | No PBP, unmatched crosswalk, unparsable clocks, or first-80 far outside `[first_start − 30m, last_end + 30m]` |

**Primary analysis set** = `HIGH` ∪ `MEDIUM`.

All 1,230 observations remain in the ledger so exclusion bias is measurable.

`alignment_confidence` is a **data-quality** label, not a trading feature
unless a pre-registered experiment uses it as a stratum.

## Empirical validation (required before modeling)

`time_alignment_audit.json` reports:

- Crosswalk match rate and PBP coverage
- Period-stamp parse rate
- First-period start minus `gameTimeUTC` (minutes)
- Last-period end minus first-period start vs boxscore `duration`
- Replay leave-one-out residuals
- Counts by confidence
- Exclusion-bias: `q` in primary vs excluded vs full 1,230

If the primary set’s close-path `q` diverges materially from 26.02% without
a documented reason, stop and report selection bias before promoting any
filter.
