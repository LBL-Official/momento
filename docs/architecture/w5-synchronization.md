# W5 — MLB event ↔ Kalshi market time synchronization

**Status:** implemented as a research join layer (`momento-research-sync`).  
**Not W6.** This document does not specify state-transition tensors, Greeks, or FIRST01 replay.

## Purpose

Given a Kalshi market observation at time `t`, answer:

> What canonical MLB game/play state existed at `t`, and what canonical
> Kalshi observation existed at that same `t`?

without using future PBP, settlement, or later score/runner/count information.

## Authoritative dataset

W5 evaluates the **PBP ∩ MATCHED Kalshi trades** cohort, not the 238 UNMATCHED
TRADES_ONLY W4 price-path universe.

Expected brief: 1,684 games / 3,368 contract sides. Actual counts are measured
in `Backtesting Suite/Foundation/W5/synchronization_report.json`. Do not
substitute a different catalog.

Historical L2/order-book snapshots are **UNAVAILABLE** for this cohort.
Observations are **TRADE**. Trades are not converted to quotes, bid/ask, or L2.

Unmatched Kalshi catalog rows remain in ingest identity artifacts. They are
classified upstream (`UNMATCHED` / `AMBIGUOUS`) and are not this cohort.

## Time contract

- Canonical comparison clock: **UTC instants** (`DateTime<Utc>`).
- Source timestamps are preserved verbatim (`market_timestamp_source`,
  `source_event_time`).
- Explicit offset is required (`Z` or `±HH:MM`). Missing offset is
  `MISSING_TIMESTAMP` — never filled from the host timezone.
- Fractional digits in the source string are preserved; precision is not upgraded.
- `retrieval_timestamp` is provenance only and **never** orders history.

Kinds:

| Kind | Meaning |
|------|---------|
| `PBP_OFFICIAL` | StatsAPI play `startTime` (W3) |
| `KALSHI_TRADE_CREATED` | Kalshi `created_time` |
| `MISSING_TIMESTAMP` | Unparseable or absent source time |

## PBP event semantics

W3 reconstructed events are the only game-state source. W5 does not rebuild
baseball state.

Each timed event carries:

- `event_id`, `sequence`, source + UTC timestamps
- `previous_event_id` / `next_event_id`
- `state_before` / `state_after` from W3 `MlbPbpTransition`

Untimed PBP rows remain in canonical order for replay but are not AS-OF keys.
Identical timestamps keep **canonical sequence** order. Event wall times are
not altered to make the join easier.

## Market observation semantics

Supported types: `TRADE`, `QUOTE`, `CANDLE`, `L2_SNAPSHOT`, `L2_DELTA`.

This cohort lands **TRADE** only. Bid/ask and L2 fields stay `None`.
`first_observed_price_cents` is the first timed trade print. It is **not**
`starting_price` or `market_open_price`.

Market open/close timestamps are not invented.

Each contract side (ticker suffix / team) is synchronized independently to the
same `GameId` / PBP timeline.

## AS-OF algorithm

Sorted PBP times × sorted market times. Binary search for a single lookup;
two-pointer for a tape.

```text
state_at(t) = after-state of the latest timed event with effective_time <= t
```

- Never select the next event after `t`.
- `next_event_*` is diagnostic only.
- Observations with `t > last_pbp_time` are `AFTER_LAST_EVENT` and **do not**
  snap to the last state.
- Observations with `t < first_pbp_time` are `BEFORE_FIRST_EVENT` and **do not**
  receive the first state.

### Exact timestamp boundary

If `market_time == event_time`:

- `synchronization_status = AT_EVENT`
- `timestamp_relation = AT_EVENT`
- `pre_event_state` = W3 before-state of that event
- `post_event_state` = W3 after-state of that event
- `game_state` (applicable) = W3 **after-state**, because W3 timestamps are
  the instant the event becomes effective

This is not a silent before/after choice: the collision is explicit.

If `event_A < t < event_B`: applicable state is **after(A)** (`AFTER_EVENT`).

Same-timestamp PBP events: last canonical `sequence` at that instant wins.

If duplicate event identity/sequence prevents a unique clock, records are
`AMBIGUOUS_TIMESTAMP` and no game state is attached.

## Game window

The usable window is `[first_timed_pbp, last_timed_pbp]` from canonical events.
Market presence, game start, game completion, and “inside event window” are
distinct. Market close is not used as game completion.

## Identity

Uses existing MATCHED `game_pk` ↔ ticker pairs. No inference from price or
time alone.

| Status | Meaning |
|--------|---------|
| `IDENTITY_UNMATCHED` | No GameId mapping |
| `IDENTITY_AMBIGUOUS` | Mapping not unique |
| (cohort default) | MATCHED; join proceeds |

## Synchronization classifications

| Status | Meaning |
|--------|---------|
| `SYNCHRONIZED` | AS-OF match, `t` strictly after prior event, lag ≤ 5s |
| `AT_EVENT` | `t` equals matched event time |
| `SYNCHRONIZED_WITH_TIMESTAMP_GAP` | AS-OF match with lag > 5s |
| `BEFORE_FIRST_EVENT` | `t` before first timed PBP |
| `AFTER_LAST_EVENT` | `t` after last timed PBP |
| `AMBIGUOUS_TIMESTAMP` | Clock/identity collision; not guessed |
| `MISSING_TIMESTAMP` | Source time absent or unparseable |
| `IDENTITY_UNMATCHED` / `IDENTITY_AMBIGUOUS` | Identity failure |
| `SOURCE_DATA_INVALID` | Empty/corrupt timeline |

ADR-0003 quality remains: `EXACT | WITHIN_1S | WITHIN_3S | WITHIN_5S | WITHIN_INNING | AMBIGUOUS | UNMATCHED | UNAVAILABLE`.
`EXACT` only when lag is 0 (`AT_EVENT`).

## Anti-lookahead

Applicable `game_state` at `t` uses only PBP evidence with `effective_time <= t`.
Later score, outs, runners, innings, settlement, and `FINAL` status cannot
appear on earlier rows. Tests cover between-events, exact boundary, scoring,
inning change, rain delay, extra innings, and final-score isolation.

Market state at `t` uses only that observation (and prior observation **ids**
for path links). Prices are never interpolated.

## Provenance

Every row keeps source lineage, source timestamp, timestamp kind, optional
retrieval time, observation id, event ids, dataset version, and a
deterministic `synchronization_id`.

## Query API

```text
synchronize_market_observation(SyncParams, observation)
synchronize_market(SyncParams, observations)
synchronize_game(...)
synchronized_observations_for_game(GameId)
synchronized_observations_for_market(MarketId)
synchronized_observations_for_event(GameId, event_id)
game_state_at(events, timestamp)
synchronization_report(config)
```

SQLite indexes: `GameId+event_time`, `MarketId+market_time`,
`GameId+market_time`, `contract_id+market_time`, `event_id`,
`observation_id`, `synchronization_id`.

`prior_market_observation_id` / `next_market_observation_id` preserve the
full chronological market path. W5 does not resample to one print per play.

## CLI

```text
momento-research-w5 --sync \
  --out "Backtesting Suite/Foundation/W5" \
  [--ingest ...] [--pairs ...] [--games ...] [--markets ...] [--max-games N]
```

No Kalshi network. No credentials. Reruns replace `sync.sqlite` then rewrite
reports. Synchronization ids are a pure function of observation + match.

## Artifacts

Under `Backtesting Suite/Foundation/W5/`:

- `synchronization_report.json`
- `coverage_report.json`
- `timestamp_quality_report.json`
- `representative_synchronized_examples.json`
- `schema.sql`
- `sync.sqlite` (gitignored)

## W5 gate

Complete only when the cohort is evaluated, AS-OF is anti-lookahead, both
contract sides independently reference the same GameId/PBP timeline, quality
is measured, failures are retained with reasons, W6 can consume the typed
API, reruns are deterministic, tests pass, and clippy `-D warnings` passes.

## Limitations

- No historical L2; TRADE-only honesty.
- MATCHED trade backfill may be incomplete relative to the full 4,754-pair
  catalog; W5 reports actual PBP∩trades overlap.
- PBP timestamps are typically second precision; Kalshi may be finer.
- No clock offset is invented when the two clocks disagree.
- Pre/post snapshots in SQLite are compact; full runner/batter detail for
  round-trip lives on the in-memory W3 timeline.
- W6 canonical state engine is **not** implemented here.
